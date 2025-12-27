from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Parcel, ParcelHistory


def _get_second_scan_delay() -> timedelta:
    hours = getattr(settings, "STAFF_SECOND_SCAN_DELAY_HOURS", 48)
    return timedelta(hours=float(hours))


def _get_received_after() -> timedelta:
    days = getattr(settings, "STAFF_AUTO_RECEIVED_AFTER_DAYS", 15)
    return timedelta(days=float(days))


def _get_local_bishkek_after() -> timedelta:
    # через сколько после 1-го скана появится "Товар прибыл в Бишкек"
    days = getattr(settings, "STAFF_LOCAL_BISHKEK_AFTER_DAYS", 5)
    return timedelta(days=float(days))


def _get_local_classify_after() -> timedelta:
    # через сколько после "Бишкек" появится "Классификация"
    hours = getattr(settings, "STAFF_LOCAL_CLASSIFY_AFTER_HOURS", 2)
    return timedelta(hours=float(hours))


def _sanitize_track(track_number: str) -> str:
    track = (track_number or "").strip().replace(" ", "")
    if not track:
        raise ValueError("Трек-номер пустой.")

    max_len = Parcel._meta.get_field("track_number").max_length
    if len(track) > max_len:
        raise ValueError(f"Трек-номер слишком длинный (макс {max_len}).")

    return track


def _add_history_once(parcel: Parcel, status: int, message: str) -> None:
    """
    Идемпотентность без изменения модели:
    не создаём дубль, если такая запись уже есть.
    """
    msg = (message or "").strip()
    if not msg:
        return

    exists = ParcelHistory.objects.filter(
        parcel=parcel,
        status=status,
        message=msg,
    ).exists()

    if not exists:
        ParcelHistory.objects.create(
            parcel=parcel,
            status=status,
            message=msg,
        )


def _advance_cn_flow(parcel: Parcel, now) -> None:
    """
    Китайская авто-цепочка от auto_flow_started_at.
    + финальный авто-статус: "Получен" через N дней после 1 скана.
    """
    if not parcel.auto_flow_started_at:
        return

    dt = now - parcel.auto_flow_started_at
    seconds = dt.total_seconds()
    changed = False

    if parcel.auto_flow_stage < 1 and seconds >= 0:
        _add_history_once(parcel, Parcel.Status.AT_CN, "Товар поступил на склад в Китае")
        parcel.status = Parcel.Status.AT_CN
        parcel.auto_flow_stage = 1
        changed = True

    if parcel.auto_flow_stage < 2 and seconds >= 10:
        _add_history_once(parcel, Parcel.Status.AT_CN, "Товар отправлен на хранение.")
        parcel.auto_flow_stage = 2
        changed = True

    if parcel.auto_flow_stage < 3 and dt >= timedelta(days=2):
        _add_history_once(parcel, Parcel.Status.FROM_CN, "Товар отправлен со склада и уже в пути.")
        parcel.status = Parcel.Status.FROM_CN
        parcel.auto_flow_stage = 3
        changed = True

    if parcel.auto_flow_stage < 4 and dt >= timedelta(days=4):
        _add_history_once(parcel, Parcel.Status.FROM_CN, "По пути в Кашгар.")
        parcel.auto_flow_stage = 4
        changed = True

    received_after = _get_received_after()
    if dt >= received_after and parcel.status != Parcel.Status.RECEIVED:
        _add_history_once(parcel, Parcel.Status.RECEIVED, "Посылка получена.")
        parcel.status = Parcel.Status.RECEIVED
        changed = True

    if changed:
        parcel.save(update_fields=["status", "auto_flow_stage", "updated_at"])


