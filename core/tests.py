from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from competitions.models import Championship, Team
from core.models import Sport
from events.models import Event
from forum.models import Category, Topic
from news.models import Article

User = get_user_model()


class SampleDataMixin:
    """Carga los datos de ejemplo una vez por clase de pruebas."""

    @classmethod
    def setUpTestData(cls):
        cache.clear()
        call_command("cargar_datos_ejemplo", verbosity=0)


class PublicPagesTests(SampleDataMixin, TestCase):
    def test_public_pages_open_without_account(self):
        article = Article.objects.published().first()
        event = Event.objects.visible().first()
        championship = Championship.objects.exclude(divisions=None).first()
        team = Team.objects.first()
        topic = Topic.objects.first()
        urls = [
            reverse("home"),
            reverse("article_list"),
            article.get_absolute_url(),
            reverse("article_feed"),
            reverse("event_list"),
            reverse("event_list") + "?ver=pasados",
            event.get_absolute_url(),
            reverse("event_ics", args=[event.slug]),
            reverse("championship_list"),
            championship.get_absolute_url(),
            reverse("team_list"),
            team.get_absolute_url(),
            reverse("sport_list"),
            Sport.objects.get(slug="dragon-boat").get_absolute_url(),
            reverse("forum:index"),
            Category.objects.first().get_absolute_url(),
            topic.get_absolute_url(),
            reverse("search") + "?q=dragon",
            reverse("about"),
            reverse("rules"),
            reverse("privacy"),
            reverse("signup"),
            reverse("login"),
            reverse("profile_detail", args=["ejemplo_ane"]),
            reverse("sitemap"),
            reverse("robots_txt"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_sample_content_is_labelled(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Web en preparación")
        self.assertContains(response, "badge-sample")

    def test_page_is_in_spanish(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, '<html lang="es">')
        self.assertNotContains(response, "set_language")

    def test_unknown_page_returns_404(self):
        self.assertEqual(self.client.get("/no-existe/").status_code, 404)

    def test_search_finds_content(self):
        response = self.client.get(reverse("search"), {"q": "Turquesa"})
        self.assertContains(response, "Dragones Turquesa")

    def test_standings_show_points_and_times(self):
        league = Championship.objects.get(name__startswith="Liga Demo")
        response = self.client.get(league.get_absolute_url())
        self.assertContains(response, "Puntos")
        self.assertContains(response, "Tiempo")


class SampleDataCommandTests(TestCase):
    def test_load_and_delete_sample_data(self):
        call_command("cargar_datos_ejemplo", verbosity=0)
        self.assertTrue(Article.objects.filter(is_sample=True).exists())
        self.assertTrue(User.objects.filter(profile__is_sample=True).exists())

        real_user = User.objects.create_user("persona_real", "real@example.com", "una-clave-larga-123")
        real_article = Article.objects.create(
            title="Noticia real de prueba", summary="Resumen de la noticia real.", body="Texto.", author=real_user
        )

        call_command("borrar_datos_ejemplo", "--si", verbosity=0)
        for model in (Article, Event, Championship, Team, Topic):
            self.assertFalse(model.objects.filter(is_sample=True).exists(), model.__name__)
        self.assertFalse(User.objects.filter(profile__is_sample=True).exists())
        # Lo que no es de ejemplo no se toca.
        self.assertTrue(User.objects.filter(pk=real_user.pk).exists())
        self.assertTrue(Article.objects.filter(pk=real_article.pk).exists())
        # Los deportes y las categorías del foro son contenido fijo, no de ejemplo.
        self.assertEqual(Sport.objects.count(), 5)
        self.assertEqual(Category.objects.count(), 7)

    def test_reset_does_not_duplicate(self):
        call_command("cargar_datos_ejemplo", verbosity=0)
        count = Article.objects.count()
        call_command("cargar_datos_ejemplo", "--reset", verbosity=0)
        self.assertEqual(Article.objects.count(), count)
