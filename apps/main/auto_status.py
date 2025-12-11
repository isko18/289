from datetime import timedelta

from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from .models import Parcel, ParcelHistory, CabinetProfile


def _advance_cn_flow(parcel: Parcel) -> None:
    """
    Обновляет историю и parcel.status в зависимости от того,
    сколько времени прошло с первого скана (auto_flow_started_at).

    Этапы:
    0 -> (сразу)   "Товар поступил на склад в Китае [LIDER CARGO]"
    1 -> (+10 сек) "Товар отправлен на хранение"
    2 -> (+2 дня)  "Товар отправлен со склада и уже в пути"
    3 -> (+4 дня)  "По пути в Кашгар"
    """
    if not parcel.auto_flow_started_at:
        return

    now = timezone.now()
    dt = now - parcel.auto_flow_started_at
    seconds = dt.total_seconds()

    changed = False

    # этап 0 → 1 (самый первый статус уже создаётся при первом скане,
    # но на всякий подстрахуемся)
    if parcel.auto_flow_stage < 1 and seconds >= 0:
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_CN,
            message="Товар поступил на склад в Китае [LIDER CARGO]",
        )
        parcel.status = Parcel.Status.AT_CN
        parcel.auto_flow_stage = 1
        changed = True

    # этап 1 → 2 (через 10 секунд)
    if parcel.auto_flow_stage < 2 and seconds >= 10:
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_CN,
            message="Товар отправлен на хранение.",
        )
        parcel.auto_flow_stage = 2
        changed = True

    # этап 2 → 3 (через 2 дня)
    if parcel.auto_flow_stage < 3 and dt >= timedelta(days=2):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="Товар отправлен со склада и уже в пути.",
        )
        parcel.status = Parcel.Status.FROM_CN
        parcel.auto_flow_stage = 3
        changed = True

    # этап 3 → 4 (через 4 дня)
    if parcel.auto_flow_stage < 4 and dt >= timedelta(days=4):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="По пути в Кашгар.",
        )
        parcel.auto_flow_stage = 4
        changed = True

    if changed:
        parcel.save(update_fields=["status", "auto_flow_stage", "updated_at"])



def _advance_local_flow(parcel: Parcel, pickup_point) -> None:
    """
    Локальная цепочка после второго скана (в Киргизии / пункт выдачи).
    Этапы считаем от local_flow_started_at:

    0 -> (сразу)   "Товар прибыл в [Бишкек]" (или город из пункта)
    1 -> (+2 часа) "Классификация и обработка."
    2 -> (+2 часа) "Товар прибыл в пункт выдачи <имя>, адрес: ..."
    """
    if not parcel.local_flow_started_at:
        return

    now = timezone.now()
    dt = now - parcel.local_flow_started_at

    city = ""
    address = ""
    if pickup_point:
        address = pickup_point.address or ""
        # очень грубо вытаскиваем город: до первой запятой
        if pickup_point.address and "," in pickup_point.address:
            city = pickup_point.address.split(",")[0].strip()
        else:
            city = pickup_point.name

    changed = False

    if parcel.local_flow_stage < 1 and dt >= timedelta(seconds=0):
        msg_city = f"Товар прибыл в [{city}]." if city else "Товар прибыл на территорию Кыргызстана."
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message=msg_city,
        )
        parcel.local_flow_stage = 1
        changed = True

    if parcel.local_flow_stage < 2 and dt >= timedelta(hours=2):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="Классификация и обработка.",
        )
        parcel.local_flow_stage = 2
        changed = True

    if parcel.local_flow_stage < 3 and dt >= timedelta(hours=4):
        msg_pickup = "Товар прибыл в пункт выдачи"
        if pickup_point:
            msg_pickup += f" {pickup_point.name}"
            if address:
                msg_pickup += f", адрес: {address}"
        msg_pickup += "."
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_PICKUP,
            message=msg_pickup,
        )
        parcel.status = Parcel.Status.AT_PICKUP
        parcel.local_flow_stage = 3
        changed = True

    if changed:
        parcel.save(update_fields=["status", "local_flow_stage", "updated_at"])

def _process_staff_scan(user, track_number: str) -> str:
    """
    Обрабатывает скан:

    - если это ПЕРВЫЙ скан (нет auto_flow_started_at) —
      считаем, что товар поступил на склад в Китае, запускаем китайскую цепочку;

    - если китайская цепочка уже была (есть auto_flow_started_at) —
      запускаем/обновляем локальную цепочку (Кыргызстан / пункт выдачи).
    """
    now = timezone.now()
    track = (track_number or "").strip().replace(" ", "")[:20]

    profile = getattr(user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    # посылка может уже существовать (клиент добавил трек в кабинете)
    parcel, _ = Parcel.objects.get_or_create(
        track_number=track,
        defaults={
            "status": Parcel.Status.WAITING_CN,
        },
    )

    # ---------- ПЕРВЫЙ СКАН: Китай ----------
    if parcel.auto_flow_started_at is None:
        parcel.auto_flow_started_at = now
        parcel.auto_flow_stage = 1
        parcel.status = Parcel.Status.AT_CN
        parcel.save(update_fields=["auto_flow_started_at", "auto_flow_stage", "status", "updated_at"])

        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_CN,
            message="Товар поступил на склад в Китае [LIDER CARGO]",
        )
        # сразу дотянем остальные этапы Китая по времени (вдруг скан был задним числом)
        _advance_cn_flow(parcel)
        return "Товар зафиксирован на складе в Китае."

    # ---------- ВТОРОЙ И ПОСЛЕДУЮЩИЕ СКАНЫ ----------
    # сначала дотягиваем китайскую цепочку по времени
    _advance_cn_flow(parcel)

    # если локальная цепочка ещё не запускалась — запускаем
    if parcel.local_flow_started_at is None:
        parcel.local_flow_started_at = now
        parcel.local_flow_stage = 0
        parcel.save(update_fields=["local_flow_started_at", "local_flow_stage", "updated_at"])

        _advance_local_flow(parcel, pickup)
        return "Товар зафиксирован на локальном складе, запущена цепочка до пункта выдачи."

    # локальная уже есть — просто обновляем по текущему времени
    _advance_local_flow(parcel, pickup)
    return "Статус посылки обновлён по текущему времени."
