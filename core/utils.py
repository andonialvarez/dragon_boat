from django.conf import settings
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify


# Palabras que ya usan las URLs (p. ej. /noticias/publicar/) y no pueden ser slugs.
RESERVED_SLUGS = {"publicar", "rss", "comentarios", "editar", "borrar", "tema", "mensaje"}


def unique_slugify(instance, value, slug_field_name="slug"):
    """Devuelve un slug único para `instance` a partir de `value`.

    "Regata de Otoño" -> "regata-de-otono"; si ya existe, "regata-de-otono-2", etc.
    """
    field = instance._meta.get_field(slug_field_name)
    max_length = field.max_length
    base = slugify(value)[:max_length].strip("-") or "elemento"
    if base in RESERVED_SLUGS:
        base = f"{base}-1"
    queryset = type(instance)._default_manager.all()
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    slug = base
    counter = 2
    while queryset.filter(**{slug_field_name: slug}).exists():
        suffix = f"-{counter}"
        slug = f"{base[: max_length - len(suffix)].rstrip('-')}{suffix}"
        counter += 1
    return slug


def safe_next_url(request, candidate, fallback="/"):
    """Solo acepta redirecciones a este mismo sitio (evita redirecciones abiertas)."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host(), *settings.ALLOWED_HOSTS},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def current_year():
    return timezone.localdate().year
