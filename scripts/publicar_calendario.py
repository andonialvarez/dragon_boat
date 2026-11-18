"""Envía a la web los eventos y las clasificaciones de un fichero JSON.

Lo usa el flujo de GitHub Actions «Publicar calendario». El formato está en
calendario/README.md. Solo usa la biblioteca estándar de Python.

Uso: SITE_URL=... NEWS_API_TOKEN=... python scripts/publicar_calendario.py calendario/datos.json
Sin SITE_URL o sin NEWS_API_TOKEN solo revisa el fichero y no publica nada.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

SPORTS = {"dragon-boat", "traineras", "piraguismo", "remo-olimpico", "vaa"}
KINDS = {"regata", "campeonato", "liga", "festival", "travesia", "formacion", "otro"}
STATUSES = {"programado", "aplazado", "cancelado"}
SCOPES = {"local", "autonomico", "nacional", "internacional"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LIMITS = {"title": 180, "name": 180, "summary": 280, "source_name": 120, "city": 120, "venue": 180}
TIMEOUT = 120
# Tras un cambio en main, Render tarda unos minutos en desplegar la versión nueva.
DEPLOY_WAIT_SECONDS = 20 * 60


def _common(item, where, errors, refs):
    if not isinstance(item, dict):
        errors.append(f"{where}: debe ser un objeto")
        return False
    ref = str(item.get("ref") or "").strip()
    if not ref:
        errors.append(f"{where}: falta «ref»")
    elif ref in refs:
        errors.append(f"{where}: «ref» repetida ({ref})")
    refs.add(ref)
    if item.get("sport") not in SPORTS:
        errors.append(f"{where}: deporte desconocido «{item.get('sport')}»")
    source = str(item.get("source_url") or "")
    if not source.startswith(("http://", "https://")):
        errors.append(f"{where}: falta «source_url» (hay que citar siempre la fuente)")
    for field in ("start_date", "end_date", "registration_deadline"):
        value = item.get(field)
        if value and not (isinstance(value, str) and DATE.match(value)):
            errors.append(f"{where}: «{field}» debe tener formato AAAA-MM-DD")
    for field, limit in LIMITS.items():
        if len(str(item.get(field) or "")) > limit:
            errors.append(f"{where}: «{field}» supera los {limit} caracteres")
    return True


def validate(data):
    if not isinstance(data, dict):
        return ["el fichero debe ser un objeto con «eventos» y «clasificaciones»"]
    events = data.get("eventos") or []
    championships = data.get("clasificaciones") or []
    if not isinstance(events, list) or not isinstance(championships, list):
        return ["«eventos» y «clasificaciones» deben ser listas"]
    if not events and not championships:
        return ["el fichero no tiene eventos ni clasificaciones"]
    errors = []
    championship_refs, event_refs = set(), set()
    for number, item in enumerate(championships, start=1):
        where = f"clasificación {number}"
        if not _common(item, where, errors, championship_refs):
            continue
        if not item.get("name"):
            errors.append(f"{where}: falta «name»")
        if item.get("scope") and item["scope"] not in SCOPES:
            errors.append(f"{where}: ámbito desconocido «{item['scope']}»")
        for division in item.get("divisions") or []:
            if not isinstance(division, dict) or not division.get("name"):
                errors.append(f"{where}: cada categoría necesita «name»")
                continue
            for row in division.get("standings") or []:
                if not isinstance(row, dict) or not row.get("name") or not isinstance(row.get("position"), int):
                    errors.append(f"{where}, {division['name']}: cada puesto necesita «position» (número) y «name»")
    for number, item in enumerate(events, start=1):
        where = f"evento {number}"
        if not _common(item, where, errors, event_refs):
            continue
        if not item.get("title"):
            errors.append(f"{where}: falta «title»")
        if not item.get("start_date"):
            errors.append(f"{where}: falta «start_date»")
        if item.get("kind") and item["kind"] not in KINDS:
            errors.append(f"{where}: tipo desconocido «{item['kind']}»")
        if item.get("status") and item["status"] not in STATUSES:
            errors.append(f"{where}: estado desconocido «{item['status']}»")
        for field in ("website", "registration_url"):
            value = str(item.get(field) or "")
            if value and not value.startswith(("http://", "https://")):
                errors.append(f"{where}: «{field}» debe empezar por http:// o https://")
    return errors


def request(url, data=None, token=""):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if data is not None else "GET")
    req.add_header("User-Agent", "DragonBoatWeb-calendario/1.0")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def send(site, token, data):
    """Envía el fichero; si la web aún no tiene la API (404) o no responde, espera y reintenta."""
    deadline = time.monotonic() + DEPLOY_WAIT_SECONDS
    while True:
        try:
            status, body = request(f"{site}/api/calendario/", data, token)
        except OSError as error:
            status, body = 0, str(error)
        if status not in (0, 404, 502, 503) or time.monotonic() > deadline:
            return status, body
        print(f"La web aún no está lista ({status or body}); reintento en 60 s…")
        time.sleep(60)


def main(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    errors = validate(data)
    if errors:
        print("El fichero tiene errores:\n- " + "\n- ".join(errors))
        return 1
    events, championships = data.get("eventos") or [], data.get("clasificaciones") or []

    site = os.environ.get("SITE_URL", "").rstrip("/")
    token = os.environ.get("NEWS_API_TOKEN", "")
    if not site or not token:
        print(
            f"Fichero correcto ({len(events)} eventos, {len(championships)} clasificaciones). "
            "Faltan SITE_URL o NEWS_API_TOKEN: no se publica nada."
        )
        return 0

    status, body = send(site, token, {"eventos": events, "clasificaciones": championships})
    if status != 200:
        print(f"ERROR {status}: {body[:500]}")
        return 1
    report = json.loads(body)
    for label, key in (("Clasificación nueva", "creadas"), ("Clasificación actualizada", "actualizadas")):
        for name in report["clasificaciones"][key]:
            print(f"{label}: {name}")
    for label, key in (("Evento nuevo", "creados"), ("Evento actualizado", "actualizados")):
        for name in report["eventos"][key]:
            print(f"{label}: {name}")
    print(
        "Resultado: "
        f"{len(report['eventos']['creados'])} eventos nuevos, {len(report['eventos']['actualizados'])} actualizados, "
        f"{len(report['clasificaciones']['creadas'])} clasificaciones nuevas, "
        f"{len(report['clasificaciones']['actualizadas'])} actualizadas."
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
