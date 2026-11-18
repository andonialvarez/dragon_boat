"""API para mantener actualizados el calendario de eventos y las clasificaciones.

La usa el flujo de GitHub Actions «Publicar calendario», que envía el fichero
`calendario/datos.json` (lo prepara cada semana una tarea programada de Claude):

    POST /api/calendario/   (cabecera `Authorization: Bearer <NEWS_API_TOKEN>`)

Cuerpo: {"eventos": [...], "clasificaciones": [...]} (formato en calendario/README.md).

Cada evento y cada campeonato lleva una referencia `ref` estable: si ya existe uno
con esa referencia se actualiza en lugar de crear otro, así que el mismo fichero se
puede enviar varias veces sin duplicar nada.
"""

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from competitions.models import Championship, Division, Standing, Team
from core.models import Sport
from news.api import token_required

from .models import Event

MAX_ITEMS = 200

EVENT_TEXT = {
    "title": 180,
    "venue": 180,
    "city": 120,
    "region": 120,
    "country": 80,
    "summary": 280,
    "description": 5000,
    "distances": 150,
    "organizer": 180,
    "source_name": 120,
}
EVENT_URLS = {"website": 200, "registration_url": 200, "source_url": 500}

CHAMPIONSHIP_TEXT = {
    "name": 180,
    "organizer": 180,
    "location": 180,
    "description": 5000,
    "source_name": 120,
}


class PayloadError(ValueError):
    pass


def _text(item, field, limit, where):
    value = item.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PayloadError(f"{where}: «{field}» debe ser un texto")
    return value.strip()[:limit]


def _url(item, field, limit, where):
    value = _text(item, field, 10_000, where)
    if not value:
        return ""
    if len(value) > limit:
        raise PayloadError(f"{where}: «{field}» es demasiado largo")
    try:
        URLValidator(schemes=["http", "https"])(value)
    except ValidationError:
        raise PayloadError(f"{where}: «{field}» no es un enlace válido") from None
    return value


def _date(item, field, where, required=False):
    value = item.get(field)
    if not value:
        if required:
            raise PayloadError(f"{where}: falta «{field}»")
        return None
    parsed = parse_date(str(value)) if isinstance(value, str) else None
    if parsed is None:
        raise PayloadError(f"{where}: «{field}» debe ser una fecha AAAA-MM-DD")
    return parsed


def _ref(item, where):
    ref = item.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        raise PayloadError(f"{where}: falta «ref» (una referencia fija, p. ej. «concha-2026»)")
    return ref.strip()[:120]


def _choice(item, field, choices, default, where):
    value = item.get(field) or default
    if value not in choices:
        raise PayloadError(f"{where}: «{field}» desconocido: {value}")
    return value


def _sport(item, sports, where):
    slug = item.get("sport")
    if slug not in sports:
        raise PayloadError(f"{where}: deporte desconocido: {slug}")
    return sports[slug]


def save_championship(item, sports, number):
    where = f"clasificación {number}"
    ref = _ref(item, where)
    values = {field: _text(item, field, limit, where) for field, limit in CHAMPIONSHIP_TEXT.items()}
    if not values["name"]:
        raise PayloadError(f"{where}: falta «name»")
    if not item.get("source_url"):
        raise PayloadError(f"{where}: falta «source_url» (hay que citar siempre la fuente)")
    values["source_url"] = _url(item, "source_url", 500, where)
    values["sport"] = _sport(item, sports, where)
    values["scope"] = _choice(item, "scope", Championship.Scope.values, Championship.Scope.NATIONAL, where)
    values["start_date"] = _date(item, "start_date", where)
    values["end_date"] = _date(item, "end_date", where)
    season = item.get("season") or (values["start_date"].year if values["start_date"] else date.today().year)
    if not isinstance(season, int) or not 1900 <= season <= 2100:
        raise PayloadError(f"{where}: «season» debe ser un año")
    values["season"] = season

    divisions = item.get("divisions") or []
    if not isinstance(divisions, list):
        raise PayloadError(f"{where}: «divisions» debe ser una lista")

    championship, created = Championship.objects.update_or_create(external_ref=ref, defaults=values)
    # Las categorías se sustituyen enteras: el fichero manda.
    if divisions:
        championship.divisions.all().delete()
    teams = {team.name.casefold(): team for team in Team.objects.all()}
    for order, division_data in enumerate(divisions):
        division_where = f"{where}, categoría {order + 1}"
        if not isinstance(division_data, dict):
            raise PayloadError(f"{division_where}: debe ser un objeto")
        name = _text(division_data, "name", 180, division_where)
        if not name:
            raise PayloadError(f"{division_where}: falta «name»")
        division = Division.objects.create(
            championship=championship,
            name=name,
            notes=_text(division_data, "notes", 250, division_where),
            order=order,
        )
        seen_teams = set()
        for row_number, row in enumerate(division_data.get("standings") or [], start=1):
            row_where = f"{division_where}, puesto {row_number}"
            if not isinstance(row, dict):
                raise PayloadError(f"{row_where}: debe ser un objeto")
            competitor = _text(row, "name", 150, row_where)
            if not competitor:
                raise PayloadError(f"{row_where}: falta «name»")
            position = row.get("position")
            if not isinstance(position, int) or position < 1:
                raise PayloadError(f"{row_where}: «position» debe ser un número entero")
            points = row.get("points")
            if points is not None:
                try:
                    points = Decimal(str(points))
                except InvalidOperation:
                    raise PayloadError(f"{row_where}: «points» debe ser un número") from None
            # Si el club ya tiene ficha en la web, se enlaza con ella.
            team = teams.get(competitor.casefold())
            if team and team.pk in seen_teams:
                team = None
            if team:
                seen_teams.add(team.pk)
            Standing.objects.create(
                division=division,
                team=team,
                competitor="" if team else competitor,
                position=position,
                points=points,
                result_time=_text(row, "time", 20, row_where),
                notes=_text(row, "notes", 200, row_where),
            )
    return championship, created


