from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import SampleFlagMixin
from core.utils import unique_slugify
from core.validators import validate_image_extension, validate_image_size

POSTS_PER_PAGE = 20


class Category(models.Model):
    name = models.CharField(_("nombre"), max_length=100)
    slug = models.SlugField(_("slug"), max_length=110, unique=True, blank=True)
    description = models.CharField(_("descripción"), max_length=250, blank=True)
    icon = models.CharField(_("icono"), max_length=8, blank=True)
    sport = models.ForeignKey(
        "core.Sport",
        verbose_name=_("deporte"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forum_categories",
    )
    order = models.PositiveSmallIntegerField(_("orden"), default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("categoría del foro")
        verbose_name_plural = _("categorías del foro")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("forum:category", args=[self.slug])


class Topic(SampleFlagMixin):
    category = models.ForeignKey(
        Category, verbose_name=_("categoría"), on_delete=models.CASCADE, related_name="topics"
    )
    title = models.CharField(_("título"), max_length=160)
    slug = models.SlugField(_("slug"), max_length=170, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("autor"), on_delete=models.CASCADE, related_name="forum_topics"
    )
    created_at = models.DateTimeField(_("creado"), default=timezone.now)
    last_activity_at = models.DateTimeField(_("última actividad"), default=timezone.now, db_index=True)
    is_pinned = models.BooleanField(_("fijado arriba"), default=False)
    is_locked = models.BooleanField(_("cerrado"), default=False, help_text=_("No admite más respuestas."))

    class Meta:
        ordering = ["-is_pinned", "-last_activity_at"]
        verbose_name = _("tema")
        verbose_name_plural = _("temas")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            # El slug del tema no tiene que ser único: la URL lleva también el id.
            from django.utils.text import slugify

            self.slug = slugify(self.title)[:170].strip("-") or "tema"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("forum:topic", args=[self.pk, self.slug])


class Post(SampleFlagMixin):
    topic = models.ForeignKey(Topic, verbose_name=_("tema"), on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("autor"), on_delete=models.CASCADE, related_name="forum_posts"
    )
    body = models.TextField(_("mensaje"), max_length=8000)
    image = models.ImageField(
        _("imagen"),
        upload_to="foro/%Y/%m/",
        blank=True,
        validators=[validate_image_extension, validate_image_size],
    )
    created_at = models.DateTimeField(_("fecha"), default=timezone.now)
    updated_at = models.DateTimeField(_("editado"), auto_now=True)
    is_hidden = models.BooleanField(_("oculto por moderación"), default=False)
    is_deleted = models.BooleanField(_("borrado por su autor"), default=False)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = _("mensaje")
        verbose_name_plural = _("mensajes")

    def __str__(self):
        return f"{self.author} en «{self.topic}»"

    def get_absolute_url(self):
        earlier = self.topic.posts.filter(
            models.Q(created_at__lt=self.created_at) | models.Q(created_at=self.created_at, id__lt=self.id)
        ).count()
        page = earlier // POSTS_PER_PAGE + 1
        url = self.topic.get_absolute_url()
        if page > 1:
            url = f"{url}?pagina={page}"
        return f"{url}#mensaje-{self.pk}"

    @property
    def is_visible(self):
        return not (self.is_hidden or self.is_deleted)

    @property
    def was_edited(self):
        return (self.updated_at - self.created_at).total_seconds() > 60

    @property
    def is_first(self):
        first_id = self.topic.posts.order_by("created_at", "id").values_list("id", flat=True).first()
        return first_id == self.pk
