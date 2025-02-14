from django.contrib import admin
from .models import Client, Schedule, Profile, Block

admin.site.register(Client)
admin.site.register(Schedule)
admin.site.register(Profile)
admin.site.register(Block)
