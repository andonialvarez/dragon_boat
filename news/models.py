from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import SampleFlagMixin, TimeStampedMixin
from core.utils import unique_slugify
from core.validators import validate_image_extension, validate_image_size


class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Article.Status.PUBLISHED, published_at__lte=timezone.now())


class Article(SampleFlagMixin, TimeStampedMixin):
    class Status(models.TextChoices):
        DRAFT = "borrador", _("Borrador")
        PENDING = "pendiente", _("Pendiente de revisión")
        PUBLISHED = "publicado", _("Publicado")

    class Origin(models.TextChoices):
        EDITORIAL = "redaccion", _("Redacción")
        COMMUNITY = "comunidad", _("Comunidad")
        IMPORTED = "importada", _("De otra web")
        AI = "ia", _("Resumen semanal")

    class Category(models.TextChoices):
        COMPETITION = "competicion", _("Competición")
        CLUBS = "clubes", _("Clubes")
        INTERNATIONAL = "internacional", _("Internacional")
        TRAINING = "tecnica", _("Técnica y entrenamiento")
        INTERVIEW = "entrevista", _("Entrevista")
        COMMUNITY = "comunidad", _("Comunidad")
        OTHER = "otros", _("Otros")

    title = models.CharField(_("título"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=210, unique=True, blank=True)
    sport = models.ForeignKey(
        "core.Sport",
        verbose_name=_("deporte"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    category = models.CharField(_("sección"), max_length=20, choices=Category.choices, default=Category.COMPETITION)
    summary = models.CharField(_("entradilla"), max_length=320, help_text=_("Una o dos frases que resumen la noticia."))
    body = models.TextField(
        _("texto"),
        blank=True,
        help_text=_("Separa los párrafos con una línea en blanco. Los enlaces se convierten solos."),
    )
    cover_image = models.ImageField(
        _("imagen principal"),
        upload_to="noticias/%Y/%m/",
        blank=True,
        validators=[validate_image_extension, validate_image_size],
    )
    image_caption = models.CharField(_("pie de foto"), max_length=200, blank=True)
    image_url = models.URLField(
        _("imagen de la fuente"),
        max_length=600,
        blank=True,
        help_text=_(
            "Imagen que el medio original usa para compartir la noticia. Se busca sola en las noticias "
            "importadas y en los resúmenes; se muestra enlazada y con el nombre del medio."
        ),
    )
    image_checked_at = models.DateTimeField(
        _("foto revisada"),
        null=True,
        blank=True,
        editable=False,
        help_text=_("Cuándo se buscó o se comprobó la foto de la fuente. Vacío = se revisará en la próxima búsqueda."),
    )
    source_name = models.CharField(_("fuente"), max_length=120, blank=True)
    source_url = models.URLField(_("enlace a la fuente"), max_length=600, blank=True, db_index=True)
    source_key = models.CharField(
        _("enlace normalizado"),
        max_length=600,
        blank=True,
        db_index=True,
        editable=False,
        help_text=_("El enlace a la fuente sin www., parámetros de seguimiento ni barra final. Sirve para detectar repetidas."),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("autor"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    status = models.CharField(_("estado"), max_length=12, choices=Status.choices, default=Status.DRAFT)
    origin = models.CharField(
        _("origen"),
        max_length=12,
        choices=Origin.choices,
        default=Origin.EDITORIAL,
        help_text=_("Quién ha publicado la noticia: la redacción, un usuario, una web externa o un resumen automático."),
    )
    published_at = models.DateTimeField(_("fecha de publicación"), default=timezone.now)
    is_featured = models.BooleanField(_("destacada en portada"), default=False)
    allow_comments = models.BooleanField(_("permitir comentarios"), default=True)
    related_event = models.ForeignKey(
        "events.Event",
        verbose_name=_("evento relacionado"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    related_championship = models.ForeignKey(
        "competitions.Championship",
        verbose_name=_("campeonato relacionado"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )

    objects = ArticleQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at"]
        verbose_name = _("noticia")
        verbose_name_plural = _("noticias")
        indexes = [models.Index(fields=["status", "published_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.title)
        from .buzon import normalize_url

        self.source_key = normalize_url(self.source_url)
        if kwargs.get("update_fields") is not None and "source_url" in kwargs["update_fields"]:
            kwargs["update_fields"] = {*kwargs["update_fields"], "source_key"}
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("article_detail", args=[self.slug])

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED and self.published_at <= timezone.now()

    @property
    def picture_url(self):
        """La imagen subida o, si no hay, la del medio original."""
        return self.cover_image.url if self.cover_image else self.image_url

    @property
    def has_picture(self):
        return bool(self.cover_image or self.image_url)

    @property
    def picture_is_external(self):
        return not self.cover_image and bool(self.image_url)

    @property
    def is_external(self):
        """Noticia agregada de otra web: aquí solo hay titular, resumen y enlace."""
        return self.origin == self.Origin.IMPORTED

    @property
    def reading_minutes(self):
        words = len(self.body.split())
        return max(1, round(words / 200))


class Comment(SampleFlagMixin):
    """Comentario a una noticia. Las respuestas cuelgan de un comentario principal."""

    article = models.ForeignKey(Article, verbose_name=_("noticia"), on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("autor"), on_delete=models.CASCADE, related_name="news_comments"
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("responde a"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField(_("comentario"), max_length=3000)
    created_at = models.DateTimeField(_("fecha"), default=timezone.now)
    updated_at = models.DateTimeField(_("editado"), auto_now=True)
    is_hidden = models.BooleanField(
        _("oculto por moderación"), default=False, help_text=_("El texto deja de mostrarse en la web.")
    )
    is_deleted = models.BooleanField(_("borrado por su autor"), default=False)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("comentario")
        verbose_name_plural = _("comentarios")

    def __str__(self):
        return f"{self.author} en «{self.article}»"

    def get_absolute_url(self):
        return f"{self.article.get_absolute_url()}#comentario-{self.pk}"

    @property
    def is_visible(self):
        return not (self.is_hidden or self.is_deleted)

    @property
    def was_edited(self):
        return (self.updated_at - self.created_at).total_seconds() > 60


class NewsSource(models.Model):
    """Fuente RSS/Atom de la que se importan titulares automáticamente.

    El importador (`python manage.py importar_noticias`) solo guarda el titular,
    un resumen breve y el enlace a la noticia original, citando la fuente.
    """

    name = models.CharField(_("nombre"), max_length=120)
    feed_url = models.URLField(_("dirección del feed RSS o Atom"), max_length=600, unique=True)
    sport = models.ForeignKey(
        "core.Sport", verbose_name=_("deporte"), on_delete=models.SET_NULL, null=True, blank=True
    )
    category = models.CharField(
        _("sección"), max_length=20, choices=Article.Category.choices, default=Article.Category.OTHER
    )
    keywords = models.CharField(
        _("palabras obligatorias"),
        max_length=250,
        blank=True,
        help_text=_("Separadas por comas. Solo se importan titulares o resúmenes que contengan alguna. Vacío = todo."),
    )
    max_items = models.PositiveSmallIntegerField(_("máximo por importación"), default=10)
    is_active = models.BooleanField(_("activa"), default=True)
    last_checked_at = models.DateTimeField(_("última revisión"), null=True, blank=True)
    last_error = models.TextField(_("último error"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("fuente de noticias")
        verbose_name_plural = _("fuentes de noticias")

    def __str__(self):
        return self.name

    def keyword_list(self):
        return [word.strip().lower() for word in self.keywords.split(",") if word.strip()]


class NewsTip(models.Model):
    """Lo que un usuario deja en el buzón de noticias: un enlace o un documento.

    El documento no se guarda; solo el texto que se ha sacado de él, y únicamente
    mientras la aportación está a medias (luego pasa a la noticia o se borra).
    """

    class Kind(models.TextChoices):
        LINK = "enlace", _("Enlace")
        DOCUMENT = "documento", _("Documento")

    class Status(models.TextChoices):
        DRAFT = "borrador", _("Sin terminar")
        DUPLICATE = "repetida", _("Ya estaba publicada")
        PUBLISHED = "publicada", _("Publicada")
        PENDING = "pendiente", _("Pendiente de revisión")

    class MatchKind(models.TextChoices):
        NONE = "", _("Ninguna")
        LINK = "enlace", _("Mismo enlace")
        TITLE = "titulo", _("Título casi igual")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("usuario"), on_delete=models.CASCADE, related_name="news_tips"
    )
    kind = models.CharField(_("tipo"), max_length=10, choices=Kind.choices)
    url = models.URLField(_("enlace"), max_length=600, blank=True)
    url_keys = models.CharField(
        _("enlaces normalizados"), max_length=1900, blank=True, help_text=_("Separados por espacios.")
    )
    file_name = models.CharField(_("documento"), max_length=150, blank=True)
    comment = models.CharField(_("comentario del usuario"), max_length=500, blank=True)
    title = models.CharField(_("título"), max_length=200, blank=True)
    summary = models.CharField(_("entradilla"), max_length=320, blank=True)
    body = models.TextField(_("texto"), blank=True)
    source_name = models.CharField(_("fuente"), max_length=120, blank=True)
    image_url = models.URLField(_("imagen de la fuente"), max_length=600, blank=True)
    original_published_at = models.DateTimeField(_("fecha en la fuente"), null=True, blank=True)
    sport = models.ForeignKey(
        "core.Sport", verbose_name=_("deporte"), on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(_("estado"), max_length=10, choices=Status.choices, default=Status.DRAFT)
    match_kind = models.CharField(_("coincidencia"), max_length=10, choices=MatchKind.choices, blank=True)
    match_score = models.FloatField(_("parecido"), null=True, blank=True)
    article = models.ForeignKey(
        Article,
        verbose_name=_("noticia"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tips",
        help_text=_("La noticia que ya existía o la que se ha creado con esta aportación."),
    )
    created_at = models.DateTimeField(_("fecha"), default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("aportación al buzón")
        verbose_name_plural = _("buzón de noticias")

    def __str__(self):
        return self.title or self.url or self.file_name or f"#{self.pk}"

    def get_absolute_url(self):
        return reverse("tip_review", args=[self.pk])

    def key_list(self):
        return [key for key in self.url_keys.split() if key]

    @property
    def is_open(self):
        """Todavía se puede terminar (no hay noticia creada y no es un enlace repetido)."""
        return self.status == self.Status.DRAFT or (
            self.status == self.Status.DUPLICATE and self.match_kind == self.MatchKind.TITLE
        )
