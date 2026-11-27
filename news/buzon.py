"""Buzón de noticias: los usuarios mandan un enlace o un documento y la web
comprueba si esa noticia ya está publicada antes de añadirla.

Cómo se decide si una noticia ya existe:

1. Por el enlace. Se compara la dirección «limpia» (sin http/https, sin www.,
   sin parámetros de seguimiento como utm_*, sin barra final), y también la
   dirección canónica que declara la propia página y aquella a la que redirige.
2. Por el título. Se compara con los titulares del último año, sin tildes,
   mayúsculas ni palabras vacías. Si los títulos llevan números distintos
   (por ejemplo, el año de un campeonato) no se dan por iguales.

Los documentos (PDF, Word, OpenDocument o texto) no se guardan: se lee su texto
para preparar la noticia y el fichero se descarta.
"""

import io
import logging
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from datetime import timedelta
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit
from xml.etree import ElementTree

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from . import images
from .importer import clean_text

logger = logging.getLogger(__name__)

# ---------- Enlaces ----------

TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid", "igsh", "ref", "ref_src", "ref_url",
    "cmpid", "ocid", "_ga", "si", "share", "smid", "src", "spm", "s_cid", "rss", "origin", "via",
}  # fmt: skip
TRACKING_PREFIXES = ("utm_", "pk_", "mtm_", "hsa_", "__")


def normalize_url(url):
    """Clave para comparar enlaces: la misma noticia da la misma clave aunque cambie
    http/https, www., la barra final, el ancla o los parámetros de seguimiento."""
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url if "//" in url else f"https://{url}")
        host = (parts.hostname or "").lower()
    except ValueError:
        return ""
    if not host:
        return ""
    for prefix in ("www.", "m.", "amp."):
        if host.startswith(prefix) and host.count(".") >= 2:
            host = host[len(prefix) :]
    path = re.sub(r"/{2,}", "/", parts.path or "")
    path = re.sub(r"(/amp|/index\.(?:html?|php))$", "", path, flags=re.IGNORECASE).rstrip("/")
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS and not key.lower().startswith(TRACKING_PREFIXES)
    )
    key = host + path
    if query:
        key += "?" + urlencode(query)
    return key[:600]


class _PageParser(HTMLParser):
    """Lee título, descripción, medio, fecha y enlace canónico de la cabecera."""

    KEYS = {
        "og:title", "twitter:title", "og:description", "description", "twitter:description",
        "og:site_name", "application-name", "article:published_time", "og:published_time",
        "datepublished", "date", "dc.date",
    }  # fmt: skip

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.canonical = ""
        self.title = ""
        self._in_title = False
        self.finished = False

    def handle_starttag(self, tag, attrs):
        if self.finished:
            return
        attributes = {name.lower(): (value or "").strip() for name, value in attrs}
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or attributes.get("itemprop") or "").lower()
            if key in self.KEYS and attributes.get("content"):
                self.meta.setdefault(key, attributes["content"])
        elif tag == "link" and "canonical" in attributes.get("rel", "").lower().split():
            self.canonical = self.canonical or attributes.get("href", "")
        elif tag == "title" and not self.title:
            self._in_title = True
        elif tag == "body":
            self.finished = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


@dataclass
class LinkInfo:
    url: str
    final_url: str = ""
    canonical_url: str = ""
    title: str = ""
    summary: str = ""
    source_name: str = ""
    image_url: str = ""
    published_at: object = None
    fetched: bool = False

    def keys(self):
        return {key for key in map(normalize_url, (self.url, self.final_url, self.canonical_url)) if key}


def fetch_page(url):
    """Descarga la página (solo direcciones públicas). Devuelve (html, url final) o None."""
    return images._read_page(url)


def _strip_site_suffix(title, site_name):
    """«Titular | El Medio» -> «Titular»."""
    for separator in (" | ", " - ", " – ", " — ", " :: ", " · "):
        if separator in title:
            head, tail = title.rsplit(separator, 1)
            if site_name and tail.strip().lower() == site_name.lower() or len(tail) <= 30 and len(head) >= 20:
                return head.strip()
    return title


