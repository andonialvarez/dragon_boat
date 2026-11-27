"""Pruebas del buzón de noticias (enlaces y documentos que mandan los usuarios)."""

import io
import zipfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import Sport

from . import buzon
from .models import Article, NewsTip

User = get_user_model()

PAGE = """<html><head>
<title>Ignorado | Diario del Remo</title>
<meta property="og:title" content="El club Hondarribia estrena barco de dragon boat - Diario del Remo">
<meta property="og:description" content="El club guipuzcoano ya tiene su propio barco de veinte plazas para la temporada.">
<meta property="og:site_name" content="Diario del Remo">
<meta property="article:published_time" content="2026-11-20T10:00:00+01:00">
<link rel="canonical" href="https://www.diariodelremo.example/noticias/hondarribia-barco">
</head><body>Texto</body></html>"""


def docx_bytes(paragraphs):
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def pdf_bytes(lines):
    """PDF mínimo con una línea de texto por renglón."""
    text_ops = " ".join(f"({line}) Tj 0 -20 Td" for line in lines)
    stream = f"BT /F1 12 Tf 50 750 Td {text_ops} ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return out.getvalue()


class NormalizeUrlTests(SimpleTestCase):
    def test_same_story_same_key(self):
        key = buzon.normalize_url("https://www.medio.example/deportes/regata/")
        for variant in (
            "http://medio.example/deportes/regata",
            "https://medio.example/deportes/regata?utm_source=twitter&utm_medium=social",
            "https://m.medio.example/deportes/regata#comentarios",
            "https://medio.example/deportes/regata/amp",
            "https://medio.example/deportes/regata/?fbclid=abc",
        ):
            self.assertEqual(buzon.normalize_url(variant), key, variant)

    def test_meaningful_query_is_kept(self):
        self.assertNotEqual(
            buzon.normalize_url("https://medio.example/noticia.php?id=1"),
            buzon.normalize_url("https://medio.example/noticia.php?id=2"),
        )

    def test_empty(self):
        self.assertEqual(buzon.normalize_url(""), "")


class TitleSimilarityTests(SimpleTestCase):
    def test_same_title_with_small_changes(self):
        score = buzon.title_similarity(
            "El Club Hondarribia estrena barco de dragon boat",
            "El club Hondarribia estrena su barco de dragon boat.",
        )
        self.assertGreaterEqual(score, buzon.STRONG_MATCH)

    def test_different_years_are_not_the_same(self):
        score = buzon.title_similarity(
            "Campeonato de España de dragon boat 2025 en Sevilla", "Campeonato de España de dragon boat 2026 en Sevilla"
        )
        self.assertLess(score, buzon.STRONG_MATCH)

    def test_different_stories(self):
        score = buzon.title_similarity("Orio gana la bandera de La Concha", "Nuevo barco de dragon boat en Valencia")
        self.assertLess(score, buzon.WEAK_MATCH)


class DocumentReadingTests(TestCase):
    def test_docx(self):
        upload = SimpleUploadedFile(
            "nota.docx",
            docx_bytes(
                [
                    "El Dragon Team Bilbao, campeón de Euskadi",
                    "El equipo vizcaíno se impuso en los 200 metros del campeonato celebrado en la ría.",
                    "Segundo párrafo con más detalles de la regata.",
                ]
            ),
        )
        info = buzon.read_document(upload)
        self.assertEqual(info.title, "El Dragon Team Bilbao, campeón de Euskadi")
        self.assertTrue(info.summary.startswith("El equipo vizcaíno"))
        self.assertIn("Segundo párrafo", info.body)

    def test_pdf(self):
        upload = SimpleUploadedFile(
            "nota.pdf",
            pdf_bytes(["Regata de traineras en Getaria", "La regata se celebra el domingo por la manana en la bahia."]),
        )
        info = buzon.read_document(upload)
        self.assertEqual(info.title, "Regata de traineras en Getaria")
        self.assertIn("domingo", info.body)

    def test_text_file(self):
        upload = SimpleUploadedFile("nota.txt", "Título de la nota\n\nUn texto suficientemente largo para la prueba.".encode())
        self.assertEqual(buzon.read_document(upload).title, "Título de la nota")

    def test_rejects_unknown_type_and_empty(self):
        with self.assertRaises(buzon.DocumentError):
            buzon.read_document(SimpleUploadedFile("foto.jpg", b"\xff\xd8\xff"))
        with self.assertRaises(buzon.DocumentError):
            buzon.read_document(SimpleUploadedFile("vacio.txt", b"  "))
        with self.assertRaises(buzon.DocumentError):
            buzon.read_document(SimpleUploadedFile("roto.docx", b"no es un zip"))

    def test_guess_sport(self):
        self.assertEqual(buzon.guess_sport("Regata de traineras en Getaria").slug, "traineras")
        self.assertEqual(buzon.guess_sport("Copa de España de dragon boat y kayak").slug, "dragon-boat")
        self.assertIsNone(buzon.guess_sport("Algo sin pistas"))


