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
