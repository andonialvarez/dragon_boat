from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from forum.models import Category, Post, Topic
from news.models import Article, Comment

from .models import Reaction

User = get_user_model()


class ReactionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("lucia", "lucia@example.com", "remo-y-pala-2026")
        cls.article = Article.objects.create(
            title="Noticia con reacciones", summary="Resumen.", body="Texto.", status=Article.Status.PUBLISHED
        )

    def url(self, target="noticia", pk=None, kind="like"):
        return reverse("toggle_reaction", args=[target, pk or self.article.pk, kind])

    def test_anonymous_is_sent_to_login(self):
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        response = self.client.post(self.url(), HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()["login_required"])
        self.assertFalse(Reaction.objects.exists())

    def test_toggle_on_and_off(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url(), HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response.status_code, 200)
        like = next(item for item in response.json()["reactions"] if item["kind"] == "like")
        self.assertEqual(like["count"], 1)
        self.assertTrue(like["mine"])
        self.assertEqual(Reaction.objects.count(), 1)

        self.client.post(self.url(), HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(Reaction.objects.count(), 0)

    def test_without_javascript_redirects_back(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url(kind="dragon"), {"next": self.article.get_absolute_url()})
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertEqual(Reaction.objects.get().kind, "dragon")

    def test_get_is_not_allowed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_unknown_target_or_kind(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url(kind="enfado")).status_code, 404)
        self.assertEqual(self.client.post(self.url(target="usuario")).status_code, 404)

    def test_comments_and_forum_posts(self):
        comment = Comment.objects.create(article=self.article, author=self.user, body="Comentario")
        category = Category.objects.first()
        topic = Topic.objects.create(category=category, title="Tema de prueba", author=self.user)
        post = Post.objects.create(topic=topic, author=self.user, body="Mensaje")
        self.client.force_login(self.user)
        self.client.post(self.url("comentario", comment.pk, "clap"))
        self.client.post(self.url("mensaje", post.pk, "fire"))
        self.assertEqual(Reaction.objects.count(), 2)

    def test_hidden_or_unpublished_content_cannot_get_reactions(self):
        hidden = Comment.objects.create(article=self.article, author=self.user, body="Oculto", is_hidden=True)
        draft = Article.objects.create(title="Borrador", summary="Resumen.", body="Texto.", status=Article.Status.DRAFT)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url("comentario", hidden.pk)).status_code, 404)
        self.assertEqual(self.client.post(self.url("noticia", draft.pk)).status_code, 404)
