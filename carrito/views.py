from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogo.models import Producto

from .models import Carrito, ItemCarrito


@login_required
def ver_carrito(request):
    carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
    return render(request, 'carrito/ver.html', {'carrito': carrito})


@login_required
@require_POST
def agregar_al_carrito(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id, activo=True)
    carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
    item = ItemCarrito.objects.filter(carrito=carrito, producto=producto).first()
    cantidad_actual = item.cantidad if item else 0

    if cantidad_actual + 1 > producto.stock:
        messages.error(request, 'No hay suficiente stock de este producto.')
    elif item:
        item.cantidad += 1
        item.save()
        messages.success(request, 'Producto agregado al carrito.')
    else:
        ItemCarrito.objects.create(carrito=carrito, producto=producto, cantidad=1)
        messages.success(request, 'Producto agregado al carrito.')

    return redirect('ver_carrito')


@login_required
@require_POST
def actualizar_cantidad(request, item_id):
    item = get_object_or_404(ItemCarrito, pk=item_id, carrito__usuario=request.user)

    try:
        cantidad = int(request.POST.get('cantidad', 0))
    except ValueError:
        cantidad = 0

    if cantidad < 1:
        messages.error(request, 'La cantidad debe ser mayor que cero.')
    elif cantidad > item.producto.stock:
        messages.error(request, 'No hay suficiente stock de este producto.')
    else:
        item.cantidad = cantidad
        item.save()
        messages.success(request, 'Cantidad actualizada.')

    return redirect('ver_carrito')


@login_required
@require_POST
def eliminar_del_carrito(request, item_id):
    item = get_object_or_404(ItemCarrito, pk=item_id, carrito__usuario=request.user)
    item.delete()
    messages.success(request, 'Producto eliminado del carrito.')
    return redirect('ver_carrito')
