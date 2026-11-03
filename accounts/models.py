import hashlib

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

AVATAR_COLORS = ["#c8102e", "#0e5e6f", "#e8a33d", "#2e7d32", "#5b3cc4", "#0b5394", "#b4451f", "#00838f"]


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(_("sobre mí"), max_length=600, blank=True)
    club = models.CharField(_("club o equipo"), max_length=120, blank=True)
    city = models.CharField(_("localidad"), max_length=120, blank=True)
    favorite_sport = models.ForeignKey(
        "core.Sport",
        verbose_name=_("deporte favorito"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_sample = models.BooleanField(_("usuario de ejemplo"), default=False, db_index=True)

    class Meta:
        verbose_name = _("perfil")
        verbose_name_plural = _("perfiles")

    def __str__(self):
        return str(self.user)

    def get_absolute_url(self):
        return reverse("profile_detail", args=[self.user.get_username()])

    @property
    def avatar_color(self):
        digest = hashlib.md5(self.user.get_username().encode("utf-8")).hexdigest()
        return AVATAR_COLORS[int(digest, 16) % len(AVATAR_COLORS)]

    @property
    def initial(self):
        return (self.user.get_username()[:1] or "?").upper()
