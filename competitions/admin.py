from django.contrib import admin

from core.admin import SampleListFilter

from .models import Championship, Division, Standing, Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "region", "country", "founded_year", "is_sample")
    list_filter = ("sports", "country", SampleListFilter)
    search_fields = ("name", "short_name", "city", "region")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("sports",)


class DivisionInline(admin.TabularInline):
    model = Division
    extra = 1
    fields = ("name", "notes", "order")
    show_change_link = True


class StandingInline(admin.TabularInline):
    model = Standing
    extra = 3
    fields = ("position", "team", "points", "result_time", "notes")
    autocomplete_fields = ("team",)


@admin.register(Championship)
class ChampionshipAdmin(admin.ModelAdmin):
    list_display = ("name", "sport", "season", "scope", "start_date", "is_featured", "is_sample")
    list_filter = ("sport", "season", "scope", "is_featured", SampleListFilter)
    search_fields = ("name", "organizer", "location")
    inlines = [DivisionInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "sport", "season", "scope", "description", "cover_image")}),
        ("Organización", {"fields": ("organizer", "location", ("start_date", "end_date"))}),
        ("Portada", {"fields": ("is_featured", "is_sample")}),
    )


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    """Aquí se rellena la clasificación de cada categoría (puesto, equipo, puntos, tiempo)."""

    list_display = ("name", "championship", "order")
    list_filter = ("championship__sport", "championship__season")
    search_fields = ("name", "championship__name")
    autocomplete_fields = ("championship",)
    inlines = [StandingInline]
