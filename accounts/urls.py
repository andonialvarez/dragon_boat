from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import LoginForm

urlpatterns = [
    path("registro/", views.signup, name="signup"),
    path(
        "entrar/",
        auth_views.LoginView.as_view(authentication_form=LoginForm, redirect_authenticated_user=True),
        name="login",
    ),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("perfil/", views.profile_edit, name="profile_edit"),
    path(
        "contrasena/cambiar/",
        auth_views.PasswordChangeView.as_view(success_url=reverse_lazy("password_change_done")),
        name="password_change",
    ),
    path("contrasena/cambiada/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path(
        "contrasena/recuperar/",
        auth_views.PasswordResetView.as_view(
            success_url=reverse_lazy("password_reset_done"),
            extra_email_context={"site_name": settings.SITE_NAME},
        ),
        name="password_reset",
    ),
    path("contrasena/recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "contrasena/nueva/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(success_url=reverse_lazy("password_reset_complete")),
        name="password_reset_confirm",
    ),
    path("contrasena/lista/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
