from django.contrib import admin

from .models import Sport


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "propulsion", "is_primary", "order")
    list_display_links = ("name",)
    list_editable = ("order",)
    fieldsets = (
        (None, {"fields": ("name", "slug", "icon", "color", "propulsion", "is_primary", "order")}),
        ("Descripción", {"fields": ("tagline", "description", "crew", "distances", "governing_bodies")}),
    )


class SampleListFilter(admin.SimpleListFilter):
    title = "datos de ejemplo"
    parameter_name = "ejemplo"

    def lookups(self, request, model_admin):
        return (("si", "Solo ejemplos"), ("no", "Solo datos reales"))

    def queryset(self, request, queryset):
        if self.value() == "si":
            return queryset.filter(is_sample=True)
        if self.value() == "no":
            return queryset.filter(is_sample=False)
        return queryset
