from django.contrib import admin
from apps.main.models import User, PickupPoint, CabinetProfile, Parcel, SiteSettings
# admin.site.register(User)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at", "default_dark_mode")

    def has_add_permission(self, request):
        # Разрешаем создать только одну запись
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)



@admin.register(CabinetProfile)
class CabinetProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name","user", "phone", "pickup_point", 'is_employee')
    
    
admin.site.register(PickupPoint)
admin.site.register(Parcel)
