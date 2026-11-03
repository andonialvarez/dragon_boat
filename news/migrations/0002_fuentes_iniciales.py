"""Fuentes RSS sugeridas para el importador automático de titulares.

Se pueden activar, desactivar o cambiar desde el panel (Noticias › Fuentes de noticias).
"""

from django.db import migrations

GOOGLE = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

SOURCES = [
    {
        "name": "Google Noticias · dragon boat (castellano)",
        "feed_url": GOOGLE.format(q="%22dragon+boat%22", hl="es", gl="ES", ceid="ES:es"),
        "sport": "dragon-boat",
        "keywords": "dragon boat, dragonboat, barco dragón",
        "is_active": True,
    },
    {
        "name": "Google Noticias · traineras",
        "feed_url": GOOGLE.format(q="traineras+regata", hl="es", gl="ES", ceid="ES:es"),
        "sport": "traineras",
        "keywords": "trainera, traineras, regata, bandera, estropada",
        "is_active": True,
    },
    {
        "name": "Google Noticias · piragüismo",
        "feed_url": GOOGLE.format(q="pirag%C3%BCismo", hl="es", gl="ES", ceid="ES:es"),
        "sport": "piraguismo",
        "keywords": "piragüismo, piragüista, kayak, canoa",
        "is_active": False,
    },
]


def create_sources(apps, schema_editor):
    NewsSource = apps.get_model("news", "NewsSource")
    Sport = apps.get_model("core", "Sport")
    for data in SOURCES:
        values = dict(data)
        values["sport"] = Sport.objects.filter(slug=values.pop("sport")).first()
        NewsSource.objects.update_or_create(feed_url=values.pop("feed_url"), defaults=values)


def remove_sources(apps, schema_editor):
    NewsSource = apps.get_model("news", "NewsSource")
    NewsSource.objects.filter(feed_url__in=[s["feed_url"] for s in SOURCES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0001_initial"),
        ("core", "0002_deportes_iniciales"),
    ]

    operations = [migrations.RunPython(create_sources, remove_sources)]
