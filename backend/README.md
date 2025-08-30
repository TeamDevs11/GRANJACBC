Granja CBC - Backend API
Bienvenido al repositorio del backend de la API para el proyecto "Granja CBC". Este proyecto implementa una API RESTful para gestionar un sistema de e-commerce de productos agrícolas, incluyendo usuarios, productos, inventario, carritos de compra, pedidos, pagos y reseñas.

Características Principales
Autenticación y Autorización JWT: Gestión segura de usuarios con JSON Web Tokens y control de acceso basado en roles (Cliente, Administrador).

Gestión de Usuarios: Registro, inicio de sesión, actualización de perfiles y gestión de roles.

Catálogo de Productos: Gestión de categorías y productos con detalles como precio, stock e imágenes.

Inventario: Control de la cantidad disponible de cada producto.

Carrito de Compras: Funcionalidad para que los clientes agreguen, modifiquen y eliminen productos de su carrito.

Pedidos: Creación de pedidos, seguimiento de estados y visualización del historial.

Pagos (Simulado): Procesamiento de pagos para los pedidos, con registro de transacciones.

Reseñas de Productos: Los clientes pueden dejar calificaciones y comentarios sobre los productos, con un sistema de aprobación por parte del administrador.

Historial de Ventas: Registro detallado de todas las ventas realizadas.

Base de Datos MySQL: Persistencia de datos mediante MySQL.

Documentación Interactiva: Integración con Swagger UI para una exploración y prueba sencilla de la API.

Estructura del Proyecto
GRANJACBC/
├── blueprints/             # Módulos de la API (Blueprints de Flask)
│   ├── __init__.py         # Inicialización del paquete
│   ├── carrito.py          # Gestión del carrito de compras
│   ├── categorias.py       # Gestión de categorías de productos
│   ├── clientes.py         # Gestión de perfiles de cliente
│   ├── inventarios.py      # Gestión de inventario de productos
│   ├── pagos.py            # Procesamiento de pagos (simulado)
│   ├── pedidos.py          # Gestión de pedidos de clientes
│   ├── productos.py        # Gestión de productos
│   ├── reseñas.py          # Gestión de reseñas de productos
│   ├── usuarios.py         # Gestión de usuarios y autenticación
│   └── ventas.py           # Consulta del historial de ventas
├── utils/                  # Utilidades y funciones auxiliares
│   ├── __init__.py
│   ├── auth_decorators.py  # Decoradores para control de acceso por roles
│   ├── db.py               # Conexión a la base de datos
│   └── helpers.py          # Funciones de utilidad (respuestas API, limpieza de datos)
├── venv/                   # Entorno virtual de Python
├── .env                    # Variables de entorno (configuración sensible)
├── app.py                  # Aplicación principal de Flask
├── README.md               # Este archivo
└── requirements.txt        # Dependencias del proyecto

Configuración y Ejecución
Sigue estos pasos para levantar el backend en tu entorno local:

1. Clonar el Repositorio (si aplica)
git clone <https://github.com/TeamDevs11/GRANJACBC.git>
cd GRANJACBC/backend # O la ruta donde esté tu carpeta raíz del backend

2. Crear y Activar un Entorno Virtual
Es buena práctica usar un entorno virtual para gestionar las dependencias del proyecto.

python -m venv venv

3. Instalar Dependencias
Instala todas las librerías necesarias utilizando pip:

pip install -r requirements.txt

Si el archivo requirements.txt no existe, puedes crearlo con:

pip install Flask Flask-JWT-Extended PyMySQL python-dotenv Flask-Cors flasgger Werkzeug
pip freeze > requirements.txt

4. Configurar Variables de Entorno (.env)
Crea un archivo .env en la raíz de tu proyecto (junto a app.py) y añade tus credenciales de base de datos y la clave secreta para JWT. No compartas este archivo en un repositorio público.

# Configuración de la Base de Datos MySQL
DB_HOST=localhost
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_NAME=your_database_name

# Clave Secreta para JWT (¡Cambia esto por una cadena larga y aleatoria en producción!)
JWT_SECRET_KEY=super-secret-key-para-jwt-granja-cbc

# Clave Secreta para Flask (¡Cambia esto por una cadena larga y aleatoria en producción!)
FLASK_SECRET_KEY=super-secret-flask-key-por-defecto
FLASK_RUN_PORT=5000
FLASK_DEBUG=True # Cambia a False en producción

5. Configuración de la Base de Datos MySQL
Asegúrate de tener un servidor MySQL en ejecución. Luego, crea la base de datos y las tablas necesarias.

Crear la Base de Datos:

CREATE DATABASE your_database_name; -- Usa el nombre que configuraste en DB_NAME
USE your_database_name;

Crear y Modificar Tablas (Esquema Completo):

Asegúrate de ejecutar las siguientes sentencias SQL en el orden correcto para crear todas las tablas y sus relaciones.

