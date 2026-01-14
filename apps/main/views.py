from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import CabinetProfile, PickupPoint, Parcel, track_validator
from apps.main.auto_status import (
    _process_staff_scan,
    _advance_cn_flow,
    _advance_local_flow,
)

User = get_user_model()


def _normalize_phone(phone: str) -> str:
    """
    Превращает '000 000 000' в '+996000000000'
    """
    raw = (phone or "").strip().replace(" ", "")
    if not raw:
        return ""

    if raw.startswith("+996"):
        return raw

    if raw.startswith("996"):
        return f"+{raw}"

    if len(raw) == 9 and raw.isdigit():
        return "+996" + raw

    if not raw.startswith("+"):
        raw = "+" + raw

    return raw


def _normalize_track(track: str) -> str:
    """
    Нормализует трек:
    - убираем пробелы
    - делаем UPPER (чтобы не было дублей ab12 и AB12)
    - проверяем валидатором track_validator
    """
    t = (track or "").strip().replace(" ", "")
    if not t:
        return ""

    t = t.upper()

    max_len = Parcel._meta.get_field("track_number").max_length
    if len(t) > max_len:
        return ""

    try:
        track_validator(t)
    except Exception:
        return ""

    return t


def _dt_str(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _serialize_history(parcel: Parcel):
    """
    Возвращает список событий истории в нужном формате (последнее сверху).
    Если истории нет — отдаём текущее состояние посылки.
    """
    events = []
    rel = getattr(parcel, "history", None)

    if rel is not None:
        for idx, h in enumerate(rel.all().order_by("-occurred_at", "-id")):
            dt = getattr(h, "occurred_at", None) or h.created_at
            events.append(
                {
                    "status_display": h.get_status_display(),
                    "message": (h.message or ""),
                    "datetime": _dt_str(dt),
                    "is_latest": idx == 0,
                }
            )

    if not events:
        created = getattr(parcel, "created_at", None) or timezone.now()
        events.append(
            {
                "status_display": parcel.get_status_display(),
                "message": "",
                "datetime": _dt_str(created),
                "is_latest": True,
            }
        )

    return events


# ================== РЕГИСТРАЦИЯ ==================


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "cabinet_profile", None)
        if profile and profile.is_employee:
            return redirect("staff_parcels")
        return redirect("cabinet_home")

    context = {"form_data": {}, "errors": {}}

    if request.method == "GET":
        return render(request, "register.html", context)

    full_name = request.POST.get("full_name", "").strip()
    phone_input = request.POST.get("phone", "")
    password = request.POST.get("password", "")
    password_confirm = request.POST.get("password_confirm", "")

    phone = _normalize_phone(phone_input)
    errors = {}

    if not full_name:
        errors["full_name"] = "Укажите ФИО."

    if not phone:
        errors["phone"] = "Укажите номер телефона."
    else:
        if User.objects.filter(username=phone).exists():
            errors["phone"] = "Пользователь с таким телефоном уже зарегистрирован."

    if not password or not password_confirm:
        errors["password"] = "Укажите пароль и его подтверждение."
    elif password != password_confirm:
        errors["password"] = "Пароли не совпадают."

    if errors:
        context["errors"] = errors
        context["form_data"] = {"full_name": full_name, "phone": phone_input}
        return render(request, "register.html", context)

    user = User.objects.create_user(username=phone, password=password)
    user.first_name = full_name
    user.save(update_fields=["first_name"])

    CabinetProfile.objects.create(
        user=user,
        full_name=full_name,
        phone=phone,
        is_employee=False,
    )

    login(request, user)
    return redirect("cabinet_home")


