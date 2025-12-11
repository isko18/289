from .models import SiteSettings


def site_settings(request):
    """
    Добавляет в контекст переменную site_settings во все шаблоны.
    """
    settings_obj = SiteSettings.objects.first()
    return {
        "site_settings": settings_obj,
    }
