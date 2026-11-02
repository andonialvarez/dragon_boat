from django import forms
from django.utils.translation import gettext_lazy as _

from core.validators import validate_image_extension, validate_image_size

from .models import Post, Topic

BODY_WIDGET_ATTRS = {"rows": 7, "maxlength": 8000}


def _clean_body(value):
    value = value.strip()
    if len(value) < 2:
        raise forms.ValidationError(_("El mensaje está vacío."))
    return value


class TopicForm(forms.Form):
    title = forms.CharField(
        label=_("Título"),
        max_length=160,
        min_length=5,
        widget=forms.TextInput(attrs={"placeholder": _("Resume tu pregunta o tema en una frase")}),
    )
    body = forms.CharField(
        label=_("Mensaje"),
        max_length=8000,
        widget=forms.Textarea(attrs={**BODY_WIDGET_ATTRS, "rows": 9}),
    )
    image = forms.ImageField(
        label=_("Imagen (opcional)"),
        required=False,
        help_text=_("JPG, PNG, WEBP o GIF."),
        validators=[validate_image_extension, validate_image_size],
    )

    def clean_title(self):
        return self.cleaned_data["title"].strip()

    def clean_body(self):
        return _clean_body(self.cleaned_data["body"])


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["body", "image"]
        labels = {"body": _("Tu respuesta"), "image": _("Imagen (opcional)")}
        widgets = {
            "body": forms.Textarea(attrs={**BODY_WIDGET_ATTRS, "placeholder": _("Escribe tu respuesta...")}),
        }

    def clean_body(self):
        return _clean_body(self.cleaned_data["body"])


class PostEditForm(PostForm):
    class Meta(PostForm.Meta):
        labels = {"body": _("Mensaje"), "image": _("Imagen")}


class TopicTitleForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ["title"]
        labels = {"title": _("Título del tema")}
