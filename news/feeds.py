from django.conf import settings
from django.contrib.syndication.views import Feed
from django.urls import reverse_lazy

from .models import Article


class LatestArticlesFeed(Feed):
    link = reverse_lazy("article_list")

    def title(self):
        return f"{settings.SITE_NAME} · Noticias"

    def description(self):
        return settings.SITE_TAGLINE

    def items(self):
        return Article.objects.published().select_related("sport")[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.summary

    def item_pubdate(self, item):
        return item.published_at

    def item_categories(self, item):
        return [item.sport.name] if item.sport else []