def save_event(item, sports, championships, number):
    where = f"evento {number}"
    ref = _ref(item, where)
    values = {field: _text(item, field, limit, where) for field, limit in EVENT_TEXT.items()}
    if not values["title"]:
        raise PayloadError(f"{where}: falta «title»")
    if not item.get("source_url"):
        raise PayloadError(f"{where}: falta «source_url» (hay que citar siempre la fuente)")
    for field, limit in EVENT_URLS.items():
        values[field] = _url(item, field, limit, where)
    if not values["country"]:
        values["country"] = "España"
    values["sport"] = _sport(item, sports, where)
    values["kind"] = _choice(item, "kind", Event.Kind.values, Event.Kind.REGATTA, where)
    values["status"] = _choice(item, "status", Event.Status.values, Event.Status.SCHEDULED, where)
    values["start_date"] = _date(item, "start_date", where, required=True)
    values["end_date"] = _date(item, "end_date", where)
    if values["end_date"] and values["end_date"] < values["start_date"]:
        raise PayloadError(f"{where}: «end_date» es anterior a «start_date»")
    values["registration_deadline"] = _date(item, "registration_deadline", where)
    values["championship"] = None
    if item.get("championship"):
        values["championship"] = championships.get(item["championship"]) or Championship.objects.filter(
            external_ref=item["championship"]
        ).first()
        if values["championship"] is None:
            raise PayloadError(f"{where}: no existe la clasificación «{item['championship']}»")
    values["is_published"] = True
    return Event.objects.update_or_create(external_ref=ref, defaults=values)


@csrf_exempt
@require_POST
@token_required
def update_calendar(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "el cuerpo debe ser JSON"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "se esperaba un objeto con «eventos» y «clasificaciones»"}, status=400)
    events = payload.get("eventos") or []
    championships = payload.get("clasificaciones") or []
    if not isinstance(events, list) or not isinstance(championships, list):
        return JsonResponse({"error": "«eventos» y «clasificaciones» deben ser listas"}, status=400)
    if len(events) + len(championships) > MAX_ITEMS:
        return JsonResponse({"error": f"como mucho {MAX_ITEMS} elementos por envío"}, status=400)

    sports = {sport.slug: sport for sport in Sport.objects.all()}
    report = {"eventos": {"creados": [], "actualizados": []}, "clasificaciones": {"creadas": [], "actualizadas": []}}
    try:
        with transaction.atomic():
            saved = {}
            for number, item in enumerate(championships, start=1):
                if not isinstance(item, dict):
                    raise PayloadError(f"clasificación {number}: debe ser un objeto")
                championship, created = save_championship(item, sports, number)
                saved[championship.external_ref] = championship
                report["clasificaciones"]["creadas" if created else "actualizadas"].append(championship.name)
            for number, item in enumerate(events, start=1):
                if not isinstance(item, dict):
                    raise PayloadError(f"evento {number}: debe ser un objeto")
                event, created = save_event(item, sports, saved, number)
                report["eventos"]["creados" if created else "actualizados"].append(event.title)
    except PayloadError as error:
        # Nada se guarda si algo falla: así el fichero se corrige y se vuelve a enviar.
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse(report)
