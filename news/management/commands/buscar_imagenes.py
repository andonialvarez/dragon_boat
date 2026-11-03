from django.conf import settings
from django.core.management.base import BaseCommand

from news.images import fill_missing_images


class Command(BaseCommand):
    help = (
        "Busca la imagen que usa cada medio para compartir sus noticias (og:image) en las noticias "
        "importadas o resumidas que aún no tienen."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=40, help="Máximo de noticias que mirar (40).")
        parser.add_argument("--segundos", type=int, default=90, help="Tiempo máximo en segundos (90).")
        parser.add_argument("--dias", type=int, default=60, help="Solo noticias de los últimos N días (60).")

    def handle(self, *args, **options):
        if not settings.NEWS_FETCH_IMAGES:
            self.stdout.write("La búsqueda de imágenes está desactivada (NEWS_FETCH_IMAGES).")
            return
        result = fill_missing_images(limit=options["limite"], seconds=options["segundos"], days=options["dias"])
        self.stdout.write(
            self.style.SUCCESS(f"Imágenes encontradas: {result['updated']} de {result['checked']} noticias revisadas.")
        )
