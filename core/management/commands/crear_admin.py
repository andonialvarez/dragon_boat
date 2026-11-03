"""Crea el usuario administrador a partir de variables de entorno.

Pensado para servidores sin consola (como el plan gratuito de Render): se
ejecuta en cada despliegue y solo crea el usuario si todavía no existe. Si ya
existe no lo toca, así que cambiar la contraseña desde la web es seguro.

Variables: DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD y, opcional,
DJANGO_SUPERUSER_EMAIL.
"""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea el administrador definido en DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD si no existe."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        if not username or not password:
            self.stdout.write("Sin DJANGO_SUPERUSER_USERNAME y DJANGO_SUPERUSER_PASSWORD: no se crea administrador.")
            return

        User = get_user_model()
        if User.objects.filter(username__iexact=username).exists():
            self.stdout.write(f"El administrador «{username}» ya existe: no se cambia nada.")
            return

        user = User(username=username, email=email)
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError("La contraseña del administrador no es válida: " + " ".join(error.messages)) from error
        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Administrador «{username}» creado."))
