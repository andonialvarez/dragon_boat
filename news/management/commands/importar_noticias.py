from django.core.management.base import BaseCommand

from news.importer import import_from_sources
from news.models import NewsSource


class Command(BaseCommand):
    help = "Importa titulares de las fuentes RSS activas (Noticias › Fuentes de noticias en el panel)."

    def add_arguments(self, parser):
        parser.add_argument("--fuente", type=int, action="append", help="Id de una fuente concreta (se puede repetir).")

    def handle(self, *args, **options):
        sources = NewsSource.objects.filter(is_active=True)
        if options.get("fuente"):
            sources = NewsSource.objects.filter(pk__in=options["fuente"])
        if not sources.exists():
            self.stdout.write(self.style.WARNING("No hay fuentes activas."))
            return
        report = import_from_sources(sources)
        style = self.style.WARNING if report.errors else self.style.SUCCESS
        self.stdout.write(style(report.summary()))
