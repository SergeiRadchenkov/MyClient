# Generated by Django 5.1.5 on 2025-02-13 17:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MyClient', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='use_block',
            field=models.BooleanField(default=False, verbose_name='Оплатить блоком'),
        ),
    ]
