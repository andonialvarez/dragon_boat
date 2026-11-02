from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Profile

User = get_user_model()


def _rules_label():
    return format_html(
        _('Acepto las <a href="{}" target="_blank">normas de la comunidad</a> y la '
          '<a href="{}" target="_blank">política de privacidad</a>.'),
        reverse("rules"),
        reverse("privacy"),
    )


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        label=_("Email"),
        help_text=_("No se mostrará en la web. Sirve para recuperar la contraseña."),
    )
    accept_rules = forms.BooleanField(
        required=True,
        error_messages={"required": _("Tienes que aceptar las normas para registrarte.")},
    )
    # Campo trampa: las personas no lo ven; los robots de spam suelen rellenarlo.
    website = forms.CharField(required=False, label="", widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
        labels = {"username": _("Nombre de usuario")}
        help_texts = {
            "username": _("Es el nombre que verá la gente en el foro y en los comentarios. Letras, números y @ . + - _"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["accept_rules"].label = _rules_label()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Ya hay una cuenta con este email. ¿Has olvidado la contraseña?"))
        return email

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError(_("No se ha podido completar el registro."))
        return ""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Usuario o email"),
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["club", "city", "favorite_sport", "bio"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4, "maxlength": 600})}


class AccountEmailForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email"]
        labels = {"email": _("Email")}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if not email:
            raise forms.ValidationError(_("El email es obligatorio."))
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Ya hay otra cuenta con este email."))
        return email
