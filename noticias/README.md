# Resumen semanal de noticias

Cada lunes, una tarea programada busca las noticias de la semana sobre dragon boat
y el resto de deportes de remo y pala, escribe un **resumen propio en castellano** de
cada una (citando siempre la fuente) y deja el resultado en `noticias/semana.json`
de la rama `noticias-semanales`. El flujo de GitHub Actions «Publicar noticias» las
envía a la web.

Formato de `semana.json`, una lista de noticias:

```json
[
  {
    "title": "Titular escrito con nuestras palabras",
    "summary": "Una o dos frases (máximo 320 caracteres).",
    "body": "Resumen de 2 a 4 párrafos, separados por una línea en blanco.",
    "sport": "dragon-boat",
    "category": "competicion",
    "source_name": "Nombre del medio",
    "source_url": "https://enlace-a-la-noticia-original"
  }
]
```

- `sport`: `dragon-boat`, `traineras`, `piraguismo`, `remo-olimpico` o `vaa`.
- `category`: `competicion`, `clubes`, `internacional`, `tecnica`, `entrevista`, `comunidad` u `otros`.
- `image_url` (opcional): imagen del medio original. Si no se pone, la web busca sola la que el
  medio usa para compartir la noticia y, si no hay, muestra una ilustración del deporte.
- Límites: `title` 200 caracteres, `summary` 320 y `source_name` 120.
- Si una noticia ya estaba publicada (mismo `source_url`), la web no la duplica.

Para comprobar un fichero antes de subirlo:
`python scripts/publicar_noticias.py noticias/semana.json` (sin `SITE_URL` ni `NEWS_API_TOKEN` solo revisa el fichero, no publica nada).
