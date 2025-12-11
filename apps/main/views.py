from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import CabinetProfile, PickupPoint, Parcel, ParcelHistory
from apps.main.auto_status import (
    _process_staff_scan,
    _advance_cn_flow,
    _advance_local_flow,
)


def _normalize_phone(phone: str) -> str:
    """
    Превращает '000 000 000' в '+996000000000'
    """
    raw = (phone or "").strip().replace(" ", "")
    if not raw:
        return ""

    # если уже с +996..., оставляем
    if raw.startswith("+996"):
        return raw

    # если содержит только цифры и начинается на 996
    if raw.startswith("996"):
        return "+{}".format(raw)

    # если это только 9 цифр — добавим +996
    if len(raw) == 9 and raw.isdigit():
        return "+996" + raw

    # на крайняк — просто плюс и то, что дали
    if not raw.startswith("+"):
        raw = "+" + raw

    return raw


# ================== РЕГИСТРАЦИЯ ==================


@require_http_methods(["GET", "POST"])
def register_view(request):
    # если уже залогинен — сразу в нужный кабинет
    if request.user.is_authenticated:
        profile = getattr(request.user, "cabinet_profile", None)
        if profile and profile.is_employee:
            return redirect("staff_parcels")
        return redirect("cabinet_home")

    pickup_points = PickupPoint.objects.filter(is_active=True).order_by("name")

    context = {
        "form_data": {},
        "errors": {},
        "pickup_points": pickup_points,
    }

    if request.method == "GET":
        return render(request, "register.html", context)

    # POST
    full_name = request.POST.get("full_name", "").strip()
    phone_input = request.POST.get("phone", "")
    pickup_point_id = request.POST.get("pickup_point", "")
    password = request.POST.get("password", "")
    password_confirm = request.POST.get("password_confirm", "")

    phone = _normalize_phone(phone_input)

    errors = {}
    pickup_point_obj = None

    # ФИО
    if not full_name:
        errors["full_name"] = "Укажите ФИО."

    # Телефон
    if not phone:
        errors["phone"] = "Укажите номер телефона."
    else:
        if User.objects.filter(username=phone).exists():
            errors["phone"] = "Пользователь с таким телефоном уже зарегистрирован."

    # Пароль
    if not password or not password_confirm:
        errors["password"] = "Укажите пароль и его подтверждение."
    elif password != password_confirm:
        errors["password"] = "Пароли не совпадают."
    elif len(password) < 8:
        errors["password"] = "Пароль должен содержать минимум 8 символов."

    # Пункт выдачи
    if not pickup_point_id:
        errors["pickup_point"] = "Выберите пункт выдачи."
    else:
        try:
            pickup_point_obj = PickupPoint.objects.get(
                pk=pickup_point_id,
                is_active=True,
            )
        except PickupPoint.DoesNotExist:
            errors["pickup_point"] = "Неверный пункт выдачи."

    if errors:
        context["errors"] = errors
        context["form_data"] = {
            "full_name": full_name,
            "phone": phone_input,
            "pickup_point": pickup_point_id,
        }
        return render(request, "register.html", context)

    # создаём пользователя
    user = User.objects.create_user(
        username=phone,
        password=password,
    )
    user.first_name = full_name
    user.save()

    # профиль (is_employee по умолчанию False для обычных клиентов)
    CabinetProfile.objects.create(
        user=user,
        phone=phone,
        pickup_point=pickup_point_obj,
        is_employee=False,
    )

    # автологин
    login(request, user)
    return redirect("cabinet_home")


# ================== ЛОГИН / ЛОГАУТ ==================


@require_http_methods(["GET", "POST"])
def login_view(request):
    # если уже залогинен — сразу в нужный кабинет
    if request.user.is_authenticated:
        profile = getattr(request.user, "cabinet_profile", None)
        if profile and profile.is_employee:
            return redirect("staff_parcels")
        return redirect("cabinet_home")

    context = {
        "errors": {},
        "form_data": {},
    }

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
        context["form_data"] = {
            "phone": phone_input,
        }
        return render(request, "login.html", context)

    login(request, user)

    # после логина сразу маршрутизируем по роли
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

    # если это сотрудник — сразу в панель сотрудника
    if profile and profile.is_employee:
        return redirect("staff_parcels")

    if request.method == "POST":
        raw_tracks = request.POST.getlist("tracks")
        cleaned = []

        for t in raw_tracks:
            t = (t or "").strip().replace(" ", "")
            if not t:
                continue
            t = t[:20]
            cleaned.append(t)

        cleaned = cleaned[:5]

        for track in cleaned:
            parcel, created = Parcel.objects.get_or_create(
                track_number=track,
                defaults={"status": Parcel.Status.WAITING_CN},
            )
            if parcel.user is None:
                parcel.user = request.user
                parcel.save()

        return redirect("cabinet_home")

    # ---- авто-обновление статусов перед показом ----
    pickup = getattr(profile, "pickup_point", None)

    user_parcels = list(Parcel.objects.filter(user=request.user))

    for p in user_parcels:
        _advance_cn_flow(p)
        _advance_local_flow(p, pickup)

    # перечитываем из базы уже обновлённые значения
    user_parcels_qs = Parcel.objects.filter(user=request.user)

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
    """
    Просмотр профиля.
    """
    profile = getattr(request.user, "cabinet_profile", None)
    return render(
        request,
        "cabinet_profile.html",
        {
            "user_profile": profile,
        },
    )


