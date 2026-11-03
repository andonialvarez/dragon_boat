from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .utils import unique_slugify


class SampleFlagMixin(models.Model):
    """Marca un registro como dato de ejemplo (ficticio).

    Los datos de ejemplo se muestran con una etiqueta visible y se pueden borrar
    de golpe con `python manage.py borrar_datos_ejemplo`.
    """

    is_sample = models.BooleanField(
        _("dato de ejemplo"),
        default=False,
        db_index=True,
        help_text=_("Marca los contenidos ficticios de demostración. Se muestran con una etiqueta «Ejemplo»."),
    )

    class Meta:
        abstract = True


class TimeStampedMixin(models.Model):
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("actualizado"), auto_now=True)

    class Meta:
        abstract = True


class Sport(models.Model):
    class Propulsion(models.TextChoices):
        PALA = "pala", _("Pala (mirando hacia delante)")
        REMO = "remo", _("Remo (de espaldas)")

    name = models.CharField(_("nombre"), max_length=80)
    slug = models.SlugField(_("slug"), max_length=90, unique=True, blank=True)
    icon = models.CharField(_("icono"), max_length=8, blank=True, help_text=_("Un emoji, p. ej. 🐉"))
    color = models.CharField(
        _("color"),
        max_length=7,
        default="#0e5e6f",
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", _("Usa un color hexadecimal, p. ej. #c8102e"))],
    )
    propulsion = models.CharField(_("propulsión"), max_length=10, choices=Propulsion.choices, default=Propulsion.PALA)
    tagline = models.CharField(_("lema"), max_length=200, blank=True)
    description = models.TextField(_("descripción"), blank=True)
    crew = models.CharField(_("tripulación"), max_length=200, blank=True)
    distances = models.CharField(_("distancias habituales"), max_length=200, blank=True)
    governing_bodies = models.CharField(_("organismos"), max_length=250, blank=True)
    is_primary = models.BooleanField(_("deporte principal"), default=False)
    order = models.PositiveSmallIntegerField(_("orden"), default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("deporte")
        verbose_name_plural = _("deportes")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("sport_detail", args=[self.slug])
