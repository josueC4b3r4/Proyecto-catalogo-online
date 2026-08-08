import re
import shutil
import tempfile
from io import BytesIO

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Usuario


def imagen_de_prueba(nombre='foto.png', color='red'):
    archivo = BytesIO()
    Image.new('RGB', (20, 20), color).save(archivo, 'PNG')
    archivo.seek(0)
    return SimpleUploadedFile(nombre, archivo.read(), content_type='image/png')

DATOS_VALIDOS = {
    'username': 'ana',
    'email': 'ana@ejemplo.com',
    'password1': 'RopaTienda2026',
    'password2': 'RopaTienda2026',
}


class RegistroClienteTests(TestCase):
    def test_visitante_ve_el_formulario(self):
        respuesta = self.client.get(reverse('registro'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="username"')
        self.assertContains(respuesta, 'name="password1"')

    def test_cliente_valido_se_registra(self):
        respuesta = self.client.post(reverse('registro'), DATOS_VALIDOS)
        self.assertRedirects(respuesta, reverse('inicio'))

        usuario = Usuario.objects.get(username='ana')
        self.assertEqual(usuario.rol, Usuario.CLIENTE)
        self.assertNotEqual(usuario.password, 'RopaTienda2026')

    def test_sesion_inicia_automaticamente(self):
        self.client.post(reverse('registro'), DATOS_VALIDOS)

        respuesta = self.client.get(reverse('inicio'))
        self.assertTrue(respuesta.wsgi_request.user.is_authenticated)
        self.assertEqual(respuesta.wsgi_request.user.username, 'ana')

    def test_datos_invalidos_muestran_errores(self):
        datos = dict(DATOS_VALIDOS, password2='OtraDistinta2026')
        respuesta = self.client.post(reverse('registro'), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('password2', respuesta.context['form'].errors)
        self.assertFalse(Usuario.objects.filter(username='ana').exists())

    def test_usuario_autenticado_es_redirigido(self):
        Usuario.objects.create_user(username='pedro', password='RopaTienda2026')
        self.client.login(username='pedro', password='RopaTienda2026')

        respuesta = self.client.get(reverse('registro'))
        self.assertRedirects(respuesta, reverse('inicio'))


class LoginLogoutTests(TestCase):
    def setUp(self):
        Usuario.objects.create_user(
            username='ana',
            email='ana@ejemplo.com',
            password='RopaTienda2026',
        )

    def esta_autenticado(self):
        return self.client.get(reverse('inicio')).wsgi_request.user.is_authenticated

    def test_login_con_credenciales_correctas(self):
        respuesta = self.client.post(reverse('login'), {
            'username': 'ana',
            'password': 'RopaTienda2026',
        })
        self.assertRedirects(respuesta, reverse('inicio'))
        self.assertTrue(self.esta_autenticado())

    def test_login_con_contrasena_incorrecta(self):
        respuesta = self.client.post(reverse('login'), {
            'username': 'ana',
            'password': 'contrasena-equivocada',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self.esta_autenticado())

    def test_logout_por_post_cierra_la_sesion(self):
        self.client.login(username='ana', password='RopaTienda2026')
        self.assertTrue(self.esta_autenticado())

        respuesta = self.client.post(reverse('logout'))
        self.assertRedirects(respuesta, reverse('inicio'))
        self.assertFalse(self.esta_autenticado())

    def test_logout_por_get_no_esta_permitido(self):
        self.client.login(username='ana', password='RopaTienda2026')

        respuesta = self.client.get(reverse('logout'))
        self.assertEqual(respuesta.status_code, 405)
        self.assertTrue(self.esta_autenticado())


class RecuperarContrasenaTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='ana', email='ana@ejemplo.com', password='RopaTienda2026'
        )

    def pedir_enlace(self, correo='ana@ejemplo.com'):
        return self.client.post(reverse('password_reset'), {'email': correo})

    def enlace_del_correo(self):
        cuerpo = mail.outbox[0].body
        return re.search(r'/recuperar/[^/]+/[^/\s]+/', cuerpo).group(0)

    def test_visitante_ve_el_formulario(self):
        respuesta = self.client.get(reverse('password_reset'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Recuperar')

    def test_pedir_enlace_envia_un_correo(self):
        self.pedir_enlace()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana@ejemplo.com'])
        self.assertIn('Elegancia', mail.outbox[0].subject)

    def test_el_correo_trae_un_enlace_valido(self):
        self.pedir_enlace()
        respuesta = self.client.get(self.enlace_del_correo(), follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['validlink'])

    def test_correo_desconocido_no_envia_nada_pero_no_lo_delata(self):
        respuesta = self.pedir_enlace('nadie@ejemplo.com')
        self.assertRedirects(respuesta, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_cambia_la_contrasena_y_permite_entrar(self):
        self.pedir_enlace()
        destino = self.client.get(self.enlace_del_correo(), follow=True).request['PATH_INFO']

        self.client.post(
            destino,
            {'new_password1': 'OtraClave2026', 'new_password2': 'OtraClave2026'},
        )

        self.assertTrue(self.client.login(username='ana', password='OtraClave2026'))

    def test_la_contrasena_anterior_deja_de_servir(self):
        self.pedir_enlace()
        destino = self.client.get(self.enlace_del_correo(), follow=True).request['PATH_INFO']

        self.client.post(
            destino,
            {'new_password1': 'OtraClave2026', 'new_password2': 'OtraClave2026'},
        )

        self.assertFalse(self.client.login(username='ana', password='RopaTienda2026'))

    def test_el_enlace_solo_sirve_una_vez(self):
        self.pedir_enlace()
        enlace = self.enlace_del_correo()
        destino = self.client.get(enlace, follow=True).request['PATH_INFO']
        self.client.post(
            destino,
            {'new_password1': 'OtraClave2026', 'new_password2': 'OtraClave2026'},
        )

        respuesta = self.client.get(enlace, follow=True)
        self.assertFalse(respuesta.context['validlink'])

    def test_rechaza_dos_contrasenas_distintas(self):
        self.pedir_enlace()
        destino = self.client.get(self.enlace_del_correo(), follow=True).request['PATH_INFO']

        self.client.post(
            destino,
            {'new_password1': 'OtraClave2026', 'new_password2': 'NoCoincide2026'},
        )

        self.assertTrue(self.client.login(username='ana', password='RopaTienda2026'))

    def test_la_contrasena_no_viaja_en_el_correo(self):
        self.pedir_enlace()
        self.assertNotIn('RopaTienda2026', mail.outbox[0].body)

    def test_el_login_ofrece_recuperar(self):
        respuesta = self.client.get(reverse('login'))
        self.assertContains(respuesta, reverse('password_reset'))


class PerfilTests(TestCase):
    DATOS = {
        'first_name': 'Ana',
        'last_name': 'Ramirez',
        'email': 'ana@ejemplo.com',
        'telefono': '5512345678',
        'direccion': 'Calle Falsa 123',
    }

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='ana', email='ana@ejemplo.com', password='RopaTienda2026'
        )
        self.client.force_login(self.usuario)

    def test_visitante_no_entra_al_perfil(self):
        self.client.logout()
        respuesta = self.client.get(reverse('mi_perfil'))
        self.assertRedirects(respuesta, f"{reverse('login')}?next={reverse('mi_perfil')}")

    def test_el_formulario_llega_con_los_datos_actuales(self):
        self.usuario.telefono = '5599887766'
        self.usuario.save()

        respuesta = self.client.get(reverse('mi_perfil'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '5599887766')

    def test_guarda_los_cambios(self):
        self.client.post(reverse('mi_perfil'), self.DATOS)
        self.usuario.refresh_from_db()

        self.assertEqual(self.usuario.first_name, 'Ana')
        self.assertEqual(self.usuario.telefono, '5512345678')
        self.assertEqual(self.usuario.direccion, 'Calle Falsa 123')

    def test_rechaza_un_telefono_corto(self):
        self.client.post(reverse('mi_perfil'), {**self.DATOS, 'telefono': '123'})
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.telefono, '')

    def test_no_permite_repetir_el_correo_de_otro(self):
        Usuario.objects.create_user(username='otro', email='ocupado@ejemplo.com')

        self.client.post(reverse('mi_perfil'), {**self.DATOS, 'email': 'ocupado@ejemplo.com'})
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, 'ana@ejemplo.com')

    def test_puede_guardar_conservando_su_propio_correo(self):
        respuesta = self.client.post(reverse('mi_perfil'), self.DATOS)
        self.assertRedirects(respuesta, reverse('mi_perfil'))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, 'Ana')

    def test_no_se_puede_cambiar_el_nombre_de_usuario(self):
        self.client.post(reverse('mi_perfil'), {**self.DATOS, 'username': 'otro_nombre'})
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'ana')

    def test_no_se_puede_volver_administrador_desde_el_perfil(self):
        self.client.post(
            reverse('mi_perfil'),
            {**self.DATOS, 'rol': Usuario.ADMINISTRADOR, 'is_staff': True, 'is_superuser': True},
        )
        self.usuario.refresh_from_db()

        self.assertEqual(self.usuario.rol, Usuario.CLIENTE)
        self.assertFalse(self.usuario.is_staff)
        self.assertFalse(self.usuario.is_superuser)

    def test_no_puede_editar_el_perfil_de_otro(self):
        otro = Usuario.objects.create_user(username='otro', email='otro@ejemplo.com')

        self.client.post(reverse('mi_perfil'), self.DATOS)
        otro.refresh_from_db()

        self.assertEqual(otro.email, 'otro@ejemplo.com')
        self.assertEqual(otro.telefono, '')


class FotoDePerfilTests(TestCase):
    DATOS = {
        'first_name': 'Ana',
        'last_name': 'Ramirez',
        'email': 'ana@ejemplo.com',
        'telefono': '5512345678',
        'direccion': 'Calle Falsa 123',
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carpeta = tempfile.mkdtemp()
        cls.media = override_settings(MEDIA_ROOT=cls.carpeta)
        cls.media.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media.disable()
        shutil.rmtree(cls.carpeta, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='ana', email='ana@ejemplo.com', password='RopaTienda2026'
        )
        self.client.force_login(self.usuario)

    def test_un_usuario_nuevo_no_tiene_foto(self):
        self.assertFalse(self.usuario.foto)

    def test_sube_una_foto(self):
        self.client.post(
            reverse('mi_perfil'), {**self.DATOS, 'foto': imagen_de_prueba()}
        )
        self.usuario.refresh_from_db()

        self.assertTrue(self.usuario.foto)
        self.assertIn('perfiles/', self.usuario.foto.name)

    def test_la_foto_se_ve_en_el_perfil(self):
        self.client.post(
            reverse('mi_perfil'), {**self.DATOS, 'foto': imagen_de_prueba()}
        )
        self.usuario.refresh_from_db()

        respuesta = self.client.get(reverse('mi_perfil'))
        self.assertContains(respuesta, self.usuario.foto.url)

    def test_la_foto_se_ve_en_el_menu(self):
        self.client.post(
            reverse('mi_perfil'), {**self.DATOS, 'foto': imagen_de_prueba()}
        )
        self.usuario.refresh_from_db()

        respuesta = self.client.get(reverse('inicio'))
        self.assertContains(respuesta, 'class="avatar"')
        self.assertContains(respuesta, self.usuario.foto.url)

    def test_sin_foto_muestra_la_inicial(self):
        respuesta = self.client.get(reverse('inicio'))
        self.assertContains(respuesta, 'avatar-letra')
        self.assertContains(respuesta, '>A<', html=False)

    def test_reemplaza_la_foto_anterior(self):
        self.client.post(
            reverse('mi_perfil'), {**self.DATOS, 'foto': imagen_de_prueba('primera.png')}
        )
        self.usuario.refresh_from_db()
        primera = self.usuario.foto.name

        self.client.post(
            reverse('mi_perfil'),
            {**self.DATOS, 'foto': imagen_de_prueba('segunda.png', 'blue')},
        )
        self.usuario.refresh_from_db()

        self.assertNotEqual(self.usuario.foto.name, primera)
        self.assertIn('segunda', self.usuario.foto.name)

    def test_rechaza_un_archivo_que_no_es_imagen(self):
        falsa = SimpleUploadedFile('trampa.png', b'esto no es una imagen', 'image/png')

        respuesta = self.client.post(reverse('mi_perfil'), {**self.DATOS, 'foto': falsa})
        self.usuario.refresh_from_db()

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self.usuario.foto)

    def test_guardar_sin_enviar_foto_no_borra_la_que_habia(self):
        self.client.post(
            reverse('mi_perfil'), {**self.DATOS, 'foto': imagen_de_prueba()}
        )
        self.usuario.refresh_from_db()
        guardada = self.usuario.foto.name

        self.client.post(reverse('mi_perfil'), {**self.DATOS, 'first_name': 'Anita'})
        self.usuario.refresh_from_db()

        self.assertEqual(self.usuario.foto.name, guardada)
        self.assertEqual(self.usuario.first_name, 'Anita')

    def test_el_formulario_acepta_archivos(self):
        respuesta = self.client.get(reverse('mi_perfil'))
        self.assertContains(respuesta, 'enctype="multipart/form-data"')

    def test_la_foto_no_deja_cambiar_el_rol(self):
        self.client.post(
            reverse('mi_perfil'),
            {**self.DATOS, 'foto': imagen_de_prueba(), 'rol': Usuario.ADMINISTRADOR},
        )
        self.usuario.refresh_from_db()

        self.assertTrue(self.usuario.foto)
        self.assertEqual(self.usuario.rol, Usuario.CLIENTE)
