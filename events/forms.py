from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Event


class EventSubmitForm(forms.ModelForm):
    """Formulario para que cualquier usuario registrado publique un evento o regata."""

    title = forms.CharField(label=_("Nombre del evento"), max_length=180, min_length=5)
    summary = forms.CharField(
        label=_("Resumen"),
        max_length=280,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 280}),
    )
    description = forms.CharField(
        label=_("Descripción"),
        required=False,
        max_length=10000,
        widget=forms.Textarea(attrs={"rows": 8, "maxlength": 10000}),
        help_text=_("Programa, categorías, horarios, cómo llegar..."),
    )

    class Meta:
        model = Event
        fields = [
            "sport",
            "kind",
            "title",
            "summary",
            "description",
            "start_date",
            "end_date",
            "start_time",
            "venue",
            "city",
            "region",
            "country",
            "distances",
            "organizer",
            "website",
            "registration_url",
            "registration_deadline",
            "cover_image",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "registration_deadline": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", _("La fecha de fin no puede ser anterior a la de inicio."))
        return cleaned
