from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic import DetailView, ListView

from core.community import can_manage, over_daily_limit, requires_approval
from core.models import Sport

from .forms import EventSubmitForm
from .models import Event


class EventListView(ListView):
    template_name = "events/event_list.html"
    context_object_name = "events"
    paginate_by = 20
    page_kwarg = "pagina"

    def get_queryset(self):
        self.show_past = self.request.GET.get("ver") == "pasados"
        queryset = Event.objects.past() if self.show_past else Event.objects.upcoming()
        self.sport = None
        sport_slug = self.request.GET.get("deporte")
        if sport_slug:
            self.sport = get_object_or_404(Sport, slug=sport_slug)
            queryset = queryset.filter(sport=self.sport)
        return queryset.select_related("sport", "championship")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"show_past": self.show_past, "current_sport": self.sport})
        return context


class EventDetailView(DetailView):
    model = Event
    template_name = "events/event_detail.html"
    context_object_name = "event"

    def get_queryset(self):
        queryset = Event.objects.select_related("sport", "championship", "created_by")
        user = self.request.user
        if user.is_staff:
            return queryset
        if user.is_authenticated:
            return queryset.filter(Q(is_published=True) | Q(created_by=user))
        return queryset.visible()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        context["can_manage"] = can_manage(self.request.user, event.created_by_id)
        context["participants"] = event.participants.all().prefetch_related("sports")
        context["articles"] = event.articles.published()[:4]
        context["more_events"] = (
            Event.objects.upcoming().filter(sport=event.sport).exclude(pk=event.pk).select_related("sport")[:3]
        )
        return context


def _ics_escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line):
    """Las líneas de un .ics no deben pasar de 75 octetos."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        char_bytes = char.encode("utf-8")
        if len(current) + len(char_bytes) > (75 if not parts else 74):
            parts.append(current.decode("utf-8"))
            current = b""
        current += char_bytes
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def event_ics(request, slug):
    """Descarga el evento en formato calendario (Google Calendar, Outlook, iPhone...)."""
    event = get_object_or_404(Event.objects.visible(), slug=slug)
    url = request.build_absolute_uri(event.get_absolute_url())
    stamp = timezone.now().astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if event.start_time and not event.is_multiday:
        start = timezone.make_aware(datetime.combine(event.start_date, event.start_time))
        end = start + timedelta(hours=3)
        date_lines = [
            f"DTSTART:{start.astimezone(dt_timezone.utc):%Y%m%dT%H%M%SZ}",
            f"DTEND:{end.astimezone(dt_timezone.utc):%Y%m%dT%H%M%SZ}",
        ]
    else:
        last_day = event.last_day + timedelta(days=1)  # DTEND de día completo no se incluye.
        date_lines = [
            f"DTSTART;VALUE=DATE:{event.start_date:%Y%m%d}",
            f"DTEND;VALUE=DATE:{last_day:%Y%m%d}",
        ]

    description = event.summary or event.description[:500]
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{_ics_escape(settings.SITE_NAME)}//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:evento-{event.pk}@{request.get_host()}",
        f"DTSTAMP:{stamp}",
        *date_lines,
        f"SUMMARY:{_ics_escape(event.title)}",
        f"LOCATION:{_ics_escape(event.place or event.city)}",
        f"DESCRIPTION:{_ics_escape(description + chr(10) + chr(10) + url)}",
        f"URL:{url}",
        "STATUS:CANCELLED" if event.status == Event.Status.CANCELLED else "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    body = "\r\n".join(_fold(line) for line in lines) + "\r\n"
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{event.slug}.ics"'
    return response


@login_required
def event_create(request):
    if over_daily_limit(request.user):
        messages.error(request, _("Has llegado al límite de publicaciones de hoy. Vuelve a intentarlo mañana."))
        return redirect("event_list")
    form = EventSubmitForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        event.created_by = request.user
        event.is_published = not requires_approval(request.user)
        event.save()
        form.save_m2m()
        if event.is_published:
            messages.success(request, _("¡Evento publicado!"))
        else:
            messages.success(request, _("¡Gracias! El evento se publicará cuando lo revise el equipo."))
        return redirect(event)
    return render(request, "events/event_form.html", {"form": form, "is_new": True})


def _manageable_event(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if not can_manage(request.user, event.created_by_id):
        raise PermissionDenied
    return event


@login_required
def event_edit(request, slug):
    event = _manageable_event(request, slug)
    form = EventSubmitForm(request.POST or None, request.FILES or None, instance=event)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Evento actualizado."))
        return redirect(event)
    return render(request, "events/event_form.html", {"form": form, "event": event, "is_new": False})


@login_required
def event_delete(request, slug):
    event = _manageable_event(request, slug)
    if request.method == "POST":
        event.delete()
        messages.success(request, _("Evento borrado."))
        return redirect("event_list")
    return render(request, "events/event_confirm_delete.html", {"event": event})
