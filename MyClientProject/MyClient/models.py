from django.db import models
from django.utils.timezone import now

class Client(models.Model):
    first_name = models.CharField("Имя", max_length=100)
    last_name = models.CharField("Фамилия", max_length=100)
    metro = models.CharField("Метро", max_length=255)
    street = models.CharField("Улица", max_length=255)
    house_number = models.CharField("Номер дома", max_length=10)
    intercom = models.CharField("Домофон", max_length=50, blank=True, null=True)
    phone = models.CharField("Телефон", max_length=15, blank=True, null=True)
    price_offline = models.DecimalField("Цена за работу оффлайн", max_digits=10, decimal_places=2)
    price_online = models.DecimalField("Цена за работу онлайн", max_digits=10, decimal_places=2)

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
    name = models.CharField("Имя", max_length=100)
    surname = models.CharField("Фамилия", max_length=100)
    specialization = models.CharField("Специальность", max_length=255)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.specialization})"