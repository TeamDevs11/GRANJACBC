import re
from datetime import datetime
import logging
from flask import jsonify 
from contextlib import contextmanager 
import pymysql.cursors 

from utils.db import conectar_db

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def api_response(data=None, message="Operación exitosa.", status_code=200, error=None):
    """
    Estandariza las respuestas de la API en formato JSON.
    Recibe datos, un mensaje, un código de estado HTTP y un error opcional.
    """
    response_payload = {
        "mensaje": message,
        "data": data
    }
    if error:
        response_payload["error"] = error
    return jsonify(response_payload), status_code

def limpiar_string(cadena):
    """
    Limpia una cadena de texto, eliminando espacios en blanco al inicio y al final,
    y reemplazando múltiples espacios internos por uno solo.
    """
    if not isinstance(cadena, str):
        return cadena
    # Eliminar espacios extra y dejar solo uno entre palabras, luego trim
    return re.sub(r'\s+', ' ', cadena).strip()

def es_email_valido(email):
    """Verifica si una cadena tiene un formato de email básico válido."""
    # Patrón de regex para una validación de email estándar
    patron = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(patron, email) is not None

def formatear_fecha_hora(dt_obj, formato="%Y-%m-%d %H:%M:%S"):
    """Formatea un objeto datetime a una cadena de texto."""
    if isinstance(dt_obj, datetime):
        return dt_obj.strftime(formato)
    return None

def log_accion(tipo_accion, mensaje, nivel='info'):
    """Registra una acción o evento en los logs de la aplicación."""
    if nivel == 'info':
        logger.info(f"{tipo_accion}: {mensaje}")
    elif nivel == 'warning':
        logger.warning(f"{tipo_accion}: {mensaje}")
    elif nivel == 'error':
        logger.error(f"{tipo_accion}: {mensaje}")

@contextmanager
def db_session():
    """
    Proporciona una sesión de base de datos con manejo automático de conexión, cursor,
    commit y rollback. Garantiza que la conexión se cierra siempre.
    """
    conn = None
    cursor = None
    try:
        conn = conectar_db()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 
        yield conn, cursor 
        conn.commit() 
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error en la sesión de base de datos: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

