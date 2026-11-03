from urllib.parse import urlparse

from django import template
from django.template.defaultfilters import date as date_filter
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def nav_current(context, prefix):
    """Marca el enlace del menú de la sección en la que estás."""
    request = context.get("request")
    if not request:
        return ""
    path = request.path
    if (prefix == "/" and path == "/") or (prefix != "/" and path.startswith(prefix)):
        return mark_safe('aria-current="page"')
    return ""


@register.inclusion_tag("includes/avatar.html")
def avatar(user, size=""):
    profile = getattr(user, "profile", None)
    username = user.get_username() if user else "?"
    return {
        "username": username,
        "initial": (username[:1] or "?").upper(),
        "color": profile.avatar_color if profile else "#0d6a73",
        "size": size,
    }


FULL_DATE = "j \\d\\e F \\d\\e Y"
DAY_MONTH = "j \\d\\e F"


@register.simple_tag
def date_range(start, end=None):
    """«14 de noviembre de 2026» o «14–16 de noviembre de 2026»."""
    if not end or end == start:
        return date_filter(start, FULL_DATE)
    if start.year != end.year:
        return f"{date_filter(start, FULL_DATE)} – {date_filter(end, FULL_DATE)}"
    if start.month != end.month:
        return f"{date_filter(start, DAY_MONTH)} – {date_filter(end, FULL_DATE)}"
    return f"{start.day}–{date_filter(end, FULL_DATE)}"


@register.filter
def hostname(url):
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host.removeprefix("www.")


@register.simple_tag
def sport_style(sport):
    """Atributo style con el color del deporte, para chips y marcadores."""
    if not sport:
        return ""
    return format_html('style="--sport: {}"', sport.color)
