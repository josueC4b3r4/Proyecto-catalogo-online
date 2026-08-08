from django import forms
from django.utils import timezone

from .models import Devolucion, Pedido

def tarjeta_de_prueba():
    dentro_de_cinco_anios = timezone.localdate().year + 5
    return {
        'numero': '4242 4242 4242 4242',
        'expiracion': f'12/{dentro_de_cinco_anios % 100:02d}',
        'cvv': '123',
    }


def digitos(texto):
    return ''.join(c for c in texto if c.isdigit())


def pasa_luhn(numero):
    suma = 0
    for posicion, caracter in enumerate(reversed(numero)):
        valor = int(caracter)
        if posicion % 2 == 1:
            valor *= 2
            if valor > 9:
                valor -= 9
        suma += valor
    return suma % 10 == 0


def marca_de(numero):
    if numero.startswith('4'):
        return 'Visa'
    if numero[:2] in ('34', '37'):
        return 'Amex'
    if numero[:2] in ('51', '52', '53', '54', '55'):
        return 'Mastercard'
    if 2221 <= int(numero[:4]) <= 2720:
        return 'Mastercard'
    return 'Tarjeta'


class DatosEnvioForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ('nombre_completo', 'telefono', 'direccion', 'metodo_pago')
        labels = {
            'nombre_completo': 'Nombre completo',
            'telefono': 'Teléfono',
            'direccion': 'Dirección de entrega',
            'metodo_pago': 'Forma de pago',
        }
        widgets = {
            'direccion': forms.Textarea(attrs={'rows': 3}),
            'metodo_pago': forms.RadioSelect,
        }

    def clean_telefono(self):
        telefono = self.cleaned_data['telefono']
        digitos = ''.join(c for c in telefono if c.isdigit())
        if len(digitos) < 10:
            raise forms.ValidationError('El teléfono debe tener al menos 10 dígitos.')
        return telefono


class PagoTarjetaForm(forms.Form):
    use_required_attribute = False

    numero = forms.CharField(
        label='Número de tarjeta',
        error_messages={'required': 'Escribe el número de la tarjeta.'},
        widget=forms.TextInput(attrs={
            'placeholder': '1234 5678 9012 3456',
            'autocomplete': 'off',
            'inputmode': 'numeric',
        }),
    )
    expiracion = forms.CharField(
        label='Vencimiento',
        error_messages={'required': 'Escribe el vencimiento como MM/AA.'},
        widget=forms.TextInput(attrs={
            'placeholder': 'MM/AA',
            'autocomplete': 'off',
            'inputmode': 'numeric',
        }),
    )
    cvv = forms.CharField(
        label='CVC/CVV',
        error_messages={'required': 'Escribe el código de seguridad de la tarjeta.'},
        widget=forms.TextInput(attrs={
            'placeholder': 'CVC',
            'autocomplete': 'off',
            'inputmode': 'numeric',
        }),
    )
    nombre_tarjeta = forms.CharField(
        label='Nombre en la tarjeta',
        error_messages={'required': 'Escribe el nombre del titular de la tarjeta.'},
        widget=forms.TextInput(attrs={
            'placeholder': 'Como aparece en el plástico',
            'autocomplete': 'off',
        }),
    )

    def clean_numero(self):
        numero = digitos(self.cleaned_data['numero'])

        if len(numero) < 13 or len(numero) > 19:
            raise forms.ValidationError('Un número de tarjeta tiene entre 13 y 19 dígitos.')
        if not pasa_luhn(numero):
            raise forms.ValidationError('Ese número de tarjeta no es válido.')

        return numero

    def clean_expiracion(self):
        partes = digitos(self.cleaned_data['expiracion'])

        if len(partes) != 4:
            raise forms.ValidationError('Escribe el vencimiento como MM/AA.')

        mes = int(partes[:2])
        anio = 2000 + int(partes[2:])

        if mes < 1 or mes > 12:
            raise forms.ValidationError('El mes debe estar entre 01 y 12.')

        hoy = timezone.localdate()
        if (anio, mes) < (hoy.year, hoy.month):
            raise forms.ValidationError('Esa tarjeta ya está vencida.')

        return f'{mes:02d}/{partes[2:]}'

    def clean_cvv(self):
        cvv = digitos(self.cleaned_data['cvv'])

        if len(cvv) < 3 or len(cvv) > 4:
            raise forms.ValidationError('El código de seguridad tiene 3 o 4 dígitos.')

        return cvv

    def clean_nombre_tarjeta(self):
        nombre = self.cleaned_data['nombre_tarjeta'].strip()

        if len(nombre) < 3:
            raise forms.ValidationError('El nombre del titular es demasiado corto.')

        return nombre

    def marca(self):
        return marca_de(self.cleaned_data['numero'])

    def ultimos_cuatro(self):
        return self.cleaned_data['numero'][-4:]


class DevolucionForm(forms.ModelForm):
    class Meta:
        model = Devolucion
        fields = ('motivo', 'descripcion')
        labels = {
            'motivo': '¿Qué pasó con el producto?',
            'descripcion': 'Explícanos con detalle',
        }
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_descripcion(self):
        descripcion = self.cleaned_data['descripcion'].strip()
        if len(descripcion) < 15:
            raise forms.ValidationError(
                'Describe el problema con al menos 15 letras para que podamos revisarlo.'
            )
        return descripcion
