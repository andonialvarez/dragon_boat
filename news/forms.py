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


class TipForm(forms.Form):
    """Primer paso del buzón: un enlace o un documento."""

    url = forms.URLField(
        label=_("Enlace a la noticia"),
        required=False,
        max_length=600,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://…", "inputmode": "url", "autocomplete": "off"}),
    )
    document = forms.FileField(
        label=_("…o un documento"),
        required=False,
        help_text=_("PDF, Word (.docx), OpenDocument (.odt) o texto. Por ejemplo, la nota de prensa de tu club."),
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.docx,.odt,.txt,.md"}),
    )
    comment = forms.CharField(
        label=_("Comentario (opcional)"),
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 500, "placeholder": _("Algo que debamos saber de esta noticia")}),
    )

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        if data.get("url") and data.get("document"):
            raise forms.ValidationError(_("Manda un enlace o un documento, no los dos a la vez."))
        if not data.get("url") and not data.get("document"):
            raise forms.ValidationError(_("Pega un enlace o elige un documento."))
        return data


class TipPublishForm(forms.Form):
    """Segundo paso del buzón: revisar lo que ha encontrado la web y publicar."""

    sport = forms.ModelChoiceField(label=_("Deporte"), queryset=None)
    category = forms.ChoiceField(label=_("Sección"), choices=Article.Category.choices)
    title = forms.CharField(label=_("Título"), max_length=200, min_length=8)
    summary = forms.CharField(
        label=_("Entradilla"),
        max_length=320,
        min_length=20,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 320}),
        help_text=_("Una o dos frases que resuman la noticia."),
    )
    body = forms.CharField(
        label=_("Texto"),
        min_length=40,
        max_length=20000,
        widget=forms.Textarea(attrs={"rows": 12, "maxlength": 20000}),
        help_text=_("Repásalo: el texto sale del documento y a veces se cuela algún salto de línea raro."),
    )
    source_name = forms.CharField(label=_("Medio o club"), max_length=120, required=False)

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import Sport

        self.fields["sport"].queryset = Sport.objects.all()
        if kind == "enlace":
            del self.fields["body"]
            self.fields["source_name"].required = True
            self.fields["source_name"].help_text = _("El medio que publica la noticia. Se cita siempre.")
        else:
            self.fields["source_name"].label = _("Autor o club (opcional)")
            self.fields["source_name"].help_text = _("Quién firma el documento, si no eres tú.")
