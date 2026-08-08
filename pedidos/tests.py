import re
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from carrito.models import Carrito, ItemCarrito
from catalogo.models import Categoria, Producto
from usuarios.models import Usuario

from .forms import DatosEnvioForm, PagoTarjetaForm
from .models import DetallePedido, Devolucion, Pedido

TARJETA_VALIDA = {
    'numero': '4242 4242 4242 4242',
    'expiracion': f'12/{(timezone.localdate().year + 5) % 100:02d}',
    'cvv': '123',
    'nombre_tarjeta': 'Cliente De Prueba',
}

DATOS_VALIDOS = {
    'nombre_completo': 'Cliente De Prueba',
    'telefono': '5512345678',
    'direccion': 'Calle Falsa 123',
    'metodo_pago': Pedido.TARJETA,
    **TARJETA_VALIDA,
}

DATOS_EFECTIVO = {
    'nombre_completo': 'Cliente De Prueba',
    'telefono': '5512345678',
    'direccion': 'Calle Falsa 123',
    'metodo_pago': Pedido.EFECTIVO,
}


class PedidosBaseTests(TestCase):
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
        self.carrito = Carrito.objects.create(usuario=self.cliente)

    def llenar_carrito(self):
        ItemCarrito.objects.create(carrito=self.carrito, producto=self.tenis, cantidad=2)
        ItemCarrito.objects.create(carrito=self.carrito, producto=self.otro_tenis, cantidad=1)


class AccesoTests(PedidosBaseTests):
    def test_visitante_no_ve_sus_pedidos(self):
        respuesta = self.client.get(reverse('mis_pedidos'))
        self.assertRedirects(respuesta, f"{reverse('login')}?next={reverse('mis_pedidos')}")

    def test_visitante_no_puede_confirmar(self):
        respuesta = self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_visitante_no_ve_un_comprobante(self):
        self.llenar_carrito()
        self.client.force_login(self.cliente)
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        pedido = Pedido.objects.get()
        self.client.logout()
        respuesta = self.client.get(reverse('detalle_pedido', args=[pedido.pk]))
        self.assertEqual(respuesta.status_code, 302)


class CompraTests(PedidosBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)
        self.llenar_carrito()

    def test_la_compra_crea_el_pedido_y_sus_renglones(self):
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.usuario, self.cliente)
        self.assertEqual(pedido.detalles.count(), 2)

    def test_el_total_es_la_suma_de_los_renglones(self):
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.total, Decimal('450.00'))
        self.assertEqual(sum(d.subtotal for d in pedido.detalles.all()), pedido.total)

    def test_guarda_los_datos_de_entrega(self):
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.nombre_completo, 'Cliente De Prueba')
        self.assertEqual(pedido.direccion, 'Calle Falsa 123')

    def test_descuenta_el_stock(self):
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        self.tenis.refresh_from_db()
        self.otro_tenis.refresh_from_db()
        self.assertEqual(self.tenis.stock, 3)
        self.assertEqual(self.otro_tenis.stock, 2)

    def test_vacia_el_carrito(self):
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        self.assertFalse(self.carrito.items.exists())

    def test_pagar_con_tarjeta_deja_el_pedido_pagado(self):
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        self.assertEqual(Pedido.objects.get().estado, Pedido.PAGADO)

    def test_pagar_en_efectivo_deja_el_pedido_pendiente(self):
        self.client.post(
            reverse('confirmar_compra'), {**DATOS_VALIDOS, 'metodo_pago': Pedido.EFECTIVO}
        )
        self.assertEqual(Pedido.objects.get().estado, Pedido.PENDIENTE)

    def test_el_precio_queda_congelado(self):
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        detalle = DetallePedido.objects.get(producto=self.tenis)

        self.tenis.precio = Decimal('999.00')
        self.tenis.save()

        detalle.refresh_from_db()
        self.assertEqual(detalle.precio, Decimal('100.00'))
        self.assertEqual(detalle.subtotal, Decimal('200.00'))


