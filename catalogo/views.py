from django.shortcuts import get_object_or_404, render

from .models import Categoria, Producto


def inicio(request):
    productos = Producto.objects.filter(activo=True)[:4]
    return render(request, 'inicio.html', {'productos': productos})


def lista_productos(request):
    productos = Producto.objects.filter(activo=True)

    categoria = request.GET.get('categoria', '')
    talla = request.GET.get('talla', '')
    color = request.GET.get('color', '')

    if categoria.isdigit():
        productos = productos.filter(categoria_id=int(categoria))
    if talla:
        productos = productos.filter(talla=talla)
    if color:
        productos = productos.filter(color=color)

    disponibles = Producto.objects.filter(activo=True)

    contexto = {
        'productos': productos,
        'categorias': Categoria.objects.filter(activo=True),
        'tallas': disponibles.exclude(talla='').values_list('talla', flat=True).distinct().order_by('talla'),
        'colores': disponibles.exclude(color='').values_list('color', flat=True).distinct().order_by('color'),
        'categoria_elegida': categoria,
        'talla_elegida': talla,
        'color_elegido': color,
        'hay_filtros': bool(categoria or talla or color),
    }
    return render(request, 'catalogo/lista.html', contexto)


def detalle_producto(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id, activo=True)
    return render(request, 'catalogo/detalle.html', {'producto': producto})
