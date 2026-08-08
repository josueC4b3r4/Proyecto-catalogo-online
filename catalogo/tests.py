from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .models import Categoria, Producto


class CatalogoTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre='Tenis')
        self.producto = Producto.objects.create(
            nombre='Tenis Nike Court Vision',
            categoria=self.categoria,
            precio=Decimal('1799.00'),
            talla='27.5',
            color='Negro',
            stock=11,
        )

    def test_catalogo_muestra_productos_de_la_base(self):
        respuesta = self.client.get(reverse('catalogo'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Tenis Nike Court Vision')
        self.assertContains(respuesta, '1799.00')

    def test_producto_inactivo_no_aparece_en_el_catalogo(self):
        self.producto.activo = False
        self.producto.save()

        respuesta = self.client.get(reverse('catalogo'))
        self.assertNotContains(respuesta, 'Tenis Nike Court Vision')

    def test_detalle_muestra_los_datos_del_producto(self):
        respuesta = self.client.get(
            reverse('detalle_producto', args=[self.producto.id])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Tenis Nike Court Vision')
        self.assertContains(respuesta, '27.5')

    def test_producto_inexistente_devuelve_404(self):
        respuesta = self.client.get(reverse('detalle_producto', args=[9999]))
        self.assertEqual(respuesta.status_code, 404)

    def test_detalle_de_producto_inactivo_devuelve_404(self):
        self.producto.activo = False
        self.producto.save()

        respuesta = self.client.get(
            reverse('detalle_producto', args=[self.producto.id])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_inicio_muestra_productos_recientes(self):
        respuesta = self.client.get(reverse('inicio'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Tenis Nike Court Vision')


class FiltrosDelCatalogoTests(TestCase):
    def setUp(self):
        self.tenis = Categoria.objects.create(nombre='Tenis')
        self.playeras = Categoria.objects.create(nombre='Playeras')

        self.nike = Producto.objects.create(
            nombre='Tenis Nike Court Vision',
            categoria=self.tenis,
            precio=Decimal('1799.00'),
            talla='27.5',
            color='Negro',
            stock=11,
        )
        self.jordan = Producto.objects.create(
            nombre='Tenis Jordan',
            categoria=self.tenis,
            precio=Decimal('2500.00'),
            talla='28.5',
            color='Rojo',
            stock=6,
        )
        self.playera = Producto.objects.create(
            nombre='Playera básica',
            categoria=self.playeras,
            precio=Decimal('249.00'),
            talla='M',
            color='Negro',
            stock=25,
        )

    def nombres(self, respuesta):
        return sorted(p.nombre for p in respuesta.context['productos'])

    def test_sin_filtros_muestra_todo(self):
        respuesta = self.client.get(reverse('catalogo'))
        self.assertEqual(len(respuesta.context['productos']), 3)
        self.assertFalse(respuesta.context['hay_filtros'])

    def test_filtra_por_categoria(self):
        respuesta = self.client.get(reverse('catalogo'), {'categoria': self.playeras.pk})
        self.assertEqual(self.nombres(respuesta), ['Playera básica'])

    def test_filtra_por_talla(self):
        respuesta = self.client.get(reverse('catalogo'), {'talla': '28.5'})
        self.assertEqual(self.nombres(respuesta), ['Tenis Jordan'])

    def test_filtra_por_color(self):
        respuesta = self.client.get(reverse('catalogo'), {'color': 'Negro'})
        self.assertEqual(self.nombres(respuesta), ['Playera básica', 'Tenis Nike Court Vision'])

    def test_combina_varios_filtros(self):
        respuesta = self.client.get(
            reverse('catalogo'), {'categoria': self.tenis.pk, 'color': 'Negro'}
        )
        self.assertEqual(self.nombres(respuesta), ['Tenis Nike Court Vision'])

    def test_filtro_sin_resultados_no_falla(self):
        respuesta = self.client.get(reverse('catalogo'), {'talla': 'XXL'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['productos']), 0)
        self.assertContains(respuesta, 'Ningún producto coincide')

    def test_categoria_no_numerica_se_ignora(self):
        respuesta = self.client.get(reverse('catalogo'), {'categoria': 'abc'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['productos']), 3)

    def test_los_filtros_solo_ofrecen_valores_existentes(self):
        respuesta = self.client.get(reverse('catalogo'))
        self.assertEqual(sorted(respuesta.context['tallas']), ['27.5', '28.5', 'M'])
        self.assertEqual(sorted(respuesta.context['colores']), ['Negro', 'Rojo'])

    def test_los_filtros_no_muestran_productos_inactivos(self):
        self.jordan.activo = False
        self.jordan.save()

        respuesta = self.client.get(reverse('catalogo'), {'categoria': self.tenis.pk})
        self.assertEqual(self.nombres(respuesta), ['Tenis Nike Court Vision'])
        self.assertNotIn('28.5', list(respuesta.context['tallas']))


class ReglasDelModeloTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre='Tenis')
        self.producto = Producto.objects.create(
            nombre='Tenis Nike Court Vision',
            categoria=self.categoria,
            precio=Decimal('1799.00'),
            stock=11,
        )

    def test_precio_no_puede_ser_negativo(self):
        self.producto.precio = Decimal('-1.00')
        with self.assertRaises(ValidationError):
            self.producto.full_clean()

    def test_stock_no_puede_ser_negativo(self):
        self.producto.stock = -1
        with self.assertRaises(ValidationError):
            self.producto.full_clean()

    def test_no_se_puede_borrar_categoria_con_productos(self):
        with self.assertRaises(ProtectedError):
            self.categoria.delete()

        self.assertTrue(Categoria.objects.filter(pk=self.categoria.pk).exists())
