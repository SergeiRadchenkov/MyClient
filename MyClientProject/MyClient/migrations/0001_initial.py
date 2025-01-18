# Generated by Django 5.1.5 on 2025-01-17 17:25

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100, verbose_name='Имя')),
                ('last_name', models.CharField(max_length=100, verbose_name='Фамилия')),
                ('metro', models.CharField(max_length=255, verbose_name='Метро')),
                ('street', models.CharField(max_length=255, verbose_name='Улица')),
                ('house_number', models.CharField(max_length=10, verbose_name='Номер дома')),
                ('intercom', models.CharField(blank=True, max_length=50, null=True, verbose_name='Домофон')),
                ('price_offline', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Цена за работу оффлайн')),
                ('price_online', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Цена за работу онлайн')),
            ],
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Имя')),
                ('surname', models.CharField(max_length=100, verbose_name='Фамилия')),
                ('specialization', models.CharField(max_length=255, verbose_name='Специальность')),
            ],
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=django.utils.timezone.now, verbose_name='Дата')),
                ('time', models.TimeField(verbose_name='Время')),
                ('is_online', models.BooleanField(default=False, verbose_name='Онлайн')),
                ('is_completed', models.BooleanField(default=False, verbose_name='Выполнено')),
                ('cost', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Стоимость')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='MyClient.client')),
            ],
        ),
    ]
