from django.contrib import admin
from django.contrib.auth import get_user_model

from apps.main.models import PickupPoint, CabinetProfile, Parcel, SiteSettings, ParcelHistory

User = get_user_model()


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at", "default_dark_mode")
    list_filter = ("default_dark_mode", "updated_at")
    search_fields = ("title",)
    ordering = ("-updated_at",)

    def has_add_permission(self, request):
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(PickupPoint)
class PickupPointAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "address", "phone")
    ordering = ("name",)


@admin.register(CabinetProfile)
class CabinetProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "phone", "pickup_point", "is_employee")
    list_filter = ("is_employee", "pickup_point")
    search_fields = ("full_name", "phone", "user__username", "user__first_name", "user__last_name")
    ordering = ("full_name",)
    raw_id_fields = ("user",)
    autocomplete_fields = ("pickup_point",)


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ("track_number", "user", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("track_number", "user__username", "user__first_name", "user__last_name")
    ordering = ("-created_at",)
    raw_id_fields = ("user",)


@admin.register(ParcelHistory)
class ParcelHistoryAdmin(admin.ModelAdmin):
    list_display = ("parcel", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("parcel__track_number", "message")
    ordering = ("-created_at",)
    raw_id_fields = ("parcel",)
