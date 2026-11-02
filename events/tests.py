from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Sport

from .models import Event

User = get_user_model()
PASSWORD = "remo-y-pala-2026"


def event_form_data(**overrides):
    start = timezone.localdate() + timedelta(days=20)
    data = {
        "sport": Sport.objects.get(slug="dragon-boat").pk,
        "kind": Event.Kind.REGATTA,
        "title": "Regata popular de prueba",
        "summary": "Regata abierta a todos los clubes.",
        "description": "Programa completo de la regata.",
        "start_date": start.isoformat(),
        "end_date": "",
        "start_time": "10:30",
        "venue": "Dársena",
        "city": "Bilbao",
        "region": "Bizkaia",
        "country": "España",
        "distances": "200 m",
        "organizer": "Club de prueba",
        "website": "",
        "registration_url": "",
        "registration_deadline": "",
    }
    data.update(overrides)
    return data


def make_event(title, start_date, sport="dragon-boat", **fields):
    return Event.objects.create(title=title, start_date=start_date, sport=Sport.objects.get(slug=sport), **fields)


class EventListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        today = timezone.localdate()
        cls.upcoming = make_event(title="Regata que viene", start_date=today + timedelta(days=3))
        cls.ongoing = make_event(
            title="Festival en marcha", start_date=today - timedelta(days=1), end_date=today + timedelta(days=1)
        )
        cls.past = make_event(title="Regata pasada", start_date=today - timedelta(days=10))
        cls.hidden = make_event(title="Evento sin revisar", start_date=today + timedelta(days=4), is_published=False)

    def test_upcoming_and_past(self):
        upcoming = self.client.get(reverse("event_list"))
        self.assertContains(upcoming, "Regata que viene")
        self.assertContains(upcoming, "Festival en marcha")
        self.assertNotContains(upcoming, "Regata pasada")
        self.assertNotContains(upcoming, "Evento sin revisar")
        past = self.client.get(reverse("event_list"), {"ver": "pasados"})
        self.assertContains(past, "Regata pasada")
        self.assertNotContains(past, "Regata que viene")

    def test_filter_by_sport(self):
        Event.objects.filter(pk=self.upcoming.pk).update(sport=Sport.objects.get(slug="traineras"))
        response = self.client.get(reverse("event_list"), {"deporte": "traineras"})
        self.assertContains(response, "Regata que viene")
        self.assertNotContains(response, "Festival en marcha")

    def test_unpublished_event_is_hidden(self):
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)


class CalendarExportTests(TestCase):
    def test_single_day_with_time(self):
        event = make_event(
            title="Regata, con comas; y punto y coma",
            start_date=date(2030, 6, 15),
            start_time=time(10, 0),
            city="Bilbao",
        )
        response = self.client.get(reverse("event_ics", args=[event.slug]))
        self.assertEqual(response["Content-Type"], "text/calendar; charset=utf-8")
        body = response.content.decode()
        self.assertIn("BEGIN:VEVENT", body)
        self.assertIn("DTSTART:20300615T080000Z", body)  # 10:00 en Madrid (verano) = 08:00 UTC
        self.assertIn(r"SUMMARY:Regata\, con comas\; y punto y coma", body)
        self.assertTrue(body.endswith("\r\n"))

    def test_multi_day_is_all_day(self):
        event = make_event(title="Campeonato de tres días", start_date=date(2030, 7, 1), end_date=date(2030, 7, 3))
        body = self.client.get(reverse("event_ics", args=[event.slug])).content.decode()
        self.assertIn("DTSTART;VALUE=DATE:20300701", body)
        self.assertIn("DTEND;VALUE=DATE:20300704", body)


class EventPublishingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("organiza", "organiza@example.com", PASSWORD)
        cls.other = User.objects.create_user("curiosa", "curiosa@example.com", PASSWORD)

    def test_publishing_requires_login(self):
        response = self.client.get(reverse("event_create"))
        self.assertIn(reverse("login"), response["Location"])

    def test_any_user_can_publish(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("event_create"), event_form_data())
        event = Event.objects.get()
        self.assertRedirects(response, event.get_absolute_url())
        self.assertTrue(event.is_published)
        self.assertEqual(event.created_by, self.user)
        self.assertEqual(event.city, "Bilbao")

    def test_end_date_before_start_is_rejected(self):
        self.client.force_login(self.user)
        start = timezone.localdate() + timedelta(days=20)
        data = event_form_data(start_date=start.isoformat(), end_date=(start - timedelta(days=1)).isoformat())
        response = self.client.post(reverse("event_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Event.objects.exists())

    @override_settings(COMMUNITY_REQUIRES_APPROVAL=True)
    def test_approval_mode(self):
        self.client.force_login(self.user)
        self.client.post(reverse("event_create"), event_form_data())
        event = Event.objects.get()
        self.assertFalse(event.is_published)
        self.assertEqual(self.client.get(event.get_absolute_url()).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(event.get_absolute_url()).status_code, 404)

    def test_only_creator_can_edit_or_delete(self):
        event = make_event(title="Evento ajeno", start_date=timezone.localdate(), created_by=self.user)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("event_edit", args=[event.slug])).status_code, 403)
        self.assertEqual(self.client.post(reverse("event_delete", args=[event.slug])).status_code, 403)
        self.client.force_login(self.user)
        self.client.post(reverse("event_edit", args=[event.slug]), event_form_data(title="Evento corregido"))
        event.refresh_from_db()
        self.assertEqual(event.title, "Evento corregido")
        self.client.post(reverse("event_delete", args=[event.slug]))
        self.assertFalse(Event.objects.exists())
