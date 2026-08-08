from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, Producto
from usuarios.models import Usuario

from .models import Carrito, ItemCarrito


class CarritoBaseTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre='Tenis')
        self.tenis = Producto.objects.create(
            nombre='Tenis de prueba',
            categoria=self.categoria,
            precio=Decimal('100.00'),
            stock=5,
        )
        self.otro_tenis = Producto.objects.create(
            nombre='Otro tenis',
            categoria=self.categoria,
            precio=Decimal('250.00'),
            stock=3,
        )
        self.cliente = Usuario.objects.create_user(username='cliente_prueba')


class AccesoTests(CarritoBaseTests):
    def test_visitante_es_redirigido_al_login(self):
        respuesta = self.client.get(reverse('ver_carrito'))
        self.assertRedirects(respuesta, f"{reverse('login')}?next={reverse('ver_carrito')}")

    def test_visitante_no_puede_agregar(self):
        respuesta = self.client.post(reverse('agregar_al_carrito', args=[self.tenis.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(ItemCarrito.objects.count(), 0)

    def test_agregar_rechaza_get(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('agregar_al_carrito', args=[self.tenis.pk]))
        self.assertEqual(respuesta.status_code, 405)
        self.assertEqual(ItemCarrito.objects.count(), 0)


class AgregarTests(CarritoBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)

    def test_agregar_crea_carrito_e_item(self):
        self.client.post(reverse('agregar_al_carrito', args=[self.tenis.pk]))
        carrito = Carrito.objects.get(usuario=self.cliente)
        item = carrito.items.get()
        self.assertEqual(item.producto, self.tenis)
        self.assertEqual(item.cantidad, 1)

    def test_agregar_dos_veces_suma_cantidad(self):
        self.client.post(reverse('agregar_al_carrito', args=[self.tenis.pk]))
        self.client.post(reverse('agregar_al_carrito', args=[self.tenis.pk]))
        self.assertEqual(ItemCarrito.objects.count(), 1)
        self.assertEqual(ItemCarrito.objects.get().cantidad, 2)

    def test_no_agrega_mas_alla_del_stock(self):
        for _ in range(self.tenis.stock):
            self.client.post(reverse('agregar_al_carrito', args=[self.tenis.pk]))
        self.client.post(reverse('agregar_al_carrito', args=[self.tenis.pk]))
        self.assertEqual(ItemCarrito.objects.get().cantidad, self.tenis.stock)

    def test_no_agrega_producto_inactivo(self):
        self.tenis.activo = False
        self.tenis.save()
        respuesta = self.client.post(reverse('agregar_al_carrito', args=[self.tenis.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(ItemCarrito.objects.count(), 0)


class ActualizarTests(CarritoBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)
        self.carrito = Carrito.objects.create(usuario=self.cliente)
        self.item = ItemCarrito.objects.create(
            carrito=self.carrito, producto=self.tenis, cantidad=2
        )

    def test_actualiza_cantidad_valida(self):
        self.client.post(reverse('actualizar_cantidad', args=[self.item.pk]), {'cantidad': 4})
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 4)

    def test_rechaza_cantidad_mayor_que_stock(self):
        self.client.post(reverse('actualizar_cantidad', args=[self.item.pk]), {'cantidad': 50})
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 2)

    def test_rechaza_cantidad_cero(self):
        self.client.post(reverse('actualizar_cantidad', args=[self.item.pk]), {'cantidad': 0})
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 2)

    def test_rechaza_cantidad_no_numerica(self):
        self.client.post(reverse('actualizar_cantidad', args=[self.item.pk]), {'cantidad': 'diez'})
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 2)


class EliminarTests(CarritoBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)
        self.carrito = Carrito.objects.create(usuario=self.cliente)
        self.item = ItemCarrito.objects.create(
            carrito=self.carrito, producto=self.tenis, cantidad=1
        )

    def test_elimina_su_propio_item(self):
        self.client.post(reverse('eliminar_del_carrito', args=[self.item.pk]))
        self.assertEqual(ItemCarrito.objects.count(), 0)

    def test_no_elimina_el_producto_del_catalogo(self):
        self.client.post(reverse('eliminar_del_carrito', args=[self.item.pk]))
        self.assertTrue(Producto.objects.filter(pk=self.tenis.pk).exists())


class CarritoAjenoTests(CarritoBaseTests):
    def setUp(self):
        super().setUp()
        self.intruso = Usuario.objects.create_user(username='intruso')
        self.carrito = Carrito.objects.create(usuario=self.cliente)
        self.item = ItemCarrito.objects.create(
            carrito=self.carrito, producto=self.tenis, cantidad=1
        )
        self.client.force_login(self.intruso)

    def test_no_puede_eliminar_item_ajeno(self):
        respuesta = self.client.post(reverse('eliminar_del_carrito', args=[self.item.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(ItemCarrito.objects.filter(pk=self.item.pk).exists())

    def test_no_puede_actualizar_item_ajeno(self):
        respuesta = self.client.post(
            reverse('actualizar_cantidad', args=[self.item.pk]), {'cantidad': 5}
        )
        self.assertEqual(respuesta.status_code, 404)
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 1)

    def test_no_ve_el_carrito_ajeno(self):
        respuesta = self.client.get(reverse('ver_carrito'))
        self.assertNotContains(respuesta, self.tenis.nombre)


class TotalesTests(CarritoBaseTests):
    def setUp(self):
        super().setUp()
        self.carrito = Carrito.objects.create(usuario=self.cliente)

    def test_subtotal_multiplica_precio_por_cantidad(self):
        item = ItemCarrito.objects.create(
            carrito=self.carrito, producto=self.tenis, cantidad=3
        )
        self.assertEqual(item.subtotal, Decimal('300.00'))

    def test_total_suma_todos_los_items(self):
        ItemCarrito.objects.create(carrito=self.carrito, producto=self.tenis, cantidad=2)
        ItemCarrito.objects.create(carrito=self.carrito, producto=self.otro_tenis, cantidad=1)
        self.assertEqual(self.carrito.total, Decimal('450.00'))

    def test_total_de_carrito_vacio_es_cero(self):
        self.assertEqual(self.carrito.total, 0)