# ================== ЛОГИН / ЛОГАУТ ==================


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "cabinet_profile", None)
        if profile and profile.is_employee:
            return redirect("staff_parcels")
        return redirect("cabinet_home")

    context = {"errors": {}, "form_data": {}}

    if request.method == "GET":
        return render(request, "login.html", context)

    phone_input = request.POST.get("phone", "")
    password = request.POST.get("password", "")
    phone = _normalize_phone(phone_input)

    errors = {}
    if not phone:
        errors["phone"] = "Укажите номер телефона."
    if not password:
        errors["password"] = "Укажите пароль."

    user = None
    if not errors:
        user = authenticate(request, username=phone, password=password)
        if user is None:
            errors["non_field"] = "Неверный телефон или пароль."

    if errors or user is None:
        context["errors"] = errors
        context["form_data"] = {"phone": phone_input}
        return render(request, "login.html", context)

    login(request, user)

    profile = getattr(user, "cabinet_profile", None)
    if profile and profile.is_employee:
        return redirect("staff_parcels")
    return redirect("cabinet_home")


def logout_view(request):
    logout(request)
    return redirect("login")


# ================== КАБИНЕТ: ГЛАВНАЯ (КЛИЕНТ) ==================


@login_required
@require_http_methods(["GET", "POST"])
def cabinet_home(request):
    profile = getattr(request.user, "cabinet_profile", None)

    if profile and profile.is_employee:
        return redirect("staff_parcels")

    if request.method == "POST":
        raw_tracks = request.POST.getlist("tracks")
        cleaned = []

        for t in raw_tracks:
            t2 = _normalize_track(t)
            if not t2:
                continue
            cleaned.append(t2)

        cleaned = cleaned[:5]

        for track in cleaned:
            parcel, _ = Parcel.objects.get_or_create(
                track_number=track,
                defaults={"status": Parcel.Status.WAITING_CN},
            )
            if parcel.user_id is None:
                parcel.user = request.user
                parcel.save(update_fields=["user"])

        return redirect("cabinet_home")

    now = timezone.now().replace(microsecond=0)
    pickup = getattr(profile, "pickup_point", None)

    user_parcels_qs = Parcel.objects.filter(user=request.user)

    # авто-обновление статусов перед показом
    for p in user_parcels_qs:
        _advance_cn_flow(p, now)
        _advance_local_flow(p, pickup, now)

    # статистика
    status_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for row in user_parcels_qs.values("status").annotate(c=Count("id")):
        st = row["status"]
        if st in status_counts:
            status_counts[st] = row["c"]

    context = {
        "user_profile": profile,
        "parcels": user_parcels_qs.order_by("-created_at"),
        "status_count_1": status_counts[1],
        "status_count_2": status_counts[2],
        "status_count_3": status_counts[3],
        "status_count_4": status_counts[4],
    }
    return render(request, "cabinet_home.html", context)


# ================== КАБИНЕТ: ПРОФИЛЬ ==================


@login_required
def cabinet_profile(request):
    profile = getattr(request.user, "cabinet_profile", None)
    return render(request, "cabinet_profile.html", {"user_profile": profile})


@login_required
def cabinet_profile_edit(request):
    profile, _ = CabinetProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.first_name or "",
            "phone": request.user.username,
            "is_employee": False,
        },
    )

    pickup_points = PickupPoint.objects.filter(is_active=True).order_by("name")

    if request.method == "GET":
        return render(
            request,
            "cabinet_edit_profile.html",
            {"user_profile": profile, "pickup_points": pickup_points, "errors": {}},
        )

    full_name = request.POST.get("full_name", "").strip()
    phone_input = request.POST.get("phone", "")
    pickup_point_id = request.POST.get("pickup_point", "")

    phone = _normalize_phone(phone_input)
    errors = {}
    pickup_point_obj = None

    if not full_name:
        errors["full_name"] = "Укажите ФИО."

    if not phone:
        errors["phone"] = "Укажите номер телефона."
    else:
        if User.objects.filter(username=phone).exclude(pk=request.user.pk).exists():
            errors["phone"] = "Пользователь с таким телефоном уже зарегистрирован."

    if pickup_point_id:
        try:
            pickup_point_obj = PickupPoint.objects.get(pk=pickup_point_id, is_active=True)
        except PickupPoint.DoesNotExist:
            errors["pickup_point"] = "Неверный пункт выдачи."

    if errors:
        return render(
            request,
            "cabinet_edit_profile.html",
            {
                "user_profile": profile,
                "pickup_points": pickup_points,
                "errors": errors,
                "form_data": {
                    "full_name": full_name,
                    "phone": phone_input,
                    "pickup_point": pickup_point_id,
                },
            },
        )

    request.user.first_name = full_name
    request.user.username = phone
    request.user.save(update_fields=["first_name", "username"])

    profile.full_name = full_name
    profile.phone = phone
    profile.pickup_point = pickup_point_obj
    profile.save(update_fields=["full_name", "phone", "pickup_point"])

    return redirect("cabinet_profile")


