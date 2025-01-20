from django import forms
from django.contrib.auth.forms import UserChangeForm
from .models import Profile, Client
from django.contrib.auth.models import User
from django.forms import ModelForm

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

class ClientForm(ModelForm):
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'metro', 'street', 'house_number',
                  'entrance', 'floor', 'intercom', 'phone', 'price_offline', 'price_online']
        widgets = {
            'last_name': forms.TextInput(attrs={'required': False}),
            'metro': forms.TextInput(attrs={'list': 'metro-list',
                                            'class': 'form-control', 'placeholder': 'Введите станцию метро...',
                                            'required': False}),
            'street': forms.TextInput(attrs={'required': False}),
            'house_number': forms.TextInput(attrs={'required': False}),
            'entrance': forms.TextInput(attrs={'required': False}),
            'floor': forms.TextInput(attrs={'required': False}),
            'intercom': forms.TextInput(attrs={'required': False}),
            'phone': forms.TextInput(attrs={'required': False}),
            'price_offline': forms.NumberInput(attrs={'required': False}),
            'price_online': forms.NumberInput(attrs={'required': False}),
        }