@login_required
def cabinet_profile_edit(request):
    """
    Редактирование профиля.
    """
    profile, _ = CabinetProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "phone": request.user.username,
            "is_employee": False,
        },
    )

    pickup_points = PickupPoint.objects.filter(is_active=True).order_by("name")

    if request.method == "GET":
        return render(
            request,
            "cabinet_edit_profile.html",
            {
                "user_profile": profile,
                "pickup_points": pickup_points,
                "errors": {},
            },
        )

    # POST — сохраняем изменения
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
        # проверяем, что номер не занят другим пользователем
        if User.objects.filter(username=phone).exclude(pk=request.user.pk).exists():
            errors["phone"] = "Пользователь с таким телефоном уже зарегистрирован."

    if pickup_point_id:
        try:
            pickup_point_obj = PickupPoint.objects.get(
                pk=pickup_point_id,
                is_active=True,
            )
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
    request.user.save()

    profile.phone = phone
    profile.pickup_point = pickup_point_obj
    profile.save()

    return redirect("cabinet_profile")


# ================== ПАНЕЛЬ СОТРУДНИКА ==================


@login_required
@require_http_methods(["GET", "POST"])
def staff_parcels_view(request):
    """
    Панель сотрудника:
    - один инпут под сканер / ввод трека;
    - первый скан запускает китайскую цепочку;
    - последующие сканы включают/обновляют локальную цепочку.
    """
    profile = getattr(request.user, "cabinet_profile", None)
    if not profile or not profile.is_employee:
        # не сотрудник — в обычный кабинет
        return redirect("cabinet_home")

    error_message = ""
    success_message = ""

    if request.method == "POST":
        raw = request.POST.get("track_number", "")
        track = (raw or "").strip().replace(" ", "")

        if not track:
            error_message = "Укажите трек-номер."
        else:
            msg = _process_staff_scan(request.user, track)
            success_message = msg

    # последние 30 посылок (по created_at)
    recent_parcels = Parcel.objects.order_by("-created_at")[:30]

    context = {
        "error_message": error_message,
        "success_message": success_message,
        "recent_parcels": recent_parcels,
    }
    return render(request, "staff_parcels.html", context)


# ================== ИСТОРИЯ КОНКРЕТНОЙ ПОСЫЛКИ (JSON) ==================


@login_required
def parcel_history_view(request, pk: int):
    """
    JSON для истории конкретной посылки (таймлайн в модалке).
    Перед отдачей истории подтягиваем авто-этапы по текущему времени.
    """
    parcel = get_object_or_404(Parcel, pk=pk, user=request.user)

    # подтянем авто-статусы перед формированием ответа
    profile = getattr(request.user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    _advance_cn_flow(parcel)
    _advance_local_flow(parcel, pickup)

    events = []
    qs = getattr(parcel, "history", None)

    if qs is not None:
        # после _advance_* в истории уже будут новые записи,
        # берём их в порядке "новые сверху"
        for idx, h in enumerate(qs.all().order_by("-created_at")):
            events.append(
                {
                    "status_display": h.get_status_display(),
                    "message": getattr(h, "message", "") or "",
                    "datetime": h.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_latest": idx == 0,
                }
            )

    if not events:
        created = (
            parcel.created_at if hasattr(parcel, "created_at") else timezone.now()
        )
        events.append(
            {
                "status_display": parcel.get_status_display(),
                "message": "",
                "datetime": created.strftime("%Y-%m-%d %H:%M:%S"),
                "is_latest": True,
            }
        )

    return JsonResponse(
        {
            "track_number": parcel.track_number,
            "events": events,
        }
    )


# ================== РЕДИРЕКТ С ГЛАВНОЙ ==================


def index_redirect(request):
    """
    / -> если залогинен:
           сотрудник -> staff_parcels
           клиент    -> cabinet_home
         если нет -> login
    """
    if request.user.is_authenticated:
        profile = getattr(request.user, "cabinet_profile", None)
        if profile and profile.is_employee:
            return redirect("staff_parcels")
        return redirect("cabinet_home")
    return redirect("login")
