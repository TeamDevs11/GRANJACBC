from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from flasgger import Swagger 
import os

from blueprints.usuarios import usuarios_bp 
from blueprints.productos import productos_bp


load_dotenv()

# Inicia la aplicación Flask
app = Flask(__name__)

#Configuración de la Aplicación
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
jwt = JWTManager(app)

CORS(app)

# genera la interfaz de Swagger 
swagger = Swagger(app)

# las rutas definidas dentro de cada Blueprint sean accesibles bajo el path especificado.
app.register_blueprint(usuarios_bp, url_prefix='/auth')
app.register_blueprint(productos_bp, url_prefix='/productos') 

# Ruta de Inicio 
@app.route('/')
def home():
    print("DEBUG: La función 'home()' en app.py ha sido llamada.")
    return jsonify({"mensaje": "Bienvenido a la API de Granja CBC. Visita /apidocs/ para la documentación interactiva."})

if __name__ == '__main__':
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    app.run(debug=debug_mode, port=port)
