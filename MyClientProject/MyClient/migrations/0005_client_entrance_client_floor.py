# Generated by Django 5.1.5 on 2025-01-19 11:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MyClient', '0004_alter_profile_specialization'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='entrance',
            field=models.CharField(default=None, max_length=10, verbose_name='Подъезд'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='client',
            name='floor',
            field=models.CharField(default=None, max_length=10, verbose_name='Этаж'),
            preserve_default=False,
        ),
    ]
