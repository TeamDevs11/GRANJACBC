from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from flasgger import Swagger
import os

# Importar blueprints
from blueprints.usuarios import usuarios_bp
from blueprints.productos import productos_bp
from blueprints.inventarios import inventarios_bp
from blueprints.clientes import clientes_bp
from blueprints.carrito import carrito_bp
from blueprints.categorias import categorias_bp
from blueprints.pagos import pagos_bp
from blueprints.pedidos import pedidos_bp
from blueprints.resenas import resenas_bp 
from blueprints.ventas import ventas_bp



load_dotenv()

# Inicia la aplicación Flask
app = Flask(__name__)

# Configuración de la Aplicación
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "clave-super-secreta")  # Clave JWT
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY", "super-secret-flask-key-por-defecto")

jwt = JWTManager(app)
CORS(app)

# --- Configuración de Flasgger (Swagger UI) ---
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'mi_apidocs',
            "route": '/mi_apidocs.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "converters": "rules",
    "specs_route": "/apidocs/",
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header usando el esquema Bearer. Ejemplo: \"Authorization: Bearer {token}\""
        }
    },
    "security": [
        {"Bearer": []}
    ]
}

swagger = Swagger(app, config=swagger_config)

# Registrar Blueprints
app.register_blueprint(usuarios_bp, url_prefix='/auth')       
app.register_blueprint(productos_bp, url_prefix='/productos')
app.register_blueprint(inventarios_bp, url_prefix='/inventarios')
app.register_blueprint(clientes_bp, url_prefix='/clientes')
app.register_blueprint(carrito_bp, url_prefix='/carrito')
app.register_blueprint(categorias_bp, url_prefix='/categorias')
app.register_blueprint(pagos_bp, url_prefix='/pagos')
app.register_blueprint(pedidos_bp, url_prefix='/pedidos')
app.register_blueprint(resenas_bp, url_prefix='/resenas')
app.register_blueprint(ventas_bp, url_prefix='/ventas')

@app.route('/')
def home():
    return jsonify({"mensaje": "Bienvenido a la API de Granja CBC. Visita /apidocs/ para la documentación interactiva."})

# --- Manejo de errores JWT personalizado ---
@jwt.unauthorized_loader
def unauthorized_response(callback):
    return jsonify({"success": False, "message": "Autenticación requerida: Token JWT no proporcionado."}), 401

@jwt.invalid_token_loader
def invalid_token_response(callback):
    return jsonify({"success": False, "message": "Token de autenticación inválido."}), 401

@jwt.expired_token_loader
def expired_token_response(jwt_header, jwt_payload):
    return jsonify({"success": False, "message": "Token de autenticación expirado."}), 401

@jwt.revoked_token_loader
def revoked_token_response(jwt_header, jwt_payload):
    return jsonify({"success": False, "message": "Token de autenticación revocado."}), 401

@app.errorhandler(403)
def forbidden(error):
    return jsonify({"success": False, "message": "Acceso denegado: No tienes permiso para realizar esta acción."}), 403

if __name__ == '__main__':
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    app.run(debug=debug_mode, port=port)
