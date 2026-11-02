from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import SampleFlagMixin, TimeStampedMixin
from core.utils import current_year, unique_slugify
from core.validators import validate_image_extension, validate_image_size


class Team(SampleFlagMixin, TimeStampedMixin):
    name = models.CharField(_("nombre"), max_length=150)
    slug = models.SlugField(_("slug"), max_length=160, unique=True, blank=True)
    short_name = models.CharField(_("nombre corto"), max_length=40, blank=True)
    sports = models.ManyToManyField("core.Sport", verbose_name=_("deportes"), related_name="teams", blank=True)
    city = models.CharField(_("localidad"), max_length=120, blank=True)
    region = models.CharField(_("provincia o comunidad"), max_length=120, blank=True)
    country = models.CharField(_("país"), max_length=80, default="España")
    founded_year = models.PositiveSmallIntegerField(_("año de fundación"), null=True, blank=True)
    description = models.TextField(_("descripción breve"), blank=True)
    logo = models.ImageField(
        _("escudo o logo"),
        upload_to="equipos/",
        blank=True,
        validators=[validate_image_extension, validate_image_size],
    )
    website = models.URLField(_("web"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("equipo o club")
        verbose_name_plural = _("equipos y clubes")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("team_detail", args=[self.slug])

    @property
    def origin(self):
        """«Bilbao, Bizkaia (España)» con lo que haya disponible."""
        place = ", ".join(part for part in [self.city, self.region] if part)
        if self.country and self.country.lower() != "españa":
            return f"{place} ({self.country})" if place else self.country
        return place or self.country

    @property
    def display_short_name(self):
        return self.short_name or self.name

    @property
    def initials(self):
        """Iniciales para el escudo por defecto: «Dragones Turquesa» -> «DT»."""
        stopwords = {"de", "del", "la", "las", "los", "el", "y", "club", "cd", "c.d.", "cp", "sd"}
        words = [w for w in self.display_short_name.split() if w.lower() not in stopwords] or self.name.split()
        return "".join(word[0] for word in words[:2]).upper()


class ChampionshipQuerySet(models.QuerySet):
    def current_first(self):
        return self.order_by("-season", "-start_date", "name")


class Championship(SampleFlagMixin, TimeStampedMixin):
    class Scope(models.TextChoices):
        LOCAL = "local", _("Local")
        REGIONAL = "autonomico", _("Autonómico")
        NATIONAL = "nacional", _("Nacional")
        INTERNATIONAL = "internacional", _("Internacional")

    name = models.CharField(_("nombre"), max_length=180)
    slug = models.SlugField(_("slug"), max_length=190, unique=True, blank=True)
    sport = models.ForeignKey(
        "core.Sport", verbose_name=_("deporte"), on_delete=models.PROTECT, related_name="championships"
    )
    season = models.PositiveSmallIntegerField(_("temporada"), default=current_year)
    scope = models.CharField(_("ámbito"), max_length=20, choices=Scope.choices, default=Scope.NATIONAL)
    organizer = models.CharField(_("organiza"), max_length=180, blank=True)
    location = models.CharField(_("sede o sedes"), max_length=180, blank=True)
    start_date = models.DateField(_("fecha de inicio"), null=True, blank=True)
    end_date = models.DateField(_("fecha de fin"), null=True, blank=True)
    description = models.TextField(_("descripción"), blank=True)
    cover_image = models.ImageField(
        _("imagen"),
        upload_to="campeonatos/",
        blank=True,
        validators=[validate_image_extension, validate_image_size],
    )
    is_featured = models.BooleanField(
        _("destacado en portada"),
        default=False,
        help_text=_("La portada muestra la clasificación del campeonato destacado más reciente."),
    )

    objects = ChampionshipQuerySet.as_manager()

    class Meta:
        ordering = ["-season", "-start_date", "name"]
        verbose_name = _("campeonato")
        verbose_name_plural = _("campeonatos")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("championship_detail", args=[self.slug])

    @property
    def status(self):
        today = timezone.localdate()
        if self.start_date and today < self.start_date:
            return "proximamente"
        if self.end_date and today > self.end_date:
            return "finalizado"
        if self.start_date:
            return "en_curso"
        return ""

    @property
    def status_label(self):
        return {
            "proximamente": _("Próximamente"),
            "finalizado": _("Finalizado"),
            "en_curso": _("En curso"),
        }.get(self.status, "")

    def participating_teams(self):
        """Equipos que aparecen en alguna clasificación o inscritos en sus eventos."""
        return (
            Team.objects.filter(
                models.Q(standings__division__championship=self)
                | models.Q(events__championship=self, events__is_published=True)
            )
            .distinct()
            .prefetch_related("sports")
        )


class Division(models.Model):
    """Una categoría o prueba dentro de un campeonato, con su propia clasificación.

    Ejemplos: «Mixto · barco grande (20) · 200 m», «Clasificación general».
    """

    championship = models.ForeignKey(
        Championship, verbose_name=_("campeonato"), on_delete=models.CASCADE, related_name="divisions"
    )
    name = models.CharField(_("categoría o prueba"), max_length=180)
    notes = models.CharField(_("notas"), max_length=250, blank=True)
    order = models.PositiveSmallIntegerField(_("orden"), default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = _("categoría del campeonato")
        verbose_name_plural = _("categorías del campeonato")

    def __str__(self):
        return f"{self.championship} · {self.name}"

    # Qué columnas mostrar en la tabla (según los datos que se hayan rellenado).
    @property
    def has_points(self):
        return any(row.points is not None for row in self.standings.all())

    @property
    def has_times(self):
        return any(row.result_time for row in self.standings.all())

    @property
    def has_notes(self):
        return any(row.notes for row in self.standings.all())


class Standing(models.Model):
    division = models.ForeignKey(
        Division, verbose_name=_("categoría"), on_delete=models.CASCADE, related_name="standings"
    )
    team = models.ForeignKey(Team, verbose_name=_("equipo"), on_delete=models.CASCADE, related_name="standings")
    position = models.PositiveSmallIntegerField(_("puesto"))
    points = models.DecimalField(_("puntos"), max_digits=7, decimal_places=2, null=True, blank=True)
    result_time = models.CharField(_("tiempo"), max_length=20, blank=True, help_text=_("Por ejemplo 0:52,31"))
    notes = models.CharField(_("observaciones"), max_length=200, blank=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("puesto en la clasificación")
        verbose_name_plural = _("clasificación")
        constraints = [
            models.UniqueConstraint(fields=["division", "team"], name="un_puesto_por_equipo_y_categoria"),
        ]

    def __str__(self):
        return f"{self.position}. {self.team}"
