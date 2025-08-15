from flask import jsonify, request
from flask_restx import Namespace, Resource
from utils.db import conectar_db
import pymysql.cursors
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from utils.auth_decorators import admin_required, admin_or_employee_required, jwt_auth_required
from utils.helpers import api_response, db_session, limpiar_string, es_email_valido


auth_users_ns = Namespace('auth', description='Operaciones de Autenticación y Gestión de Usuarios')


# Funciones Auxiliares para Roles (Uso interno del Namespace)
def get_role_name_by_id(id_rol):
    conn = None
    cursor = None
    try:
        conn = conectar_db()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        query = "SELECT nombre_rol FROM roles WHERE id_rol = %s"
        cursor.execute(query, (id_rol,))
        result = cursor.fetchone()
        return result['nombre_rol'] if result else None
    except Exception as e:
        print(f"Error al obtener nombre de rol por ID {id_rol}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_role_id_by_name(nombre_rol):
    conn = None
    cursor = None
    try:
        conn = conectar_db()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        query = "SELECT id_rol FROM roles WHERE nombre_rol = %s"
        cursor.execute(query, (nombre_rol,))
        result = cursor.fetchone()
        return result['id_rol'] if result else None
    except Exception as e:
        print(f"Error al obtener ID de rol por nombre {nombre_rol}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Definición de Rutas como Clases Resource
@auth_users_ns.route('/registro')
class UserRegister(Resource):
    @auth_users_ns.doc('Crea una nueva cuenta de usuario')
    def post(self):
        """Crea una nueva cuenta de usuario."""
        data = request.get_json()
        nombre = limpiar_string(data.get('nombre'))
        usuario = limpiar_string(data.get('usuario'))
        contrasena = data.get('contrasena')
        telefono = limpiar_string(data.get('telefono')) if data.get('telefono') else None

        if not all([nombre, usuario, contrasena]):
            return api_response(message="Nombre, usuario y contraseña son campos requeridos.", status_code=400)
        
        if not es_email_valido(usuario):
             return api_response(message="El formato del nombre de usuario (email) no es válido.", status_code=400)
        if len(contrasena) < 8:
            return api_response(message="La contraseña debe tener al menos 8 caracteres.", status_code=400)

        try:
            with db_session() as (conn, cursor):
                check_user_query = "SELECT id_usuario FROM usuarios WHERE usuario = %s"
                cursor.execute(check_user_query, (usuario,))
                if cursor.fetchone():
                    return api_response(message="El nombre de usuario ya está registrado.", status_code=400)

                hashed_password = generate_password_hash(contrasena)

                id_rol_cliente = get_role_id_by_name("Cliente")
                if not id_rol_cliente:
                    return api_response(message="Error: Rol 'Cliente' no encontrado en la base de datos.", status_code=500)

                insert_query = """
                    INSERT INTO usuarios (nombre, usuario, contrasena, telefono, id_rol)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (nombre, usuario, hashed_password, telefono, id_rol_cliente))
                user_id = cursor.lastrowid

                query_new_user = """
                    SELECT u.id_usuario, u.nombre, u.usuario, u.telefono, r.nombre_rol AS rol
                    FROM usuarios u JOIN roles r ON u.id_rol = r.id_rol WHERE u.id_usuario = %s
                """
                cursor.execute(query_new_user, (user_id,))
                new_user_data = cursor.fetchone()

                return api_response(data=new_user_data, message="Usuario registrado exitosamente.", status_code=201)

        except Exception as e:
            return api_response(message="Error interno del servidor al registrar usuario.", status_code=500, error=str(e))


@auth_users_ns.route('/login')
class UserLogin(Resource):
    @auth_users_ns.doc('Inicia sesión y devuelve un token JWT')
    def post(self):
        """Inicia sesión y devuelve un token JWT."""
        data = request.get_json()
        usuario = limpiar_string(data.get('usuario'))
        contrasena = data.get('contrasena')

        if not all([usuario, contrasena]):
            return api_response(message="Usuario y contraseña son campos requeridos.", status_code=400)

        try:
            with db_session() as (conn, cursor):
                query = """
                    SELECT u.id_usuario, u.nombre, u.contrasena, r.nombre_rol, r.id_rol
                    FROM usuarios u
                    JOIN roles r ON u.id_rol = r.id_rol
                    WHERE u.usuario = %s
                """
                cursor.execute(query, (usuario,))
                user = cursor.fetchone()

                if user and check_password_hash(user['contrasena'], contrasena):
                    rol_nombre = user['nombre_rol']
                    
                    access_token = create_access_token(identity=user['id_usuario'], 
                                                       additional_claims={"roles": [rol_nombre]})
                    
                    return api_response(data={
                        "id_usuario": user['id_usuario'],
                        "nombre": user['nombre'],
                        "rol": rol_nombre,
                        "token": access_token
                    }, message="Inicio de sesión exitoso.", status_code=200)
                else:
                    return api_response(message="Credenciales inválidas.", status_code=401)

        except Exception as e:
            return api_response(message="Error interno del servidor al iniciar sesión.", status_code=500, error=str(e))

@auth_users_ns.route('/me')
class UserProfile(Resource):
    @jwt_auth_required()
    @auth_users_ns.doc('Obtiene el perfil del usuario autenticado')
    def get(self):
        """Obtiene el perfil del usuario autenticado."""
        current_user_id = get_jwt_identity()
        
        try:
            with db_session() as (conn, cursor):
                query = """
                    SELECT u.id_usuario, u.nombre, u.usuario, u.telefono, r.nombre_rol AS rol
                    FROM usuarios u
                    JOIN roles r ON u.id_rol = r.id_rol
                    WHERE u.id_usuario = %s
                """
                cursor.execute(query, (current_user_id,))
                user_profile = cursor.fetchone()

                if user_profile:
                    return api_response(data=user_profile, message="Perfil de usuario obtenido.", status_code=200)
                else:
                    return api_response(message="Perfil de usuario no encontrado.", status_code=404)

        except Exception as e:
            return api_response(message="Error interno del servidor al obtener perfil de usuario.", status_code=500, error=str(e))

@auth_users_ns.route('/usuarios')
class UserList(Resource):
    @jwt_required()
    @admin_required()
    @auth_users_ns.doc('Obtiene una lista de todos los usuarios registrados (solo Admin)')
    def get(self):
        """Obtiene una lista de todos los usuarios registrados."""
        try:
            with db_session() as (conn, cursor):
                query = """
                    SELECT u.id_usuario, u.nombre, u.usuario, u.telefono, r.nombre_rol AS rol
                    FROM usuarios u
                    JOIN roles r ON u.id_rol = r.id_rol
                """
                cursor.execute(query)
                users = cursor.fetchall()
                
                return api_response(data=users, message="Lista de usuarios obtenida.", status_code=200)

        except Exception as e:
            return api_response(message="Error interno del servidor al obtener todos los usuarios.", status_code=500, error=str(e))


@auth_users_ns.route('/usuarios/<int:id_usuario>')
@auth_users_ns.param('id_usuario', 'El ID del usuario a gestionar')
class UserManagement(Resource):
    @jwt_required()
    @auth_users_ns.doc('Actualiza el perfil de un usuario')
    def put(self, id_usuario):
        """Actualiza el perfil de un usuario."""
        data = request.get_json()
        nombre = limpiar_string(data.get('nombre'))
        usuario_name = limpiar_string(data.get('usuario'))
        telefono = limpiar_string(data.get('telefono')) if data.get('telefono') else None

        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_roles = claims.get("roles", [])

        if current_user_id != id_usuario and "Admin" not in user_roles:
            return api_response(message="Acceso denegado: No tienes permiso para actualizar este perfil.", status_code=403)

        try:
            with db_session() as (conn, cursor):
                update_fields = []
                update_values = []
                if nombre:
                    update_fields.append("nombre = %s")
                    update_values.append(nombre)
                if usuario_name:
                    update_fields.append("usuario = %s")
                    update_values.append(usuario_name)
                if telefono:
                    update_fields.append("telefono = %s")
                    update_values.append(telefono)
                
                if not update_fields:
                    return api_response(message="No hay campos para actualizar.", status_code=400)

                update_query = "UPDATE usuarios SET " + ", ".join(update_fields) + " WHERE id_usuario = %s"
                update_values.append(id_usuario)

                cursor.execute(update_query, tuple(update_values))
                
                if cursor.rowcount == 0:
                    return api_response(message="Usuario no encontrado o no se realizaron cambios.", status_code=404)

                query_updated = """
                    SELECT u.id_usuario, u.nombre, u.usuario, u.telefono, r.nombre_rol AS rol
                    FROM usuarios u
                    JOIN roles r ON u.id_rol = r.id_rol
                    WHERE u.id_usuario = %s
                """
                cursor.execute(query_updated, (id_usuario,))
                updated_user = cursor.fetchone()

                return api_response(data=updated_user, message="Perfil de usuario actualizado exitosamente.", status_code=200)

        except Exception as e:
            return api_response(message="Error interno del servidor al actualizar usuario.", status_code=500, error=str(e))

    @jwt_required()
    @admin_required()
    @auth_users_ns.doc('Elimina un usuario (solo Admin)')
    def delete(self, id_usuario):
        """Elimina un usuario."""
        try:
            with db_session() as (conn, cursor):
                delete_query = "DELETE FROM usuarios WHERE id_usuario = %s"
                cursor.execute(delete_query, (id_usuario,))
                
                if cursor.rowcount == 0:
                    return api_response(message="Usuario no encontrado.", status_code=404)

                return api_response(message="Usuario eliminado exitosamente.", status_code=200)

        except Exception as e:
            return api_response(message="Error interno del servidor al eliminar usuario.", status_code=500, error=str(e))


@auth_users_ns.route('/usuarios/<int:id_usuario>/contrasena')
@auth_users_ns.param('id_usuario', 'El ID del usuario cuya contraseña se va a actualizar')
class UserPassword(Resource):
    @jwt_required()
    @auth_users_ns.doc('Actualiza la contraseña de un usuario')
    def put(self, id_usuario):
        """Permite a un usuario cambiar su propia contraseña. Admin puede cambiar cualquier contraseña."""
        data = request.get_json()
        current_password = data.get('contrasena_actual')
        new_password = data.get('nueva_contrasena')

        if not new_password:
            return api_response(message="Nueva contraseña es requerida.", status_code=400)
        
        if len(new_password) < 8:
            return api_response(message="La nueva contraseña debe tener al menos 8 caracteres.", status_code=400)

        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_roles = claims.get("roles", [])

        try:
            with db_session() as (conn, cursor):
                query = "SELECT contrasena FROM usuarios WHERE id_usuario = %s"
                cursor.execute(query, (id_usuario,))
                user = cursor.fetchone()

                if not user:
                    return api_response(message="Usuario no encontrado.", status_code=404)
                
                if "Admin" not in user_roles:
                    if current_user_id != id_usuario:
                        return api_response(message="Acceso denegado: No tienes permiso para cambiar la contraseña de otro usuario.", status_code=403)
                    
                    if not current_password or not check_password_hash(user['contrasena'], current_password):
                        return api_response(message="Contraseña actual incorrecta.", status_code=400)

                hashed_new_password = generate_password_hash(new_password)

                update_query = "UPDATE usuarios SET contrasena = %s WHERE id_usuario = %s"
                cursor.execute(update_query, (hashed_new_password, id_usuario))
                
                if cursor.rowcount == 0:
                    return api_response(message="No se pudo actualizar la contraseña.", status_code=500)

                return api_response(message="Contraseña actualizada exitosamente.", status_code=200)

        except Exception as e:
            return api_response(message="Error interno del servidor al actualizar contraseña.", status_code=500, error=str(e))


@auth_users_ns.route('/usuarios/<int:id_usuario>/rol')
@auth_users_ns.param('id_usuario', 'El ID del usuario cuyo rol se va a actualizar')
class UserRole(Resource):
    @jwt_required()
    @admin_required()
    @auth_users_ns.doc('Actualiza el rol de un usuario (Solo Admin)')
    def put(self, id_usuario):
        """Actualiza el rol de un usuario específico."""
        data = request.get_json()
        id_rol = data.get('id_rol')

        if not id_rol:
            return api_response(message="ID del rol es requerido.", status_code=400)

        try:
            with db_session() as (conn, cursor):
                cursor.execute("SELECT id_usuario FROM usuarios WHERE id_usuario = %s", (id_usuario,))
                if not cursor.fetchone():
                    return api_response(message="Usuario no encontrado.", status_code=404)
                
                cursor.execute("SELECT id_rol FROM roles WHERE id_rol = %s", (id_rol,))
                if not cursor.fetchone():
                    return api_response(message="ID de rol no válido.", status_code=400)

                update_query = "UPDATE usuarios SET id_rol = %s WHERE id_usuario = %s"
                cursor.execute(update_query, (id_rol, id_usuario))
                
                query_updated = """
                    SELECT u.id_usuario, u.nombre, u.usuario, u.telefono, r.nombre_rol AS rol
                    FROM usuarios u
                    JOIN roles r ON u.id_rol = r.id_rol
                    WHERE u.id_usuario = %s
                """
                cursor.execute(query_updated, (id_usuario,))
                updated_user = cursor.fetchone()

                return api_response(data=updated_user, message="Rol de usuario actualizado exitosamente.", status_code=200)

        except Exception as e:
            return api_response(message="Error interno del servidor al actualizar rol de usuario.", status_code=500, error=str(e))


@auth_users_ns.route('/roles')
class RoleList(Resource):
    @jwt_required()
    @admin_required()
    @auth_users_ns.doc('Obtiene una lista de todos los roles de usuario disponibles (Solo Admin)')
    def get(self):
        """Obtiene una lista de todos los roles de usuario disponibles."""
        try:
            with db_session() as (conn, cursor):
                query = "SELECT id_rol, nombre_rol FROM roles"
                cursor.execute(query)
                roles = cursor.fetchall()
                
                return api_response(data=roles, message="Lista de roles obtenida.", status_code=200)

        except Exception as e:
            return api_response(message="Error interno del servidor al obtener roles.", status_code=500, error=str(e))
