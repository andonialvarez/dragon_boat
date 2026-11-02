"""Reglas comunes para lo que publican los usuarios (noticias y eventos)."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def requires_approval(user):
    return settings.COMMUNITY_REQUIRES_APPROVAL and not user.is_staff


def over_daily_limit(user):
    if user.is_staff:
        return False
    from events.models import Event
    from news.models import Article

    since = timezone.now() - timedelta(hours=24)
    total = (
        Article.objects.filter(author=user, created_at__gte=since).count()
        + Event.objects.filter(created_by=user, created_at__gte=since).count()
    )
    return total >= settings.COMMUNITY_DAILY_LIMIT


def can_manage(user, owner_id):
    return user.is_authenticated and (user.is_staff or user.pk == owner_id)
