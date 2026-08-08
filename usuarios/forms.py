from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Usuario


class RegistroClienteForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = Usuario
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email']
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe una cuenta registrada con este correo.')
        return email

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.rol = Usuario.CLIENTE
        if commit:
            usuario.save()
        return usuario


class PerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ('foto', 'first_name', 'last_name', 'email', 'telefono', 'direccion')
        labels = {
            'foto': 'Foto de perfil',
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'telefono': 'Teléfono',
            'direccion': 'Dirección de entrega',
        }
        widgets = {
            'direccion': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if not email:
            raise forms.ValidationError('El correo es obligatorio.')
        repetido = Usuario.objects.filter(email=email).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError('Ya existe otra cuenta registrada con este correo.')
        return email

    def clean_telefono(self):
        telefono = self.cleaned_data['telefono']
        if telefono:
            digitos = ''.join(c for c in telefono if c.isdigit())
            if len(digitos) < 10:
                raise forms.ValidationError('El teléfono debe tener al menos 10 dígitos.')
        return telefono