-- Tabla: roles (Si no existe)
CREATE TABLE roles (
    id_rol INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nombre_rol VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT
);

-- Insertar roles iniciales (si no existen)
INSERT IGNORE INTO roles (id_rol, nombre_rol, descripcion) VALUES
(1, 'Administrador', 'Control total del sistema.'),
(2, 'Cliente', 'Usuario para realizar compras.'),
(3, 'Empleado', 'Gestión de inventario y productos.');

-- Tabla: usuarios (Si no existe o para crearla)
CREATE TABLE usuarios (
    id_usuario INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    usuario VARCHAR(255) NOT NULL UNIQUE, -- Email del usuario
    contrasena VARCHAR(255) NOT NULL,
    telefono VARCHAR(20) NULL,
    id_rol INT(11) NOT NULL,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_rol) REFERENCES roles(id_rol) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Tabla: categorias (Si no existe)
CREATE TABLE categorias (
    id_categoria INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nombre_categoria VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT
);

-- Tabla: productos (Si no existe)
CREATE TABLE productos (
    id_producto INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nombre_producto VARCHAR(255) NOT NULL,
    descripcion TEXT,
    id_categoria INT(11) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    unidad_medida VARCHAR(50) NULL, -- Ej. 'kg', 'unidad', 'litro'
    imagen_url VARCHAR(255) NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Tabla: inventarios (Si no existe)
CREATE TABLE inventarios (
    id_inventario INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_producto INT(11) NOT NULL UNIQUE,
    cantidad_disponible INT(11) NOT NULL DEFAULT 0,
    ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Tabla: clientes (Modificada para vincular con usuarios y añadir 'ciudad')
CREATE TABLE clientes (
    id_cliente INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT(11) NOT NULL UNIQUE, -- FK a usuarios
    nombre VARCHAR(255) NOT NULL,
    direccion VARCHAR(255) NULL,
    ciudad VARCHAR(100) NULL,
    telefono VARCHAR(20) NULL,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Tabla: pedidos (Si no existe)
CREATE TABLE pedidos (
    id_pedido INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_cliente INT(11) NOT NULL,
    fecha_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado_pedido VARCHAR(50) DEFAULT 'Pendiente', -- Ej. Pendiente, En proceso, Completado, Cancelado
    total_pedido DECIMAL(10, 2) NOT NULL,
    direccion_envio VARCHAR(255) NULL,
    ciudad_envio VARCHAR(100) NULL,
    telefono_contacto VARCHAR(20) NULL,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Tabla: detalle_pedidos (Si no existe)
CREATE TABLE detalle_pedidos (
    id_detalle_pedido INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_pedido INT(11) NOT NULL,
    id_producto INT(11) NOT NULL,
    cantidad INT(11) NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Tabla: carrito (Si no existe)
CREATE TABLE carrito (
    id_item_carrito INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_cliente INT(11) NOT NULL,
    id_producto INT(11) NOT NULL,
    cantidad INT(11) NOT NULL,
    fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Tabla: pagos (Si no existe)
CREATE TABLE pagos (
    id_pago INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_pedido INT(11) NOT NULL,
    fecha_pago TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    monto DECIMAL(10, 2) NOT NULL,
    metodo_pago VARCHAR(50) NOT NULL,
    estado_pago VARCHAR(50) DEFAULT 'Pendiente', -- Ej. 'Pendiente', 'Aprobado', 'Rechazado', 'Reembolsado'
    transaccion_id VARCHAR(255) NULL,
    FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Tabla: reseñas_productos (Si no existe)
CREATE TABLE reseñas_productos (
    id_reseña INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_producto INT(11) NOT NULL,
    id_cliente INT(11) NOT NULL,
    calificacion INT(1) NOT NULL, -- Calificación del 1 al 5
    comentario TEXT NULL,
    fecha_reseña TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aprobada TINYINT(1) NOT NULL DEFAULT 0, -- 0=No aprobada, 1=Aprobada
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Tabla: estados_venta (Si no existe)
CREATE TABLE estados_venta (
    id_estado_venta INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nombre_estado VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT
);

-- Inserta estados de venta iniciales (si no existen)
INSERT IGNORE INTO estados_venta (id_estado_venta, nombre_estado, descripcion) VALUES
(1, 'Pendiente', 'La venta ha sido creada pero aún no procesada.'),
(2, 'Procesando', 'La venta está siendo preparada o en proceso de envío.'),
(3, 'Enviado', 'El producto ha sido enviado al cliente.'),
(4, 'Completado', 'El cliente ha recibido el producto y la venta ha finalizado.'),
(5, 'Cancelado', 'La venta ha sido cancelada por el cliente o el administrador.');

-- Tabla: direcciones (Sugerida, si la vas a usar en lugar de texto plano en pedidos/ventas)
-- Si ya tienes id_direccion_envio y id_direccion_facturacion en 'ventas', necesitarás esta tabla.
CREATE TABLE IF NOT EXISTS direcciones (
    id_direccion INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_cliente INT(11) NOT NULL,
    calle VARCHAR(255) NOT NULL,
    numero VARCHAR(50) NULL,
    colonia VARCHAR(255) NULL,
    ciudad VARCHAR(100) NOT NULL,
    estado VARCHAR(100) NULL,
    codigo_postal VARCHAR(20) NULL,
    referencia TEXT NULL,
    tipo_direccion VARCHAR(50) DEFAULT 'Envio', -- Ej. 'Envio', 'Facturacion'
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Tabla: ventas (Modificada para usar la FK id_estado_venta y la tabla 'direcciones' si existe)
CREATE TABLE ventas (
    id_venta INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_cliente INT(11) NOT NULL,
    id_usuario INT(11) NOT NULL, -- Para referencia al usuario que hizo la compra
    fecha DATE NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    id_estado_venta INT(11) NOT NULL,
    id_direccion_envio INT(11) NULL,
    id_direccion_facturacion INT(11) NULL,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (id_estado_venta) REFERENCES estados_venta(id_estado_venta) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (id_direccion_envio) REFERENCES direcciones(id_direccion) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (id_direccion_facturacion) REFERENCES direcciones(id_direccion) ON DELETE SET NULL ON UPDATE CASCADE
);

-- Tabla: detalles_venta (Si no existe, con el ajuste de 'precio_unitario' y 'subtotal')
CREATE TABLE detalles_venta (
    id_detalle_venta INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_venta INT(11) NOT NULL,
    id_producto INT(11) NOT NULL,
    cantidad INT(11) NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (id_venta) REFERENCES ventas(id_venta) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE RESTRICT ON UPDATE CASCADE
);


6. Ejecutar la Aplicación Flask
Desde la raíz de tu proyecto, con el entorno virtual activado:

python app.py

La API estará disponible en http://127.0.0.1:5000 (o el puerto que hayas configurado en .env).

Documentación de la API (Swagger UI)
Una vez que la aplicación esté en ejecución, puedes acceder a la documentación interactiva de la API a través de Swagger UI:

 Abre tu navegador y ve a: http://127.0.0.1:5000/apidocs/

Desde allí podrás ver todos los endpoints, sus parámetros, modelos de respuesta y probarlos directamente.

Para probar los endpoints protegidos (con candado 🔒):

Ve a la sección auth y utiliza POST /auth/login con las credenciales de un usuario existente (o crea uno con POST /auth/registro).

Copia el access_token de la respuesta.

Haz clic en el botón Authorize (o el icono de candado en un endpoint específico).

Pega el token en el campo Value con el prefijo Bearer  (ej. Bearer eyJhbGciOiJIUzI1Ni...).

Haz clic en Authorize y luego en Close.

Ahora podrás probar los endpoints protegidos.

Integración Crucial
La creación de una "venta" se dispara lógicamente cuando un pedido es pagado y completado. Para esto, la función auxiliar registrar_venta_desde_pedido en blueprints/ventas.py debe ser llamada.

Modifica blueprints/pagos.py (en la ruta POST /pagos/procesar) para incluir esta llamada después de un pago exitoso y la actualización del estado del pedido a 'Completado'.

# Dentro de blueprints/pagos.py, en la función procesar_pago, después del conn.commit()
# y de obtener el pago_registrado:

# ... (código existente) ...

# 4. Actualizar el estado del pedido a 'Completado'
update_pedido_query = "UPDATE pedidos SET estado_pedido = 'Completado' WHERE id_pedido = %s"
cursor.execute(update_pedido_query, (id_pedido,))

# Llama a la función para registrar la venta
from blueprints.ventas import registrar_venta_desde_pedido # <--- ¡Importa la función!
venta_registrada = registrar_venta_desde_pedido(id_pedido, conn, cursor) # Pasa conn y cursor

if venta_registrada:
    response_data['mensaje_venta'] = "Venta registrada exitosamente a partir del pedido."
else:
    response_data['mensaje_venta'] = "Advertencia: La venta no pudo ser registrada automáticamente."

conn.commit() # Confirmar todas las transacciones

# ... (resto de la función) ...

 Pruebas (Opcional)
El directorio tests/ está configurado para contener pruebas unitarias y de integración. Se recomienda escribir pruebas para asegurar la funcionalidad y estabilidad de la API.

Contacto
Para cualquier pregunta o sugerencia, puedes contactar a Alex Andres Pinto Bohorquez (alexpintob75@gmail.com) o Arelis Maria Troncoso Campos (arelistroncosocampos@gmail.com).

¡Disfruta construyendo el frontend para tu Granja CBC!