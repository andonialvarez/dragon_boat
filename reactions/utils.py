"""Reacciones con emoji para noticias, comentarios y mensajes del foro."""

from collections import defaultdict

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from .models import Reaction

# Solo se puede reaccionar a estos modelos. La clave es la que aparece en la URL.
TARGETS = {
    "noticia": "news.Article",
    "comentario": "news.Comment",
    "mensaje": "forum.Post",
}
TARGET_BY_LABEL = {label.lower(): key for key, label in TARGETS.items()}


def target_model(key):
    label = TARGETS.get(key)
    return apps.get_model(label) if label else None


def target_key(obj):
    return TARGET_BY_LABEL.get(obj._meta.label_lower)


def build_summary(counts, mine):
    """Lista de reacciones en orden fijo: [{kind, emoji, label, count, mine}, ...]."""
    return [
        {
            "kind": kind,
            "emoji": Reaction.EMOJI[kind],
            "label": label,
            "count": counts.get(kind, 0),
            "mine": kind in mine,
        }
        for kind, label in Reaction.Kind.choices
    ]


def attach_reactions(objects, user):
    """Calcula las reacciones de varios objetos del mismo modelo con dos consultas.

    Deja el resultado en `obj.reaction_summary`, que es lo que usa la plantilla.
    """
    objects = [obj for obj in objects if obj is not None]
    if not objects:
        return objects
    content_type = ContentType.objects.get_for_model(objects[0])
    ids = [obj.pk for obj in objects]

    counts = defaultdict(dict)
    rows = (
        Reaction.objects.filter(content_type=content_type, object_id__in=ids)
        .values("object_id", "kind")
        .annotate(total=Count("id"))
    )
    for row in rows:
        counts[row["object_id"]][row["kind"]] = row["total"]

    mine = defaultdict(set)
    if user is not None and user.is_authenticated:
        for object_id, kind in Reaction.objects.filter(
            content_type=content_type, object_id__in=ids, user=user
        ).values_list("object_id", "kind"):
            mine[object_id].add(kind)

    for obj in objects:
        obj.reaction_summary = build_summary(counts[obj.pk], mine[obj.pk])
    return objects


def summary_for(obj, user):
    if not hasattr(obj, "reaction_summary"):
        attach_reactions([obj], user)
    return obj.reaction_summary
