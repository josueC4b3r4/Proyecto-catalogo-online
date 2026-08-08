from django.urls import path

from . import views

urlpatterns = [
    path('', views.mis_pedidos, name='mis_pedidos'),
    path('confirmar/', views.confirmar_compra, name='confirmar_compra'),
    path('devoluciones/', views.mis_devoluciones, name='mis_devoluciones'),
    path(
        'devolver/<int:detalle_id>/',
        views.solicitar_devolucion,
        name='solicitar_devolucion',
    ),
    path('<int:pedido_id>/', views.detalle_pedido, name='detalle_pedido'),
]
