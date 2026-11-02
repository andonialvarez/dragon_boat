from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    """Permite entrar escribiendo el nombre de usuario o el email."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or password is None:
            return None

        users = UserModel._default_manager.filter(username__iexact=username)
        if not users.exists() and "@" in username:
            users = UserModel._default_manager.filter(email__iexact=username)

        user = users.order_by("id").first()
        if user is None:
            # Igual que ModelBackend: gasta el mismo tiempo para no revelar si existe.
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
