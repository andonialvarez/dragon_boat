from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from competitions.models import Championship, Team
from events.models import Event
from forum.models import Topic
from news.models import Article

from .models import Sport


class StaticSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return ["home", "article_list", "event_list", "championship_list", "team_list", "sport_list", "forum:index"]

    def location(self, item):
        return reverse(item)


class ArticleSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Article.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class SimpleSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def __init__(self, queryset):
        self.queryset = queryset

    def items(self):
        return self.queryset.all()


sitemaps = {
    "paginas": StaticSitemap,
    "noticias": ArticleSitemap,
    "eventos": SimpleSitemap(Event.objects.filter(is_published=True)),
    "campeonatos": SimpleSitemap(Championship.objects.all()),
    "equipos": SimpleSitemap(Team.objects.all()),
    "deportes": SimpleSitemap(Sport.objects.all()),
    "foro": SimpleSitemap(Topic.objects.all()),
}
