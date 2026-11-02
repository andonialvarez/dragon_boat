from urllib.parse import quote_plus

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import SampleFlagMixin, TimeStampedMixin
from core.utils import unique_slugify
from core.validators import validate_image_extension, validate_image_size


class EventQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_published=True)

    def upcoming(self):
        today = timezone.localdate()
        return self.visible().filter(
            models.Q(end_date__gte=today) | models.Q(end_date__isnull=True, start_date__gte=today)
        ).order_by("start_date", "start_time", "title")

    def past(self):
        today = timezone.localdate()
        return self.visible().filter(
            models.Q(end_date__lt=today) | models.Q(end_date__isnull=True, start_date__lt=today)
        ).order_by("-start_date", "title")


class Event(SampleFlagMixin, TimeStampedMixin):
    class Kind(models.TextChoices):
        REGATTA = "regata", _("Regata")
        CHAMPIONSHIP = "campeonato", _("Campeonato")
        LEAGUE = "liga", _("Jornada de liga")
        FESTIVAL = "festival", _("Festival")
        CROSSING = "travesia", _("Travesía")
        TRAINING = "formacion", _("Curso o clinic")
        OTHER = "otro", _("Otro")

    class Status(models.TextChoices):
        SCHEDULED = "programado", _("Programado")
        POSTPONED = "aplazado", _("Aplazado")
        CANCELLED = "cancelado", _("Cancelado")

    title = models.CharField(_("título"), max_length=180)
    slug = models.SlugField(_("slug"), max_length=190, unique=True, blank=True)
    sport = models.ForeignKey("core.Sport", verbose_name=_("deporte"), on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(_("tipo"), max_length=20, choices=Kind.choices, default=Kind.REGATTA)
    status = models.CharField(_("estado"), max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    start_date = models.DateField(_("fecha de inicio"))
    end_date = models.DateField(_("fecha de fin"), null=True, blank=True, help_text=_("Déjalo vacío si dura un día."))
    start_time = models.TimeField(_("hora de inicio"), null=True, blank=True)
    venue = models.CharField(_("lugar"), max_length=180, blank=True, help_text=_("Puerto, río, embalse, dársena..."))
    city = models.CharField(_("localidad"), max_length=120, blank=True)
    region = models.CharField(_("provincia o comunidad"), max_length=120, blank=True)
    country = models.CharField(_("país"), max_length=80, default="España")
    summary = models.CharField(_("resumen"), max_length=280, blank=True)
    description = models.TextField(_("descripción"), blank=True)
    distances = models.CharField(_("distancias"), max_length=150, blank=True, help_text=_("Por ejemplo: 200 m, 500 m"))
    organizer = models.CharField(_("organiza"), max_length=180, blank=True)
    website = models.URLField(_("web del evento"), blank=True)
    registration_url = models.URLField(_("enlace de inscripción"), blank=True)
    registration_deadline = models.DateField(_("fin de inscripción"), null=True, blank=True)
    championship = models.ForeignKey(
        "competitions.Championship",
        verbose_name=_("campeonato"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    participants = models.ManyToManyField(
        "competitions.Team",
        verbose_name=_("equipos inscritos"),
        related_name="events",
        blank=True,
    )
    cover_image = models.ImageField(
        _("imagen"),
        upload_to="eventos/%Y/",
        blank=True,
        validators=[validate_image_extension, validate_image_size],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("publicado por"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events_created",
    )
    is_published = models.BooleanField(
        _("visible en la web"),
        default=True,
        help_text=_("Desmárcalo para ocultarlo (por ejemplo, si está pendiente de revisión)."),
    )

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["start_date", "start_time", "title"]
        verbose_name = _("evento")
        verbose_name_plural = _("eventos y regatas")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("event_detail", args=[self.slug])

    @property
    def last_day(self):
        return self.end_date or self.start_date

    @property
    def is_past(self):
        return self.last_day < timezone.localdate()

    @property
    def is_multiday(self):
        return bool(self.end_date and self.end_date != self.start_date)

    @property
    def place(self):
        return ", ".join(part for part in [self.venue, self.city, self.region] if part)

    @property
    def map_url(self):
        query = ", ".join(part for part in [self.venue, self.city, self.region, self.country] if part)
        if not query:
            return ""
        return f"https://www.openstreetmap.org/search?query={quote_plus(query)}"

    @property
    def registration_open(self):
        if self.status != self.Status.SCHEDULED or self.is_past or not self.registration_url:
            return False
        if self.registration_deadline:
            return timezone.localdate() <= self.registration_deadline
        return True
