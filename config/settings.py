"""
Configuración de Django para la web Dragon Boat.

Todo lo que cambia entre tu ordenador y el servidor se lee de variables de
entorno (o de un fichero .env en la raíz del proyecto). Mira .env.example.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Seguridad básica -------------------------------------------------------

DEBUG = env_bool("DEBUG", default=False)
# `python manage.py test` funciona sin configurar nada.
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG or TESTING:
        # Solo para desarrollo local y pruebas. En producción SECRET_KEY es obligatoria.
        SECRET_KEY = "django-insecure-solo-para-desarrollo-local"
    else:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "Falta la variable de entorno SECRET_KEY. Copia .env.example a .env "
            "para trabajar en local (con DEBUG=true) o define SECRET_KEY en el servidor."
        )

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Render publica el dominio del servicio en esta variable.
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")


# --- Aplicaciones -----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",
    # Aplicaciones del proyecto
    "core",
    "accounts",
    "reactions",
    "news",
    "events",
    "competitions",
    "forum",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Base de datos ----------------------------------------------------------
# Sin DATABASE_URL se usa SQLite (un fichero db.sqlite3), perfecto para local.
# En producción define DATABASE_URL=postgres://usuario:clave@host:5432/nombre

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Usuarios y sesiones ----------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    # Permite iniciar sesión con el nombre de usuario o con el email.
    "accounts.backends.UsernameOrEmailBackend",
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"


# --- Idioma y zona horaria --------------------------------------------------

LANGUAGE_CODE = "es"  # La web está en castellano.
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True


# --- Ficheros estáticos y subidos -------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# Opcional: guardar las imágenes subidas en un almacenamiento compatible con S3
# (Cloudflare R2, Backblaze B2, AWS S3...). Requiere `pip install django-storages[s3]`.
if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL") or None
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME") or None
    AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN") or None
    AWS_QUERYSTRING_AUTH = env_bool("AWS_QUERYSTRING_AUTH", default=False)
    AWS_S3_FILE_OVERWRITE = False

# Servir /media/ desde Django en producción (sitios pequeños con disco persistente).
SERVE_MEDIA = env_bool("SERVE_MEDIA", default=False)

# Tamaño máximo de las imágenes que suben los usuarios (en MB).
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


# --- Correo -----------------------------------------------------------------
# En local los correos (p. ej. recuperar contraseña) se muestran en la consola.

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG or not os.environ.get("EMAIL_HOST")
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Dragon Boat <no-responder@localhost>")


# --- Producción -------------------------------------------------------------

if not DEBUG and not TESTING:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
    SECURE_HSTS_PRELOAD = False
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}


# --- Publicación abierta y noticias automáticas -----------------------------

# Si es true, lo que publican los usuarios queda pendiente hasta que alguien del
# equipo lo apruebe en el panel. Si es false (por defecto), se publica al momento.
COMMUNITY_REQUIRES_APPROVAL = env_bool("COMMUNITY_REQUIRES_APPROVAL", default=False)
# Máximo de noticias + eventos que puede publicar un usuario en 24 horas (antispam).
COMMUNITY_DAILY_LIMIT = int(os.environ.get("COMMUNITY_DAILY_LIMIT", "10"))

# Clave para la API de publicación automática (importador y resúmenes de Claude).
# Si está vacía, la API queda desactivada.
NEWS_API_TOKEN = os.environ.get("NEWS_API_TOKEN", "")


# --- Datos de la web --------------------------------------------------------

SITE_NAME = os.environ.get("SITE_NAME", "Dragon Boat")
SITE_TAGLINE = os.environ.get(
    "SITE_TAGLINE", "Noticias, regatas y comunidad del dragon boat y el remo"
)
