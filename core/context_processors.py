from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import Sport

SAMPLE_CACHE_KEY = "site:has_sample_data"


def has_sample_data():
    value = cache.get(SAMPLE_CACHE_KEY)
    if value is None:
        from competitions.models import Championship, Team
        from events.models import Event
        from forum.models import Topic
        from news.models import Article

        value = any(
            model.objects.filter(is_sample=True).exists()
            for model in (Article, Event, Championship, Team, Topic)
        )
        cache.set(SAMPLE_CACHE_KEY, value, 60)
    return value


def site(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "nav_sports": Sport.objects.all(),
        "has_sample_data": has_sample_data(),
        "current_year": timezone.localdate().year,
    }