class ValidacionesTests(PedidosBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)

    def test_no_se_puede_comprar_con_el_carrito_vacio(self):
        respuesta = self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        self.assertRedirects(respuesta, reverse('ver_carrito'))
        self.assertEqual(Pedido.objects.count(), 0)

    def test_no_se_puede_comprar_sin_carrito(self):
        self.carrito.delete()
        respuesta = self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        self.assertRedirects(respuesta, reverse('ver_carrito'))
        self.assertEqual(Pedido.objects.count(), 0)

    def test_rechaza_la_compra_si_ya_no_hay_stock(self):
        ItemCarrito.objects.create(carrito=self.carrito, producto=self.tenis, cantidad=2)
        self.tenis.stock = 1
        self.tenis.save()

        respuesta = self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)

        self.assertRedirects(respuesta, reverse('ver_carrito'))
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(self.carrito.items.count(), 1)
        self.tenis.refresh_from_db()
        self.assertEqual(self.tenis.stock, 1)

    def test_rechaza_un_telefono_corto(self):
        self.llenar_carrito()
        respuesta = self.client.post(
            reverse('confirmar_compra'), {**DATOS_VALIDOS, 'telefono': '123'}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_rechaza_datos_incompletos(self):
        self.llenar_carrito()
        respuesta = self.client.post(
            reverse('confirmar_compra'), {**DATOS_VALIDOS, 'direccion': ''}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)


class DatosDelPerfilTests(PedidosBaseTests):
    def test_el_formulario_llega_con_los_datos_del_perfil(self):
        self.cliente.first_name = 'Ana'
        self.cliente.last_name = 'Ramirez'
        self.cliente.telefono = '5512345678'
        self.cliente.direccion = 'Calle Falsa 123'
        self.cliente.save()

        self.client.force_login(self.cliente)
        self.llenar_carrito()

        respuesta = self.client.get(reverse('confirmar_compra'))
        inicial = respuesta.context['form'].initial

        self.assertEqual(inicial['nombre_completo'], 'Ana Ramirez')
        self.assertEqual(inicial['telefono'], '5512345678')
        self.assertEqual(inicial['direccion'], 'Calle Falsa 123')

    def test_sin_datos_en_el_perfil_el_formulario_llega_vacio(self):
        self.client.force_login(self.cliente)
        self.llenar_carrito()

        respuesta = self.client.get(reverse('confirmar_compra'))
        inicial = respuesta.context['form'].initial

        self.assertEqual(inicial['telefono'], '')
        self.assertEqual(inicial['direccion'], '')


class AtomicidadTests(PedidosBaseTests):
    def test_si_falla_a_la_mitad_no_queda_rastro(self):
        self.client.force_login(self.cliente)
        self.llenar_carrito()

        llamadas = {'n': 0}
        guardar_original = Producto.save

        def guardar_que_falla(self, *args, **kwargs):
            llamadas['n'] += 1
            if llamadas['n'] == 2:
                raise RuntimeError('fallo simulado')
            return guardar_original(self, *args, **kwargs)

        with patch.object(Producto, 'save', guardar_que_falla):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)

        self.tenis.refresh_from_db()
        self.otro_tenis.refresh_from_db()

        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(DetallePedido.objects.count(), 0)
        self.assertEqual(self.tenis.stock, 5)
        self.assertEqual(self.otro_tenis.stock, 3)
        self.assertEqual(self.carrito.items.count(), 2)


