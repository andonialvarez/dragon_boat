# Dragon Boat · remo y pala

Web de noticias, calendario de regatas, clasificaciones, equipos y foro sobre **dragon boat**, con sitio también para las traineras, el piragüismo, el remo olímpico, la va'a y el resto de deportes de remo y pala.

- **Leer es libre**: noticias, eventos, clasificaciones, equipos, deportes y foro se ven sin cuenta.
- **Con cuenta** (registro sin confirmar el email): comentar y responder en las noticias, reaccionar (👍 ❤️ 👏 🔥 🐉), escribir en el foro y **publicar noticias y eventos**.
- **Noticias automáticas**: un importador recoge titulares de fuentes RSS (siempre con enlace al original) y hay una API para que una tarea programada publique resúmenes propios citando la fuente.
- Pensada para el **móvil**: se adapta a teléfonos, tablets y ordenador.
- La web está en **castellano**.

> **Contenido de ejemplo.** Al principio la web trae equipos, campeonatos, resultados, noticias y temas del foro **inventados**, marcados con la etiqueta «Ejemplo», para ver cómo queda. Se borran con un solo comando (ver más abajo). Ningún resultado de ejemplo es real.

---

## Índice

1. [Tecnología](#tecnología)
2. [Ponerla en marcha en tu ordenador (Windows)](#ponerla-en-marcha-en-tu-ordenador-windows)
3. [Cómo se usa](#cómo-se-usa)
4. [Datos de ejemplo](#datos-de-ejemplo)
5. [Noticias automáticas](#noticias-automáticas)
6. [Publicarla en internet](#publicarla-en-internet)
7. [Antes de abrirla al público](#antes-de-abrirla-al-público)
8. [Pruebas](#pruebas)
9. [Estructura del proyecto](#estructura-del-proyecto)

---

## Tecnología

| Pieza | Para qué |
| --- | --- |
| **Python + Django 5.2 (LTS)** | El corazón de la web. Django trae de serie usuarios, inicio de sesión, recuperación de contraseña, protección contra ataques habituales y un **panel de administración** para gestionar todo sin programar. Versión con soporte hasta 2028. |
| **SQLite** (en tu ordenador) / **PostgreSQL** (en el servidor) | Base de datos. En local no hay que instalar nada; en producción se usa PostgreSQL indicando `DATABASE_URL`. |
| **HTML + CSS + un poco de JavaScript** | Sin frameworks de interfaz ni pasos de compilación. Todo funciona también sin JavaScript (las reacciones, por ejemplo, recargan la página si no hay JS). |
| **WhiteNoise + Gunicorn** | Sirven la web en el servidor. |
| **feedparser** | Lee los feeds RSS/Atom del importador de noticias. |

¿Por qué así? Es una pila muy conocida, barata de alojar (un solo servicio + una base de datos), fácil de mantener por una persona y con el panel de administración hecho, que en una web de comunidad ahorra mucho trabajo.

---

## Ponerla en marcha en tu ordenador (Windows)

### 1. Instala lo necesario (una sola vez)

- **Python 3.12 o 3.13** desde [python.org/downloads](https://www.python.org/downloads/). En el instalador marca **«Add python.exe to PATH»**.
- **Git** desde [git-scm.com](https://git-scm.com/download/win) (o GitHub Desktop).

### 2. Descarga el código en tu carpeta

Abre **PowerShell** y ve a la carpeta:

```powershell
cd "C:\Users\andon\Desktop\I+D+I\dragon_boat"
```

- Si la carpeta **ya es una copia del repositorio** (tiene una carpeta oculta `.git`):

  ```powershell
  git pull
  ```

  Mientras el pull request no esté aprobado, para probar esta rama: `git fetch` y luego `git checkout claude/web-dragon-boat`.

- Si la carpeta está **vacía**:

  ```powershell
  git clone https://github.com/andonialvarez/dragon_boat.git .
  ```

### 3. Prepara el entorno de Python (una sola vez)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

> Si PowerShell no deja ejecutar `Activate.ps1`, ejecuta una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a intentarlo. En la consola clásica (cmd) se activa con `.venv\Scripts\activate.bat`.

### 4. Crea la base de datos, los datos de ejemplo y tu usuario administrador

```powershell
python manage.py migrate
python manage.py cargar_datos_ejemplo
python manage.py createsuperuser
```

### 5. Arranca la web

```powershell
python manage.py runserver
```

Abre **http://127.0.0.1:8000** en el navegador. El panel de administración está en **http://127.0.0.1:8000/admin/**.

Para verla **en tu móvil** (conectado a la misma wifi): averigua la IP de tu ordenador con `ipconfig` (por ejemplo `192.168.1.40`), añade esa IP a `ALLOWED_HOSTS` en el `.env` (`ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.40`), arranca con `python manage.py runserver 0.0.0.0:8000` y abre `http://192.168.1.40:8000` en el móvil.

**Las siguientes veces** solo hace falta:

```powershell
cd "C:\Users\andon\Desktop\I+D+I\dragon_boat"
.venv\Scripts\Activate.ps1
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

(En macOS o Linux es igual, cambiando `py` por `python3`, la activación por `source .venv/bin/activate` y `copy` por `cp`.)

---

## Cómo se usa

### Lo que puede hacer cualquier persona registrada

- **Publicar noticias** (Noticias › «Publicar noticia») y **eventos o regatas** (Eventos › «Publicar evento»). Se publican al momento y llevan la etiqueta «Comunidad». Cada persona puede editar o borrar lo suyo.
- **Comentar** las noticias, **responder** a otros comentarios y **reaccionar**.
- **Abrir temas y responder en el foro**, con una imagen opcional.

Hay un límite de 10 publicaciones (noticias + eventos) por persona y día para frenar el spam (`COMMUNITY_DAILY_LIMIT`).

**Si prefieres revisar antes de publicar**, pon `COMMUNITY_REQUIRES_APPROVAL=true`: lo que suban los usuarios quedará «pendiente» hasta que lo apruebes en el panel (acción «Publicar» en Noticias o Eventos).

### El panel de administración (`/admin/`)

Desde ahí se gestiona todo sin tocar código:

- **Campeonatos y clasificaciones**: crea el campeonato, sus categorías (por ejemplo «Mixto · barco grande · 200 m») y, dentro de cada categoría, la tabla con puesto, equipo, puntos y/o tiempo. La web muestra solo las columnas que tengan datos.
- **Equipos**: nombre, localidad, zona, país, año de fundación, deportes, escudo y descripción.
- **Noticias, eventos y deportes**: crear, editar, destacar en portada, aprobar o pasar a borrador.
- **Moderación**: ocultar comentarios o mensajes del foro (acción «Ocultar»), fijar o cerrar temas del foro, desactivar usuarios.
- **Fuentes de noticias**: las fuentes RSS del importador automático.

En todas las listas hay un filtro «datos de ejemplo» para ver solo lo inventado o solo lo real.

---

## Datos de ejemplo

```powershell
python manage.py cargar_datos_ejemplo          # los crea
python manage.py cargar_datos_ejemplo --reset  # los borra y los vuelve a crear (fechas actualizadas)
python manage.py borrar_datos_ejemplo          # los borra todos (pide confirmación)
```

Solo se borra lo marcado como ejemplo y los usuarios de ejemplo (`ejemplo_*`, `redaccion_ejemplo`). Lo que hayas creado tú no se toca. Cuando no queda ningún dato de ejemplo, el aviso amarillo de la parte superior desaparece solo.

Los **deportes** (dragon boat, traineras, piragüismo, remo olímpico, va'a) y las **categorías del foro** no son datos de ejemplo: son contenido fijo que se puede editar en el panel.

---

## Noticias automáticas

Hay dos caminos, que se pueden usar a la vez. Cada noticia indica su origen («De otra web», «Resumen con IA», «Comunidad»...).

### 1. Importador de titulares RSS

Lee los feeds de **Noticias › Fuentes de noticias** (en el panel) y guarda solo el **titular, un resumen corto y el enlace a la noticia original**, citando el medio. Al abrirla, la web manda a leer la noticia completa a su fuente. Vienen configuradas búsquedas de Google Noticias sobre dragon boat y traineras (y una de piragüismo desactivada); se pueden añadir los feeds de clubes, federaciones o medios.

```powershell
python manage.py importar_noticias
```

Descarta titulares que no contengan las palabras clave de la fuente, los de más de 30 días y los repetidos.

**Para que se ejecute solo** hay un flujo de GitHub Actions (`.github/workflows/importar-noticias.yml`) que **cada lunes por la mañana** pide a la web que importe. Se activa añadiendo dos secretos en GitHub (*Settings › Secrets and variables › Actions*): `SITE_URL` (la dirección de la web) y `NEWS_API_TOKEN` (el mismo valor que en el servidor). La frecuencia se cambia en la línea `cron` del fichero.

### 2. API para publicar resúmenes

Pensada para una **tarea programada de Claude** (o cualquier otro programa) que busca noticias, escribe un **resumen propio en castellano** y lo publica citando la fuente. Se activa definiendo `NEWS_API_TOKEN` en el servidor.

```http
POST /api/noticias/
Authorization: Bearer <NEWS_API_TOKEN>
Content-Type: application/json

{
  "title": "Titular de la noticia",
  "summary": "Una o dos frases de resumen.",
  "body": "Texto del resumen, con párrafos separados por una línea en blanco.",
  "sport": "dragon-boat",
  "category": "competicion",
  "source_name": "Nombre del medio",
  "source_url": "https://enlace-a-la-noticia-original"
}
```

- `sport`: `dragon-boat`, `traineras`, `piraguismo`, `remo-olimpico`, `vaa` (opcional).
- `category`: `competicion`, `clubes`, `internacional`, `tecnica`, `entrevista`, `comunidad`, `otros`.
- Si ya existe una noticia con el mismo `source_url`, no se duplica: responde `{"duplicate": true, ...}`.
- `POST /api/noticias/importar/` (con la misma cabecera) lanza el importador RSS.

---

## Publicarla en internet

El repositorio está listo para **[Render](https://render.com)** con el fichero `render.yaml`:

1. Crea una cuenta en Render entrando con tu GitHub.
2. **New › Blueprint** › elige el repositorio `dragon_boat`. Render lee `render.yaml`, crea la web y la base de datos PostgreSQL, y genera `SECRET_KEY` y `NEWS_API_TOKEN`.
3. Antes de confirmar, Render pide dos valores: `DJANGO_SUPERUSER_PASSWORD` (la contraseña que quieras para entrar en `/admin/` con el usuario `andoni`) y `DJANGO_SUPERUSER_EMAIL` (tu email). El administrador se crea solo en el primer despliegue; el plan gratuito no tiene consola, así que no hace falta usarla.
4. Para usar tu propio dominio, añádelo en Render (*Settings › Custom Domains*) y en las variables `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`.

**Ten en cuenta:**

- El plan gratuito de Render sirve para probar, pero tiene límites (la web «se duerme» tras un rato sin visitas y tarda en despertar, y la base de datos gratuita caduca al cabo de un tiempo). Revisa sus condiciones actuales; para uso real conviene un plan de pago básico.
- **Imágenes subidas** (fotos de noticias, eventos y foro): el disco de los servicios web se borra en cada despliegue. Para conservarlas, elige una de estas opciones:
  - Un **disco persistente** en Render (planes de pago): móntalo en `/var/data` y define `MEDIA_ROOT=/var/data/media` y `SERVE_MEDIA=true`.
  - Un almacenamiento compatible con S3 (Cloudflare R2, Backblaze B2, AWS S3): añade `django-storages[s3]` a `requirements.txt` y define las variables `AWS_*` de `.env.example`.
- Para que funcione **«¿Has olvidado la contraseña?»**, configura un servidor de correo (variables `EMAIL_*`). Sin él, los emails solo se escriben en el registro del servidor.

Otras opciones válidas: PythonAnywhere, Railway, Fly.io o un VPS. Lo necesario es: `pip install -r requirements.txt`, `python manage.py collectstatic`, `python manage.py migrate` y arrancar con `gunicorn config.wsgi:application`, con las variables de `.env.example`.

---

## Antes de abrirla al público

- [ ] Completar la página de **Privacidad** (`templates/core/privacy.html`) con el nombre del responsable y un contacto.
- [ ] Revisar las **Normas** de la comunidad (`templates/core/rules.html`).
- [ ] Borrar los datos de ejemplo: `python manage.py borrar_datos_ejemplo`.
- [ ] Crear el usuario administrador y, si quieres, otros miembros del equipo (en el panel, marcando «Es staff»).
- [ ] Configurar el correo para recuperar contraseñas.
- [ ] Decidir dónde se guardan las imágenes subidas (ver arriba).
- [ ] Decidir si lo que publica la comunidad sale al momento o con revisión (`COMMUNITY_REQUIRES_APPROVAL`).

---

## Pruebas

```powershell
python manage.py test
```

Comprueban, entre otras cosas, que las páginas públicas se ven sin cuenta, que comentar, reaccionar y escribir en el foro piden iniciar sesión, el registro (y su trampa antispam), la publicación de noticias y eventos con sus permisos, el importador RSS, la API y los comandos de datos de ejemplo. Se ejecutan también en GitHub en cada pull request.

---

## Estructura del proyecto

```
config/        Configuración de Django (settings, urls)
core/          Portada, deportes, buscador, páginas fijas y comandos de datos de ejemplo
accounts/      Registro, inicio de sesión y perfiles
news/          Noticias, comentarios, importador RSS y API
events/        Eventos y regatas (con descarga para el calendario del móvil)
competitions/  Campeonatos, categorías, clasificaciones y equipos
forum/         Foro: categorías, temas y mensajes
reactions/     Reacciones a noticias, comentarios y mensajes del foro
templates/     Plantillas HTML
static/        CSS, JavaScript e imágenes de la web
```
