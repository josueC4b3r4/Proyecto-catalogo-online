# Elegancia — Sistema de Catálogo Online

Sistema web de venta de ropa por catálogo. Proyecto escolar desarrollado con
Django y MariaDB.

Permite que un administrador registre categorías y productos desde el panel de
administración, y que un cliente se registre, consulte el catálogo, agregue
productos al carrito y confirme una compra con pago simulado.

## Tecnologías

- Python 3.14
- Django 5.2 LTS
- MariaDB 12.3
- mysqlclient, Pillow, django-environ
- HTML, CSS y JavaScript básico con plantillas de Django

## Requisitos previos

Antes de instalar necesitas tener en la computadora: Python, Git, MariaDB y
un editor como Visual Studio Code.

## Instalación

### 1. Clonar el proyecto

```powershell
git clone https://github.com/josueC4b3r4/Proyecto-catalogo-online.git
cd Proyecto-catalogo-online
```

### 2. Crear el entorno virtual e instalar dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Crear la base de datos

Entra a MariaDB como root:

```powershell
& "C:\Program Files\MariaDB 12.3\bin\mariadb.exe" -u root -p
```

Y ejecuta:

```sql
CREATE DATABASE catalogo_online_nuevo_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;

CREATE USER 'catalogo_app'@'localhost' IDENTIFIED BY 'la-contrasena-que-elijas';

GRANT ALL PRIVILEGES ON catalogo_online_nuevo_db.* TO 'catalogo_app'@'localhost';
GRANT ALL PRIVILEGES ON `test_catalogo_online_nuevo_db`.* TO 'catalogo_app'@'localhost';
FLUSH PRIVILEGES;
```

El segundo `GRANT` es para la base temporal que Django crea al ejecutar las
pruebas. Sin él, `manage.py test` falla con el error 1044.

### 4. Configurar las variables de entorno

Copia `.env.example` como `.env` y completa `DB_PASSWORD` con la contraseña que
elegiste en el paso anterior. Genera también una `SECRET_KEY` nueva.

Edita el archivo desde Visual Studio Code, no desde la terminal de PowerShell:
PowerShell agrega un BOM invisible que impide leer la primera variable.

El archivo `.env` nunca se sube a Git.

### 5. Crear las tablas y el usuario administrador

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

### 6. Cargar los datos de demostración

```powershell
.\.venv\Scripts\python.exe manage.py loaddata datos_demo/catalogo.json
```

Esto crea las categorías y los productos de ejemplo. Debe responder
`Installed 15 object(s) from 1 fixture(s)`: 4 categorías y 11 productos.

Las fotos de los productos no están en el repositorio, porque `media/` se
ignora en Git. Cópialas aparte (memoria USB o Google Drive) dentro de
`media/productos/`, conservando los nombres `TENIS1.jpg` y `TENIS2.jpg`. Si
faltan, el catálogo se muestra con las imágenes rotas.

Para volver a exportar los datos más adelante, hay que forzar UTF-8, porque en
Windows `dumpdata` escribe el archivo con la codificación antigua del sistema y
`loaddata` no puede leer los acentos:

```powershell
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\python.exe manage.py dumpdata catalogo --indent 2 -o datos_demo/catalogo.json
```

Los usuarios no se exportan a propósito: ese archivo contendría los hashes de
las contraseñas y no debe subirse a un repositorio.

### 7. Ejecutar el servidor

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Disponible en http://127.0.0.1:8000/ y el panel en http://127.0.0.1:8000/admin/

## Pruebas

```powershell
.\.venv\Scripts\python.exe manage.py test
```

Las pruebas usan una base de datos temporal que Django crea y destruye sola, así
que no modifican los datos reales.

Son 155: 38 de usuarios, 18 del catálogo, 19 del carrito y 80 de pedidos.

## Requisitos funcionales cubiertos

| RF | Descripción | Estado |
|----|-------------|--------|
| RF-01 | Autenticación y control de accesos | Completo |
| RF-02 | Catálogo con filtros por categoría, talla y color | Completo |
| RF-03 | CRUD del catálogo desde el panel | Completo |
| RF-04 | Carrito de compras persistente | Completo |
| RF-05 | Procesamiento del pago | Simulado, sin guardar la tarjeta |
| RF-06 | Descuento de existencias al comprar | Completo |
| RF-07 | Estados del pedido y control logístico | Completo |
| RF-08 | Cupones y descuentos | Fuera de alcance |
| RF-09 | Historial de compras | Completo sin la descarga en PDF |
| RF-10 | Reportes estadísticos y gráficas | Fuera de alcance |
| RF-11 | Recuperación de contraseña por correo | Completo |
| RF-12 | Gestión del perfil del cliente | Completo |
| RF-13 | Notificaciones automatizadas | Fuera de alcance |
| RF-14 | Calificaciones y reseñas | Fuera de alcance |
| RF-15 | Solicitud de devoluciones | Completo, sin reembolso automático |

Un pedido avanza en un solo sentido: pendiente de pago, pagado, en preparación,
enviado y entregado. Se puede cancelar mientras no haya salido, y el sistema
rechaza cualquier salto, como enviar algo que todavía no se ha pagado.

El formulario de pago pide número de tarjeta, vencimiento, código de seguridad
y titular, y los valida: el número debe pasar el algoritmo de Luhn y la fecha no
puede estar vencida. De todo eso la base guarda únicamente la marca y los
últimos cuatro dígitos, igual que hacen las pasarelas reales. El número completo
y el código de seguridad se descartan al terminar la petición. Los campos llegan
llenos con la tarjeta de prueba 4242 4242 4242 4242 para que nadie tenga que
escribir una tarjeta real durante una demostración.

Las devoluciones se piden por producto, no por pedido completo, y solo sobre
pedidos entregados. Cada renglón admite una sola solicitud: eso lo garantiza un
índice único en la base, no una comprobación en Python. El administrador acepta
o rechaza desde el panel y está obligado a escribir una respuesta al cliente.

Los correos de recuperación se imprimen en la terminal en lugar de enviarse,
porque el proyecto no tiene servidor de correo configurado.

## Estructura

```
config/      configuración del proyecto y rutas principales
usuarios/    modelo Usuario, registro e inicio de sesión
catalogo/    categorías y productos
carrito/     carrito de compras
pedidos/     pedidos y pago simulado
templates/   plantillas HTML
static/      CSS, JavaScript e imágenes del sitio
media/       imágenes de productos subidas desde el panel
datos_demo/  datos de ejemplo para cargar con loaddata
```

Todas las plantillas heredan de `templates/base.html`, que contiene el
encabezado, el menú, los mensajes y el pie. Cada plantilla solo define su
propio contenido con `{% block contenido %}`.

Los colores del sitio están definidos como variables al inicio de
`static/css/estilos.css`. Cambiarlos ahí cambia el sitio completo.

## Estado del proyecto

- [x] Etapa 1: entorno y conexión con MariaDB
- [x] Etapa 2: usuarios, registro, inicio y cierre de sesión
- [x] Etapa 3: catálogo de productos
- [x] Etapa 4: carrito de compras
- [x] Etapa 5: pedidos y pago simulado
- [x] Etapa 6: diseño final y datos de demostración
- [ ] Etapa 7: repaso y preparación de la defensa

## Mejoras futuras

Funciones que quedaron fuera del alcance de esta versión escolar: cupones,
reseñas, reembolsos automáticos, guías de envío, reportes con gráficas,
comprobantes en PDF, correos automáticos y pasarelas de pago reales. El pago de
esta versión es únicamente una simulación y no almacena información real de
tarjetas.
