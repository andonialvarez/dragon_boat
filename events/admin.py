from django.contrib import admin

from core.admin import SampleListFilter

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "sport", "kind", "start_date", "city", "status", "is_published", "created_by", "is_sample")
    list_filter = ("is_published", "sport", "kind", "status", SampleListFilter)
    search_fields = ("title", "city", "region", "venue")
    raw_id_fields = ("created_by",)
    actions = ["publish", "unpublish"]
    date_hierarchy = "start_date"
    filter_horizontal = ("participants",)
    autocomplete_fields = ("championship",)
    fieldsets = (
        (None, {"fields": ("title", "slug", "sport", "kind", "status", "summary", "description", "cover_image")}),
        ("Fecha y lugar", {"fields": (("start_date", "end_date", "start_time"), "venue", ("city", "region", "country"))}),
        ("Competición", {"fields": ("distances", "championship", "participants")}),
        ("Organización e inscripción", {"fields": ("organizer", "website", "registration_url", "registration_deadline")}),
        ("Publicación", {"fields": ("is_published", "created_by", "is_sample")}),
    )

    @admin.action(description="Mostrar en la web (aprobar)")
    def publish(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="Ocultar de la web")
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)
