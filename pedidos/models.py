from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from catalogo.models import Producto


class Pedido(models.Model):
    PENDIENTE = 'PENDIENTE'
    PAGADO = 'PAGADO'
    EN_PREPARACION = 'EN_PREPARACION'
    ENVIADO = 'ENVIADO'
    ENTREGADO = 'ENTREGADO'
    CANCELADO = 'CANCELADO'
    ESTADOS = [
        (PENDIENTE, 'Pendiente de pago'),
        (PAGADO, 'Pagado'),
        (EN_PREPARACION, 'En preparación'),
        (ENVIADO, 'Enviado'),
        (ENTREGADO, 'Entregado'),
        (CANCELADO, 'Cancelado'),
    ]

    SIGUIENTES = {
        PENDIENTE: [PAGADO, CANCELADO],
        PAGADO: [EN_PREPARACION, CANCELADO],
        EN_PREPARACION: [ENVIADO, CANCELADO],
        ENVIADO: [ENTREGADO],
        ENTREGADO: [],
        CANCELADO: [],
    }

    TARJETA = 'TARJETA'
    EFECTIVO = 'EFECTIVO'
    METODOS_PAGO = [
        (TARJETA, 'Tarjeta'),
        (EFECTIVO, 'Efectivo contra entrega'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='pedidos'
    )
    nombre_completo = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)
    direccion = models.TextField()
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default=EFECTIVO)
    tarjeta_marca = models.CharField(max_length=20, blank=True)
    tarjeta_final = models.CharField(max_length=4, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    total = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f'Pedido {self.pk} de {self.usuario.username}'

    @property
    def tarjeta_enmascarada(self):
        if not self.tarjeta_final:
            return ''
        return f'{self.tarjeta_marca} **** **** **** {self.tarjeta_final}'

    def clean(self):
        if not self.pk:
            return

        anterior = Pedido.objects.get(pk=self.pk).estado
        if self.estado == anterior:
            return

        if self.estado not in self.SIGUIENTES[anterior]:
            permitidos = self.SIGUIENTES[anterior]
            etiquetas = dict(self.ESTADOS)
            if permitidos:
                opciones = ', '.join(etiquetas[e] for e in permitidos)
                detalle = f'Desde "{etiquetas[anterior]}" solo puede pasar a: {opciones}.'
            else:
                detalle = f'Un pedido "{etiquetas[anterior]}" ya no cambia de estado.'
            raise ValidationError({'estado': detalle})


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    precio = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=1),
                name='detallepedido_cantidad_minima',
            )
        ]

    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre}'

    @property
    def subtotal(self):
        return self.precio * self.cantidad


class Devolucion(models.Model):
    DANADO = 'DANADO'
    EQUIVOCADO = 'EQUIVOCADO'
    NO_CORRESPONDE = 'NO_CORRESPONDE'
    OTRO = 'OTRO'
    MOTIVOS = [
        (DANADO, 'El producto llegó dañado'),
        (EQUIVOCADO, 'Me enviaron un producto distinto'),
        (NO_CORRESPONDE, 'No corresponde a la descripción'),
        (OTRO, 'Otro motivo'),
    ]

    SOLICITADA = 'SOLICITADA'
    ACEPTADA = 'ACEPTADA'
    RECHAZADA = 'RECHAZADA'
    ESTADOS = [
        (SOLICITADA, 'Solicitada'),
        (ACEPTADA, 'Aceptada'),
        (RECHAZADA, 'Rechazada'),
    ]

    detalle = models.OneToOneField(
        DetallePedido, on_delete=models.CASCADE, related_name='devolucion'
    )
    motivo = models.CharField(max_length=20, choices=MOTIVOS)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default=SOLICITADA)
    respuesta = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'devolución'
        verbose_name_plural = 'devoluciones'

    def __str__(self):
        return f'Devolución del pedido {self.detalle.pedido_id}: {self.detalle.producto.nombre}'

    @property
    def pedido(self):
        return self.detalle.pedido

    def clean(self):
        if self.detalle_id and self.detalle.pedido.estado != Pedido.ENTREGADO:
            raise ValidationError(
                'Solo se pueden devolver productos de un pedido ya entregado.'
            )

        if self.estado != self.SOLICITADA and not self.respuesta.strip():
            raise ValidationError({
                'respuesta': 'Explica al cliente por qué aceptas o rechazas la devolución.'
            })
