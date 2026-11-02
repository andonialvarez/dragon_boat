from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from competitions.models import Championship, Division, Standing, Team
from events.models import Event
from forum.models import Topic
from forum.views import topics_with_stats
from news.models import Article

from .models import Sport


def home(request):
    articles = list(
        Article.objects.published()
        .select_related("sport")
        .annotate(comment_count=Count("comments", filter=Q(comments__is_hidden=False, comments__is_deleted=False)))
        .order_by("-is_featured", "-published_at")[:7]
    )
    # La destacada va arriba; el resto, por fecha.
    lead = articles[0] if articles else None
    latest = sorted(articles[1:], key=lambda a: a.published_at, reverse=True)

    standings = Standing.objects.select_related("team").order_by("position")
    featured_championship = (
        Championship.objects.filter(divisions__standings__isnull=False)
        .select_related("sport")
        .prefetch_related(Prefetch("divisions", queryset=Division.objects.prefetch_related(Prefetch("standings", queryset=standings))))
        .order_by("-is_featured", "-season", "-start_date")
        .distinct()
        .first()
    )
    featured_division = None
    if featured_championship:
        featured_division = next((d for d in featured_championship.divisions.all() if d.standings.all()), None)

    context = {
        "lead": lead,
        "latest": latest,
        "upcoming_events": Event.objects.upcoming().select_related("sport")[:5],
        "featured_championship": featured_championship,
        "featured_division": featured_division,
        "recent_topics": topics_with_stats(Topic.objects.order_by("-last_activity_at"))[:5],
        "sports": Sport.objects.annotate(team_count=Count("teams", distinct=True)),
        "stats": {
            "teams": Team.objects.count(),
            "events": Event.objects.upcoming().count(),
            "championships": Championship.objects.count(),
        },
    }
    return render(request, "core/home.html", context)


def sport_list(request):
    sports = Sport.objects.annotate(
        team_count=Count("teams", distinct=True),
        championship_count=Count("championships", distinct=True),
    )
    return render(request, "core/sport_list.html", {"sports": sports})


def sport_detail(request, slug):
    sport = get_object_or_404(Sport, slug=slug)
    return render(
        request,
        "core/sport_detail.html",
        {
            "sport": sport,
            "articles": Article.objects.published().filter(sport=sport).select_related("sport")[:4],
            "events": Event.objects.upcoming().filter(sport=sport).select_related("sport")[:5],
            "championships": Championship.objects.filter(sport=sport).current_first()[:5],
            "teams": sport.teams.all()[:12],
            "forum_categories": sport.forum_categories.all(),
        },
    )


def search(request):
    query = request.GET.get("q", "").strip()
    results = {}
    if len(query) >= 2:
        results = {
            "articles": Article.objects.published()
            .filter(Q(title__icontains=query) | Q(summary__icontains=query) | Q(body__icontains=query))
            .select_related("sport")[:10],
            "events": Event.objects.visible()
            .filter(Q(title__icontains=query) | Q(city__icontains=query) | Q(description__icontains=query))
            .select_related("sport")
            .order_by("-start_date")[:10],
            "championships": Championship.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            ).select_related("sport")[:10],
            "teams": Team.objects.filter(
                Q(name__icontains=query) | Q(city__icontains=query) | Q(region__icontains=query)
            )[:10],
            "topics": Topic.objects.filter(
                Q(title__icontains=query)
                | Q(posts__body__icontains=query, posts__is_hidden=False, posts__is_deleted=False)
            )
            .select_related("category")
            .distinct()
            .order_by("-last_activity_at")[:10],
        }
    total = sum(len(items) for items in results.values())
    return render(request, "core/search.html", {"query": query, "results": results, "total": total})


def about(request):
    return render(request, "core/about.html")


def rules(request):
    return render(request, "core/rules.html")


def privacy(request):
    return render(request, "core/privacy.html")


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /cuentas/",
        "Disallow: /reacciones/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def error_404(request, exception):
    return render(request, "404.html", status=404)


def error_500(request):
    # Sin contexto ni base de datos: si algo grave falla, esta página debe salir igual.
    from django.template import loader

    return HttpResponse(loader.get_template("500.html").render(), status=500)


def error_403(request, exception):
    return render(request, "403.html", status=403)
