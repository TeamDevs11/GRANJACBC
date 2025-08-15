from flask import Flask, jsonify
from flask_cors import CORS
from flask_restx import Api
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os

# Importa el Namespace de autenticación.
# ¡Asegúrate de que este archivo exista en `blueprints/auth_users.py` y exporte 'auth_users_ns'!
from blueprints.auth_users import auth_users_ns # NOTA: ¡ESTA LÍNEA DEBE DECIR 'auth_users_ns', NO '_bp'!

# Importa tus otros Namespaces (descomentar y adaptar cuando los tengas listos)
# from blueprints.productos import productos_ns
# from blueprints.inventarios import inventarios_ns
# from blueprints.clientes import clientes_ns
# # from blueprints.carrito import carrito_ns
# from blueprints.ventas import ventas_ns
# from blueprints.pagos import pagos_ns
# # from blueprints.reseñas import reseñas_ns
# # from blueprints.auditoria import auditoria_ns


# Carga las variables de entorno desde el archivo .env
load_dotenv()

# Inicializa la aplicación Flask
app = Flask(__name__)

# Configura la clave secreta para los tokens JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
jwt = JWTManager(app)

# Configura CORS para permitir solicitudes desde el frontend
CORS(app)

# Configuración de Flask-RESTx para la Documentación (Swagger UI)
# Esto crea la interfaz interactiva de tu API en /apidocs/
api = Api(
    app,
    version='1.0',
    title='API de Granja CBC',
    description='Documentación de la API para la gestión de productos, inventario, usuarios, clientes, ventas y más de Granja CBC.',
    doc='/apidocs/'
)

# Registra los Namespaces de tu API con Flask-RESTx.
# Esto hace que las rutas definidas en auth_users_ns sean accesibles.
api.add_namespace(auth_users_ns, path='/auth') # NOTA: ¡Y AQUÍ TAMBIÉN DEBE DECIR 'auth_users_ns', NO '_bp'!

# Registra tus otros Namespaces aquí cuando los vayas creando y adaptando.
# api.add_namespace(productos_ns, path='/productos')
# api.add_namespace(inventarios_ns, path='/inventario')
# api.add_namespace(clientes_ns, path='/clientes')
# # api.add_namespace(carrito_ns, path='/carrito')
# api.add_namespace(ventas_ns, path='/ventas')
# api.add_namespace(pagos_ns, path='/pagos')
# # api.add_namespace(reseñas_ns, path='/reseñas')
# # api.add_namespace(auditoria_ns, path='/auditoria')


# Ruta de inicio (raíz de la API)
@app.route('/')
def home():
    # Mensaje de depuración: verifica si esta función se ejecuta
    print("DEBUG: La función 'home()' en app.py ha sido llamada.")
    return jsonify({"mensaje": "Bienvenido a la API de Granja CBC. Visita /apidocs/ para la documentación interactiva."})

# Punto de entrada para ejecutar la aplicación
if __name__ == '__main__':
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    app.run(debug=debug_mode, port=port)
