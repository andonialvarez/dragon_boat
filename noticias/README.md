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
- `image_url` (muy recomendable): la foto de la noticia, ver más abajo.
- Límites: `title` 200 caracteres, `summary` 320 y `source_name` 120.
- Si una noticia ya estaba publicada (mismo `source_url`), la web no la duplica.

## Foto de cada noticia

Andoni quiere que cada noticia lleve una foto de la propia noticia siempre que exista.

1. Busca la foto que usa el artículo original para compartirse (`og:image` o `twitter:image`), por ejemplo:
   `curl -sL -m 20 -A "Mozilla/5.0" "<source_url>" | grep -oiE '<meta[^>]+(og:image|twitter:image)[^>]*>' | head -3`.
   Si no se puede descargar la página, pide a WebFetch la dirección de la foto principal del artículo.
2. Ponla en `image_url` solo si es una foto de verdad de esa noticia (la regata, la tripulación, el lugar,
   la entrega de premios…). **No valen**: el logotipo del medio, su imagen genérica para compartir (la misma
   que usa su portada), iconos, banners, anuncios, mapas ni imágenes de menos de unos 400 px de ancho.
3. Dirección absoluta `http(s)`, con los espacios escritos como `%20`. Nunca una foto de otro medio u otra
   noticia, y nunca una dirección inventada.
4. Si no hay foto adecuada, **no pongas `image_url`**. La web vuelve a mirar la fuente y, si tampoco
   encuentra nada válido, muestra la noticia con su diseño sin foto (texto más grande y el color del deporte).
5. Entre dos noticias igual de interesantes, elige la que tiene foto.

La web también revisa sola las fotos que encuentra: descarta logotipos, imágenes genéricas y las muy
pequeñas, y sigue los enlaces de Google Noticias hasta el medio original para buscar su foto.

Para comprobar un fichero antes de subirlo:
`python scripts/publicar_noticias.py noticias/semana.json` (sin `SITE_URL` ni `NEWS_API_TOKEN` solo revisa el fichero, no publica nada).
