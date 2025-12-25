from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import Parcel, ParcelHistory

def _get_second_scan_delay() -> timedelta:
    """Задержка для второго сканирования."""
    hours = getattr(settings, "STAFF_SECOND_SCAN_DELAY_HOURS", 48)
    return timedelta(hours=float(hours))

def _get_received_after() -> timedelta:
    """Задержка для статуса 'Получен' после первого сканирования."""
    days = getattr(settings, "STAFF_AUTO_RECEIVED_AFTER_DAYS", 15)
    return timedelta(days=float(days))

def _advance_cn_flow(parcel: Parcel) -> None:
    """Автоматические обновления статусов для китайской цепочки."""
    if not parcel.auto_flow_started_at:
        return

    now = timezone.now()
    dt = now - parcel.auto_flow_started_at
    seconds = dt.total_seconds()

    changed = False

    # 2-й скан: Товар отправлен на хранение (через 10 секунд после 1-го скана)
    if parcel.auto_flow_stage < 2 and seconds >= 10:
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.AT_CN,
            message="Товар отправлен на хранение.",
        )
        parcel.auto_flow_stage = 2
        changed = True

    # 3-й скан: Товар отправлен со склада и уже в пути (через 2 дня после Товара отправлен на хранение)
    if parcel.auto_flow_stage < 3 and dt >= timedelta(days=2):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="Товар отправлен со склада и уже в пути.",
        )
        parcel.status = Parcel.Status.FROM_CN
        parcel.auto_flow_stage = 3
        changed = True

    # 4-й скан: По пути в Кашгар (через 4 дня после Товара отправлен со склада)
    if parcel.auto_flow_stage < 4 and dt >= timedelta(days=4):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="По пути в Кашгар.",
        )
        parcel.auto_flow_stage = 4
        changed = True

    # 5-й скан: Товар прибыл в Бишкек (через 1 день после По пути в Кашгар)
    if parcel.auto_flow_stage < 5 and dt >= timedelta(days=5):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="Товар прибыл в Бишкек.",
        )
        parcel.auto_flow_stage = 5
        changed = True

    # 6-й скан: Классификация и обработка (через 4 часа после Товара прибыл в Бишкек)
    if parcel.auto_flow_stage < 6 and dt >= timedelta(days=5, hours=4):
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message="Классификация и обработка.",
        )
        parcel.auto_flow_stage = 6
        changed = True

    if changed:
        parcel.save(update_fields=["status", "auto_flow_stage", "updated_at"])

def _advance_local_flow(parcel: Parcel, pickup_point) -> None:
    """Автоматическое обновление статуса для локальной цепочки."""
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

    # 2-й скан: Товар прибыл в пункт выдачи
    if parcel.local_flow_stage < 1 and dt >= timedelta(seconds=0):
        msg_city = "Товар прибыл в Бишкек." if city else "Товар прибыл на территорию Кыргызстана."
        ParcelHistory.objects.create(
            parcel=parcel,
            status=Parcel.Status.FROM_CN,
            message=msg_city,
        )
        parcel.local_flow_stage = 1
        changed = True

    # 3-й скан: Классификация и обработка (через 2 часа после прибытия)
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
    2-й скан: ставим "прибыл в пункт выдачи" (AT_PICKUP).
    """
    now = timezone.now()
    track = (track_number or "").strip().replace(" ", "")[:20]

    profile = getattr(user, "cabinet_profile", None)
    pickup = getattr(profile, "pickup_point", None)

    parcel, _ = Parcel.objects.get_or_create(
        track_number=track,
        defaults={"status": Parcel.Status.WAITING_CN},
    )

    # 1-й скан: фиксируем статус "Товар поступил на склад в Китае"
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

    # 2-й скан: фиксируем статус "Товар прибыл в пункт выдачи"
    delay = _get_second_scan_delay()
    allowed_at = parcel.auto_flow_started_at + delay
    if now < allowed_at:
        left = allowed_at - now
        h = int(left.total_seconds() // 3600)
        m = int((left.total_seconds() % 3600) // 60)
        raise ValueError(f"2 скан будет доступен через {h}ч {m}м.")

    _advance_cn_flow(parcel)

    if parcel.status == Parcel.Status.RECEIVED:
        return "Посылка уже в статусе 'Получен'."
    
    if parcel.status == Parcel.Status.AT_PICKUP:
        return "2 скан уже был: посылка уже в пункте выдачи."

    # Локальная цепочка
    if parcel.local_flow_started_at is None:
        parcel.local_flow_started_at = now
        parcel.local_flow_stage = 0
        parcel.save(update_fields=["local_flow_started_at", "local_flow_stage", "updated_at"])

    _advance_local_flow(parcel, pickup)

    msg = "Товар прибыл в пункт выдачи"
    if pickup:
        msg += f" {pickup.name}"
        if pickup.address:
            msg += f"\nАдрес: {pickup.address}"
        if pickup.phone:
            msg += f"\nНомер телефона: {pickup.phone}"

    ParcelHistory.objects.create(
        parcel=parcel,
        status=Parcel.Status.AT_PICKUP,
        message=msg,
    )

    parcel.status = Parcel.Status.AT_PICKUP
    parcel.local_flow_stage = max(parcel.local_flow_stage or 0, 3)
    parcel.save(update_fields=["status", "local_flow_stage", "updated_at"])

    return "2 скан: Товар прибыл в пункт выдачи."
