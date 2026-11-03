from django.contrib import admin

from core.admin import SampleListFilter

from .models import Category, Post, Topic


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "sport", "order")
    list_display_links = ("name",)
    list_editable = ("order",)


class PostInline(admin.TabularInline):
    model = Post
    extra = 0
    fields = ("author", "body", "created_at", "is_hidden", "is_deleted")
    readonly_fields = ("author", "created_at")
    show_change_link = True


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "last_activity_at", "is_pinned", "is_locked", "is_sample")
    list_filter = ("category", "is_pinned", "is_locked", SampleListFilter)
    list_editable = ("is_pinned", "is_locked")
    search_fields = ("title", "author__username")
    raw_id_fields = ("author",)
    inlines = [PostInline]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("short_body", "author", "topic", "created_at", "is_hidden", "is_deleted")
    list_filter = ("is_hidden", "is_deleted", "topic__category", SampleListFilter)
    search_fields = ("body", "author__username", "topic__title")
    raw_id_fields = ("topic", "author")
    date_hierarchy = "created_at"
    actions = ["hide", "unhide"]

    @admin.display(description="Mensaje")
    def short_body(self, obj):
        return (obj.body[:80] + "…") if len(obj.body) > 80 else obj.body or "—"

    @admin.action(description="Ocultar (moderación)")
    def hide(self, request, queryset):
        queryset.update(is_hidden=True)

    @admin.action(description="Volver a mostrar")
    def unhide(self, request, queryset):
        queryset.update(is_hidden=False)
