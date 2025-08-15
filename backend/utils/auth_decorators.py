from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity

from utils.db import conectar_db
import pymysql.cursors

def get_user_role_from_db(user_id):
    conn = None
    cursor = None
    rol_name = None
    try:
        conn = conectar_db()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        query = """
            SELECT r.nombre_rol
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            WHERE u.id_usuario = %s
        """
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        if result:
            rol_name = result['nombre_rol']
    except Exception as e:
        print(f"Error al obtener el rol del usuario {user_id} desde la DB: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return rol_name

def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            claims = get_jwt()
            user_roles_from_jwt = claims.get("roles", [])

            if "Admin" not in user_roles_from_jwt:
                user_role_from_db = get_user_role_from_db(current_user_id)
                if user_role_from_db == "Admin":
                    user_roles_from_jwt.append("Admin")
            
            if "Admin" not in user_roles_from_jwt:
                return jsonify({"mensaje": "Acceso denegado: Se requiere rol de Administrador."}), 403

            return fn(*args, **kwargs)
        return decorator
    return wrapper

def admin_or_employee_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            claims = get_jwt()
            user_roles_from_jwt = claims.get("roles", [])

            if not ("Admin" in user_roles_from_jwt or "Empleado" in user_roles_from_jwt):
                user_role_from_db = get_user_role_from_db(current_user_id)
                if user_role_from_db in ["Admin", "Empleado"]:
                    user_roles_from_jwt.append(user_role_from_db)

            if not ("Admin" in user_roles_from_jwt or "Empleado" in user_roles_from_jwt):
                return jsonify({"mensaje": "Acceso denegado: Se requiere rol de Administrador o Empleado."}), 403

            return fn(*args, **kwargs)
        return decorator
    return wrapper

def jwt_auth_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            return fn(*args, **kwargs)
        return decorator
    return wrapper
