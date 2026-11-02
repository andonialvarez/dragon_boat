from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class Reaction(models.Model):
    class Kind(models.TextChoices):
        LIKE = "like", _("Me gusta")
        LOVE = "love", _("Me encanta")
        CLAP = "clap", _("Aplausos")
        FIRE = "fire", _("Brutal")
        DRAGON = "dragon", _("¡Dragón!")

    EMOJI = {
        Kind.LIKE: "👍",
        Kind.LOVE: "❤️",
        Kind.CLAP: "👏",
        Kind.FIRE: "🔥",
        Kind.DRAGON: "🐉",
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    kind = models.CharField(_("reacción"), max_length=10, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("reacción")
        verbose_name_plural = _("reacciones")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id", "kind"],
                name="una_reaccion_de_cada_tipo_por_usuario",
            )
        ]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.user} {self.EMOJI.get(self.kind, '')} {self.content_type.model}#{self.object_id}"
