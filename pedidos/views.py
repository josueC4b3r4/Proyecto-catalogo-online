from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from carrito.models import Carrito

from .forms import DatosEnvioForm, DevolucionForm, PagoTarjetaForm, tarjeta_de_prueba
from .models import DetallePedido, Devolucion, Pedido


@login_required
def confirmar_compra(request):
    carrito = Carrito.objects.filter(usuario=request.user).first()

    if carrito is None or not carrito.items.exists():
        messages.error(request, 'Tu carrito está vacío.')
        return redirect('ver_carrito')

    tarjeta_inicial = tarjeta_de_prueba()
    tarjeta_inicial['nombre_tarjeta'] = (
        request.user.get_full_name() or request.user.username
    )

    if request.method == 'POST':
        form = DatosEnvioForm(request.POST)
        con_tarjeta = request.POST.get('metodo_pago') == Pedido.TARJETA
        form_tarjeta = PagoTarjetaForm(
            request.POST if con_tarjeta else None, initial=tarjeta_inicial
        )
        pago_aprobado = form_tarjeta.is_valid() if con_tarjeta else True

        if form.is_valid() and pago_aprobado:
            items = list(carrito.items.select_related('producto'))
            sin_stock = [i.producto.nombre for i in items if i.cantidad > i.producto.stock]

            if sin_stock:
                messages.error(
                    request, f'Ya no hay suficiente stock de: {", ".join(sin_stock)}.'
                )
                return redirect('ver_carrito')

            pedido = form.save(commit=False)
            pedido.usuario = request.user
            pedido.total = carrito.total

            if con_tarjeta:
                pedido.estado = Pedido.PAGADO
                pedido.tarjeta_marca = form_tarjeta.marca()
                pedido.tarjeta_final = form_tarjeta.ultimos_cuatro()
            else:
                pedido.estado = Pedido.PENDIENTE

            with transaction.atomic():
                pedido.save()
                for item in items:
                    DetallePedido.objects.create(
                        pedido=pedido,
                        producto=item.producto,
                        precio=item.producto.precio,
                        cantidad=item.cantidad,
                    )
                    item.producto.stock -= item.cantidad
                    item.producto.save()
                carrito.items.all().delete()

            if con_tarjeta:
                messages.success(
                    request,
                    f'Pago aprobado con {pedido.tarjeta_enmascarada}. '
                    f'Tu compra quedó registrada.',
                )
            else:
                messages.success(
                    request, 'Tu compra fue registrada. Pagarás al recibirla.'
                )
            return redirect('detalle_pedido', pedido.pk)
    else:
        form = DatosEnvioForm(initial={
            'nombre_completo': request.user.get_full_name(),
            'telefono': request.user.telefono,
            'direccion': request.user.direccion,
            'metodo_pago': Pedido.TARJETA,
        })
        form_tarjeta = PagoTarjetaForm(initial=tarjeta_inicial)

    return render(request, 'pedidos/confirmar.html', {
        'form': form,
        'form_tarjeta': form_tarjeta,
        'carrito': carrito,
    })


@login_required
def mis_pedidos(request):
    pedidos = Pedido.objects.filter(usuario=request.user)
    return render(request, 'pedidos/lista.html', {'pedidos': pedidos})


@login_required
def detalle_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id, usuario=request.user)
    return render(request, 'pedidos/detalle.html', {'pedido': pedido})


@login_required
def solicitar_devolucion(request, detalle_id):
    detalle = get_object_or_404(
        DetallePedido.objects.select_related('pedido', 'producto'),
        pk=detalle_id,
        pedido__usuario=request.user,
    )

    if detalle.pedido.estado != Pedido.ENTREGADO:
        messages.error(
            request, 'Solo puedes devolver productos de un pedido ya entregado.'
        )
        return redirect('detalle_pedido', detalle.pedido_id)

    if Devolucion.objects.filter(detalle=detalle).exists():
        messages.error(request, 'Ya solicitaste la devolución de este producto.')
        return redirect('detalle_pedido', detalle.pedido_id)

    if request.method == 'POST':
        form = DevolucionForm(request.POST)
        if form.is_valid():
            devolucion = form.save(commit=False)
            devolucion.detalle = detalle
            devolucion.save()
            messages.success(
                request,
                'Tu solicitud fue registrada. Te avisaremos cuando la revisemos.',
            )
            return redirect('mis_devoluciones')
    else:
        form = DevolucionForm()

    return render(
        request, 'pedidos/devolucion.html', {'form': form, 'detalle': detalle}
    )


@login_required
def mis_devoluciones(request):
    devoluciones = Devolucion.objects.filter(
        detalle__pedido__usuario=request.user
    ).select_related('detalle__producto', 'detalle__pedido')
    return render(
        request, 'pedidos/devoluciones.html', {'devoluciones': devoluciones}
    )
