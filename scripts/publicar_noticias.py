"""Publica en la web las noticias de un fichero JSON usando la API.

Lo usa el flujo de GitHub Actions «Publicar noticias», que se lanza cuando la
tarea semanal sube `noticias/semana.json` a la rama `noticias-semanales`.

Formato del fichero: una lista de noticias, cada una con
    title, summary, body, sport, category, source_name, source_url
(ver noticias/README.md). Solo usa la biblioteca estándar de Python.

Uso: SITE_URL=... NEWS_API_TOKEN=... python scripts/publicar_noticias.py noticias/semana.json
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

REQUIRED = ("title", "summary", "body", "source_name", "source_url")
MAX_LENGTH = {"title": 200, "summary": 320, "source_name": 120}  # Lo que admite la web.
SPORTS = {"dragon-boat", "traineras", "piraguismo", "remo-olimpico", "vaa"}
CATEGORIES = {"competicion", "clubes", "internacional", "tecnica", "entrevista", "comunidad", "otros"}
TIMEOUT = 120  # El plan gratuito de Render tarda en «despertar».


def validate(items):
    """Devuelve una lista de errores (vacía si todo está bien)."""
    if not isinstance(items, list) or not items:
        return ["el fichero debe contener una lista con al menos una noticia"]
    errors = []
    seen = set()
    for number, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"noticia {number}: debe ser un objeto")
            continue
        for field in REQUIRED:
            if not str(item.get(field) or "").strip():
                errors.append(f"noticia {number}: falta «{field}»")
        for field, limit in MAX_LENGTH.items():
            if len(str(item.get(field) or "").strip()) > limit:
                errors.append(f"noticia {number}: «{field}» supera los {limit} caracteres")
        url = str(item.get("source_url") or "")
        if url and not url.startswith(("http://", "https://")):
            errors.append(f"noticia {number}: «source_url» debe empezar por http:// o https://")
        if url in seen:
            errors.append(f"noticia {number}: «source_url» repetido en el fichero")
        seen.add(url)
        if item.get("sport") and item["sport"] not in SPORTS:
            errors.append(f"noticia {number}: deporte desconocido «{item['sport']}»")
        if item.get("category") and item["category"] not in CATEGORIES:
            errors.append(f"noticia {number}: sección desconocida «{item['category']}»")
    return errors


def request(url, data=None, token=""):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if data is not None else "GET")
    req.add_header("User-Agent", "DragonBoatWeb-publicador/1.0")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def is_duplicate(body):
    try:
        return bool(json.loads(body).get("duplicate"))
    except (ValueError, AttributeError):
        return False


def wake_up(site):
    """Hace peticiones hasta que la web responde (o se rinde tras ~4 minutos)."""
    for attempt in range(6):
        try:
            status, _body = request(f"{site}/robots.txt")
            if status == 200:
                return True
        except OSError as error:
            print(f"La web aún no responde ({error}); reintento…")
        time.sleep(10 * (attempt + 1))
    return False


def main(path):
    with open(path, encoding="utf-8") as handle:
        items = json.load(handle)
    errors = validate(items)
    if errors:
        print("El fichero tiene errores:\n- " + "\n- ".join(errors))
        return 1

    site = os.environ.get("SITE_URL", "").rstrip("/")
    token = os.environ.get("NEWS_API_TOKEN", "")
    if not site or not token:
        print(f"Fichero correcto ({len(items)} noticias). Faltan SITE_URL o NEWS_API_TOKEN: no se publica nada.")
        return 0

    if not wake_up(site):
        print("La web no responde.")
        return 1

    created = duplicated = failed = 0
    for item in items:
        payload = {key: item[key] for key in (*REQUIRED, "sport", "category") if item.get(key)}
        payload["origin"] = "ia"  # Se muestra como «Resumen con IA».
        status, body = request(f"{site}/api/noticias/", payload, token)
        if status == 201:
            created += 1
            print(f"Publicada: {item['title']}")
        elif status == 200 and is_duplicate(body):
            duplicated += 1
            print(f"Ya estaba publicada: {item['title']}")
        else:
            failed += 1
            print(f"ERROR {status} con «{item['title']}»: {body[:300]}")
    print(f"Resultado: {created} publicadas, {duplicated} repetidas, {failed} con error.")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
