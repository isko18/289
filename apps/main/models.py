from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

# Телефон в формате E.164 (например: +996XXXXXXXXX)
phone_validator = RegexValidator(
    regex=r"^\+\d{6,15}$",
    message=_("Телефон должен быть в формате +<код><номер>, например +996700123456"),
)

# Трек: буквы/цифры и немного безопасных символов
track_validator = RegexValidator(
    regex=r"^[A-Za-z0-9._\-]{1,64}$",
    message=_("Трек-номер может содержать только буквы/цифры и символы . _ -"),
)


class SiteSettings(models.Model):
    """
    Глобальные настройки витрины/кабинета.
    Держим одну запись (singleton).
    """
    title = models.CharField("Название проекта", max_length=100, default="kargoexpress")

    logo = models.ImageField(
        "Логотип",
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="PNG/SVG с логотипом. Если не задан, используется статика img/logo.png",
    )

    bg_light = models.ImageField(
        "Фон (светлая тема)",
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Можно GIF или картинку. Используется в светлом режиме.",
    )

    bg_dark = models.ImageField(
        "Фон (тёмная тема)",
        upload_to="branding/",
        blank=True,
        null=True,
        help_text="Можно GIF или картинку. Используется в тёмном режиме.",
    )

    default_dark_mode = models.BooleanField("Тёмная тема по умолчанию", default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def save(self, *args, **kwargs):
        # Жёсткий singleton: всегда id=1
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or "Настройки сайта"


class PickupPoint(models.Model):
    name = models.CharField("Название", max_length=255)
    address = models.CharField("Адрес", max_length=255, blank=True)
    phone = models.CharField(
        "Номер телефона",
        max_length=32,
        blank=True,
        null=True,
        validators=[phone_validator],
    )
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Пункт выдачи"
        verbose_name_plural = "Пункты выдачи"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.address})" if self.address else self.name


class CabinetProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cabinet_profile",
    )
    full_name = models.CharField("ФИО", max_length=255)

    phone = models.CharField(
        "Телефон",
        max_length=32,
        blank=True,
        null=True,
        validators=[phone_validator],
    )

    pickup_point = models.ForeignKey(
        PickupPoint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles",
        verbose_name="Пункт выдачи",
    )
    is_employee = models.BooleanField("Сотрудник компании", default=False)

    class Meta:
        verbose_name = "Профиль кабинета"
        verbose_name_plural = "Профили кабинета"
        constraints = [
            # уникален только если не NULL и не пустая строка
            models.UniqueConstraint(
                fields=["phone"],
                condition=Q(phone__isnull=False) & ~Q(phone=""),
                name="uniq_cabinet_phone_not_empty",
            ),
        ]

    def __str__(self):
        return f"Профиль {getattr(self.user, 'username', self.user_id)}"


class Parcel(models.Model):
    class Status(models.IntegerChoices):
        WAITING_CN = 0, "Ожидает поступления на склад в Китае"
        AT_CN = 1, "Принят на склад в Китае"
        FROM_CN = 2, "Отправлен из Китая"
        AT_PICKUP = 3, "Прибыл в пункт выдачи"
        RECEIVED = 4, "Получен"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcels",
        verbose_name="Пользователь (если уже привязан)",
    )

    track_number = models.CharField(
        "Трек-номер",
        max_length=64,
        unique=True,
        validators=[track_validator],
    )

    status = models.PositiveSmallIntegerField(
        "Текущий статус",
        choices=Status.choices,
        default=Status.WAITING_CN,
        db_index=True,
    )

    auto_flow_started_at = models.DateTimeField("Старт авто-цепочки (Китай)", null=True, blank=True)
    auto_flow_stage = models.PositiveSmallIntegerField("Этап авто-цепочки", default=0)

    local_flow_started_at = models.DateTimeField("Старт локальной цепочки (Киргизия)", null=True, blank=True)
    local_flow_stage = models.PositiveSmallIntegerField("Этап локальной цепочки", default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Посылка"
        verbose_name_plural = "Посылки"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return self.track_number


class ParcelHistory(models.Model):
    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.CASCADE,
        related_name="history",
        verbose_name="Посылка",
    )
    status = models.PositiveSmallIntegerField("Статус", choices=Parcel.Status.choices, db_index=True)
    message = models.TextField("Сообщение", blank=True)

    # ✅ точное время события по расписанию
    occurred_at = models.DateTimeField("Время события", default=timezone.now, db_index=True)

    # ✅ когда реально вставили запись в БД
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "История посылки"
        verbose_name_plural = "История посылок"
        ordering = ("-occurred_at", "-id")
        indexes = [
            models.Index(fields=["parcel", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.parcel.track_number}: {self.get_status_display()}"
