from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.static import serve as serve_media

from accounts import views as account_views
from competitions.urls import championship_urls, team_urls
from core import views as core_views
from core.sitemaps import sitemaps
from news.urls import api_urlpatterns

admin.site.site_header = f"{settings.SITE_NAME} · Panel de administración"
admin.site.site_title = f"{settings.SITE_NAME} · Panel"
admin.site.index_title = "Gestión de contenidos"
admin.site.site_url = "/"

urlpatterns = [
    path("", core_views.home, name="home"),
    path("noticias/", include("news.urls")),
    path("eventos/", include("events.urls")),
    path("campeonatos/", include(championship_urls)),
    path("equipos/", include(team_urls)),
    path("foro/", include("forum.urls")),
    path("deportes/", core_views.sport_list, name="sport_list"),
    path("deportes/<slug:slug>/", core_views.sport_detail, name="sport_detail"),
    path("buscar/", core_views.search, name="search"),
    path("acerca/", core_views.about, name="about"),
    path("normas/", core_views.rules, name="rules"),
    path("privacidad/", core_views.privacy, name="privacy"),
    path("cuentas/", include("accounts.urls")),
    path("usuarios/<str:username>/", account_views.profile_detail, name="profile_detail"),
    path("reacciones/", include("reactions.urls")),
    path("api/", include(api_urlpatterns)),
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
]

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"

# Imágenes subidas. En local las sirve Django; en producción, solo si SERVE_MEDIA=true
# (útil con un disco persistente). Con almacenamiento S3 no hace falta.
if settings.DEBUG or settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve_media, {"document_root": settings.MEDIA_ROOT}),
    ]
