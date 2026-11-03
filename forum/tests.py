import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Post, Topic

User = get_user_model()
PASSWORD = "remo-y-pala-2026"
MEDIA = tempfile.mkdtemp(prefix="dragonboat-tests-")


def png_upload(name="foto.png"):
    buffer = BytesIO()
    Image.new("RGB", (40, 20), "#c8102e").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA)
class ForumTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.get(slug="dragon-boat")
        cls.ane = User.objects.create_user("ane", "ane@example.com", PASSWORD)
        cls.iker = User.objects.create_user("iker", "iker@example.com", PASSWORD)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def new_topic_url(self):
        return reverse("forum:new_topic", args=[self.category.slug])

    def make_topic(self, author=None, **fields):
        topic = Topic.objects.create(
            category=self.category, title="¿Cómo se marca el ritmo?", author=author or self.ane, **fields
        )
        Post.objects.create(topic=topic, author=author or self.ane, body="Primer mensaje del tema.")
        return topic

    def test_reading_is_public(self):
        topic = self.make_topic()
        self.assertEqual(self.client.get(reverse("forum:index")).status_code, 200)
        self.assertContains(self.client.get(topic.get_absolute_url()), "Primer mensaje del tema.")

    def test_writing_requires_login(self):
        topic = self.make_topic()
        response = self.client.get(self.new_topic_url())
        self.assertIn(reverse("login"), response["Location"])
        response = self.client.post(reverse("forum:reply", args=[topic.pk]), {"body": "Hola"})
        self.assertIn(reverse("login"), response["Location"])
        self.assertEqual(Post.objects.count(), 1)

    def test_create_topic_with_image(self):
        self.client.force_login(self.ane)
        response = self.client.post(
            self.new_topic_url(),
            {
                "title": "Busco consejos para tamborilear",
                "body": "¿Qué ritmo usáis en la salida?",
                "image": png_upload(),
            },
        )
        topic = Topic.objects.get()
        self.assertRedirects(response, topic.get_absolute_url())
        post = topic.posts.get()
        self.assertTrue(post.image.name.startswith("foro/"))
        self.assertEqual(topic.author, self.ane)

    def test_rejects_files_that_are_not_images(self):
        self.client.force_login(self.ane)
        fake = SimpleUploadedFile("virus.png", b"esto no es una imagen", content_type="image/png")
        self.client.post(self.new_topic_url(), {"title": "Tema con adjunto falso", "body": "Texto", "image": fake})
        self.assertFalse(Topic.objects.exists())

    def test_reply_updates_activity(self):
        topic = self.make_topic()
        before = topic.last_activity_at
        self.client.force_login(self.iker)
        response = self.client.post(
            reverse("forum:reply", args=[topic.pk]), {"body": "Cuenta en voz alta: uno, dos..."}
        )
        post = Post.objects.get(author=self.iker)
        self.assertRedirects(response, post.get_absolute_url(), fetch_redirect_response=False)
        topic.refresh_from_db()
        self.assertGreater(topic.last_activity_at, before)

    def test_locked_topic_rejects_replies(self):
        topic = self.make_topic(is_locked=True)
        self.client.force_login(self.iker)
        self.client.post(reverse("forum:reply", args=[topic.pk]), {"body": "¿Sigue abierto?"})
        self.assertEqual(topic.posts.count(), 1)

    def test_only_author_edits_and_deletes(self):
        topic = self.make_topic()
        reply = Post.objects.create(topic=topic, author=self.iker, body="Mi respuesta")
        self.client.force_login(self.ane)
        self.assertEqual(
            self.client.post(reverse("forum:post_edit", args=[reply.pk]), {"body": "Cambio"}).status_code, 403
        )
        self.assertEqual(self.client.post(reverse("forum:post_delete", args=[reply.pk])).status_code, 403)

        self.client.force_login(self.iker)
        self.client.post(reverse("forum:post_delete", args=[reply.pk]))
        reply.refresh_from_db()
        self.assertTrue(reply.is_deleted)

    def test_deleting_only_post_removes_topic(self):
        topic = self.make_topic()
        self.client.force_login(self.ane)
        response = self.client.post(reverse("forum:post_delete", args=[topic.posts.get().pk]))
        self.assertRedirects(response, self.category.get_absolute_url())
        self.assertFalse(Topic.objects.exists())

    def test_old_topic_url_redirects_to_canonical(self):
        topic = self.make_topic()
        response = self.client.get(reverse("forum:topic_short", args=[topic.pk]))
        self.assertRedirects(response, topic.get_absolute_url(), status_code=301)

    def test_pagination_links_to_last_page(self):
        topic = self.make_topic()
        for number in range(30):
            Post.objects.create(topic=topic, author=self.iker, body=f"Respuesta {number}")
        last = topic.posts.last()
        self.assertIn("?pagina=2", last.get_absolute_url())
        response = self.client.get(topic.get_absolute_url() + "?pagina=2")
        self.assertContains(response, "Respuesta 29")
