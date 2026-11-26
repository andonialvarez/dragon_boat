# Calendario de eventos y resultados

Cada lunes, una tarea programada busca en internet **eventos con fecha confirmada** y
**resultados recientes** de dragon boat, traineras y piragüismo, y los deja en
`calendario/datos.json` de la rama `calendario-semanal`. El flujo de GitHub Actions
«Publicar calendario» los envía a la web (`POST /api/calendario/`). Si el fichero cambia
en `main`, también se publica.

Además de `datos.json`, en `calendario/` puede haber otros ficheros con el mismo formato, por ejemplo
`borrador-rfep-2027.json` (borrador del calendario estatal 2027 de la RFEP, con `status: provisional`).
Cuando uno de ellos cambia en `main`, se publica solo ese fichero.

- Los eventos aparecen en **Eventos** y, por deporte, en **Clasificaciones › Próximas pruebas**.
- Los resultados aparecen en **Clasificaciones**, con su fuente enlazada.
- Nunca se inventa nada: cada evento y cada clasificación lleva `source_url`.

La web **no duplica**: cada elemento lleva una referencia fija `ref`. Si se vuelve a enviar
con la misma `ref`, se actualiza (por ejemplo, para cambiar fechas, marcarlo como
`aplazado` o `cancelado`, o completar una clasificación).

## Formato

```json
{
  "eventos": [
    {
      "ref": "bandera-concha-2027",
      "title": "Bandera de La Concha 2027",
      "sport": "traineras",
      "kind": "regata",
      "status": "programado",
      "start_date": "2027-09-05",
      "end_date": "2027-09-12",
      "venue": "Bahía de La Concha",
      "city": "Donostia",
      "region": "Gipuzkoa",
      "country": "España",
      "summary": "Una o dos frases (máximo 280 caracteres).",
      "description": "Opcional, más detalle.",
      "distances": "3 millas náuticas",
      "organizer": "Quién organiza",
      "website": "https://web-oficial-del-evento",
      "registration_url": "https://inscripciones (opcional)",
      "source_name": "Nombre de la fuente",
      "source_url": "https://pagina-donde-se-ha-comprobado",
      "championship": "ref-de-una-clasificacion (opcional)"
    }
  ],
  "clasificaciones": [
    {
      "ref": "bandera-concha-2026",
      "name": "Bandera de La Concha 2026",
      "sport": "traineras",
      "season": 2026,
      "scope": "nacional",
      "organizer": "Quién organiza",
      "location": "Sede o sedes",
      "start_date": "2026-09-06",
      "end_date": "2026-09-13",
      "description": "Breve explicación.",
      "source_name": "Nombre de la fuente",
      "source_url": "https://resultados-oficiales",
      "divisions": [
        {
          "name": "Bandera masculina",
          "notes": "Opcional",
          "standings": [
            {"position": 1, "name": "Orio Orialki", "time": "39:27,56"},
            {"position": 2, "name": "Donostiarra", "points": 12, "notes": "Opcional"}
          ]
        }
      ]
    }
  ]
}
```

- `sport`: `dragon-boat`, `traineras`, `piraguismo`, `remo-olimpico` o `vaa`.
- `kind`: `regata`, `campeonato`, `liga`, `festival`, `travesia`, `formacion` u `otro`.
- `status`: `programado`, `provisional` (fechas sacadas de un borrador, la web las marca como «Fechas provisionales»), `aplazado` o `cancelado`.
- `scope`: `local`, `autonomico`, `nacional` o `internacional`.
- Fechas en formato `AAAA-MM-DD`. `country` es «España» si no se pone.
- Al enviar una clasificación con `divisions`, sus categorías se **sustituyen** enteras.
- Si el nombre de un puesto coincide con un equipo que ya tiene ficha en la web, se enlaza con ella.
- Si algo del fichero está mal, la web no guarda nada de ese envío y responde con el error.

Para comprobar el fichero antes de subirlo:
`python scripts/publicar_calendario.py calendario/datos.json` (sin `SITE_URL` ni `NEWS_API_TOKEN` solo lo revisa).
