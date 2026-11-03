"""Importador de titulares desde fuentes RSS/Atom.

Por respeto a los derechos de autor solo se guarda el titular, un resumen breve
y el enlace a la noticia original, citando siempre la fuente.
"""

import html
import logging
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import feedparser
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from .models import Article

logger = logging.getLogger(__name__)

USER_AGENT = "DragonBoatWeb/1.0 (+https://github.com/andonialvarez/dragon_boat)"
MAX_AGE_DAYS = 30
TIMEOUT_SECONDS = 20


@dataclass
class ImportReport:
    created: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)

    def summary(self):
        text = _("%(created)s noticias nuevas, %(skipped)s descartadas o repetidas.") % {
            "created": self.created,
            "skipped": self.skipped,
        }
        if self.errors:
            text += " " + _("Errores: %(errors)s") % {"errors": "; ".join(self.errors)}
        return text


def clean_text(value, limit=None):
    text = html.unescape(strip_tags(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"
    return text


def entry_datetime(entry):
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime(*value[:6], tzinfo=dt_timezone.utc)
    return None


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 (URL del panel)
        return response.read()


def import_source(source, content=None, now=None):
    """Importa una fuente. `content` permite pasar el XML directamente (pruebas)."""
    now = now or timezone.now()
    raw = content if content is not None else fetch(source.feed_url)
    parsed = feedparser.parse(raw)
    if parsed.bozo and not parsed.entries:
        raise ValueError(str(parsed.get("bozo_exception") or _("El feed no se puede leer.")))

    keywords = source.keyword_list()
    created = skipped = 0
    for entry in parsed.entries:
        if created >= source.max_items:
            break
        link = (entry.get("link") or "").strip()
        title = clean_text(entry.get("title"), 200)
        if not link.startswith(("http://", "https://")) or not title:
            skipped += 1
            continue

        publisher = clean_text((entry.get("source") or {}).get("title", ""), 120)
        # Google Noticias añade « - Medio» al final del titular.
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3].strip()

        summary = clean_text(entry.get("summary") or entry.get("description"), 320)
        if summary.lower().startswith(title.lower()[:40]):
            summary = ""  # Algunos feeds repiten el titular como resumen.

        haystack = f"{title} {summary}".lower()
        if keywords and not any(word in haystack for word in keywords):
            skipped += 1
            continue

        published_at = entry_datetime(entry) or now
        if published_at < now - timedelta(days=MAX_AGE_DAYS):
            skipped += 1
            continue
        published_at = min(published_at, now)

        if Article.objects.filter(source_url=link).exists():
            skipped += 1
            continue

        source_name = publisher or source.name
        if not summary:
            summary = _("Titular publicado por %(source)s. Pulsa en el enlace para leer la noticia completa.") % {
                "source": source_name
            }
        Article.objects.create(
            title=title,
            summary=summary,
            body=summary,
            sport=source.sport,
            category=source.category,
            origin=Article.Origin.IMPORTED,
            status=Article.Status.PUBLISHED,
            published_at=published_at,
            source_name=source_name,
            source_url=link[:600],
        )
        created += 1
    return created, skipped


def import_from_sources(sources):
    report = ImportReport()
    for source in sources:
        try:
            created, skipped = import_source(source)
            report.created += created
            report.skipped += skipped
            source.last_error = ""
        except Exception as error:  # Una fuente rota no debe parar las demás.
            logger.warning("Error importando %s: %s", source.feed_url, error)
            report.errors.append(f"{source.name}: {error}")
            source.last_error = str(error)[:2000]
        source.last_checked_at = timezone.now()
        source.save(update_fields=["last_checked_at", "last_error"])
    return report