def read_link(url):
    """Información de la noticia de un enlace. Si la página no responde, solo trae el enlace."""
    info = LinkInfo(url=url)
    if (urlsplit(url).hostname or "").lower() == images.GOOGLE_NEWS_HOST:
        real = images.resolve_google_news(url)
        if real:
            info.url = real
    page = fetch_page(info.url)
    if not page:
        info.source_name = _host_name(info.url)
        return info
    html, final_url = page
    info.fetched = True
    info.final_url = final_url
    parser = _PageParser()
    try:
        parser.feed(html)
    except Exception:  # HTML roto: nos quedamos con lo que se haya podido leer.
        pass
    meta = parser.meta
    canonical = images.clean_image_url(parser.canonical, final_url) if parser.canonical else ""
    info.canonical_url = canonical if images.is_http_url(canonical) else ""
    info.source_name = clean_text(meta.get("og:site_name") or meta.get("application-name"), 120) or _host_name(
        final_url
    )
    raw_title = meta.get("og:title") or meta.get("twitter:title") or parser.title
    info.title = clean_text(_strip_site_suffix(clean_text(raw_title), info.source_name), 200)
    info.summary = clean_text(
        meta.get("og:description") or meta.get("description") or meta.get("twitter:description"), 320
    )
    for key in ("article:published_time", "og:published_time", "datepublished", "date", "dc.date"):
        value = parse_datetime(meta.get(key, "")) if meta.get(key) else None
        if value:
            if timezone.is_naive(value):
                value = timezone.make_aware(value)
            info.published_at = min(value, timezone.now())
            break
    if settings.NEWS_FETCH_IMAGES:
        image = images.extract_image(html, final_url)
        if image and images.is_suitable_image(image, final_url):
            info.image_url = image
    return info


def _host_name(url):
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


# ---------- Documentos ----------

DOCUMENT_EXTENSIONS = (".pdf", ".docx", ".odt", ".txt", ".md")
MAX_TEXT = 20000
MAX_PDF_PAGES = 40
MAX_XML_BYTES = 15_000_000  # Contra ficheros comprimidos que se inflan al abrirlos.

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ODF_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


class DocumentError(ValueError):
    pass


@dataclass
class DocumentInfo:
    file_name: str
    title: str = ""
    summary: str = ""
    body: str = ""
    paragraphs: list = field(default_factory=list)


def _clean_paragraph(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _zip_xml(data, name):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        info = archive.getinfo(name)
    except (zipfile.BadZipFile, KeyError) as error:
        raise DocumentError(_("El documento está dañado o no es del tipo que dice ser.")) from error
    if info.file_size > MAX_XML_BYTES:
        raise DocumentError(_("El documento es demasiado grande para leerlo."))
    try:
        return ElementTree.fromstring(archive.read(name))
    except ElementTree.ParseError as error:
        raise DocumentError(_("El documento está dañado o no es del tipo que dice ser.")) from error


def _docx_paragraphs(data):
    root = _zip_xml(data, "word/document.xml")
    paragraphs = []
    for paragraph in root.iter(f"{W}p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{W}t" and node.text:
                parts.append(node.text)
            elif node.tag in (f"{W}tab", f"{W}br"):
                parts.append(" ")
        paragraphs.append("".join(parts))
    return paragraphs


def _odt_paragraphs(data):
    root = _zip_xml(data, "content.xml")
    return ["".join(node.itertext()) for node in root.iter() if node.tag in (f"{ODF_TEXT}p", f"{ODF_TEXT}h")]


def _pdf_paragraphs(data):
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PDF_PAGES])
    except Exception as error:  # pypdf lanza muchos tipos de error con PDF raros.
        logger.info("PDF ilegible: %s", error)
        raise DocumentError(_("No se ha podido abrir el PDF.")) from error
    # En los PDF cada línea va suelta: se juntan las que siguen la misma frase.
    paragraphs, current = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
        if re.search(r"[.!?:»\"”]$", line) or len(line) < 40 and len(current) == 1:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _text_paragraphs(data):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    return re.split(r"\n\s*\n", text.replace("\r\n", "\n"))


def read_document(uploaded):
    """Saca título, entradilla y texto de un documento subido."""
    name = (uploaded.name or "documento").rsplit("/", 1)[-1][:150]
    extension = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if extension not in DOCUMENT_EXTENSIONS:
        raise DocumentError(_("Ese tipo de documento no se puede leer. Usa PDF, Word (.docx), OpenDocument (.odt) o texto."))
    if uploaded.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise DocumentError(_("El documento pesa más de %(mb)s MB.") % {"mb": settings.MAX_UPLOAD_MB})
    data = uploaded.read()
    reader = {
        ".pdf": _pdf_paragraphs,
        ".docx": _docx_paragraphs,
        ".odt": _odt_paragraphs,
    }.get(extension, _text_paragraphs)
    paragraphs = [p for p in map(_clean_paragraph, reader(data)) if p]
    if sum(len(p) for p in paragraphs) < 40:
        raise DocumentError(
            _("No hemos encontrado texto en el documento. Si es un escaneo o una foto, copia el texto a mano.")
        )

    info = DocumentInfo(file_name=name, paragraphs=paragraphs)
    rest = list(paragraphs)
    # Título: el primer párrafo corto con al menos tres palabras.
    for index, paragraph in enumerate(rest[:5]):
        if len(paragraph) <= 200 and len(paragraph.split()) >= 3:
            info.title = paragraph.rstrip(".")
            rest = rest[index + 1 :]
            break
    if not info.title:
        stem = name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
        info.title = clean_text(stem, 200)
    info.summary = clean_text(rest[0], 320) if rest else ""
    body = "\n\n".join(rest)
    info.body = body[:MAX_TEXT]
    return info


