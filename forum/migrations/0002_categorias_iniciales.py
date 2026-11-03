"""Crea las categorías iniciales del foro. Se pueden cambiar desde el panel."""

from django.db import migrations

# slug, icono, deporte, {"es": (nombre, descripción)}
CATEGORIES = [
    ("dragon-boat", "🐉", "dragon-boat", {
        "es": ("Dragon boat", "Técnica, entrenamiento, tamborileros, timoneles y todo lo que pasa dentro del barco."),
    }),
    ("competiciones-y-regatas", "🏁", None, {
        "es": ("Competiciones y regatas", "Calendario, inscripciones, resultados y crónicas de regatas."),
    }),
    ("clubes-y-equipos", "🤝", None, {
        "es": ("Clubes y equipos", "Busco equipo, busco palistas y presentaciones de clubes."),
    }),
    ("traineras-y-remo", "⚓", "traineras", {
        "es": ("Traineras y remo", "Banco fijo, banco móvil, ligas y regatas de remo."),
    }),
    ("piraguismo-y-otras-modalidades", "🛶", "piraguismo", {
        "es": ("Piragüismo y otras modalidades", "Kayak, canoa, va'a, kayak de mar y más."),
    }),
    ("material-y-embarcaciones", "🧰", None, {
        "es": ("Material y embarcaciones", "Palas, barcos, ropa, transporte y mantenimiento."),
    }),
    ("charla-general", "💬", None, {
        "es": ("Charla general", "Presentaciones, dudas sobre la web y todo lo demás."),
    }),
]


def create_categories(apps, schema_editor):
    Category = apps.get_model("forum", "Category")
    Sport = apps.get_model("core", "Sport")
    for order, (slug, icon, sport_slug, texts) in enumerate(CATEGORIES, start=1):
        values = {
            "icon": icon,
            "order": order,
            "sport": Sport.objects.filter(slug=sport_slug).first() if sport_slug else None,
            "name": texts["es"][0],
            "description": texts["es"][1],
        }
        Category.objects.update_or_create(slug=slug, defaults=values)


def remove_categories(apps, schema_editor):
    Category = apps.get_model("forum", "Category")
    Category.objects.filter(slug__in=[row[0] for row in CATEGORIES], topics__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("forum", "0001_initial"),
        ("core", "0002_deportes_iniciales"),
    ]

    operations = [migrations.RunPython(create_categories, remove_categories)]