class ComprobantesTests(PedidosBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)
        self.llenar_carrito()
        self.client.post(reverse('confirmar_compra'), DATOS_VALIDOS)
        self.pedido = Pedido.objects.get()
        self.intruso = Usuario.objects.create_user(username='intruso')

    def test_el_dueno_ve_su_comprobante(self):
        respuesta = self.client.get(reverse('detalle_pedido', args=[self.pedido.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.tenis.nombre)

    def test_otro_usuario_no_ve_el_comprobante(self):
        self.client.force_login(self.intruso)
        respuesta = self.client.get(reverse('detalle_pedido', args=[self.pedido.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_el_historial_solo_muestra_los_pedidos_propios(self):
        self.client.force_login(self.intruso)
        respuesta = self.client.get(reverse('mis_pedidos'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self.tenis.nombre)
        self.assertEqual(respuesta.context['pedidos'].count(), 0)

    def test_el_historial_muestra_la_compra(self):
        respuesta = self.client.get(reverse('mis_pedidos'))
        self.assertEqual(respuesta.context['pedidos'].count(), 1)


class EstadosDelPedidoTests(PedidosBaseTests):
    def crear(self, estado):
        pedido = Pedido.objects.create(
            usuario=self.cliente,
            nombre_completo='Cliente De Prueba',
            telefono='5512345678',
            direccion='Calle Falsa 123',
            total=Decimal('100.00'),
            estado=estado,
        )
        return pedido

    def cambiar(self, pedido, nuevo):
        pedido.estado = nuevo
        pedido.full_clean()
        pedido.save()

    def test_pagado_puede_pasar_a_preparacion(self):
        pedido = self.crear(Pedido.PAGADO)
        self.cambiar(pedido, Pedido.EN_PREPARACION)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.EN_PREPARACION)

    def test_el_recorrido_completo_funciona(self):
        pedido = self.crear(Pedido.PENDIENTE)
        for estado in (Pedido.PAGADO, Pedido.EN_PREPARACION, Pedido.ENVIADO, Pedido.ENTREGADO):
            self.cambiar(pedido, estado)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.ENTREGADO)

    def test_un_pedido_sin_pagar_no_se_puede_enviar(self):
        pedido = self.crear(Pedido.PENDIENTE)
        with self.assertRaises(ValidationError):
            self.cambiar(pedido, Pedido.ENVIADO)

    def test_no_se_puede_saltar_la_preparacion(self):
        pedido = self.crear(Pedido.PAGADO)
        with self.assertRaises(ValidationError):
            self.cambiar(pedido, Pedido.ENVIADO)

    def test_un_pedido_entregado_ya_no_cambia(self):
        pedido = self.crear(Pedido.ENTREGADO)
        with self.assertRaises(ValidationError):
            self.cambiar(pedido, Pedido.CANCELADO)

    def test_un_pedido_cancelado_no_revive(self):
        pedido = self.crear(Pedido.CANCELADO)
        with self.assertRaises(ValidationError):
            self.cambiar(pedido, Pedido.PAGADO)

    def test_no_se_puede_cancelar_algo_ya_enviado(self):
        pedido = self.crear(Pedido.ENVIADO)
        with self.assertRaises(ValidationError):
            self.cambiar(pedido, Pedido.CANCELADO)

    def test_se_puede_cancelar_antes_del_envio(self):
        for estado in (Pedido.PENDIENTE, Pedido.PAGADO, Pedido.EN_PREPARACION):
            pedido = self.crear(estado)
            self.cambiar(pedido, Pedido.CANCELADO)
            pedido.refresh_from_db()
            self.assertEqual(pedido.estado, Pedido.CANCELADO)

    def test_guardar_sin_cambiar_el_estado_no_molesta(self):
        pedido = self.crear(Pedido.ENTREGADO)
        pedido.telefono = '5599887766'
        pedido.full_clean()
        pedido.save()
        pedido.refresh_from_db()
        self.assertEqual(pedido.telefono, '5599887766')

    def test_el_cliente_ve_el_estado_en_su_comprobante(self):
        pedido = self.crear(Pedido.ENVIADO)
        self.client.force_login(self.cliente)

        respuesta = self.client.get(reverse('detalle_pedido', args=[pedido.pk]))
        self.assertContains(respuesta, 'Enviado')


class ReglasDelModeloTests(PedidosBaseTests):
    def crear_pedido(self):
        pedido = Pedido.objects.create(
            usuario=self.cliente,
            nombre_completo='Cliente De Prueba',
            telefono='5512345678',
            direccion='Calle Falsa 123',
            total=Decimal('100.00'),
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=self.tenis, precio=Decimal('100.00'), cantidad=1
        )
        return pedido

    def test_la_base_rechaza_cantidad_cero(self):
        pedido = self.crear_pedido()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DetallePedido.objects.create(
                    pedido=pedido,
                    producto=self.otro_tenis,
                    precio=Decimal('250.00'),
                    cantidad=0,
                )

    def test_no_se_puede_borrar_un_producto_vendido(self):
        self.crear_pedido()
        with self.assertRaises(ProtectedError):
            self.tenis.delete()

    def test_no_se_puede_borrar_un_usuario_con_pedidos(self):
        self.crear_pedido()
        with self.assertRaises(ProtectedError):
            self.cliente.delete()

    def test_borrar_el_pedido_arrastra_sus_renglones(self):
        pedido = self.crear_pedido()
        pedido.delete()
        self.assertEqual(DetallePedido.objects.count(), 0)

    def test_el_subtotal_multiplica_precio_por_cantidad(self):
        pedido = self.crear_pedido()
        detalle = DetallePedido.objects.create(
            pedido=pedido, producto=self.otro_tenis, precio=Decimal('250.00'), cantidad=3
        )
        self.assertEqual(detalle.subtotal, Decimal('750.00'))


class PagoConTarjetaTests(PedidosBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)
        self.llenar_carrito()

    def pagar(self, **cambios):
        datos = dict(DATOS_VALIDOS)
        datos.update(cambios)
        return self.client.post(reverse('confirmar_compra'), datos)

    def buscar_en_toda_la_base(self, texto):
        with connection.cursor() as cur:
            cur.execute(
                'SELECT TABLE_NAME FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA = DATABASE()'
            )
            tablas = [fila[0] for fila in cur.fetchall()]

            for tabla in tablas:
                cur.execute(f'SELECT * FROM `{tabla}`')
                for fila in cur.fetchall():
                    if any(texto in str(valor) for valor in fila):
                        return tabla
        return None

    def test_una_tarjeta_valida_deja_el_pedido_pagado(self):
        self.pagar()
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.estado, Pedido.PAGADO)
        self.assertEqual(pedido.tarjeta_marca, 'Visa')
        self.assertEqual(pedido.tarjeta_final, '4242')

    def test_el_numero_completo_no_queda_en_ninguna_tabla(self):
        self.pagar()
        tabla = self.buscar_en_toda_la_base('4242424242424242')
        self.assertIsNone(tabla, f'el numero completo aparecio en la tabla {tabla}')

    def test_el_codigo_de_seguridad_no_queda_guardado(self):
        self.pagar(cvv='987')
        tabla = self.buscar_en_toda_la_base('987')
        self.assertIsNone(tabla, f'el CVV aparecio en la tabla {tabla}')

    def test_un_numero_invalido_no_cobra_nada(self):
        respuesta = self.pagar(numero='1234 5678 9012 3456')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_un_numero_invalido_no_toca_el_stock(self):
        self.pagar(numero='1234 5678 9012 3456')
        self.tenis.refresh_from_db()
        self.otro_tenis.refresh_from_db()
        self.assertEqual(self.tenis.stock, 5)
        self.assertEqual(self.otro_tenis.stock, 3)
        self.assertEqual(self.carrito.items.count(), 2)

    def test_una_tarjeta_vencida_se_rechaza(self):
        pasado = timezone.localdate().year - 1
        self.pagar(expiracion=f'01/{pasado % 100:02d}')
        self.assertEqual(Pedido.objects.count(), 0)

    def test_un_mes_imposible_se_rechaza(self):
        self.pagar(expiracion='13/35')
        self.assertEqual(Pedido.objects.count(), 0)

    def test_un_cvv_corto_se_rechaza(self):
        self.pagar(cvv='12')
        self.assertEqual(Pedido.objects.count(), 0)

    def test_un_cvv_largo_se_rechaza(self):
        self.pagar(cvv='12345')
        self.assertEqual(Pedido.objects.count(), 0)

    def test_un_nombre_vacio_se_rechaza(self):
        self.pagar(nombre_tarjeta='')
        self.assertEqual(Pedido.objects.count(), 0)

    def test_el_numero_admite_espacios_y_guiones(self):
        self.pagar(numero='4242-4242 4242-4242')
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.tarjeta_final, '4242')

    def test_reconoce_las_marcas(self):
        casos = [
            ('4242 4242 4242 4242', 'Visa'),
            ('5555 5555 5555 4444', 'Mastercard'),
            ('2223 0031 2200 3222', 'Mastercard'),
            ('3782 822463 10005', 'Amex'),
            ('6011 1111 1111 1117', 'Tarjeta'),
        ]
        for numero, marca in casos:
            form = PagoTarjetaForm({**TARJETA_VALIDA, 'numero': numero})
            self.assertTrue(form.is_valid(), f'{numero} no paso la validacion')
            self.assertEqual(form.marca(), marca, f'fallo con {numero}')

    def test_el_comprobante_muestra_la_tarjeta_enmascarada(self):
        self.pagar()
        pedido = Pedido.objects.get()
        respuesta = self.client.get(reverse('detalle_pedido', args=[pedido.pk]))
        self.assertContains(respuesta, '**** **** **** 4242')
        self.assertNotContains(respuesta, '4242424242424242')

    def test_el_formulario_llega_con_la_tarjeta_de_prueba(self):
        respuesta = self.client.get(reverse('confirmar_compra'))
        self.assertContains(respuesta, '4242 4242 4242 4242')


class ClienteSinNombreTests(PedidosBaseTests):
    def setUp(self):
        super().setUp()
        self.recien_registrado = Usuario.objects.create_user(username='ana')
        self.carrito_nuevo = Carrito.objects.create(usuario=self.recien_registrado)
        ItemCarrito.objects.create(
            carrito=self.carrito_nuevo, producto=self.tenis, cantidad=1
        )
        self.client.force_login(self.recien_registrado)

    def valores_del_formulario(self, html):
        valores = {}
        for campo in ('numero', 'expiracion', 'cvv', 'nombre_tarjeta'):
            encontrado = re.search(
                r'name="' + campo + r'"[^>]*value="([^"]*)"', html
            ) or re.search(r'value="([^"]*)"[^>]*name="' + campo + r'"', html)
            valores[campo] = encontrado.group(1) if encontrado else ''
        return valores

    def test_ningun_campo_de_tarjeta_llega_vacio(self):
        respuesta = self.client.get(reverse('confirmar_compra'))
        valores = self.valores_del_formulario(respuesta.content.decode())

        for campo, valor in valores.items():
            self.assertNotEqual(valor, '', f'{campo} llego vacio al cliente')

    def test_puede_comprar_enviando_lo_que_venia_prellenado(self):
        respuesta = self.client.get(reverse('confirmar_compra'))
        datos = self.valores_del_formulario(respuesta.content.decode())
        datos.update({
            'nombre_completo': 'Ana Perez',
            'telefono': '1234567891',
            'direccion': 'Av. Siempre Viva 742',
            'metodo_pago': Pedido.TARJETA,
        })

        respuesta = self.client.post(reverse('confirmar_compra'), datos)
        self.assertEqual(Pedido.objects.count(), 1, 'el cliente no pudo comprar')
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.estado, Pedido.PAGADO)

    def test_el_telefono_de_diez_digitos_es_valido(self):
        form = DatosEnvioForm({
            'nombre_completo': 'Ana Perez',
            'telefono': '1234567891',
            'direccion': 'Av. Siempre Viva 742',
            'metodo_pago': Pedido.EFECTIVO,
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_si_falta_el_titular_el_error_dice_cual_es(self):
        datos = {
            **TARJETA_VALIDA,
            'nombre_tarjeta': '',
            'nombre_completo': 'Ana Perez',
            'telefono': '1234567891',
            'direccion': 'Av. Siempre Viva 742',
            'metodo_pago': Pedido.TARJETA,
        }
        respuesta = self.client.post(reverse('confirmar_compra'), datos)
        self.assertContains(respuesta, 'titular de la tarjeta')
        self.assertNotContains(respuesta, 'Este campo es obligatorio')


class PagoEnEfectivoTests(PedidosBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)
        self.llenar_carrito()

    def test_efectivo_no_exige_datos_de_tarjeta(self):
        self.client.post(reverse('confirmar_compra'), DATOS_EFECTIVO)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)
        self.assertEqual(pedido.tarjeta_marca, '')
        self.assertEqual(pedido.tarjeta_final, '')

    def test_efectivo_ignora_una_tarjeta_basura(self):
        datos = dict(DATOS_EFECTIVO)
        datos.update({'numero': 'no soy un numero', 'cvv': 'x', 'expiracion': 'ayer'})
        self.client.post(reverse('confirmar_compra'), datos)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)
        self.assertEqual(pedido.tarjeta_final, '')

    def test_efectivo_funciona_con_los_campos_de_tarjeta_vacios(self):
        datos = dict(DATOS_EFECTIVO)
        datos.update({'numero': '', 'expiracion': '', 'cvv': '', 'nombre_tarjeta': ''})
        self.client.post(reverse('confirmar_compra'), datos)

        self.assertEqual(Pedido.objects.count(), 1)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.estado, Pedido.PENDIENTE)

    def test_los_campos_de_tarjeta_no_llevan_required_en_el_html(self):
        respuesta = self.client.get(reverse('confirmar_compra'))
        html = respuesta.content.decode()

        for campo in ('numero', 'expiracion', 'cvv', 'nombre_tarjeta'):
            etiqueta = re.search(r'<input[^>]*name="' + campo + r'"[^>]*>', html)
            self.assertIsNotNone(etiqueta, f'no se encontro el campo {campo}')
            self.assertNotIn(
                'required',
                etiqueta.group(0),
                f'{campo} lleva required: al ocultarse con efectivo bloquea el envio',
            )

    def test_el_servidor_sigue_exigiendo_la_tarjeta_cuando_se_elige_tarjeta(self):
        datos = dict(DATOS_VALIDOS)
        datos.update({'numero': '', 'expiracion': '', 'cvv': '', 'nombre_tarjeta': ''})
        respuesta = self.client.post(reverse('confirmar_compra'), datos)

        self.assertEqual(Pedido.objects.count(), 0)
        self.assertContains(respuesta, 'Escribe el número de la tarjeta.')

    def test_el_comprobante_en_efectivo_no_menciona_tarjeta(self):
        self.client.post(reverse('confirmar_compra'), DATOS_EFECTIVO)
        pedido = Pedido.objects.get()
        respuesta = self.client.get(reverse('detalle_pedido', args=[pedido.pk]))
        self.assertNotContains(respuesta, '****')


