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

from .importer import import_source
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
        self.assertContains(response, reverse("signup"))

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
  <description>&lt;p&gt;Veinte tripulaciones de dragon boat compiten en el Guadalquivir.&lt;/p&gt;</description>
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
