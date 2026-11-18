"""Foto de las noticias que vienen de otras webs.

Cada medio declara en su página la imagen que usa para compartir la noticia en
redes (`og:image`). La guardamos como enlace, sin copiarla, y se muestra con el
crédito del medio. Antes de quedárnosla comprobamos que es una foto de verdad:
ni el logotipo del medio, ni su imagen genérica, ni un icono pequeño.

Si una noticia no tiene foto adecuada, la web la muestra con un diseño sin foto.
"""

import base64
import http.client
import ipaddress
import json
import logging
import re
import socket
import struct
import time
import urllib.request
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import quote, urlencode, urljoin, urlsplit

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; DragonBoatWeb/1.0; +https://github.com/andonialvarez/dragon_boat)"
BROWSER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TIMEOUT_SECONDS = 6
MAX_BYTES = 800_000  # Las etiquetas están en la cabecera: no hace falta bajar la página entera.
IMAGE_PROBE_BYTES = 65_536  # Basta con el principio del fichero para saber su tamaño.
MAX_URL_LENGTH = 600
GOOGLE_NEWS_HOST = "news.google.com"
META_KEYS = ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")

# Una foto de noticia mide al menos esto; lo más pequeño suele ser un icono o un logotipo.
MIN_WIDTH = 400
MIN_HEIGHT = 200
MIN_RATIO, MAX_RATIO = 0.6, 3.2  # Ancho / alto: fuera de esto son banners o tiras.
GENERIC_WORDS = re.compile(
    r"(?:^|[/_.\-])(?:logo|logos|logotipo|favicon|icon|icons|sprite|placeholder|default|"
    r"no[-_]?image|noimage|sin[-_]?imagen|blank|avatar|share[-_]?image|og[-_]?default|social[-_]?default)"
    r"(?:$|[/_.\-\d])",
    re.IGNORECASE,
)


def is_http_url(url):
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def clean_image_url(url, base_url=""):
    """Devuelve la URL absoluta de la imagen si es válida, o una cadena vacía.

    Codifica los espacios y otros caracteres que algunos medios dejan sin codificar
    (si no, la web rechaza la dirección al guardarla).
    """
    url = (url or "").strip()
    if not url:
        return ""
    if base_url:
        url = urljoin(base_url, url)
    if url.startswith("//"):
        url = "https:" + url
    url = quote(url, safe=":/?#[]@!$&'()*+,;=%~")
    return url if is_http_url(url) and len(url) <= MAX_URL_LENGTH else ""


class _HeadParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.link_image = ""
        self.google_params = {}
        self.finished = False

    def handle_starttag(self, tag, attrs):
        attributes = {name.lower(): (value or "").strip() for name, value in attrs}
        # Página intermedia de Google Noticias: lleva la firma para pedir el enlace real.
        if "data-n-a-sg" in attributes and not self.google_params:
            self.google_params = {"signature": attributes["data-n-a-sg"], "timestamp": attributes.get("data-n-a-ts")}
        if self.finished:
            return
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            if key in META_KEYS and attributes.get("content"):
                self.meta.setdefault(key, attributes["content"])
        elif tag == "link" and "image_src" in attributes.get("rel", "").lower() and attributes.get("href"):
            self.link_image = self.link_image or attributes["href"]
        elif tag == "body":
            self.finished = True


def _parse(html):
    parser = _HeadParser()
    try:
        parser.feed(html)
    except Exception:  # HTML roto: nos quedamos con lo que se haya podido leer.
        pass
    return parser


def extract_image(html, base_url):
    """Busca la imagen para compartir en el HTML de una página."""
    parser = _parse(html)
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


def _open(url, *, headers=None, data=None, max_bytes=MAX_BYTES, timeout=TIMEOUT_SECONDS):
    """Descarga el principio de una dirección pública. Devuelve (tipo, bytes, url final) o None."""
    if not is_http_url(url) or not _is_public_host(urlsplit(url).hostname.lower()):
        return None
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (solo http/https)
            content_type = response.headers.get_content_type()
            charset = response.headers.get_content_charset() or "utf-8"
            return content_type, charset, response.read(max_bytes), response.geturl()
    except (OSError, ValueError, LookupError, http.client.HTTPException) as error:
        logger.info("No se pudo leer %s: %s", url, error)
        return None


