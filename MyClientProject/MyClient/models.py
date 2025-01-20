'''models.py'''
from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Client(models.Model):
    first_name = models.CharField("Имя", max_length=100)
    last_name = models.CharField("Фамилия", max_length=100, blank=True)
    metro = models.CharField("Метро", max_length=255, blank=True)
    street = models.CharField("Улица", max_length=255, blank=True)
    house_number = models.CharField("Номер дома", max_length=10, blank=True)
    entrance = models.CharField("Подъезд", max_length=10, blank=True)
    floor = models.CharField("Этаж", max_length=10, blank=True, null=True)
    intercom = models.CharField("Домофон", max_length=50, blank=True, null=True)
    phone = models.CharField("Телефон", max_length=15, blank=True, null=True)
    price_offline = models.DecimalField("Цена за работу оффлайн", max_digits=10, decimal_places=2)
    price_online = models.DecimalField("Цена за работу онлайн", max_digits=10, decimal_places=2)
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
    cost = models.DecimalField("Стоимость", max_digits=10, decimal_places=2)

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
