from django.contrib import admin
from django.utils import timezone

from .models import DetallePedido, Devolucion, Pedido


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    can_delete = False
    readonly_fields = ('producto', 'precio', 'cantidad', 'subtotal')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'fecha', 'estado', 'metodo_pago', 'total')
    list_filter = ('estado', 'metodo_pago', 'fecha')
    search_fields = ('id', 'usuario__username', 'nombre_completo')
    list_editable = ('estado',)
    inlines = [DetallePedidoInline]
    readonly_fields = (
        'usuario',
        'fecha',
        'nombre_completo',
        'telefono',
        'direccion',
        'metodo_pago',
        'tarjeta_enmascarada',
        'total',
    )
    fieldsets = (
        (None, {'fields': ('usuario', 'fecha', 'estado')}),
        ('Datos de entrega', {'fields': ('nombre_completo', 'telefono', 'direccion')}),
        ('Pago', {'fields': ('metodo_pago', 'tarjeta_enmascarada', 'total')}),
    )

    @admin.display(description='Tarjeta')
    def tarjeta_enmascarada(self, obj):
        return obj.tarjeta_enmascarada or 'No aplica'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Devolucion)
class DevolucionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'producto',
        'numero_pedido',
        'cliente',
        'motivo',
        'fecha',
        'estado',
    )
    list_filter = ('estado', 'motivo', 'fecha')
    search_fields = (
        'detalle__producto__nombre',
        'detalle__pedido__usuario__username',
    )
    readonly_fields = ('detalle', 'motivo', 'descripcion', 'fecha', 'fecha_respuesta')
    fieldsets = (
        (
            'Solicitud del cliente',
            {'fields': ('detalle', 'motivo', 'descripcion', 'fecha')},
        ),
        ('Resolución', {'fields': ('estado', 'respuesta', 'fecha_respuesta')}),
    )

    @admin.display(description='Producto')
    def producto(self, obj):
        return obj.detalle.producto.nombre

    @admin.display(description='Pedido')
    def numero_pedido(self, obj):
        return obj.detalle.pedido_id

    @admin.display(description='Cliente')
    def cliente(self, obj):
        return obj.detalle.pedido.usuario.username

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if 'estado' in form.changed_data and obj.estado != Devolucion.SOLICITADA:
            obj.fecha_respuesta = timezone.now()
        super().save_model(request, obj, form, change)