def _read_page(url, headers=None):
    result = _open(url, headers={"Accept": "text/html,application/xhtml+xml", **(headers or {})})
    if not result:
        return None
    content_type, charset, raw, final_url = result
    if content_type not in ("text/html", "application/xhtml+xml"):
        return None
    try:
        return raw.decode(charset, "replace"), final_url
    except LookupError:
        return raw.decode("utf-8", "replace"), final_url


# ---------- Google Noticias ----------

GOOGLE_COOKIES = {"Cookie": "CONSENT=YES+cb; SOCS=CAI"}  # Evita la página de consentimiento.


def _google_article_id(url):
    parts = urlsplit(url)
    if (parts.hostname or "").lower() != GOOGLE_NEWS_HOST:
        return ""
    match = re.search(r"/articles/([A-Za-z0-9_\-]+)", parts.path)
    return match.group(1) if match else ""


def _decode_old_google_id(article_id):
    """Los enlaces antiguos de Google Noticias llevan la dirección dentro, en base64."""
    try:
        raw = base64.urlsafe_b64decode(article_id + "=" * (-len(article_id) % 4))
    except (ValueError, TypeError):
        return ""
    match = re.search(rb"https?://[\x21-\x7e]+", raw)
    if not match:
        return ""
    url = match.group(0).decode("ascii", "ignore")
    # Detrás de la dirección puede venir otro campo binario: lo cortamos.
    url = re.split(r"[\x00-\x20\x7f]", url)[0].rstrip("\"'")
    return url if is_http_url(url) and GOOGLE_NEWS_HOST not in url else ""


def resolve_google_news(url):
    """Devuelve el enlace a la noticia original de un enlace de Google Noticias (o "")."""
    article_id = _google_article_id(url)
    if not article_id:
        return ""
    direct = _decode_old_google_id(article_id)
    if direct and "AU_yqL" not in direct:
        return direct
    page = _read_page(f"https://{GOOGLE_NEWS_HOST}/rss/articles/{article_id}", headers=GOOGLE_COOKIES)
    if not page:
        return ""
    params = _parse(page[0]).google_params
    if not params.get("signature") or not params.get("timestamp"):
        return ""
    request_payload = (
        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
        f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{article_id}",{int(params["timestamp"])},"{params["signature"]}"]'
    )
    body = urlencode({"f.req": json.dumps([[["Fbv4je", request_payload, None, "generic"]]])}).encode()
    result = _open(
        f"https://{GOOGLE_NEWS_HOST}/_/DotsSplashUi/data/batchexecute",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", **GOOGLE_COOKIES},
    )
    if not result:
        return ""
    try:
        text = result[2].decode("utf-8", "replace")
        chunk = json.loads(text.split("\n\n", 1)[1])[:-2]
        real_url = json.loads(chunk[0][2])[1]
    except (IndexError, ValueError, TypeError, KeyError):
        logger.info("Google Noticias no devolvió el enlace de %s", url)
        return ""
    return real_url if isinstance(real_url, str) and is_http_url(real_url) else ""


# ---------- ¿Es una foto adecuada? ----------


