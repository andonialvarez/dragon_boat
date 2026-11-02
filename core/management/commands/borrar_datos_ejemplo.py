from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction

from competitions.models import Championship, Team
from core.context_processors import SAMPLE_CACHE_KEY
from events.models import Event
from forum.models import Post, Topic
from news.models import Article, Comment

User = get_user_model()


class Command(BaseCommand):
    help = "Borra TODOS los contenidos marcados como dato de ejemplo (y los usuarios de ejemplo)."

    def add_arguments(self, parser):
        parser.add_argument("--si", action="store_true", help="No pedir confirmación.")

    def handle(self, *args, **options):
        if not options["si"]:
            answer = input("Se borrarán todos los datos de ejemplo. ¿Continuar? [s/N] ")
            if answer.strip().lower() not in {"s", "si", "sí", "y", "yes"}:
                self.stdout.write("Cancelado.")
                return

        with transaction.atomic():
            counts = {}
            # El orden importa: primero lo que depende de otras cosas.
            for label, model in (
                ("comentarios", Comment),
                ("mensajes del foro", Post),
                ("temas del foro", Topic),
                ("noticias", Article),
                ("eventos", Event),
                ("campeonatos", Championship),
                ("equipos", Team),
            ):
                deleted = model.objects.filter(is_sample=True).delete()[1]
                counts[label] = deleted.get(model._meta.label, 0)
            deleted = User.objects.filter(profile__is_sample=True).delete()[1]
            counts["usuarios"] = deleted.get(User._meta.label, 0)
        cache.delete(SAMPLE_CACHE_KEY)
        summary = ", ".join(f"{label}: {number}" for label, number in counts.items())
        self.stdout.write(self.style.SUCCESS(f"Datos de ejemplo borrados ({summary})."))
