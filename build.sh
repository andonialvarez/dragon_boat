#!/usr/bin/env bash
# Pasos de instalación en el servidor (Render los ejecuta en cada despliegue).
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
# Crea el administrador la primera vez (variables DJANGO_SUPERUSER_*).
python manage.py crear_admin
# Imagen de las noticias que vienen de otras webs (si un medio no responde, no pasa nada).
python manage.py buscar_imagenes --segundos 60 || echo "No se pudieron buscar imágenes; se reintentará."
