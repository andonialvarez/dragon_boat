from django.urls import path

from . import views

urlpatterns = [
    path("<slug:target>/<int:pk>/<slug:kind>/", views.toggle_reaction, name="toggle_reaction"),
]
