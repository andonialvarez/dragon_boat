"""Prueba temporal: busca fotos de noticias reales (Google Noticias y resúmenes anteriores)."""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DEBUG", "true")
import logging
logging.basicConfig(level=logging.INFO)
import django

django.setup()
import feedparser

from news import images

FEEDS = [
    "https://news.google.com/rss/search?q=%22dragon+boat%22&hl=es&gl=ES&ceid=ES:es",
    "https://news.google.com/rss/search?q=traineras+regata&hl=es&gl=ES&ceid=ES:es",
    "https://news.google.com/rss/search?q=pirag%C3%BCismo&hl=es&gl=ES&ceid=ES:es",
]
for feed in FEEDS:
    raw = urllib.request.urlopen(urllib.request.Request(feed, headers={"User-Agent": images.USER_AGENT}), timeout=20).read()
    for entry in feedparser.parse(raw).entries[:8]:
        real = images.resolve_google_news(entry.link)
        photo = images.find_image(entry.link)
        print(f"GN | {entry.title[:70]}\n   -> {real or 'SIN RESOLVER'}\n   foto: {photo or 'NINGUNA'}")
for url in [] or json.load(open(os.path.join(os.path.dirname(__file__), "_probe_urls.json"))):
    page = images._read_page(url)
    raw_img = images.extract_image(*page) if page else ""
    photo = images.find_image(url)
    print(f"RS | {url[:90]}\n   og: {raw_img or '-'}\n   foto: {photo or 'NINGUNA (descartada)' if raw_img else 'NINGUNA'}")
