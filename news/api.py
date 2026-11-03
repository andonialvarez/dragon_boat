"""API mínima para publicar noticias de forma automática.

La usan:
- un cron (por ejemplo GitHub Actions) para lanzar el importador RSS: POST /api/noticias/importar/
- una tarea programada de Claude que busca noticias, escribe un resumen propio en
  castellano y lo publica citando la fuente: POST /api/noticias/

Autenticación: cabecera `Authorization: Bearer <NEWS_API_TOKEN>`. Si NEWS_API_TOKEN
no está definida, la API responde 404 (desactivada).
"""

import hmac
import json
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Sport

from .images import clean_image_url, fill_missing_images, find_image
from .importer import import_from_sources
from .models import Article, NewsSource

TEXT_FIELDS = {"title": 200, "summary": 320, "body": 20000}


def token_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        expected = settings.NEWS_API_TOKEN
        if not expected:
            raise Http404
        header = request.headers.get("Authorization", "")
        given = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
        if not given or not hmac.compare_digest(given.encode(), expected.encode()):
            return JsonResponse({"error": "token no válido"}, status=401)
        return view(request, *args, **kwargs)

    return wrapper


def _text(payload, field, max_length):
    value = payload.get(field) or ""
    if not isinstance(value, str):
        raise ValidationError(f"«{field}» debe ser un texto")
    return value.strip()[:max_length]


@csrf_exempt
@require_POST
@token_required
def create_article(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValidationError("se esperaba un objeto JSON")
        texts = {field: _text(payload, field, max_length) for field, max_length in TEXT_FIELDS.items()}
        if not texts["title"] or not texts["summary"]:
            raise ValidationError("faltan «title» y «summary»")

        source_url = (payload.get("source_url") or "").strip()
        if source_url:
            URLValidator(schemes=["http", "https"])(source_url)
            existing = Article.objects.filter(source_url=source_url).first()
            if existing:
                return JsonResponse(
                    {
                        "duplicate": True,
                        "id": existing.pk,
                        "url": request.build_absolute_uri(existing.get_absolute_url()),
                    }
                )

        sport = None
        if payload.get("sport"):
            sport = Sport.objects.filter(slug=payload["sport"]).first()
            if sport is None:
                raise ValidationError(f"deporte desconocido: {payload['sport']}")

        category = payload.get("category") or Article.Category.OTHER
        if category not in Article.Category.values:
            raise ValidationError(f"sección desconocida: {category}")
        origin = payload.get("origin") or Article.Origin.AI
        if origin not in Article.Origin.values:
            raise ValidationError(f"origen desconocido: {origin}")

        image_url = ""
        if payload.get("image_url"):
            image_url = clean_image_url(str(payload["image_url"]))
            if not image_url:
                raise ValidationError("«image_url» debe ser un enlace http:// o https://")
        elif source_url and settings.NEWS_FETCH_IMAGES:
            image_url = find_image(source_url)

        published_at = timezone.now()
        if payload.get("published_at"):
            published_at = parse_datetime(payload["published_at"])
            if published_at is None:
                raise ValidationError("«published_at» debe tener formato ISO 8601")
            if timezone.is_naive(published_at):
                published_at = timezone.make_aware(published_at)

        article = Article(
            title=texts["title"],
            summary=texts["summary"],
            body=texts["body"] or texts["summary"],
            sport=sport,
            category=category,
            origin=origin,
            status=Article.Status.PUBLISHED,
            published_at=published_at,
            source_name=(payload.get("source_name") or "")[:120],
            source_url=source_url,
            image_url=image_url,
        )
        article.full_clean(exclude=["slug"])
        article.save()
    except (ValueError, ValidationError) as error:
        message = "; ".join(error.messages) if isinstance(error, ValidationError) else str(error)
        return JsonResponse({"error": message}, status=400)

    return JsonResponse(
        {
            "id": article.pk,
            "url": request.build_absolute_uri(article.get_absolute_url()),
            "image_url": article.image_url,
        },
        status=201,
    )


@csrf_exempt
@require_POST
@token_required
def run_import(request):
    report = import_from_sources(NewsSource.objects.filter(is_active=True))
    return JsonResponse(
        {"created": report.created, "skipped": report.skipped, "errors": report.errors},
        status=200 if not report.errors else 207,
    )


@csrf_exempt
@require_POST
@token_required
def fill_images(request):
    """Busca la imagen de las noticias recientes que aún no tienen (con límite de tiempo)."""
    return JsonResponse(fill_missing_images(limit=25, seconds=18))