class DevolucionesBaseTests(PedidosBaseTests):
    def setUp(self):
        super().setUp()
        self.intruso = Usuario.objects.create_user(username='intruso_devolucion')
        self.pedido = self.crear_pedido(Pedido.ENTREGADO)
        self.detalle = self.pedido.detalles.first()

    def crear_pedido(self, estado):
        pedido = Pedido.objects.create(
            usuario=self.cliente,
            nombre_completo='Cliente De Prueba',
            telefono='5512345678',
            direccion='Calle Falsa 123',
            total=Decimal('100.00'),
            estado=estado,
        )
        DetallePedido.objects.create(
            pedido=pedido, producto=self.tenis, precio=Decimal('100.00'), cantidad=1
        )
        return pedido

    def solicitar(self, detalle=None, **cambios):
        datos = {
            'motivo': Devolucion.DANADO,
            'descripcion': 'Llego con una mancha grande en la manga izquierda',
        }
        datos.update(cambios)
        objetivo = detalle or self.detalle
        return self.client.post(
            reverse('solicitar_devolucion', args=[objetivo.pk]), datos
        )


class AccesoDevolucionesTests(DevolucionesBaseTests):
    def test_visitante_no_puede_solicitar(self):
        respuesta = self.solicitar()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Devolucion.objects.count(), 0)

    def test_visitante_no_ve_la_lista(self):
        respuesta = self.client.get(reverse('mis_devoluciones'))
        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('mis_devoluciones')}",
        )

    def test_otro_usuario_no_puede_devolver_lo_que_no_compro(self):
        self.client.force_login(self.intruso)
        respuesta = self.solicitar()
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(Devolucion.objects.count(), 0)

    def test_la_lista_solo_muestra_las_propias(self):
        self.client.force_login(self.cliente)
        self.solicitar()
        self.client.force_login(self.intruso)

        respuesta = self.client.get(reverse('mis_devoluciones'))
        self.assertEqual(respuesta.context['devoluciones'].count(), 0)
        self.assertNotContains(respuesta, self.tenis.nombre)


