from django.contrib.auth.views import redirect_to_login
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from core.utils import safe_next_url

from .models import Reaction
from .utils import attach_reactions, target_model


def wants_json(request):
    return request.headers.get("x-requested-with") == "fetch" or "application/json" in request.headers.get(
        "accept", ""
    )


def is_reactable(obj):
    """No se reacciona a contenido oculto, borrado o sin publicar."""
    if getattr(obj, "is_hidden", False) or getattr(obj, "is_deleted", False):
        return False
    if hasattr(obj, "is_published"):
        return obj.is_published
    if hasattr(obj, "article"):
        return obj.article.is_published
    return True


@require_POST
def toggle_reaction(request, target, pk, kind):
    model = target_model(target)
    if model is None or kind not in Reaction.Kind.values:
        raise Http404
    obj = get_object_or_404(model, pk=pk)
    if not is_reactable(obj):
        raise Http404

    fallback = obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else "/"
    next_url = safe_next_url(request, request.POST.get("next"), fallback)

    if not request.user.is_authenticated:
        if wants_json(request):
            login_url = f"{reverse('login')}?{urlencode({'next': next_url})}"
            return JsonResponse({"login_required": True, "login_url": login_url}, status=401)
        return redirect_to_login(next_url)

    content_type = ContentType.objects.get_for_model(model)
    lookup = {"user": request.user, "content_type": content_type, "object_id": obj.pk, "kind": kind}
    deleted, _ = Reaction.objects.filter(**lookup).delete()
    if not deleted:
        try:
            with transaction.atomic():
                Reaction.objects.create(**lookup)
        except IntegrityError:
            pass  # Doble clic muy rápido: la reacción ya existe.

    if wants_json(request):
        attach_reactions([obj], request.user)
        return JsonResponse({"reactions": obj.reaction_summary})
    return redirect(next_url)
