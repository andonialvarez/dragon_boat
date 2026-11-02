from django.urls import path

from . import views

urlpatterns = [
    path("", views.EventListView.as_view(), name="event_list"),
    path("publicar/", views.event_create, name="event_create"),
    path("<slug:slug>/", views.EventDetailView.as_view(), name="event_detail"),
    path("<slug:slug>/calendario.ics", views.event_ics, name="event_ics"),
    path("<slug:slug>/editar/", views.event_edit, name="event_edit"),
    path("<slug:slug>/borrar/", views.event_delete, name="event_delete"),
]
