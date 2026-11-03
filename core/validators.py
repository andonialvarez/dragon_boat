from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif"]

validate_image_extension = FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)


def validate_image_size(file):
    limit_mb = settings.MAX_UPLOAD_MB
    if file and file.size > limit_mb * 1024 * 1024:
        raise ValidationError(
            _("La imagen pesa demasiado. El máximo es %(limit)s MB."),
            params={"limit": limit_mb},
        )