@mock.patch("news.buzon.fetch_page", return_value=(PAGE, "https://www.diariodelremo.example/noticias/hondarribia-barco"))
class TipBoxViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("miren", "miren@example.com", "remo-y-pala-2026")
        cls.dragon = Sport.objects.get(slug="dragon-boat")

    def setUp(self):
        self.client.force_login(self.user)

    def test_needs_login(self, _fetch):
        self.client.logout()
        response = self.client.get(reverse("tip_box"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_page_loads(self, _fetch):
        response = self.client.get(reverse("tip_box"))
        self.assertContains(response, "Buzón de noticias")
        self.assertContains(self.client.get(reverse("article_list")), reverse("tip_box"))

    def test_new_link_is_prepared_and_published(self, _fetch):
        response = self.client.post(reverse("tip_box"), {"url": "https://diariodelremo.example/noticias/hondarribia-barco?utm_source=x"})
        tip = NewsTip.objects.get()
        self.assertRedirects(response, tip.get_absolute_url())
        self.assertEqual(tip.status, NewsTip.Status.DRAFT)
        self.assertEqual(tip.title, "El club Hondarribia estrena barco de dragon boat")
        self.assertEqual(tip.source_name, "Diario del Remo")
        self.assertEqual(tip.sport, self.dragon)
        self.assertEqual(tip.url, "https://www.diariodelremo.example/noticias/hondarribia-barco")

        page = self.client.get(tip.get_absolute_url())
        self.assertContains(page, "No la tenemos todavía")
        response = self.client.post(
            tip.get_absolute_url(),
            {
                "sport": self.dragon.pk,
                "category": Article.Category.CLUBS,
                "title": tip.title,
                "summary": tip.summary,
                "source_name": tip.source_name,
            },
        )
        article = Article.objects.get()
        self.assertRedirects(response, article.get_absolute_url())
        self.assertEqual(article.origin, Article.Origin.IMPORTED)
        self.assertEqual(article.author, self.user)
        self.assertEqual(article.status, Article.Status.PUBLISHED)
        self.assertEqual(article.source_key, "diariodelremo.example/noticias/hondarribia-barco")
        self.assertEqual(article.published_at.year, 2026)
        tip.refresh_from_db()
        self.assertEqual(tip.status, NewsTip.Status.PUBLISHED)
        self.assertEqual(tip.article, article)

    def test_same_link_is_detected(self, _fetch):
        existing = Article.objects.create(
            title="Hondarribia ya tiene barco",
            summary="Resumen",
            status=Article.Status.PUBLISHED,
            origin=Article.Origin.IMPORTED,
            source_url="http://diariodelremo.example/noticias/hondarribia-barco/",
        )
        self.client.post(reverse("tip_box"), {"url": "https://diariodelremo.example/noticias/hondarribia-barco"})
        tip = NewsTip.objects.get()
        self.assertEqual(tip.status, NewsTip.Status.DUPLICATE)
        self.assertEqual(tip.match_kind, NewsTip.MatchKind.LINK)
        self.assertEqual(tip.article, existing)
        page = self.client.get(tip.get_absolute_url())
        self.assertContains(page, "Esta noticia ya está en la web")
        self.assertNotContains(page, 'type="submit">Publicar')
        # Aunque se intente publicar a mano, no se crea otra.
        self.client.post(tip.get_absolute_url(), {"sport": self.dragon.pk, "category": "clubes", "title": "x" * 10})
        self.assertEqual(Article.objects.count(), 1)

    def test_same_title_from_another_site_is_detected(self, _fetch):
        Article.objects.create(
            title="El Club Hondarribia estrena barco de dragon boat",
            summary="Resumen",
            status=Article.Status.PUBLISHED,
            source_url="https://news.google.com/rss/articles/abc",
        )
        self.client.post(reverse("tip_box"), {"url": "https://diariodelremo.example/noticias/hondarribia-barco"})
        tip = NewsTip.objects.get()
        self.assertEqual(tip.status, NewsTip.Status.DUPLICATE)
        self.assertEqual(tip.match_kind, NewsTip.MatchKind.TITLE)
        page = self.client.get(tip.get_absolute_url())
        self.assertContains(page, "Parece que esta noticia ya está en la web")
        self.assertContains(page, "No es la misma: quiero publicarla")

        data = {
            "sport": self.dragon.pk,
            "category": "clubes",
            "title": tip.title,
            "summary": tip.summary,
            "source_name": "Diario del Remo",
        }
        self.client.post(tip.get_absolute_url(), data)
        self.assertEqual(Article.objects.count(), 1)  # Sin confirmar, no se publica.
        self.client.post(tip.get_absolute_url(), {**data, "confirmar": "1"})
        self.assertEqual(Article.objects.count(), 2)

    def test_unreachable_page_lets_the_user_write_the_title(self, fetch):
        fetch.return_value = None
        self.client.post(reverse("tip_box"), {"url": "https://bloqueado.example/noticia"})
        tip = NewsTip.objects.get()
        self.assertEqual(tip.title, "")
        self.assertEqual(tip.source_name, "bloqueado.example")
        page = self.client.get(tip.get_absolute_url())
        self.assertContains(page, "Escribe el titular")

    def test_document_becomes_community_article(self, _fetch):
        upload = SimpleUploadedFile(
            "nota-de-prensa.docx",
            docx_bytes(
                [
                    "Regata de traineras en Getaria este domingo",
                    "Las tripulaciones de la liga se citan en la bahía de Getaria el domingo a las once.",
                    "La organización espera mucho público en el puerto.",
                ]
            ),
        )
        self.client.post(reverse("tip_box"), {"document": upload, "comment": "Nota de nuestro club"})
        tip = NewsTip.objects.get()
        self.assertEqual(tip.kind, NewsTip.Kind.DOCUMENT)
        self.assertEqual(tip.sport.slug, "traineras")
        self.client.post(
            tip.get_absolute_url(),
            {
                "sport": tip.sport.pk,
                "category": "competicion",
                "title": tip.title,
                "summary": tip.summary,
                "body": tip.body,
                "source_name": "",
            },
        )
        article = Article.objects.get()
        self.assertEqual(article.origin, Article.Origin.COMMUNITY)
        self.assertIn("puerto", article.body)
        tip.refresh_from_db()
        self.assertEqual(tip.body, "")  # El texto no se queda duplicado en el buzón.

    @override_settings(COMMUNITY_REQUIRES_APPROVAL=True)
    def test_respects_moderation(self, _fetch):
        self.client.post(reverse("tip_box"), {"url": "https://diariodelremo.example/noticias/hondarribia-barco"})
        tip = NewsTip.objects.get()
        self.client.post(
            tip.get_absolute_url(),
            {"sport": self.dragon.pk, "category": "clubes", "title": tip.title, "summary": tip.summary, "source_name": "Diario"},
        )
        self.assertEqual(Article.objects.get().status, Article.Status.PENDING)
        tip.refresh_from_db()
        self.assertEqual(tip.status, NewsTip.Status.PENDING)

    def test_needs_link_or_document(self, _fetch):
        response = self.client.post(reverse("tip_box"), {"comment": "nada"})
        self.assertContains(response, "Pega un enlace o elige un documento")
        self.assertFalse(NewsTip.objects.exists())

    def test_other_users_cannot_see_a_tip(self, _fetch):
        self.client.post(reverse("tip_box"), {"url": "https://diariodelremo.example/noticias/hondarribia-barco"})
        tip = NewsTip.objects.get()
        other = User.objects.create_user("otro", "otro@example.com", "remo-y-pala-2026")
        self.client.force_login(other)
        self.assertEqual(self.client.get(tip.get_absolute_url()).status_code, 403)
