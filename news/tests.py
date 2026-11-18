import json
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import LiveServerTestCase, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Sport
from events.models import Event
from scripts import publicar_noticias

import base64
import struct

from . import images
from .images import (
    _decode_old_google_id,
    clean_image_url,
    extract_image,
    fill_missing_images,
    find_image,
    image_size,
    is_suitable_image,
    looks_generic,
)
from .importer import entry_image, import_source
from .models import Article, Comment, NewsSource

User = get_user_model()
PASSWORD = "remo-y-pala-2026"


def make_article(**fields):
    values = {
        "title": "Regata de prueba en la ría",
        "summary": "Resumen de una regata inventada para las pruebas.",
        "body": "Primer párrafo.\n\nSegundo párrafo.",
        "status": Article.Status.PUBLISHED,
    }
    values.update(fields)
    return Article.objects.create(**values)


def article_form_data(**overrides):
    data = {
        "sport": Sport.objects.get(slug="dragon-boat").pk,
        "category": Article.Category.CLUBS,
        "title": "Nuestro club estrena barco grande",
        "summary": "El club de prueba ya tiene su barco de veinte plazas.",
        "body": "Después de meses de rifas y cenas solidarias, el barco ya está en el agua.",
        "image_caption": "",
        "source_name": "",
        "source_url": "",
    }
    data.update(overrides)
    return data


class CommentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.article = make_article()
        cls.ane = User.objects.create_user("ane", "ane@example.com", PASSWORD)
        cls.iker = User.objects.create_user("iker", "iker@example.com", PASSWORD)

    def comment_url(self):
        return reverse("comment_add", args=[self.article.slug])

    def test_anonymous_cannot_comment(self):
        response = self.client.post(self.comment_url(), {"body": "Hola"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertFalse(Comment.objects.exists())

    def test_anonymous_sees_invitation_to_sign_up(self):
        response = self.client.get(self.article.get_absolute_url())
        # Sin avisos: la caja de comentar y las reacciones abren la ventana para entrar o registrarse.
        self.assertContains(response, 'id="unete"')
        self.assertContains(response, reverse("signup"))
        self.assertContains(response, 'data-login="comentar"')
        self.assertContains(response, 'data-login="reaccionar"')
        self.assertNotContains(response, "Inicia sesión para reaccionar")

    def test_logged_in_user_gets_no_sign_up_window(self):
        self.client.force_login(self.ane)
        response = self.client.get(self.article.get_absolute_url())
        self.assertNotContains(response, 'id="unete"')
        self.assertNotContains(response, "data-login=")

    def test_comment_and_replies(self):
        self.client.force_login(self.ane)
        self.client.post(self.comment_url(), {"body": "¡Qué regata!"})
        root = Comment.objects.get()
        self.assertEqual(root.author, self.ane)

        self.client.force_login(self.iker)
        self.client.post(self.comment_url(), {"body": "Totalmente de acuerdo", "parent_id": root.pk})
        reply = Comment.objects.get(author=self.iker)
        self.assertEqual(reply.parent, root)

        # Una respuesta a una respuesta cuelga del comentario principal (un solo nivel).
        self.client.force_login(self.ane)
        self.client.post(self.comment_url(), {"body": "¡Gracias!", "parent_id": reply.pk})
        self.assertEqual(Comment.objects.filter(parent=root).count(), 2)

        page = self.client.get(self.article.get_absolute_url())
        self.assertContains(page, "¡Qué regata!")
        self.assertContains(page, "Totalmente de acuerdo")
        self.assertContains(page, "¡Gracias!")

    def test_empty_comment_is_rejected(self):
        self.client.force_login(self.ane)
        self.client.post(self.comment_url(), {"body": "  "})
        self.assertFalse(Comment.objects.exists())

    def test_closed_comments(self):
        Article.objects.filter(pk=self.article.pk).update(allow_comments=False)
        self.client.force_login(self.ane)
        self.client.post(self.comment_url(), {"body": "No debería entrar"})
        self.assertFalse(Comment.objects.exists())

    def test_only_author_edits_or_deletes(self):
        comment = Comment.objects.create(article=self.article, author=self.ane, body="Texto original")
        self.client.force_login(self.iker)
        self.assertEqual(
            self.client.post(reverse("comment_edit", args=[comment.pk]), {"body": "Hackeado"}).status_code, 403
        )
        self.assertEqual(self.client.post(reverse("comment_delete", args=[comment.pk])).status_code, 403)

        self.client.force_login(self.ane)
        self.client.post(reverse("comment_edit", args=[comment.pk]), {"body": "Texto corregido"})
        comment.refresh_from_db()
        self.assertEqual(comment.body, "Texto corregido")

    def test_deleting_comment_with_replies_keeps_thread(self):
        root = Comment.objects.create(article=self.article, author=self.ane, body="Pregunta")
        Comment.objects.create(article=self.article, author=self.iker, body="Respuesta", parent=root)
        self.client.force_login(self.ane)
        self.client.post(reverse("comment_delete", args=[root.pk]))
        root.refresh_from_db()
        self.assertTrue(root.is_deleted)
        self.assertEqual(root.body, "")
        self.assertEqual(Comment.objects.count(), 2)

    def test_hidden_comment_text_is_not_shown(self):
        Comment.objects.create(article=self.article, author=self.ane, body="Texto moderado", is_hidden=True)
        self.assertNotContains(self.client.get(self.article.get_absolute_url()), "Texto moderado")


class CommunityPublishingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("pablo", "pablo@example.com", PASSWORD)
        cls.other = User.objects.create_user("marta", "marta@example.com", PASSWORD)

    def test_publishing_requires_login(self):
        response = self.client.get(reverse("article_create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_any_user_can_publish(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("article_create"), article_form_data())
        article = Article.objects.get()
        self.assertRedirects(response, article.get_absolute_url())
        self.assertEqual(article.status, Article.Status.PUBLISHED)
        self.assertEqual(article.origin, Article.Origin.COMMUNITY)
        self.assertEqual(article.author, self.user)
        self.client.logout()
        self.assertContains(self.client.get(reverse("article_list")), "Nuestro club estrena barco grande")

    @override_settings(COMMUNITY_REQUIRES_APPROVAL=True)
    def test_approval_mode_keeps_articles_pending(self):
        self.client.force_login(self.user)
        self.client.post(reverse("article_create"), article_form_data())
        article = Article.objects.get()
        self.assertEqual(article.status, Article.Status.PENDING)
        # Su autor la ve; el resto, no.
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 404)

    @override_settings(COMMUNITY_DAILY_LIMIT=2)
    def test_daily_limit(self):
        self.client.force_login(self.user)
        for number in range(3):
            self.client.post(reverse("article_create"), article_form_data(title=f"Noticia de prueba número {number}"))
        self.assertEqual(Article.objects.count(), 2)

    def test_only_author_can_edit_or_delete(self):
        article = make_article(author=self.user, origin=Article.Origin.COMMUNITY)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("article_edit", args=[article.slug])).status_code, 403)
        self.assertEqual(self.client.post(reverse("article_delete", args=[article.slug])).status_code, 403)

        self.client.force_login(self.user)
        self.client.post(
            reverse("article_edit", args=[article.slug]), article_form_data(title="Título corregido por su autor")
        )
        article.refresh_from_db()
        self.assertEqual(article.title, "Título corregido por su autor")
        self.client.post(reverse("article_delete", args=[article.slug]))
        self.assertFalse(Article.objects.filter(pk=article.pk).exists())

    def test_reserved_slugs_are_avoided(self):
        article = make_article(title="Publicar")
        self.assertNotEqual(article.slug, "publicar")
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 200)

    def test_future_and_draft_articles_are_hidden(self):
        future = make_article(title="Noticia programada", published_at=timezone.now() + timedelta(days=1))
        draft = make_article(title="Borrador interno", status=Article.Status.DRAFT)
        listing = self.client.get(reverse("article_list"))
        self.assertNotContains(listing, "Noticia programada")
        self.assertNotContains(listing, "Borrador interno")
        self.assertEqual(self.client.get(future.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Feed de prueba</title>
<item>
  <title>Gran regata de dragon boat en Sevilla - Diario de Prueba</title>
  <link>https://example.com/noticia-1</link>
  <source url="https://example.com">Diario de Prueba</source>
  <description>&lt;p&gt;Veinte tripulaciones de dragon boat compiten en el Guadalquivir.&lt;/p&gt;&lt;img src="/fotos/regata.jpg"&gt;</description>
  <pubDate>{recent}</pubDate>
</item>
<item>
  <title>Resultados de fútbol</title>
  <link>https://example.com/futbol</link>
  <description>Nada que ver con el remo.</description>
  <pubDate>{recent}</pubDate>
</item>
<item>
  <title>Dragon boat: noticia demasiado antigua</title>
  <link>https://example.com/antigua</link>
  <pubDate>Mon, 01 Jan 2018 10:00:00 GMT</pubDate>
</item>
</channel></rss>"""


class ImporterTests(TestCase):
    def setUp(self):
        self.source = NewsSource.objects.create(
            name="Fuente de prueba",
            feed_url="https://example.com/rss",
            sport=Sport.objects.get(slug="dragon-boat"),
            keywords="dragon boat",
        )
        recent = (timezone.now() - timedelta(hours=3)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.xml = RSS.format(recent=recent).encode()

    def test_imports_matching_headlines_only(self):
        created, skipped = import_source(self.source, content=self.xml)
        self.assertEqual((created, skipped), (1, 2))
        article = Article.objects.get()
        self.assertEqual(article.title, "Gran regata de dragon boat en Sevilla")
        self.assertEqual(article.source_name, "Diario de Prueba")
        self.assertEqual(article.source_url, "https://example.com/noticia-1")
        self.assertEqual(article.origin, Article.Origin.IMPORTED)
        self.assertNotIn("<p>", article.summary)
        self.assertTrue(article.is_published)
        # La imagen que trae el feed se guarda como enlace absoluto.
        self.assertEqual(article.image_url, "https://example.com/fotos/regata.jpg")

    def test_does_not_import_twice(self):
        import_source(self.source, content=self.xml)
        created, _skipped = import_source(self.source, content=self.xml)
        self.assertEqual(created, 0)
        self.assertEqual(Article.objects.count(), 1)

    def test_imported_article_links_to_source(self):
        import_source(self.source, content=self.xml)
        response = self.client.get(Article.objects.get().get_absolute_url())
        self.assertContains(response, "https://example.com/noticia-1")

    def test_command_records_errors(self):
        NewsSource.objects.exclude(pk=self.source.pk).update(is_active=False)
        with mock.patch("news.importer.fetch", side_effect=OSError("sin conexión")), self.assertLogs("news.importer"):
            call_command("importar_noticias", stdout=StringIO())
        self.source.refresh_from_db()
        self.assertIn("sin conexión", self.source.last_error)
        self.assertIsNotNone(self.source.last_checked_at)


@override_settings(NEWS_API_TOKEN="token-de-prueba")
class ApiTests(TestCase):
    url = "/api/noticias/"

    def post(self, payload, token="token-de-prueba"):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return self.client.post(self.url, json.dumps(payload), content_type="application/json", **headers)

    def payload(self, **overrides):
        data = {
            "title": "Resumen: Mundial de clubes de dragon boat",
            "summary": "Resumen propio de una noticia publicada en otro medio.",
            "body": "Texto del resumen.",
            "sport": "dragon-boat",
            "category": "internacional",
            "source_name": "Medio de prueba",
            "source_url": "https://example.com/mundial",
        }
        data.update(overrides)
        return data

    def test_requires_valid_token(self):
        self.assertEqual(self.post(self.payload(), token=None).status_code, 401)
        self.assertEqual(self.post(self.payload(), token="otro").status_code, 401)
        self.assertFalse(Article.objects.exists())

    @override_settings(NEWS_API_TOKEN="")
    def test_disabled_without_token_setting(self):
        self.assertEqual(self.post(self.payload()).status_code, 404)

    def test_creates_article_and_detects_duplicates(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201)
        article = Article.objects.get()
        self.assertEqual(article.origin, Article.Origin.AI)
        self.assertEqual(article.sport.slug, "dragon-boat")
        self.assertTrue(article.is_published)

        again = self.post(self.payload())
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()["duplicate"])
        self.assertEqual(Article.objects.count(), 1)

    def test_validation_errors(self):
        self.assertEqual(self.post(self.payload(title="")).status_code, 400)
        self.assertEqual(self.post(self.payload(sport="curling")).status_code, 400)
        self.assertEqual(self.post(self.payload(source_url="no-es-una-url")).status_code, 400)
        self.assertEqual(self.post(self.payload(category="inventada")).status_code, 400)
        self.assertFalse(Article.objects.exists())

    def test_run_import_endpoint(self):
        NewsSource.objects.update(is_active=False)
        response = self.client.post("/api/noticias/importar/", HTTP_AUTHORIZATION="Bearer token-de-prueba")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 0)


class EventLinkTests(TestCase):
    def test_article_shows_related_event(self):
        event = Event.objects.create(
            title="Regata relacionada",
            sport=Sport.objects.get(slug="dragon-boat"),
            start_date=timezone.localdate() + timedelta(days=5),
        )
        article = make_article(related_event=event)
        self.assertContains(self.client.get(article.get_absolute_url()), "Regata relacionada")


def weekly_item(number, **overrides):
    item = {
        "title": f"Noticia semanal {number}",
        "summary": "Resumen corto de la noticia.",
        "body": "Primer párrafo.\n\nSegundo párrafo.",
        "sport": "dragon-boat",
        "category": "competicion",
        "source_name": "Medio de prueba",
        "source_url": f"https://medio.example.com/noticia-{number}",
    }
    item.update(overrides)
    return item


class WeeklyFileValidationTests(SimpleTestCase):
    def test_valid_file(self):
        self.assertEqual(publicar_noticias.validate([weekly_item(1), weekly_item(2)]), [])

    def test_detects_problems(self):
        errors = publicar_noticias.validate(
            [
                weekly_item(1, body=""),
                weekly_item(2, source_url="medio.example.com/sin-esquema"),
                weekly_item(3, source_url="https://medio.example.com/noticia-1"),
                weekly_item(4, sport="curling", category="cotilleo"),
                weekly_item(5, summary="x" * 321),
            ]
        )
        self.assertEqual(len(errors), 6, errors)
        self.assertIn("noticia 1: falta «body»", errors)
        self.assertIn("noticia 3: «source_url» repetido en el fichero", errors)
        self.assertIn("noticia 5: «summary» supera los 320 caracteres", errors)

    def test_empty_file(self):
        self.assertTrue(publicar_noticias.validate([]))
        self.assertTrue(publicar_noticias.validate({"title": "no es una lista"}))


@override_settings(NEWS_API_TOKEN="token-de-prueba")
class WeeklyPublishingTests(LiveServerTestCase):
    """Publica un fichero semanal en una web de prueba de verdad, como hace GitHub Actions."""

    serialized_rollback = True  # Conserva los deportes que crean las migraciones.

    def publish(self, items):
        path = Path(self.tmp.name) / "semana.json"
        path.write_text(json.dumps(items), encoding="utf-8")
        env = {"SITE_URL": self.live_server_url, "NEWS_API_TOKEN": "token-de-prueba", "NO_PROXY": "*", "no_proxy": "*"}
        with mock.patch.dict("os.environ", env), mock.patch("sys.stdout", new_callable=StringIO) as output:
            code = publicar_noticias.main(str(path))
        return code, output.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_publishes_once(self):
        items = [weekly_item(1), weekly_item(2, sport="traineras", category="clubes")]
        code, output = self.publish(items)
        self.assertEqual(code, 0, output)
        self.assertIn("2 publicadas, 0 repetidas, 0 con error", output)
        article = Article.objects.get(source_url="https://medio.example.com/noticia-2")
        self.assertEqual(article.origin, Article.Origin.AI)
        self.assertEqual(article.sport.slug, "traineras")
        self.assertEqual(article.source_name, "Medio de prueba")
        self.assertEqual(article.status, Article.Status.PUBLISHED)

        # Si la tarea vuelve a subir lo mismo, no se duplica nada.
        code, output = self.publish(items)
        self.assertEqual(code, 0, output)
        self.assertIn("0 publicadas, 2 repetidas, 0 con error", output)
        self.assertEqual(Article.objects.filter(source_url__startswith="https://medio.example.com/").count(), 2)

    def test_invalid_file_publishes_nothing(self):
        code, output = self.publish([weekly_item(1, title="")])
        self.assertEqual(code, 1)
        self.assertIn("falta «title»", output)
        self.assertFalse(Article.objects.filter(source_url__startswith="https://medio.example.com/").exists())


class SourceImageTests(TestCase):
    def test_extract_image_prefers_open_graph(self):
        html = (
            '<html><head><meta name="twitter:image" content="https://cdn.example.com/tw.jpg">'
            '<meta property="og:image" content="/img/portada.jpg"></head><body>'
            '<meta property="og:image" content="https://no-cuenta.example.com/x.jpg"></body></html>'
        )
        self.assertEqual(
            extract_image(html, "https://medio.example.com/noticia"), "https://medio.example.com/img/portada.jpg"
        )

    def test_extract_image_fallbacks_and_rejections(self):
        self.assertEqual(
            extract_image('<meta name="twitter:image" content="//cdn.example.com/a.png">', "https://m.example.com/"),
            "https://cdn.example.com/a.png",
        )
        self.assertEqual(
            extract_image('<link rel="image_src" href="b.jpg">', "https://m.example.com/n/"),
            "https://m.example.com/n/b.jpg",
        )
        self.assertEqual(
            extract_image('<meta property="og:image" content="javascript:alert(1)">', "https://m.example.com/"), ""
        )
        self.assertEqual(extract_image("<p>sin imagen</p>", "https://m.example.com/"), "")

    def test_find_image_skips_private_hosts(self):
        with mock.patch("news.images.urllib.request.urlopen") as urlopen:
            self.assertEqual(find_image("http://127.0.0.1:8000/admin/"), "")
            self.assertEqual(find_image("ftp://example.com/a"), "")
            urlopen.assert_not_called()

    def test_entry_image_from_media_content(self):
        entry = {
            "link": "https://m.example.com/n",
            "media_content": [{"url": "https://m.example.com/foto.jpg", "medium": "image"}],
        }
        self.assertEqual(entry_image(entry), "https://m.example.com/foto.jpg")
        self.assertEqual(entry_image({"link": "https://m.example.com/n"}), "")

    @override_settings(NEWS_FETCH_IMAGES=True)
    def test_fill_missing_images_only_for_news_from_other_sites(self):
        imported = Article.objects.create(
            title="Importada",
            summary="Resumen.",
            origin=Article.Origin.IMPORTED,
            status=Article.Status.PUBLISHED,
            source_url="https://medio.example.com/1",
        )
        google = Article.objects.create(
            title="De Google",
            summary="Resumen.",
            origin=Article.Origin.IMPORTED,
            status=Article.Status.PUBLISHED,
            source_url="https://news.google.com/rss/articles/x",
        )
        community = Article.objects.create(
            title="De la comunidad",
            summary="Resumen.",
            origin=Article.Origin.COMMUNITY,
            status=Article.Status.PUBLISHED,
            source_url="https://medio.example.com/2",
        )
        photos = {"https://medio.example.com/1": "https://medio.example.com/foto.jpg"}
        with mock.patch("news.images.find_image", side_effect=lambda url: photos.get(url, "")) as finder:
            result = fill_missing_images()
        self.assertEqual(finder.call_count, 2)  # Las de Google Noticias también se buscan.
        self.assertEqual(result, {"checked": 2, "updated": 1, "removed": 0, "remaining": 0})
        imported.refresh_from_db()
        google.refresh_from_db()
        community.refresh_from_db()
        self.assertEqual(imported.image_url, "https://medio.example.com/foto.jpg")
        self.assertEqual((google.image_url, community.image_url), ("", ""))
        self.assertIsNotNone(google.image_checked_at)  # No se vuelve a buscar cada vez.
        with mock.patch("news.images.find_image") as finder:
            self.assertEqual(fill_missing_images()["checked"], 0)
        finder.assert_not_called()

    @override_settings(NEWS_FETCH_IMAGES=True)
    def test_fill_missing_images_removes_generic_pictures(self):
        logo = Article.objects.create(
            title="Con logotipo",
            summary="Resumen.",
            origin=Article.Origin.AI,
            status=Article.Status.PUBLISHED,
            source_url="https://medio.example.com/3",
            image_url="https://medio.example.com/static/logo-medio.png",
        )
        result = fill_missing_images()
        self.assertEqual(result["removed"], 1)
        logo.refresh_from_db()
        self.assertEqual(logo.image_url, "")


def _png(width, height):
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"


def _jpeg(width, height):
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xc0\x00\x11\x08"
        + struct.pack(">HH", height, width)
        + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    )


class PhotoQualityTests(TestCase):
    def test_image_size(self):
        self.assertEqual(image_size(_png(1200, 630)), (1200, 630))
        self.assertEqual(image_size(_jpeg(1024, 576)), (1024, 576))
        self.assertEqual(image_size(b"GIF89a" + struct.pack("<HH", 64, 32)), (64, 32))
        self.assertIsNone(image_size(b"no es una imagen"))

    def test_generic_addresses(self):
        self.assertTrue(looks_generic("https://m.example.com/img/logo.png"))
        self.assertTrue(looks_generic("https://m.example.com/assets/og-default.jpg"))
        self.assertTrue(looks_generic("https://m.example.com/favicon-192.png"))
        self.assertFalse(looks_generic("https://m.example.com/fotos/2026/regata-bilbao.jpg"))
        self.assertFalse(looks_generic("https://m.example.com/fotos/dragon-boat-logrono.jpg"))

    def test_clean_image_url_encodes_spaces(self):
        self.assertEqual(
            clean_image_url("https://img.example.com/is/image/foto regata.jpg"),
            "https://img.example.com/is/image/foto%20regata.jpg",
        )
        self.assertEqual(clean_image_url("https://img.example.com/a%20b.jpg"), "https://img.example.com/a%20b.jpg")

    def test_suitable_image_checks_size_and_home_page(self):
        def opener(url, **kwargs):
            sizes = {
                "https://m.example.com/grande.jpg": ("image/jpeg", _jpeg(1200, 675)),
                "https://m.example.com/pequena.png": ("image/png", _png(120, 120)),
                "https://m.example.com/tira.png": ("image/png", _png(1600, 200)),
                "https://m.example.com/portada.jpg": ("image/jpeg", _jpeg(1200, 630)),
            }
            content_type, data = sizes[url]
            return content_type, "utf-8", data, url

        images._home_images.clear()
        home = ('<meta property="og:image" content="https://m.example.com/portada.jpg">', "https://m.example.com/")
        with mock.patch("news.images._open", side_effect=opener), mock.patch("news.images._read_page", return_value=home):
            self.assertTrue(is_suitable_image("https://m.example.com/grande.jpg", "https://m.example.com/n/1"))
            self.assertFalse(is_suitable_image("https://m.example.com/pequena.png", "https://m.example.com/n/1"))
            self.assertFalse(is_suitable_image("https://m.example.com/tira.png", "https://m.example.com/n/1"))
            self.assertFalse(is_suitable_image("https://m.example.com/portada.jpg", "https://m.example.com/n/1"))
        images._home_images.clear()

    def test_unreachable_image_is_accepted(self):
        with mock.patch("news.images._open", return_value=None), mock.patch("news.images._read_page", return_value=None):
            images._home_images.clear()
            self.assertTrue(is_suitable_image("https://m.example.com/foto.jpg", "https://m.example.com/n/1"))
        images._home_images.clear()

    def test_old_google_news_links_are_decoded_offline(self):
        payload = b"\x08\x13\x22\x2ahttps://medio.example.com/noticia-de-regata\xd2\x01\x00"
        article_id = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        self.assertEqual(_decode_old_google_id(article_id), "https://medio.example.com/noticia-de-regata")
        self.assertEqual(_decode_old_google_id("AU_yqLxxxx"), "")

    def test_find_image_follows_google_news_to_the_outlet(self):
        page = ('<meta property="og:image" content="https://medio.example.com/foto.jpg">', "https://medio.example.com/n")
        with (
            mock.patch("news.images.resolve_google_news", return_value="https://medio.example.com/n") as resolver,
            mock.patch("news.images._read_page", return_value=page) as reader,
            mock.patch("news.images.is_suitable_image", return_value=True),
            mock.patch("news.images.GOOGLE_PAUSE_SECONDS", 0),
        ):
            self.assertEqual(find_image("https://news.google.com/rss/articles/CBMiabc?oc=5"), "https://medio.example.com/foto.jpg")
        resolver.assert_called_once()
        reader.assert_called_once_with("https://medio.example.com/n")

    @override_settings(NEWS_FETCH_IMAGES=True)
    def test_google_news_without_answer_is_retried_later(self):
        article = Article.objects.create(
            title="De Google", summary="R.", origin=Article.Origin.IMPORTED, status=Article.Status.PUBLISHED,
            source_url="https://news.google.com/rss/articles/CBMiabc",
        )
        with mock.patch("news.images.resolve_google_news", return_value=""), mock.patch("news.images.GOOGLE_PAUSE_SECONDS", 0):
            result = fill_missing_images()
        self.assertEqual((result["checked"], result["remaining"]), (1, 1))
        article.refresh_from_db()
        self.assertIsNone(article.image_checked_at)


@override_settings(NEWS_API_TOKEN="token-de-prueba")
class ApiImageTests(TestCase):
    def post(self, **extra):
        payload = {
            "title": "Resumen con imagen",
            "summary": "Resumen propio.",
            "body": "Texto.",
            "source_name": "Medio",
            "source_url": "https://medio.example.com/noticia",
        }
        payload.update(extra)
        return self.client.post(
            "/api/noticias/",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer token-de-prueba",
        )

    def test_accepts_image_url(self):
        response = self.post(image_url="https://medio.example.com/foto.jpg")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Article.objects.get().image_url, "https://medio.example.com/foto.jpg")
        self.assertEqual(self.post(source_url="https://medio.example.com/otra", image_url="data:x").status_code, 400)

    @override_settings(NEWS_FETCH_IMAGES=True)
    def test_looks_up_image_of_the_source(self):
        with mock.patch("news.api.find_image", return_value="https://medio.example.com/og.jpg") as finder:
            self.assertEqual(self.post().status_code, 201)
        finder.assert_called_once_with("https://medio.example.com/noticia")
        article = Article.objects.get()
        self.assertEqual(article.image_url, "https://medio.example.com/og.jpg")

        page = self.client.get(article.get_absolute_url())
        self.assertContains(page, 'src="https://medio.example.com/og.jpg"')
        self.assertContains(page, 'referrerpolicy="no-referrer"')
        self.assertContains(page, "Imagen: Medio")
        self.assertContains(page, 'target="_blank">Medio</a>')  # La fuente se cita con su nombre.
        self.assertContains(page, '<meta property="og:image" content="https://medio.example.com/og.jpg">')

    def test_fill_images_endpoint_requires_token(self):
        self.assertEqual(self.client.post("/api/noticias/imagenes/").status_code, 401)
        response = self.client.post("/api/noticias/imagenes/?dias=200", HTTP_AUTHORIZATION="Bearer token-de-prueba")
        self.assertEqual(response.json(), {"checked": 0, "updated": 0, "removed": 0, "remaining": 0})


class NoPhotoLayoutTests(TestCase):
    def test_article_without_photo_uses_text_layout(self):
        sport = Sport.objects.get(slug="traineras")
        article = Article.objects.create(
            title="Sin foto", summary="Resumen.", sport=sport, status=Article.Status.PUBLISHED
        )
        list_page = self.client.get(reverse("article_list"))
        self.assertContains(list_page, "news-card sin-foto")
        self.assertNotContains(list_page, "media-art")  # Ni ilustraciones de relleno.
        detail = self.client.get(article.get_absolute_url())
        self.assertContains(detail, "news-article sin-foto")
        self.assertNotContains(detail, "article-figure")

    def test_article_with_photo_shows_it(self):
        article = Article.objects.create(
            title="Con foto",
            summary="Resumen.",
            status=Article.Status.PUBLISHED,
            source_name="Medio",
            image_url="https://medio.example.com/foto.jpg",
        )
        list_page = self.client.get(reverse("article_list"))
        self.assertNotContains(list_page, "news-card sin-foto")
        self.assertContains(list_page, 'src="https://medio.example.com/foto.jpg"')
        self.assertContains(list_page, "📷 Medio")
        self.assertContains(self.client.get(article.get_absolute_url()), "article-figure")

    def test_home_leads_with_a_photo(self):
        Article.objects.create(title="Con foto", summary="R.", status=Article.Status.PUBLISHED,
                               image_url="https://medio.example.com/foto.jpg",
                               published_at=timezone.now() - timedelta(days=1))
        Article.objects.create(title="Sin foto reciente", summary="R.", status=Article.Status.PUBLISHED)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["lead"].title, "Con foto")
        self.assertEqual([a.title for a in response.context["latest"]], ["Sin foto reciente"])


@override_settings(NEWS_API_TOKEN="token-de-prueba")
class PhotoApiTests(TestCase):
    def test_pending_and_save_photos(self):
        google = Article.objects.create(
            title="De Google", summary="R.", origin=Article.Origin.IMPORTED, status=Article.Status.PUBLISHED,
            source_url="https://news.google.com/rss/articles/CBMiabc",
        )
        community = Article.objects.create(
            title="De la comunidad", summary="R.", origin=Article.Origin.COMMUNITY, status=Article.Status.PUBLISHED,
            source_url="https://medio.example.com/c",
        )
        auth = {"HTTP_AUTHORIZATION": "Bearer token-de-prueba"}
        self.assertEqual(self.client.get("/api/noticias/fotos/pendientes/").status_code, 401)
        pending = self.client.get("/api/noticias/fotos/pendientes/?dias=365", **auth).json()["articles"]
        self.assertEqual([a["id"] for a in pending], [google.pk])

        items = [
            {"id": google.pk, "image_url": "https://medio.example.com/foto regata.jpg"},
            {"id": community.pk, "image_url": "https://medio.example.com/otra.jpg"},  # No es de otra web: no se toca.
            {"id": google.pk, "image_url": "javascript:alert(1)"},
        ]
        response = self.client.post("/api/noticias/fotos/", json.dumps(items), content_type="application/json", **auth)
        self.assertEqual(response.json(), {"saved": 1, "errors": 1})
        google.refresh_from_db()
        community.refresh_from_db()
        self.assertEqual(google.image_url, "https://medio.example.com/foto%20regata.jpg")
        self.assertIsNotNone(google.image_checked_at)
        self.assertEqual(community.image_url, "")
        self.assertEqual(self.client.get("/api/noticias/fotos/pendientes/", **auth).json()["articles"], [])