# ================== ПАНЕЛЬ СОТРУДНИКА ==================


@login_required
@require_http_methods(["GET", "POST"])
def staff_parcels_view(request):
    profile = getattr(request.user, "cabinet_profile", None)
    if not profile or not profile.is_employee:
        return redirect("cabinet_home")

    error_message = ""
    success_message = ""

    if request.method == "POST":
        track_raw = request.POST.get("track_number", "")
        track = _normalize_track(track_raw)

        if not track:
            error_message = "Укажите корректный трек-номер."
        else:
            try:
                success_message = _process_staff_scan(request.user, track)
            except ValueError as e:
                error_message = str(e)
            except Exception:
                error_message = "Ошибка обработки трек-номера."

    recent_parcels = Parcel.objects.order_by("-created_at")[:30]
    return render(
        request,
        "staff_parcels.html",
        {
            "error_message": error_message,
            "success_message": success_message,
            "recent_parcels": recent_parcels,
        },
    )


# ================== ИСТОРИЯ КОНКРЕТНОЙ ПОСЫЛКИ (JSON) ==================


@login_required
def parcel_history_view(request, pk: int):
    parcel = get_object_or_404(Parcel, pk=pk, user=request.user)

    now = timezone.now().replace(microsecond=0)
    profile = getattr(request.user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    _advance_cn_flow(parcel, now)
    _advance_local_flow(parcel, pickup, now)

    return JsonResponse({"track_number": parcel.track_number, "events": _serialize_history(parcel)})


# ================== РЕДИРЕКТ С ГЛАВНОЙ ==================


def index_redirect(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "cabinet_profile", None)
        if profile and profile.is_employee:
            return redirect("staff_parcels")
        return redirect("cabinet_home")
    return redirect("login")


# ================== "ПУБЛИЧНЫЙ" ТРЕКИНГ (сейчас оставляем под login) ==================


@login_required
@require_http_methods(["GET"])
def track_public_lookup_view(request):
    """
    Сейчас это НЕ публичный трекинг, а "поиск в кабинете":
    - отдаём только посылки пользователя
    - не возвращаем parcel_id/history_url (чтобы не облегчать перебор)
    """
    track = _normalize_track(request.GET.get("track") or "")
    if not track:
        return JsonResponse({"ok": False, "error": "empty_track"}, status=400)

    parcel = Parcel.objects.filter(user=request.user, track_number__iexact=track).first()
    if not parcel:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    now = timezone.now().replace(microsecond=0)
    profile = getattr(request.user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    _advance_cn_flow(parcel, now)
    _advance_local_flow(parcel, pickup, now)

    return JsonResponse(
        {
            "ok": True,
            "track_number": parcel.track_number,
            "status": parcel.status,
            "status_label": parcel.get_status_display(),
            "events": _serialize_history(parcel),
        }
    )


@login_required
@require_http_methods(["GET"])
def parcel_history_public_view(request, pk: int):
    """
    Безопасность: нельзя смотреть чужие посылки по pk.
    """
    parcel = get_object_or_404(Parcel, pk=pk, user=request.user)

    now = timezone.now().replace(microsecond=0)
    profile = getattr(request.user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    _advance_cn_flow(parcel, now)
    _advance_local_flow(parcel, pickup, now)

    return JsonResponse({"track_number": parcel.track_number, "events": _serialize_history(parcel)})
