'''models.py'''
from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Client(models.Model):
    first_name = models.CharField("Имя", max_length=100)
    last_name = models.CharField("Фамилия", max_length=100, blank=True, null=True, default='яя')
    metro = models.CharField("Метро", max_length=255, blank=True, null=True, default='яя')
    street = models.CharField("Улица", max_length=255, blank=True, null=True, default='яя')
    house_number = models.CharField("Номер дома", max_length=10, blank=True, null=True, default='яя')
    entrance = models.CharField("Подъезд", max_length=10, blank=True, null=True, default='яя')
    floor = models.CharField("Этаж", max_length=10, blank=True, null=True, default='яя')
    intercom = models.CharField("Домофон", max_length=50, blank=True, null=True, default='яя')
    phone = models.CharField("Телефон", max_length=20, blank=True, null=True, default='яя')
    price_offline = models.DecimalField("Цена за работу оффлайн", max_digits=10, decimal_places=2, blank=True, default=0)
    price_online = models.DecimalField("Цена за работу онлайн", max_digits=10, decimal_places=2, blank=True, default=0)
    created_at = models.DateTimeField("Дата добавления", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # Новые клиенты сверху

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Schedule(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField("Дата", default=now)
    time = models.TimeField("Время")
    is_online = models.BooleanField("Онлайн", default=False)
    is_completed = models.BooleanField("Выполнено", default=False)
    is_paid = models.BooleanField("Оплачено", default=False)
    is_canceled = models.BooleanField("Отменено", default=False)
    cost = models.DecimalField("Стоимость", max_digits=10, decimal_places=2)

    def get_plan(self):
        return float(self.cost)

    def get_due(self):
        return float(self.cost) if self.is_completed and not self.is_paid else 0

    def get_paid(self):
        return float(self.cost) if self.is_paid else 0

    def get_cancel(self):
        return float(self.cost) if self.is_canceled else 0


class Block(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активный'),
        ('completed', 'Завершённый'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='blocks', verbose_name="Клиент")
    block_number = models.PositiveIntegerField("Номер блока")
    total_meetings = models.PositiveIntegerField("Количество встреч в блоке")
    completed_meetings = models.PositiveIntegerField("Пройденные встречи", default=0)
    cost = models.DecimalField("Стоимость блока", max_digits=10, decimal_places=2)
    status = models.CharField("Статус блока", max_length=10, choices=STATUS_CHOICES, default='active')

    class Meta:
        unique_together = ('client', 'block_number')  # Каждый блок уникален для клиента
        ordering = ['client', 'block_number']
        verbose_name = "Блок встреч"
        verbose_name_plural = "Блоки встреч"

    def __str__(self):
        client_name = str(self.client).removesuffix(" яя")
        return f"{client_name}. Блок {self.block_number}"

    def save(self, *args, **kwargs):
        previous_status = self.status
        # Автоматическое обновление статуса
        if self.completed_meetings >= self.total_meetings:
            self.status = 'completed'
        super().save(*args, **kwargs)

    @staticmethod
    def create_block(client, total_meetings, completed_meetings, cost):
        """
        Удобный метод для создания нового блока.
        """
        last_block = Block.objects.filter(client=client).order_by('block_number').last()
        block_number = last_block.block_number + 1 if last_block else 1
        return Block.objects.create(
            client=client,
            block_number=block_number,
            completed_meetings=completed_meetings,
            total_meetings=total_meetings,
            cost=cost
        )

    def increment_completed_meetings(self):
        """
        Увеличивает количество завершённых встреч на 1.
        """
        if self.status == 'completed':
            raise ValueError("Блок уже завершён.")
        self.completed_meetings += 1
        self.save()


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', unique=True)
    name = models.CharField("Имя", max_length=100)
    surname = models.CharField("Фамилия", max_length=100)
    specialization = models.CharField(max_length=255, blank=True, null=True)  # Специальность

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.specialization})"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class ScheduleAnalytics:
    def __init__(self, schedules):
        self.schedules = schedules


