from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

class SiteSettings(models.Model):
    """
    Глобальные настройки витрины/кабинета.
    Делаем одну запись и правим её через админку.
    """
    title = models.CharField(
        "Название проекта",
        max_length=100,
        default="LIDER CARGO",
    )

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

    default_dark_mode = models.BooleanField(
        "Тёмная тема по умолчанию",
        default=False,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return self.title or "Настройки сайта"



class PickupPoint(models.Model):
    name = models.CharField("Название", max_length=255)
    address = models.CharField("Адрес", max_length=255, blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Пункт выдачи"
        verbose_name_plural = "Пункты выдачи"

    def __str__(self):
        return f"{self.name} ({self.address})" if self.address else self.name



class CabinetProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="cabinet_profile",
    )
    full_name = models.CharField(max_length=255, verbose_name="ФИО")
    phone = models.CharField("Телефон", max_length=32, blank=True, unique=True)
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

    def __str__(self):
        return f"Профиль {self.user.username}"


class Parcel(models.Model):
    class Status(models.IntegerChoices):
        WAITING_CN = 0, "Ожидает поступления на склад в Китае"
        AT_CN = 1, "Принят на склад в Китае"
        FROM_CN = 2, "Отправлен из Китая"
        AT_PICKUP = 3, "Прибыл в пункт выдачи"
        RECEIVED = 4, "Получен"

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcels",
        verbose_name="Пользователь (если уже привязан)",
    )
    track_number = models.CharField("Трек-номер", max_length=20, unique=True)
    status = models.IntegerField(
        "Текущий статус", choices=Status.choices, default=Status.WAITING_CN
    )

    # авто-цепочка для «китайского» склада
    auto_flow_started_at = models.DateTimeField(
        "Старт авто-цепочки (Китай)", null=True, blank=True
    )
    auto_flow_stage = models.PositiveSmallIntegerField(
        "Этап авто-цепочки", default=0
    )
    # авто-цепочка для «местного» склада (после второго скана)
    local_flow_started_at = models.DateTimeField(
        "Старт локальной цепочки (Киргизия)", null=True, blank=True
    )
    local_flow_stage = models.PositiveSmallIntegerField(
        "Этап локальной цепочки", default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Посылка"
        verbose_name_plural = "Посылки"

    def __str__(self):
        return self.track_number


class ParcelHistory(models.Model):
    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.CASCADE,
        related_name="history",
        verbose_name="Посылка",
    )
    status = models.IntegerField(
        "Статус", choices=Parcel.Status.choices
    )
    message = models.TextField("Сообщение", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "История посылки"
        verbose_name_plural = "История посылок"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.parcel.track_number}: {self.get_status_display()}"