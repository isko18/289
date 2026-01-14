from datetime import timedelta
import hashlib

from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone

from .models import Parcel, ParcelHistory


def _get_second_scan_delay() -> timedelta:
    hours = getattr(settings, "STAFF_SECOND_SCAN_DELAY_HOURS", 48)
    return timedelta(hours=float(hours))


def _get_received_after() -> timedelta:
    days = getattr(settings, "STAFF_AUTO_RECEIVED_AFTER_DAYS", 15)
    return timedelta(days=float(days))


def _get_local_bishkek_after() -> timedelta:
    days = getattr(settings, "STAFF_LOCAL_BISHKEK_AFTER_DAYS", 5)
    return timedelta(days=float(days))


def _get_local_classify_after() -> timedelta:
    hours = getattr(settings, "STAFF_LOCAL_CLASSIFY_AFTER_HOURS", 2)
    return timedelta(hours=float(hours))


def _norm_dt(dt):
    return dt.replace(microsecond=0) if dt else dt


def _sanitize_track(track_number: str) -> str:
    track = (track_number or "").strip().replace(" ", "")
    if not track:
        raise ValueError("Трек-номер пустой.")

    max_len = Parcel._meta.get_field("track_number").max_length
    if len(track) > max_len:
        raise ValueError(f"Трек-номер слишком длинный (макс {max_len}).")

    return track


def _hash_message(msg: str) -> str:
    s = (msg or "").strip()
    if not s:
        return ""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _add_history_once(parcel: Parcel, status: int, message: str, occurred_at) -> None:
    """
    Идемпотентная запись истории.
    Требование: в ParcelHistory есть поля message_hash и UniqueConstraint:
      (parcel, status, occurred_at, message_hash)
    """
    msg = (message or "").strip()
    if not msg:
        return

    occurred_at = _norm_dt(occurred_at)
    msg_hash = _hash_message(msg)

    try:
        ParcelHistory.objects.create(
            parcel=parcel,
            status=status,
            message=msg,
            message_hash=msg_hash,
            occurred_at=occurred_at,
        )
    except IntegrityError:
        # дубль — ок
        return


def _advance_cn_flow(parcel: Parcel, now) -> None:
    """
    Китайская авто-цепочка от auto_flow_started_at.
    ВАЖНО: события пишем с occurred_at = started_at + offset (точное время).
    """
    if not parcel.auto_flow_started_at:
        return

    t0 = _norm_dt(parcel.auto_flow_started_at)
    now = _norm_dt(now)

    dt = now - t0
    seconds = dt.total_seconds()
    changed = False

    # stage 1: сразу
    if parcel.auto_flow_stage < 1 and seconds >= 0:
        _add_history_once(parcel, Parcel.Status.AT_CN, "Товар поступил на склад в Китае", occurred_at=t0)
        parcel.status = Parcel.Status.AT_CN
        parcel.auto_flow_stage = 1
        changed = True

    # stage 2: +10 сек
    if parcel.auto_flow_stage < 2 and seconds >= 10:
        _add_history_once(
            parcel,
            Parcel.Status.AT_CN,
            "Товар отправлен на хранение.",
            occurred_at=t0 + timedelta(seconds=10),
        )
        parcel.auto_flow_stage = 2
        changed = True

    # stage 3: +2 дня
    if parcel.auto_flow_stage < 3 and dt >= timedelta(days=2):
        _add_history_once(
            parcel,
            Parcel.Status.FROM_CN,
            "Товар отправлен со склада и уже в пути.",
            occurred_at=t0 + timedelta(days=2),
        )
        parcel.status = Parcel.Status.FROM_CN
        parcel.auto_flow_stage = 3
        changed = True

    # stage 4: +4 дня
    if parcel.auto_flow_stage < 4 and dt >= timedelta(days=4):
        _add_history_once(
            parcel,
            Parcel.Status.FROM_CN,
            "По пути в Кашгар.",
            occurred_at=t0 + timedelta(days=4),
        )
        parcel.auto_flow_stage = 4
        changed = True

    received_after = _get_received_after()
    if dt >= received_after and parcel.status != Parcel.Status.RECEIVED:
        _add_history_once(
            parcel,
            Parcel.Status.RECEIVED,
            "Посылка получена.",
            occurred_at=t0 + received_after,
        )
        parcel.status = Parcel.Status.RECEIVED
        changed = True

    if changed:
        parcel.save(update_fields=["status", "auto_flow_stage", "updated_at"])


def _advance_local_flow(parcel: Parcel, pickup_point, now) -> None:
    """
    Локальная авто-цепочка от local_flow_started_at.
    AT_PICKUP НЕ ставим автоматически — только 2-й скан.
    """
    if not parcel.local_flow_started_at:
        return

    if parcel.status == Parcel.Status.RECEIVED:
        return

    t0 = _norm_dt(parcel.local_flow_started_at)
    now = _norm_dt(now)
    dt = now - t0
    changed = False

    bishkek_after = _get_local_bishkek_after()
    classify_after = bishkek_after + _get_local_classify_after()

    if parcel.local_flow_stage < 1 and dt >= bishkek_after:
        _add_history_once(
            parcel,
            Parcel.Status.FROM_CN,
            "Товар прибыл в Бишкек.",
            occurred_at=t0 + bishkek_after,
        )
        parcel.local_flow_stage = 1
        changed = True

    if parcel.local_flow_stage < 2 and dt >= classify_after:
        _add_history_once(
            parcel,
            Parcel.Status.FROM_CN,
            "Классификация и обработка.",
            occurred_at=t0 + classify_after,
        )
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
      - ставим started_at для Китая и локалки
      - stage=0 (дальше выставит advance)
    2-й скан (только через delay):
      - ставим AT_PICKUP и history с occurred_at=now
    """
    now = _norm_dt(timezone.now())
    track = _sanitize_track(track_number)

    profile = getattr(user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    with transaction.atomic():
        parcel = Parcel.objects.select_for_update().filter(track_number=track).first()
        if not parcel:
            parcel = Parcel.objects.create(track_number=track, status=Parcel.Status.WAITING_CN)

        # ===== 1 СКАН =====
        if parcel.auto_flow_started_at is None:
            parcel.auto_flow_started_at = now
            parcel.auto_flow_stage = 0

            parcel.local_flow_started_at = now
            parcel.local_flow_stage = 0

            parcel.save(update_fields=[
                "auto_flow_started_at",
                "auto_flow_stage",
                "local_flow_started_at",
                "local_flow_stage",
                "updated_at",
            ])

            _advance_all_flows(parcel, pickup, now)
            return "1 скан: Товар зафиксирован на складе в Китае."

        # ===== 2 СКАН =====
        delay = _get_second_scan_delay()
        allowed_at = _norm_dt(parcel.auto_flow_started_at) + delay
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

        pp_name = (pickup.name if pickup else "").strip()
        msg = f"Товар прибыл в пункт выдачи {pp_name}".strip()
        msg += f"\nтрек-номер: {parcel.track_number}"

        if pickup:
            if pickup.address:
                msg += f"\nадрес: {pickup.address}"
            if pickup.phone:
                msg += f"\nномер телефона: {pickup.phone}"

        _add_history_once(parcel, Parcel.Status.AT_PICKUP, msg, occurred_at=now)

        parcel.status = Parcel.Status.AT_PICKUP
        parcel.local_flow_stage = max(parcel.local_flow_stage or 0, 3)
        parcel.save(update_fields=["status", "local_flow_stage", "updated_at"])

        return "2 скан: Товар прибыл в пункт выдачи."