# ---------- ¿Ya la tenemos? ----------

STOPWORDS = set(
    "a al algo ante con contra de del desde durante e el ella en entre era es esa ese esta este fue ha han hasta la "
    "las le les lo los mas más muy no o para pero por que qué se sin sobre su sus tras un una uno unos unas y ya "
    "the of and to in on for at by with from is are as an its it this that new"
    .split()
)  # fmt: skip
STRONG_MATCH = 0.85
WEAK_MATCH = 0.55
LOOKBACK_DAYS = 365


def _fold(text):
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9ñ ]+", " ", text)


def title_tokens(text):
    return [word for word in _fold(text).split() if word not in STOPWORDS]


def title_similarity(first, second):
    """Parecido entre dos titulares, de 0 a 1."""
    a, b = title_tokens(first), title_tokens(second)
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    common = len(set_a & set_b)
    ratio = SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()
    jaccard = common / len(set_a | set_b)
    containment = common / min(len(set_a), len(set_b)) if min(len(set_a), len(set_b)) >= 4 else 0
    score = max(ratio, jaccard, 0.9 * containment)
    numbers_a = {w for w in set_a if w.isdigit()}
    numbers_b = {w for w in set_b if w.isdigit()}
    if numbers_a and numbers_b and numbers_a != numbers_b:
        score = min(score, 0.7)  # «Campeonato 2025» y «Campeonato 2026» no son la misma noticia.
    return round(score, 3)


@dataclass
class Match:
    article: object
    score: float
    by_link: bool = False

    @property
    def strong(self):
        return self.by_link or self.score >= STRONG_MATCH


def find_matches(title="", url_keys=(), exclude_pk=None, limit=3):
    """Noticias que ya hay en la web y se parecen (mejores primero)."""
    from .models import Article

    queryset = Article.objects.exclude(status=Article.Status.DRAFT)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    url_keys = [key for key in url_keys if key]
    if url_keys:
        found = queryset.filter(source_key__in=url_keys).first()
        if found:
            return [Match(found, 1.0, by_link=True)]
    if not title:
        return []
    since = timezone.now() - timedelta(days=LOOKBACK_DAYS)
    candidates = queryset.filter(published_at__gte=since).only("id", "title", "slug", "status", "published_at")
    matches = []
    for article in candidates.iterator():
        score = title_similarity(title, article.title)
        if score >= WEAK_MATCH:
            matches.append(Match(article, score))
    matches.sort(key=lambda match: match.score, reverse=True)
    return matches[:limit]


# ---------- Deporte ----------

SPORT_WORDS = [
    ("traineras", r"trainera|traineru|bandera de|liga eusko|liga arc|\bact\b|arraun|estropada|bateles|trainerilla"),
    ("vaa", r"\bva.?a\b|outrigger|canoa polinesia|\boc[126]\b"),
    ("remo-olimpico", r"remo ol[ií]mpico|rowing|scull|dos sin|cuatro sin|ocho con|regata de remo|\bfisa\b|world rowing"),
    ("piraguismo", r"pirag[uü]|kayak|canoa|aguas bravas|sprint|maratón de piragüismo|descenso del sella|\bk[124]\b|\bc[124]\b|slalom"),
    ("dragon-boat", r"drag[oó]n|dragon ?boat|\bidbf\b|\bedbf\b|tamborile"),
]  # fmt: skip


def guess_sport(*texts):
    """Deporte probable según las palabras del texto (o None)."""
    from core.models import Sport

    haystack = " ".join(texts).lower()
    for slug, pattern in reversed(SPORT_WORDS):  # El dragon boat manda si aparece.
        if re.search(pattern, haystack):
            return Sport.objects.filter(slug=slug).first()
    return None