class SolicitarDevolucionTests(DevolucionesBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)

    def test_un_pedido_entregado_si_admite_devolucion(self):
        respuesta = self.solicitar()
        self.assertRedirects(respuesta, reverse('mis_devoluciones'))

        devolucion = Devolucion.objects.get()
        self.assertEqual(devolucion.detalle, self.detalle)
        self.assertEqual(devolucion.estado, Devolucion.SOLICITADA)
        self.assertEqual(devolucion.respuesta, '')
        self.assertIsNone(devolucion.fecha_respuesta)

    def test_ningun_otro_estado_admite_devolucion(self):
        for estado in (
            Pedido.PENDIENTE,
            Pedido.PAGADO,
            Pedido.EN_PREPARACION,
            Pedido.ENVIADO,
            Pedido.CANCELADO,
        ):
            pedido = self.crear_pedido(estado)
            self.solicitar(detalle=pedido.detalles.first())
            self.assertEqual(
                Devolucion.objects.count(), 0, f'{estado} dejo pasar la devolucion'
            )

    def test_no_se_puede_solicitar_dos_veces(self):
        self.solicitar()
        self.solicitar(descripcion='Se me olvido que ya la habia pedido antes')
        self.assertEqual(Devolucion.objects.count(), 1)

    def test_la_base_rechaza_la_devolucion_repetida(self):
        Devolucion.objects.create(
            detalle=self.detalle,
            motivo=Devolucion.DANADO,
            descripcion='La primera solicitud',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Devolucion.objects.create(
                    detalle=self.detalle,
                    motivo=Devolucion.OTRO,
                    descripcion='La segunda solicitud',
                )

    def test_una_descripcion_muy_corta_se_rechaza(self):
        respuesta = self.solicitar(descripcion='Fea')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Devolucion.objects.count(), 0)

    def test_el_motivo_debe_ser_uno_de_la_lista(self):
        self.solicitar(motivo='NO_ME_GUSTO_EL_COLOR')
        self.assertEqual(Devolucion.objects.count(), 0)

    def test_el_boton_aparece_solo_en_pedidos_entregados(self):
        entregado = self.client.get(reverse('detalle_pedido', args=[self.pedido.pk]))
        self.assertContains(entregado, 'Solicitar devolución')

        enviado = self.crear_pedido(Pedido.ENVIADO)
        respuesta = self.client.get(reverse('detalle_pedido', args=[enviado.pk]))
        self.assertNotContains(respuesta, 'Solicitar devolución')

    def test_el_boton_desaparece_despues_de_solicitarla(self):
        self.solicitar()
        respuesta = self.client.get(reverse('detalle_pedido', args=[self.pedido.pk]))
        self.assertNotContains(respuesta, 'Solicitar devolución')
        self.assertContains(respuesta, 'Devolución solicitada')