def image_size(data):
    """Ancho y alto de una imagen JPEG, PNG, GIF o WebP a partir de sus primeros bytes."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", data[6:10])
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8X":
                width = int.from_bytes(data[24:27], "little") + 1
                height = int.from_bytes(data[27:30], "little") + 1
                return width, height
            if chunk == b"VP8 ":
                width, height = struct.unpack("<HH", data[26:30])
                return width & 0x3FFF, height & 0x3FFF
            if chunk == b"VP8L":
                bits = int.from_bytes(data[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if data[:2] == b"\xff\xd8":
            position = 2
            while position + 9 < len(data):
                if data[position] != 0xFF:
                    position += 1
                    continue
                marker = data[position + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    position += 2
                    continue
                length = struct.unpack(">H", data[position + 2 : position + 4])[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    height, width = struct.unpack(">HH", data[position + 5 : position + 9])
                    return width, height
                position += 2 + length
    except struct.error:
        pass
    return None


def looks_generic(image_url):
    """Direcciones que delatan un logotipo, un icono o la imagen por defecto del medio."""
    path = urlsplit(image_url).path
    return bool(GENERIC_WORDS.search(path))


_home_images = {}


def _home_image(page_url):
    """Imagen para compartir de la portada del medio (la genérica que ponen a todo)."""
    parts = urlsplit(page_url)
    home = f"{parts.scheme}://{parts.netloc}/"
    if home not in _home_images:
        page = _read_page(home)
        _home_images[home] = extract_image(*page) if page else ""
    return _home_images[home]


def is_suitable_image(image_url, page_url=""):
    """True si la imagen parece una foto de la noticia y no algo genérico.

    Si el servidor de la imagen no deja comprobarla, se acepta: el navegador la
    quita sola si luego no carga.
    """
    if not image_url or looks_generic(image_url):
        return False
    if page_url and urlsplit(page_url).path.strip("/") and _home_image(page_url) == image_url:
        return False  # La misma imagen que la portada del medio: no es de esta noticia.
    result = _open(
        image_url,
        headers={"User-Agent": BROWSER_AGENT, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
        max_bytes=IMAGE_PROBE_BYTES,
    )
    if not result:
        return True
    content_type, _charset, data, _final_url = result
    if content_type == "image/svg+xml" or content_type.startswith(("text/", "application/json")):
        return False
    size = image_size(data)
    if not size:
        return content_type.startswith("image/")
    width, height = size
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return False
    return MIN_RATIO <= width / height <= MAX_RATIO


# ---------- Búsqueda ----------


def find_image(page_url, timeout=TIMEOUT_SECONDS):
    """Busca la foto de una noticia y la devuelve si es adecuada (o "").

    Los enlaces de Google Noticias se traducen primero al enlace del medio.
    """
    if not is_http_url(page_url):
        return ""
    if (urlsplit(page_url).hostname or "").lower() == GOOGLE_NEWS_HOST:
        page_url = resolve_google_news(page_url)
        if not page_url:
            return ""
    page = _read_page(page_url)
    if not page:
        return ""
    image = extract_image(*page)
    return image if image and is_suitable_image(image, page[1]) else ""


def image_for_article(article):
    """Foto de la fuente de una noticia, si está activada la búsqueda."""
    if not settings.NEWS_FETCH_IMAGES or not article.source_url:
        return ""
    return find_image(article.source_url)


def pending_articles(days=45):
    """Noticias de otras webs cuya foto aún no se ha buscado o revisado."""
    from .models import Article

    return (
        Article.objects.filter(
            origin__in=[Article.Origin.IMPORTED, Article.Origin.AI],
            cover_image="",
            image_checked_at__isnull=True,
            published_at__gte=timezone.now() - timedelta(days=days),
        )
        .exclude(source_url="")
        .order_by("-published_at")
    )


def fill_missing_images(limit=30, seconds=20, days=45):
    """Busca la foto de las noticias recientes de otras webs y revisa las que ya tienen.

    - Sin foto: la busca en la noticia original (también detrás de Google Noticias).
    - Con foto sin revisar: si resulta ser un logotipo o la imagen genérica del
      medio, se quita y la noticia se muestra con el diseño sin foto.

    Solo mira las que trae la web (importadas o resumidas), nunca enlaces que
    escriben los usuarios. Cada noticia se revisa una vez. Para en cuanto se acaba el tiempo.
    """
    from .models import Article

    if not settings.NEWS_FETCH_IMAGES:
        return {"checked": 0, "updated": 0, "removed": 0, "remaining": 0}
    deadline = time.monotonic() + seconds
    checked = updated = removed = 0
    for article in pending_articles(days).iterator():
        if checked >= limit or time.monotonic() >= deadline:
            break
        checked += 1
        changes = {"image_checked_at": timezone.now()}
        if article.image_url:
            if not is_suitable_image(article.image_url, article.source_url):
                changes["image_url"] = ""
                removed += 1
        else:
            image = image_for_article(article)
            if image:
                changes["image_url"] = image
                updated += 1
        Article.objects.filter(pk=article.pk).update(**changes)
    return {"checked": checked, "updated": updated, "removed": removed, "remaining": pending_articles(days).count()}
