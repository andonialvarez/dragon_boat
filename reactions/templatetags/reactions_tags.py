from django import template

from reactions.utils import summary_for, target_key

register = template.Library()


@register.inclusion_tag("reactions/bar.html", takes_context=True)
def reaction_bar(context, obj, compact=False):
    request = context.get("request")
    user = getattr(request, "user", None)
    key = target_key(obj)
    anchor = {"noticia": "reacciones", "comentario": f"comentario-{obj.pk}", "mensaje": f"mensaje-{obj.pk}"}.get(key, "")
    next_url = request.get_full_path() if request else ""
    if anchor:
        next_url = f"{next_url}#{anchor}"
    return {
        "obj": obj,
        "target": key,
        "reactions": summary_for(obj, user),
        "request": request,
        "user": user,
        "compact": compact,
        "next_url": next_url,
    }
