from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from core.models import Sport
from events.models import Event

from .models import Championship, Division, Standing, Team


class ChampionshipListView(ListView):
    template_name = "competitions/championship_list.html"
    context_object_name = "championships"
    paginate_by = 20
    page_kwarg = "pagina"

    def get_queryset(self):
        queryset = Championship.objects.select_related("sport").annotate(
            team_count=Count("divisions__standings__team", distinct=True)
        )
        self.sport = None
        sport_slug = self.request.GET.get("deporte")
        if sport_slug:
            self.sport = get_object_or_404(Sport, slug=sport_slug)
            queryset = queryset.filter(sport=self.sport)
        self.season = self.request.GET.get("temporada", "")
        if self.season.isdigit():
            queryset = queryset.filter(season=int(self.season))
        else:
            self.season = ""
        return queryset.current_first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "current_sport": self.sport,
                "current_season": self.season,
                "seasons": Championship.objects.order_by("-season").values_list("season", flat=True).distinct(),
            }
        )
        return context


class ChampionshipDetailView(DetailView):
    model = Championship
    template_name = "competitions/championship_detail.html"
    context_object_name = "championship"

    def get_queryset(self):
        standings = Standing.objects.select_related("team").order_by("position", "id")
        divisions = Division.objects.prefetch_related(Prefetch("standings", queryset=standings))
        return Championship.objects.select_related("sport").prefetch_related(Prefetch("divisions", queryset=divisions))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        championship = self.object
        context["teams"] = championship.participating_teams()
        context["events"] = championship.events.filter(is_published=True).select_related("sport").order_by("start_date")
        context["articles"] = championship.articles.published()[:4]
        return context


class TeamListView(ListView):
    template_name = "competitions/team_list.html"
    context_object_name = "teams"
    paginate_by = 24
    page_kwarg = "pagina"

    def get_queryset(self):
        queryset = Team.objects.prefetch_related("sports")
        self.sport = None
        sport_slug = self.request.GET.get("deporte")
        if sport_slug:
            self.sport = get_object_or_404(Sport, slug=sport_slug)
            queryset = queryset.filter(sports=self.sport)
        self.query = self.request.GET.get("q", "").strip()
        if self.query:
            queryset = queryset.filter(
                Q(name__icontains=self.query)
                | Q(city__icontains=self.query)
                | Q(region__icontains=self.query)
                | Q(country__icontains=self.query)
            )
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"current_sport": self.sport, "query": self.query})
        return context


class TeamDetailView(DetailView):
    model = Team
    template_name = "competitions/team_detail.html"
    context_object_name = "team"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object
        context["results"] = (
            team.standings.select_related("division__championship__sport")
            .order_by("-division__championship__season", "division__championship__name", "division__order")
        )
        context["upcoming_events"] = Event.objects.upcoming().filter(participants=team).select_related("sport")
        return context
