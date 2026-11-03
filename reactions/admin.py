from django.contrib import admin

from .models import Reaction


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "content_type", "object_id", "created_at")
    list_filter = ("kind", "content_type")
    search_fields = ("user__username",)
    raw_id_fields = ("user",)
    date_hierarchy = "created_at"
