from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.forum_index, name="index"),
    path("tema/<int:pk>/", views.topic_detail, name="topic_short"),
    path("tema/<int:pk>-<slug:slug>/", views.topic_detail, name="topic"),
    path("tema/<int:pk>/responder/", views.reply, name="reply"),
    path("mensaje/<int:pk>/editar/", views.edit_post, name="post_edit"),
    path("mensaje/<int:pk>/borrar/", views.delete_post, name="post_delete"),
    path("<slug:slug>/", views.category_detail, name="category"),
    path("<slug:slug>/nuevo-tema/", views.new_topic, name="new_topic"),
]
