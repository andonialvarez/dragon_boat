from django.contrib import admin, messages

from core.admin import SampleListFilter

from .models import Article, Comment, NewsSource


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "sport", "origin", "status", "published_at", "author", "is_featured", "is_sample")
    list_filter = ("status", "origin", "sport", "category", "is_featured", SampleListFilter)
    search_fields = ("title", "summary", "author__username")
    date_hierarchy = "published_at"
    autocomplete_fields = ("related_event", "related_championship")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("author",)
    actions = ["publish", "unpublish"]
    fieldsets = (
        (None, {"fields": ("title", "slug", "summary", "body")}),
        ("Imagen", {"fields": ("cover_image", "image_caption", "image_url")}),
        ("Clasificación", {"fields": ("sport", "category", "related_event", "related_championship")}),
        ("Publicación", {"fields": ("status", "origin", "published_at", "is_featured", "allow_comments", "is_sample")}),
        ("Fuente", {"fields": ("source_name", "source_url"), "classes": ("collapse",)}),
        ("Registro", {"fields": ("author", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Publicar (aprobar) las noticias seleccionadas")
    def publish(self, request, queryset):
        updated = queryset.exclude(status=Article.Status.PUBLISHED).update(status=Article.Status.PUBLISHED)
        self.message_user(request, f"{updated} noticia(s) publicada(s).", messages.SUCCESS)

    @admin.action(description="Pasar a borrador")
    def unpublish(self, request, queryset):
        updated = queryset.update(status=Article.Status.DRAFT)
        self.message_user(request, f"{updated} noticia(s) pasada(s) a borrador.", messages.SUCCESS)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("short_body", "author", "article", "created_at", "is_hidden", "is_deleted")
    list_filter = ("is_hidden", "is_deleted", SampleListFilter)
    search_fields = ("body", "author__username", "article__title")
    raw_id_fields = ("article", "author", "parent")
    date_hierarchy = "created_at"
    actions = ["hide", "unhide"]

    @admin.display(description="Comentario")
    def short_body(self, obj):
        return (obj.body[:80] + "…") if len(obj.body) > 80 else obj.body or "—"

    @admin.action(description="Ocultar (moderación)")
    def hide(self, request, queryset):
        queryset.update(is_hidden=True)

    @admin.action(description="Volver a mostrar")
    def unhide(self, request, queryset):
        queryset.update(is_hidden=False)


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "sport", "is_active", "last_checked_at", "has_error")
    list_filter = ("is_active", "sport")
    search_fields = ("name", "feed_url")
    actions = ["import_now"]

    @admin.display(boolean=True, description="Error")
    def has_error(self, obj):
        return bool(obj.last_error)

    @admin.action(description="Importar ahora de las fuentes seleccionadas")
    def import_now(self, request, queryset):
        from .importer import import_from_sources

        report = import_from_sources(queryset)
        self.message_user(request, report.summary(), messages.WARNING if report.errors else messages.SUCCESS)
