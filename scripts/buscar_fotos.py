"""Busca desde GitHub Actions la foto de las noticias que la web no ha podido revisar.

El servidor de la web a veces no obtiene respuesta de Google Noticias. Este script
pide a la web la lista de noticias pendientes, busca cada foto con el mismo código
de la web (news/images.py) y le manda el resultado.

Uso: SITE_URL=... NEWS_API_TOKEN=... python scripts/buscar_fotos.py [días]
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("NEWS_FETCH_IMAGES", "true")

import django  # noqa: E402

django.setup()

from news.images import find_image, is_suitable_image  # noqa: E402

TIMEOUT = 120


def call(url, token, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url, data=body, method="POST" if data is not None else "GET")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("User-Agent", "DragonBoatWeb-fotos/1.0")
    if body:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    site = os.environ["SITE_URL"].rstrip("/")
    token = os.environ["NEWS_API_TOKEN"]
    days = sys.argv[1] if len(sys.argv) > 1 else "45"
    pending = call(f"{site}/api/noticias/fotos/pendientes/?dias={days}", token)["articles"]
    print(f"Noticias pendientes: {len(pending)}")
    results = []
    for article in pending:
        if article["image_url"]:
            image = article["image_url"] if is_suitable_image(article["image_url"], article["source_url"]) else ""
        else:
            image = find_image(article["source_url"])
            if image is None:
                print(f"- {article['source_url'][:90]}: Google no responde, se reintentará")
                continue
        print(f"- {article['source_url'][:90]}: {image or 'sin foto adecuada'}")
        results.append({"id": article["id"], "image_url": image})
    if results:
        print("Guardado:", call(f"{site}/api/noticias/fotos/", token, results))


if __name__ == "__main__":
    main()
