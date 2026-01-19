from datetime import timedelta
import hashlib

from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone

from .models import Parcel, ParcelHistory, track_validator


def _get_second_scan_delay() -> timedelta:
    hours = getattr(settings, "STAFF_SECOND_SCAN_DELAY_HOURS", 48)
    return timedelta(hours=float(hours))


def _norm_dt(dt):
    return dt.replace(microsecond=0) if dt else dt


def _sanitize_track(track_number: str) -> str:
    track = (track_number or "").strip().replace(" ", "")
    if not track:
        raise ValueError("Трек-номер пустой.")

    # нормализация регистра, чтобы не было дублей типа ab12 и AB12
    track = track.upper()

    min_len = 6
    max_len = 18
    
    if len(track) < min_len:
        raise ValueError(f"Трек-номер слишком короткий (минимум {min_len} символов).")
    
    if len(track) > max_len:
        raise ValueError(f"Трек-номер слишком длинный (максимум {max_len} символов).")

    # валидируем по тому же правилу, что и модель
    track_validator(track)

    return track


def _hash_message(msg: str) -> str:
    s = (msg or "").strip()
    if not s:
        return ""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _add_history_once(parcel: Parcel, status: int, message: str, occurred_at) -> None:
    """
    Идемпотентная запись истории.
    Требование: в ParcelHistory есть UniqueConstraint:
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
    ЛОГИКА КАК НА СКРИНЕ (оставляем только 3 этапа Китая):
      1) AT_CN: "Товар поступил на склад в Китае" (сразу, t0)
      2) AT_CN: "Товар отправлен на хранение." (+10 сек)
      3) FROM_CN: "Товар отправлен со склада и уже в пути." (+2 дня)

    Этапы типа "Кашгар/Бишкек/Классификация" — УБРАНЫ.
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
        _add_history_once(
            parcel,
            Parcel.Status.AT_CN,
            "Товар поступил на склад в Китае",
            occurred_at=t0,
        )
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

    if changed:
        parcel.save(update_fields=["status", "auto_flow_stage"])


def _advance_local_flow(parcel: Parcel, pickup_point, now) -> None:
    """
    Локальные авто-этапы (Бишкек/классификация) — УБРАНЫ.
    AT_PICKUP ставится ТОЛЬКО 2-м сканом.
    """
    return


def _advance_all_flows(parcel: Parcel, pickup_point, now) -> None:
    _advance_cn_flow(parcel, now)
    _advance_local_flow(parcel, pickup_point, now)


def _process_staff_scan(user, track_number: str) -> str:
    """
    1-й скан:
      - ставим started_at для Китая и локалки
      - stage=0 (дальше выставит advance_cn_flow)
      - сразу пишем китайские этапы, которые "должны быть уже наступившими"

    2-й скан (только через delay):
      - ставим AT_PICKUP и history с occurred_at=now
      - никакие локальные авто-этапы не добавляем
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

            parcel.save(
                update_fields=[
                    "auto_flow_started_at",
                    "auto_flow_stage",
                    "local_flow_started_at",
                    "local_flow_stage",
                ]
            )

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

        # ===== сообщение как на скрине =====
        pp_name = (pickup.name if pickup else "").strip()
        pp_addr = (pickup.address if pickup and pickup.address else "").strip()

        title = "Товар прибыл в пункт выдачи"
        if pp_name:
            if pp_addr:
                title += f" [{pp_name}, адрес: {pp_addr}]"
            else:
                title += f" [{pp_name}]"

        msg_lines = [
            title + ",",
            f"трек-номер: {parcel.track_number},",
        ]

        # если адрес не попал в заголовок — добавим отдельной строкой
        if pp_addr and "адрес:" not in title:
            msg_lines.append(f"адрес: {pp_addr}")

        msg = "\n".join(msg_lines)

        _add_history_once(parcel, Parcel.Status.AT_PICKUP, msg, occurred_at=now)

        parcel.status = Parcel.Status.AT_PICKUP
        parcel.local_flow_stage = max(parcel.local_flow_stage or 0, 3)
        parcel.save(update_fields=["status", "local_flow_stage"])

        return "2 скан: Товар прибыл в пункт выдачи."