def _advance_local_flow(parcel: Parcel, pickup_point, now) -> None:
    """
    Локальная авто-цепочка.
    AT_PICKUP НЕ ставим автоматически — только 2-й скан.

    local_flow_started_at ставится на 1-м скане,
    но события появляются по таймеру:
      - "Бишкек" через STAFF_LOCAL_BISHKEK_AFTER_DAYS
      - "Классификация" через + STAFF_LOCAL_CLASSIFY_AFTER_HOURS
    """
    if not parcel.local_flow_started_at:
        return

    if parcel.status == Parcel.Status.RECEIVED:
        return

    dt = now - parcel.local_flow_started_at
    changed = False

    bishkek_after = _get_local_bishkek_after()
    classify_after = bishkek_after + _get_local_classify_after()

    if parcel.local_flow_stage < 1 and dt >= bishkek_after:
        # ОСТАВЛЯЕМ ХАРДКОД: всегда Бишкек
        _add_history_once(parcel, Parcel.Status.FROM_CN, "Товар прибыл в Бишкек.")
        parcel.local_flow_stage = 1
        changed = True

    if parcel.local_flow_stage < 2 and dt >= classify_after:
        _add_history_once(parcel, Parcel.Status.FROM_CN, "Классификация и обработка.")
        parcel.local_flow_stage = 2
        changed = True

    if changed:
        parcel.save(update_fields=["local_flow_stage", "updated_at"])


def _advance_all_flows(parcel: Parcel, pickup_point, now) -> None:
    _advance_cn_flow(parcel, now)
    _advance_local_flow(parcel, pickup_point, now)


def _process_staff_scan(user, track_number: str) -> str:
    """
    1-й скан:
      - запускаем Китай
      - запускаем Локалку СРАЗУ (local_flow_started_at = now), но без AT_PICKUP
    2-й скан (только через delay):
      - ставим AT_PICKUP
    """
    now = timezone.now()
    track = _sanitize_track(track_number)

    profile = getattr(user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    with transaction.atomic():
        parcel = (
            Parcel.objects.select_for_update()
            .filter(track_number=track)
            .first()
        )
        if not parcel:
            parcel = Parcel.objects.create(
                track_number=track,
                status=Parcel.Status.WAITING_CN,
            )

        # ===== 1 СКАН =====
        if parcel.auto_flow_started_at is None:
            parcel.auto_flow_started_at = now
            parcel.auto_flow_stage = 1
            parcel.status = Parcel.Status.AT_CN

            parcel.local_flow_started_at = now
            parcel.local_flow_stage = 0

            parcel.save(
                update_fields=[
                    "auto_flow_started_at",
                    "auto_flow_stage",
                    "status",
                    "local_flow_started_at",
                    "local_flow_stage",
                    "updated_at",
                ]
            )

            _add_history_once(
                parcel,
                Parcel.Status.AT_CN,
                "Товар поступил на склад в Китае [LIDER CARGO]",
            )

            _advance_all_flows(parcel, pickup, now)
            return "1 скан: Товар зафиксирован на складе в Китае."

        # ===== 2 СКАН =====
        delay = _get_second_scan_delay()
        allowed_at = parcel.auto_flow_started_at + delay
        if now < allowed_at:
            left = allowed_at - now
            h = int(left.total_seconds() // 3600)
            m = int((left.total_seconds() % 3600) // 60)
            raise ValueError(f"2 скан будет доступен через {h}ч {m}м.")

        _advance_all_flows(parcel, pickup, now)

        if parcel.status == Parcel.Status.RECEIVED:
            return "Посылка уже в статусе 'Получен'."

        if parcel.status == Parcel.Status.AT_PICKUP:
            return "2 скан уже был: посылка уже в пункте выдачи."

        pp_name = pickup.name if pickup else ""
        msg = f"Товар прибыл в пункт выдачи {pp_name}".strip()
        msg += f"\nтрек-номер: {parcel.track_number}"

        if pickup:
            if pickup.address:
                msg += f"\nадрес: {pickup.address}"
            if pickup.phone:
                msg += f"\nномер телефона: {pickup.phone}"

        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_PICKUP,
            message=msg,
        )

        parcel.status = Parcel.Status.AT_PICKUP
        parcel.local_flow_stage = max(parcel.local_flow_stage or 0, 3)
        parcel.save(update_fields=["status", "local_flow_stage", "updated_at"])

        return "2 скан: Товар прибыл в пункт выдачи."
