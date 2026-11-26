from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class RedirectToNewAddressMiddleware:
    """Si la variable REDIRIGIR_A tiene una dirección, todas las visitas van allí.

    Sirve para que la dirección antigua de la web siga funcionando tras mudarla:
    https://vieja.onrender.com/noticias/x/ lleva a https://nueva.onrender.com/noticias/x/.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.target = settings.REDIRECT_TO

    def __call__(self, request):
        if self.target:
            return HttpResponsePermanentRedirect(self.target + request.get_full_path())
        return self.get_response(request)
