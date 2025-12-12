from django.urls import path
from apps.main import views

urlpatterns = [
    # Аутентификация
    path("", views.index_redirect, name="index"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),  # важно: /logout/, как в шаблоне

    # Кабинет
    path("cabinet/", views.cabinet_home, name="cabinet_home"),
    path("cabinet/profile/", views.cabinet_profile, name="cabinet_profile"),
    path(
        "cabinet/profile/edit/",
        views.cabinet_profile_edit,
        name="cabinet_edit_profile",
    ),
    path(
        "cabinet/parcel/<int:pk>/history/",
        views.parcel_history_view,
        name="parcel_history",
    ),
    path("staff/parcels/", views.staff_parcels_view, name="staff_parcels"),
    path("cabinet/api/track/public/", views.track_public_lookup_view, name="track_public_lookup"),
    path("cabinet/api/parcels/<int:pk>/history-public/", views.parcel_history_public_view, name="parcel_history_public"),
]
