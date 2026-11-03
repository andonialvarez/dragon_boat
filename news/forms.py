from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Article, Comment


class CommentForm(forms.ModelForm):
    parent_id = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Comment
        fields = ["body"]
        labels = {"body": _("Tu comentario")}
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 3, "maxlength": 3000, "placeholder": _("Escribe con respeto: aquí también rema todo el mundo.")}
            )
        }

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 2:
            raise forms.ValidationError(_("El comentario está vacío."))
        return body


class CommentEditForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        labels = {"body": _("Comentario")}
        widgets = {"body": forms.Textarea(attrs={"rows": 5, "maxlength": 3000})}

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 2:
            raise forms.ValidationError(_("El comentario está vacío."))
        return body


class ArticleSubmitForm(forms.ModelForm):
    """Formulario para que cualquier usuario registrado publique una noticia."""

    title = forms.CharField(label=_("Título"), max_length=200, min_length=8)
    summary = forms.CharField(
        label=_("Entradilla"),
        max_length=320,
        min_length=20,
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 320}),
        help_text=_("Una o dos frases que resuman la noticia."),
    )
    body = forms.CharField(
        label=_("Texto"),
        min_length=40,
        max_length=20000,
        widget=forms.Textarea(attrs={"rows": 12, "maxlength": 20000}),
        help_text=_("Separa los párrafos con una línea en blanco. Los enlaces se convierten solos."),
    )
    image_caption = forms.CharField(label=_("Pie de foto"), max_length=200, required=False)

    class Meta:
        model = Article
        fields = [
            "sport",
            "category",
            "title",
            "summary",
            "body",
            "cover_image",
            "image_caption",
            "source_name",
            "source_url",
        ]
        labels = {
            "sport": _("Deporte"),
            "category": _("Sección"),
            "cover_image": _("Imagen principal (opcional)"),
            "source_name": _("Fuente (opcional)"),
            "source_url": _("Enlace a la fuente (opcional)"),
        }
        help_texts = {
            "cover_image": _("JPG, PNG, WEBP o GIF. Usa solo fotos propias o con permiso."),
            "source_name": _("Si la noticia viene de otro medio o de un club, cítalo."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sport"].required = True
