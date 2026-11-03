from django.urls import path

from . import api, views
from .feeds import LatestArticlesFeed

urlpatterns = [
    path("", views.ArticleListView.as_view(), name="article_list"),
    path("rss/", LatestArticlesFeed(), name="article_feed"),
    path("publicar/", views.article_create, name="article_create"),
    path("comentarios/<int:pk>/editar/", views.edit_comment, name="comment_edit"),
    path("comentarios/<int:pk>/borrar/", views.delete_comment, name="comment_delete"),
    path("<slug:slug>/", views.ArticleDetailView.as_view(), name="article_detail"),
    path("<slug:slug>/comentar/", views.add_comment, name="comment_add"),
    path("<slug:slug>/editar/", views.article_edit, name="article_edit"),
    path("<slug:slug>/borrar/", views.article_delete, name="article_delete"),
]

api_urlpatterns = [
    path("noticias/", api.create_article, name="api_article_create"),
    path("noticias/importar/", api.run_import, name="api_run_import"),
    path("noticias/imagenes/", api.fill_images, name="api_fill_images"),
]
