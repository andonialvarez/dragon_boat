from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

PASSWORD = "remo-y-pala-2026"


def signup_data(**overrides):
    data = {
        "username": "palista_nueva",
        "email": "Palista@Example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "accept_rules": "on",
        "website": "",
    }
    data.update(overrides)
    return data


class SignUpTests(TestCase):
    def test_signup_logs_in_without_email_confirmation(self):
        response = self.client.post(reverse("signup"), signup_data())
        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(username="palista_nueva")
        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "palista@example.com")
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_redirects_to_next(self):
        response = self.client.post(reverse("signup") + "?next=/foro/", signup_data(next="/foro/"))
        self.assertRedirects(response, "/foro/")

    def test_signup_ignores_external_next(self):
        response = self.client.post(reverse("signup"), signup_data(next="https://malicioso.example.com/"))
        self.assertRedirects(response, reverse("home"))

    def test_honeypot_blocks_bots(self):
        response = self.client.post(reverse("signup"), signup_data(website="http://spam.example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="palista_nueva").exists())

    def test_rules_must_be_accepted(self):
        data = signup_data()
        del data["accept_rules"]
        self.client.post(reverse("signup"), data)
        self.assertFalse(User.objects.filter(username="palista_nueva").exists())

    def test_duplicate_email_and_username_are_rejected(self):
        User.objects.create_user("Palista_Nueva", "palista@example.com", PASSWORD)
        response = self.client.post(reverse("signup"), signup_data(username="otra_persona"))
        self.assertContains(response, "Ya hay una cuenta con este email")
        response = self.client.post(reverse("signup"), signup_data(email="otra@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("timonel", "timonel@example.com", PASSWORD)

    def test_login_with_username_or_email(self):
        for login in ("timonel", "TIMONEL@example.com"):
            with self.subTest(login=login):
                response = self.client.post(reverse("login"), {"username": login, "password": PASSWORD})
                self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
                self.client.logout()

    def test_wrong_password(self):
        response = self.client.post(reverse("login"), {"username": "timonel", "password": "mala"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_is_post_only(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfileTests(TestCase):
    def test_profile_edit_requires_login(self):
        response = self.client.get(reverse("profile_edit"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('profile_edit')}")

    def test_edit_profile(self):
        user = User.objects.create_user("tamborilera", "tambor@example.com", PASSWORD)
        self.client.force_login(user)
        response = self.client.post(
            reverse("profile_edit"),
            {
                "club": "Club de prueba",
                "city": "Bilbao",
                "favorite_sport": "",
                "bio": "Hola",
                "cuenta-email": "nuevo@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.profile.club, "Club de prueba")
        self.assertEqual(user.email, "nuevo@example.com")
        self.assertContains(self.client.get(reverse("profile_detail", args=["tamborilera"])), "Club de prueba")
