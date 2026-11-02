from django.urls import path

from . import views

championship_urls = [
    path("", views.ChampionshipListView.as_view(), name="championship_list"),
    path("<slug:slug>/", views.ChampionshipDetailView.as_view(), name="championship_detail"),
]

team_urls = [
    path("", views.TeamListView.as_view(), name="team_list"),
    path("<slug:slug>/", views.TeamDetailView.as_view(), name="team_detail"),
]
