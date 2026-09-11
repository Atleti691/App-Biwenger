from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Usuario')
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput)


class FirstPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(label='Contraseña temporal', widget=forms.PasswordInput)
    new_password1 = forms.CharField(label='Nueva contraseña', widget=forms.PasswordInput)
    new_password2 = forms.CharField(label='Repite la nueva contraseña', widget=forms.PasswordInput)