class ResolverDevolucionTests(DevolucionesBaseTests):
    def setUp(self):
        super().setUp()
        self.devolucion = Devolucion.objects.create(
            detalle=self.detalle,
            motivo=Devolucion.DANADO,
            descripcion='Llego con una mancha grande en la manga izquierda',
        )

    def resolver(self, estado, respuesta):
        self.devolucion.estado = estado
        self.devolucion.respuesta = respuesta
        self.devolucion.full_clean()
        self.devolucion.save()

    def test_no_se_puede_aceptar_sin_explicar(self):
        with self.assertRaises(ValidationError):
            self.resolver(Devolucion.ACEPTADA, '')

    def test_no_se_puede_rechazar_sin_explicar(self):
        with self.assertRaises(ValidationError):
            self.resolver(Devolucion.RECHAZADA, '   ')

    def test_se_puede_aceptar_con_explicacion(self):
        self.resolver(Devolucion.ACEPTADA, 'Confirmamos el daño, pasa por tu cambio.')
        self.devolucion.refresh_from_db()
        self.assertEqual(self.devolucion.estado, Devolucion.ACEPTADA)

    def test_el_cliente_ve_la_respuesta(self):
        self.resolver(Devolucion.ACEPTADA, 'Confirmamos el daño, pasa por tu cambio.')
        self.client.force_login(self.cliente)

        respuesta = self.client.get(reverse('mis_devoluciones'))
        self.assertContains(respuesta, 'Aceptada')
        self.assertContains(respuesta, 'pasa por tu cambio')

    def test_el_cliente_ve_que_sigue_en_revision(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('mis_devoluciones'))
        self.assertContains(respuesta, 'En revisión')

    def test_el_modelo_rechaza_devolver_algo_no_entregado(self):
        pedido = self.crear_pedido(Pedido.ENVIADO)
        devolucion = Devolucion(
            detalle=pedido.detalles.first(),
            motivo=Devolucion.DANADO,
            descripcion='Todavia no me llega pero quiero devolverlo',
        )
        with self.assertRaises(ValidationError):
            devolucion.full_clean()

    def test_borrar_el_pedido_arrastra_la_devolucion(self):
        self.pedido.delete()
        self.assertEqual(Devolucion.objects.count(), 0)


