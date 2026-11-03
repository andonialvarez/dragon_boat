from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    fields = ("club", "city", "favorite_sport", "bio", "is_sample")


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "email", "is_staff", "is_active", "date_joined", "last_login")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups", "profile__is_sample")
