from django import forms
from django.contrib.auth.forms import UserChangeForm
from .models import Profile
from django.contrib.auth.models import User

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'specialization')  # добавьте нужные поля

    specialization = forms.CharField(max_length=255, required=False)  # поле для специальности

    def save(self, commit=True):
        user = super().save(commit=False)
        user.profile.specialization = self.cleaned_data.get('specialization', '')
        if commit:
            user.save()
            user.profile.save()
        return user