class PanelDeDevolucionesTests(DevolucionesBaseTests):
    def setUp(self):
        super().setUp()
        Devolucion.objects.create(
            detalle=self.detalle,
            motivo=Devolucion.DANADO,
            descripcion='Llego con una mancha grande en la manga izquierda',
        )
        self.admin = Usuario.objects.create_superuser(
            username='admin_devoluciones', password='clave-de-prueba-larga'
        )
        self.client.force_login(self.admin)

    def test_la_lista_del_panel_abre(self):
        respuesta = self.client.get('/admin/pedidos/devolucion/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.tenis.nombre)

    def test_los_filtros_del_panel_abren(self):
        respuesta = self.client.get('/admin/pedidos/devolucion/?estado=SOLICITADA')
        self.assertEqual(respuesta.status_code, 200)

    def test_la_ficha_del_panel_abre(self):
        devolucion = Devolucion.objects.get()
        respuesta = self.client.get(f'/admin/pedidos/devolucion/{devolucion.pk}/change/')
        self.assertEqual(respuesta.status_code, 200)

    def test_el_panel_no_deja_crear_devoluciones_a_mano(self):
        respuesta = self.client.get('/admin/pedidos/devolucion/add/')
        self.assertEqual(respuesta.status_code, 403)

    def test_el_panel_no_deja_borrar_devoluciones(self):
        devolucion = Devolucion.objects.get()
        ruta = f'/admin/pedidos/devolucion/{devolucion.pk}/delete/'
        self.assertEqual(self.client.get(ruta).status_code, 403)
        self.assertEqual(self.client.post(ruta, {'post': 'yes'}).status_code, 403)
        self.assertEqual(Devolucion.objects.count(), 1)

    def test_resolver_desde_el_panel_guarda_la_fecha(self):
        devolucion = Devolucion.objects.get()
        self.client.post(
            f'/admin/pedidos/devolucion/{devolucion.pk}/change/',
            {
                'estado': Devolucion.ACEPTADA,
                'respuesta': 'Confirmamos el daño, pasa por tu cambio.',
            },
        )
        devolucion.refresh_from_db()
        self.assertEqual(devolucion.estado, Devolucion.ACEPTADA)
        self.assertIsNotNone(devolucion.fecha_respuesta)
