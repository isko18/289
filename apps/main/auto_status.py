from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Parcel, ParcelHistory


def _get_second_scan_delay() -> timedelta:
    hours = getattr(settings, "STAFF_SECOND_SCAN_DELAY_HOURS", 48)
    return timedelta(hours=float(hours))


def _get_received_after() -> timedelta:
    # через сколько после 1-го скана ставим "Получен"
    # можно менять в settings.py: STAFF_AUTO_RECEIVED_AFTER_DAYS = 15
    days = getattr(settings, "STAFF_AUTO_RECEIVED_AFTER_DAYS", 15)
    return timedelta(days=float(days))


def _advance_cn_flow(parcel: Parcel) -> None:
    """
    Китайская авто-цепочка от auto_flow_started_at.
    + финальный авто-статус: "Получен" через N дней после 1 скана.
    """
    if not parcel.auto_flow_started_at:
        return

    now = timezone.now()
    dt = now - parcel.auto_flow_started_at
    seconds = dt.total_seconds()

    changed = False

    if parcel.auto_flow_stage < 1 and seconds >= 0:
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_CN,
            message="Товар поступил на склад в Китае",
        )
        parcel.status = Parcel.Status.AT_CN
        parcel.auto_flow_stage = 1
        changed = True

    if parcel.auto_flow_stage < 2 and seconds >= 10:
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_CN,
            message="Товар отправлен на хранение.",
        )
        parcel.auto_flow_stage = 2
        changed = True

    if parcel.auto_flow_stage < 3 and dt >= timedelta(days=2):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="Товар отправлен со склада и уже в пути.",
        )
        parcel.status = Parcel.Status.FROM_CN
        parcel.auto_flow_stage = 3
        changed = True

    if parcel.auto_flow_stage < 4 and dt >= timedelta(days=4):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="По пути в Кашгар.",
        )
        parcel.auto_flow_stage = 4
        changed = True

    # ===== ФИНАЛ: "ПОЛУЧЕН" ЧЕРЕЗ 15 ДНЕЙ (или сколько задашь) =====
    received_after = _get_received_after()
    if dt >= received_after and parcel.status != Parcel.Status.RECEIVED:
        # не спамим дублями
        already = ParcelHistory.objects.filter(
            parcel=parcel,
            status=Parcel.Status.RECEIVED,
        ).exists()
        if not already:
            ParcelHistory.objects.create(
                parcel=parcel,
                status=Parcel.Status.RECEIVED,
                message="Посылка получена.",
            )

        parcel.status = Parcel.Status.RECEIVED
        changed = True

    if changed:
        parcel.save(update_fields=["status", "auto_flow_stage", "updated_at"])


def _advance_local_flow(parcel: Parcel, pickup_point) -> None:
    """
    Локальная авто-цепочка.
    ВАЖНО: "прибыл в пункт выдачи" (AT_PICKUP) НЕ СТАВИМ автоматически.
    Её ставит ТОЛЬКО 2-й скан.
    """
    if not parcel.local_flow_started_at:
        return

    now = timezone.now()
    dt = now - parcel.local_flow_started_at

    city = ""
    if pickup_point:
        if pickup_point.address and "," in pickup_point.address:
            city = pickup_point.address.split(",")[0].strip()
        else:
            city = pickup_point.name

    changed = False

    if parcel.local_flow_stage < 1 and dt >= timedelta(seconds=0):
        msg_city = "Товар прибыл в Бишкек." if city else "Товар прибыл на территорию Кыргызстана."
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

    if changed:
        parcel.save(update_fields=["status", "local_flow_stage", "updated_at"])


def _process_staff_scan(user, track_number: str) -> str:
    """
    1-й скан: фиксируем Китай и запускаем авто-Китай.
    2-й скан (только через delay): ставим "прибыл в пункт выдачи" (AT_PICKUP).
    """
    now = timezone.now()
    track = (track_number or "").strip().replace(" ", "")[:20]

    profile = getattr(user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    parcel, _ = Parcel.objects.get_or_create(
        track_number=track,
        defaults={"status": Parcel.Status.WAITING_CN},
    )

    # ===== 1 СКАН =====
    if parcel.auto_flow_started_at is None:
        parcel.auto_flow_started_at = now
        parcel.auto_flow_stage = 1
        parcel.status = Parcel.Status.AT_CN
        parcel.save(update_fields=["auto_flow_started_at", "auto_flow_stage", "status", "updated_at"])

        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_CN,
            message="Товар поступил на склад в Китае",
        )

        _advance_cn_flow(parcel)
        return "1 скан: Товар зафиксирован на складе в Китае."

    # ===== 2 СКАН: ТОЛЬКО ПОСЛЕ DELAY =====
    delay = _get_second_scan_delay()
    allowed_at = parcel.auto_flow_started_at + delay
    if now < allowed_at:
        left = allowed_at - now
        h = int(left.total_seconds() // 3600)
        m = int((left.total_seconds() % 3600) // 60)
        raise ValueError(f"2 скан будет доступен через {h}ч {m}м.")

    # сначала обновим авто-статусы до текущего времени (включая "Получен" если уже пора)
    _advance_cn_flow(parcel)

    # если уже получен — второй скан больше не нужен
    if parcel.status == Parcel.Status.RECEIVED:
        return "Посылка уже в статусе 'Получен'."

    # если уже в пункте выдачи — не дублируем
    if parcel.status == Parcel.Status.AT_PICKUP:
        return "2 скан уже был: посылка уже в пункте выдачи."

    # локалку начинаем/обновляем (чтобы были 'Бишкек' и 'Классификация' до 2 скана)
    if parcel.local_flow_started_at is None:
        parcel.local_flow_started_at = now
        parcel.local_flow_stage = 0
        parcel.save(update_fields=["local_flow_started_at", "local_flow_stage", "updated_at"])

    _advance_local_flow(parcel, pickup)

    # ===== 2 СКАН СТАВИТ ПУНКТ ВЫДАЧИ =====
    msg = "Товар прибыл в пункт выдачи"
    if pickup:
        msg += f" {pickup.name}"
        if pickup.address:
            msg += f", адрес: {pickup.address}"
        if pickup.phone:
            msg += f"                      Номер телефона {pickup.phone}"
    msg += " "

    ParcelHistory.objects.create(
        parcel=parcel,
        status=Parcel.Status.AT_PICKUP,
        message=msg,
    )

    parcel.status = Parcel.Status.AT_PICKUP
    parcel.local_flow_stage = max(parcel.local_flow_stage or 0, 3)
    parcel.save(update_fields=["status", "local_flow_stage", "updated_at"])

    return "2 скан: Товар прибыл в пункт выдачи."
