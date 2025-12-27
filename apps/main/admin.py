from django.contrib import admin
from apps.main.models import PickupPoint, CabinetProfile, Parcel, SiteSettings

# Регистрация SiteSettings
@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at", "default_dark_mode")
    list_filter = ("default_dark_mode", "updated_at")  # Фильтр по состоянию темной темы и дате обновления

    def has_add_permission(self, request):
        # Разрешаем создать только одну запись
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)

# Регистрация CabinetProfile
@admin.register(CabinetProfile)
class CabinetProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "phone", "pickup_point", 'is_employee')
    list_filter = ("is_employee", "pickup_point")  # Фильтр по сотрудникам и пунктам выдачи

# Регистрация PickupPoint
admin.site.register(PickupPoint)

# Регистрация Parcel
@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ("track_number", "user", "status", "created_at")
    list_filter = ("status", "user", "created_at")  # Фильтр по статусу, пользователю и дате создания
    search_fields = ("track_number",)  # Фильтрация по трек-номеру

