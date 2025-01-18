from django.contrib import admin
from .models import Client, Schedule, Profile

admin.site.register(Client)
admin.site.register(Schedule)
admin.site.register(Profile)
