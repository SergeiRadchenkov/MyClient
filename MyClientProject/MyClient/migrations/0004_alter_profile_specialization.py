# Generated by Django 5.1.5 on 2025-01-18 14:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MyClient', '0003_profile_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='specialization',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
