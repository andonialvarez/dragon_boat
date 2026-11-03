"""Imagen de portada de las noticias que vienen de otras webs.

Cada medio declara en su página la imagen que usa para compartir la noticia en
redes (`og:image`). La guardamos como enlace, sin copiarla, y se muestra con el
crédito del medio. Si no hay, la web pone una ilustración del deporte.
"""

import http.client
import ipaddress
import logging
import socket
import time
import urllib.request
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; DragonBoatWeb/1.0; +https://github.com/andonialvarez/dragon_boat)"
TIMEOUT_SECONDS = 6
MAX_BYTES = 800_000  # Las etiquetas están en la cabecera: no hace falta bajar la página entera.
MAX_URL_LENGTH = 600
# Google Noticias solo redirige al medio con JavaScript: su página no tiene la imagen.
SKIP_HOSTS = {"news.google.com"}
META_KEYS = ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")


def is_http_url(url):
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def clean_image_url(url, base_url=""):
    """Devuelve la URL absoluta de la imagen si es válida, o una cadena vacía."""
    url = (url or "").strip()
    if not url:
        return ""
    if base_url:
        url = urljoin(base_url, url)
    if url.startswith("//"):
        url = "https:" + url
    return url if is_http_url(url) and len(url) <= MAX_URL_LENGTH else ""


class _HeadParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.link_image = ""
        self.finished = False

    def handle_starttag(self, tag, attrs):
        if self.finished:
            return
        attributes = {name.lower(): (value or "").strip() for name, value in attrs}
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            if key in META_KEYS and attributes.get("content"):
                self.meta.setdefault(key, attributes["content"])
        elif tag == "link" and "image_src" in attributes.get("rel", "").lower() and attributes.get("href"):
            self.link_image = self.link_image or attributes["href"]
        elif tag == "body":
            self.finished = True


def extract_image(html, base_url):
    """Busca la imagen para compartir en el HTML de una página."""
    parser = _HeadParser()
    try:
        parser.feed(html)
    except Exception:  # HTML roto: nos quedamos con lo que se haya podido leer.
        pass
    for key in META_KEYS:
        image = clean_image_url(parser.meta.get(key), base_url)
        if image:
            return image
    return clean_image_url(parser.link_image, base_url)


def _is_public_host(hostname):
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except (OSError, UnicodeError):
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global:
            return False
    return bool(addresses)


def find_image(page_url, timeout=TIMEOUT_SECONDS):
    """Descarga la cabecera de una noticia y devuelve su imagen para compartir (o "")."""
    if not is_http_url(page_url):
        return ""
    hostname = urlsplit(page_url).hostname.lower()
    if hostname in SKIP_HOSTS or not _is_public_host(hostname):
        return ""
    request = urllib.request.Request(
        page_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (solo http/https)
            if response.headers.get_content_type() not in ("text/html", "application/xhtml+xml"):
                return ""
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read(MAX_BYTES)
            final_url = response.geturl()
        html = raw.decode(charset, "replace")
    except (OSError, ValueError, LookupError, http.client.HTTPException) as error:
        logger.info("No se pudo leer %s: %s", page_url, error)
        return ""
    return extract_image(html, final_url)


def image_for_article(article):
    """Imagen de la fuente de una noticia, si está activada la búsqueda."""
    if not settings.NEWS_FETCH_IMAGES or not article.source_url:
        return ""
    return find_image(article.source_url)


def fill_missing_images(limit=30, seconds=20, days=45):
    """Busca la imagen de las noticias recientes que vienen de otras webs y no tienen.

    Solo mira las que trae la web (importadas o resumidas), nunca enlaces que
    escriben los usuarios. Para en cuanto se acaba el tiempo.
    """
    from .models import Article

    candidates = (
        Article.objects.filter(
            origin__in=[Article.Origin.IMPORTED, Article.Origin.AI],
            cover_image="",
            image_url="",
            published_at__gte=timezone.now() - timedelta(days=days),
        )
        .exclude(source_url="")
        .order_by("-published_at")
    )
    deadline = time.monotonic() + seconds
    checked = updated = 0
    for article in candidates.iterator():
        if checked >= limit or time.monotonic() >= deadline:
            break
        if urlsplit(article.source_url).hostname in SKIP_HOSTS:
            continue
        checked += 1
        image = image_for_article(article)
        if image:
            Article.objects.filter(pk=article.pk).update(image_url=image)
            updated += 1
    return {"checked": checked, "updated": updated}
