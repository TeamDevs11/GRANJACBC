from flask import Blueprint, jsonify, request
import pymysql.cursors
import bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from utils.db import conectar_db
from utils.auth_decorators import admin_required, admin_or_employee_required, jwt_auth_required
from utils.helpers import api_response, db_session, limpiar_string, es_email_valido


usuarios_bp = Blueprint('usuarios_bp', __name__)

SALT_ROUNDS = 12

# Funciones Auxiliares para Roles 
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
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Definir Rutas
@usuarios_bp.route('/registro', methods=['POST'])
def registro_usuario():
    """
    Crea una nueva cuenta de usuario.
    ---
    parameters:
      - in: body
        name: body
        schema:
          id: RegistroUsuario
          required:
            - nombre
            - usuario
            - contrasena
            - telefono
          properties:
            nombre:
              type: string
              description: Nombre completo del usuario
            usuario:
              type: string
              format: email
              description: Email (servirá como nombre de usuario para login)
            contrasena:
              type: string
              description: Contraseña del usuario (mínimo 8 caracteres)
            telefono:
              type: string
              description: Número de teléfono del usuario
    responses:
      201:
        description: Usuario registrado exitosamente
        schema:
          id: UserProfile
          properties:
            id_usuario:
              type: integer
            nombre:
              type: string
            usuario:
              type: string
            telefono:
              type: string
            rol:
              type: string
      400:
        description: Error de validación o usuario ya existe
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    nombre = limpiar_string(data.get('nombre'))
    usuario = limpiar_string(data.get('usuario'))
    contrasena = data.get('contrasena')
    telefono = limpiar_string(data.get('telefono'))

    if not all([nombre, usuario, contrasena, telefono]):
        return api_response(message="Nombre, usuario, contraseña y teléfono son campos requeridos.", status_code=400)

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

            # bcrypt para la contraseña
            hashed_password = bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt(SALT_ROUNDS)).decode('utf-8')

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

# ruta de inicio de sesion de usuario 
@usuarios_bp.route('/login', methods=['POST'])
def iniciar_sesion():
    """
    Inicia sesión y devuelve un token JWT.
    ---
    parameters:
      - in: body
        name: body
        schema:
          id: IniciarSesion
          required:
            - usuario
            - contrasena
          properties:
            usuario:
              type: string
              description: Email o nombre de usuario
            contrasena:
              type: string
              description: Contraseña
    responses:
      200:
        description: Inicio de sesión exitoso
        schema:
          properties:
            mensaje:
              type: string
            data:
              type: object
              properties:
                id_usuario:
                  type: integer
                nombre:
                  type: string
                rol:
                  type: string
                token:
                  type: string
      400:
        description: Campos requeridos
      401:
        description: Credenciales inválidas
      500:
        description: Error interno del servidor
    """
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

            # Usamos bcrypt para verificar la contraseña
            if user and bcrypt.checkpw(contrasena.encode('utf-8'), user['contrasena'].encode('utf-8')):
                rol_nombre = user['nombre_rol']

                access_token = create_access_token(identity=str(user['id_usuario']),
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

# ruta para obtner el perfil del usuario
@usuarios_bp.route('/me', methods=['GET'])
@jwt_auth_required() 
def obtener_perfil():
    """
    Obtiene el perfil del usuario autenticado.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Perfil de usuario obtenido
        schema:
          id: UserProfile
          properties:
            id_usuario:
              type: integer
            nombre:
              type: string
            usuario:
              type: string
            telefono:
              type: string
            rol:
              type: string
      401:
        description: No autorizado
      404:
        description: Usuario no encontrado
      500:
        description: Error interno del servidor
    """
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


@usuarios_bp.route('/usuarios', methods=['GET'])
@jwt_required()
@admin_required() # solo tiene actorizacion el admin
def Lista_usuarios():
    """
    Obtiene una lista de todos los usuarios registrados (solo Admin).
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de usuarios obtenida
        schema:
          type: array
          items:
            $ref: '#/definitions/UserProfile'
      401:
        description: No autorizado
      403:
        description: Acceso denegado (solo Admin)
      500:
        description: Error interno del servidor
    """
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


@usuarios_bp.route('/usuarios/<int:id_usuario>', methods=['PUT'])
@jwt_required()
def actualiza_perfil(id_usuario):
    """
    Actualiza el perfil de un usuario.
    ---
    parameters:
      - in: path
        name: id_usuario
        type: integer
        required: true
        description: El ID del usuario a actualizar
      - in: body
        name: body
        schema:
          properties:
                nombre:
                  type: string
                usuario:
                  type: string
                telefono:
                  type: string
        security:
          - Bearer: []
        responses:
          200:
            description: Perfil de usuario actualizado
            schema:
              $ref: '#/definitions/UserProfile'
          400:
            description: Datos inválidos
          403:
            description: Acceso denegado
          404:
            description: Usuario no encontrado
          500:
            description: Error interno del servidor
        """
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
            if telefono is not None:
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

# ruta eliminar usuario
@usuarios_bp.route('/usuarios/<int:id_usuario>', methods=['DELETE'])
@jwt_required()
@admin_required() # solo el admin tiene actorizacion a esta ruta 
def elimina_usuario(id_usuario):
    """
    Elimina un usuario (Solo Admin).
    ---
    parameters:
      - in: path
        name: id_usuario
        type: integer
        required: true
        description: El ID del usuario a eliminar
    security:
          - Bearer: []
    responses:
      200:
        description: Usuario eliminado exitosamente
      403:
        description: Acceso denegado (solo Admin)
      404:
        description: Usuario no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            delete_query = "DELETE FROM usuarios WHERE id_usuario = %s"
            cursor.execute(delete_query, (id_usuario,))

            if cursor.rowcount == 0:
                return api_response(message="Usuario no encontrado.", status_code=404)

            return api_response(message="Usuario eliminado exitosamente.", status_code=200)

    except Exception as e:
        return api_response(message="Error interno del servidor al eliminar usuario.", status_code=500, error=str(e))

# ruta para actualizar la contraseña el usuario 
@usuarios_bp.route('/usuarios/<int:id_usuario>/contrasena', methods=['PUT'])
@jwt_required()
def actualiza_contrasena(id_usuario):
    """
    Actualiza la contraseña de un usuario.
    Permite a un usuario cambiar su propia contraseña. Admin puede cambiar cualquier contraseña.
    ---
    parameters:
      - in: path
        name: id_usuario
        type: integer
        required: true
        description: El ID del usuario cuya contraseña se va a actualizar
      - in: body
        name: body
        schema:
          required:
            - nueva_contrasena
          properties:
            contrasena_actual:
              type: string
              description: Contraseña actual del usuario (requerida para no-admin)
            nueva_contrasena:
              type: string
              description: Nueva contraseña del usuario (mínimo 8 caracteres)
    security:
      - Bearer: []
    responses:
      200:
        description: Contraseña actualizada exitosamente
      400:
        description: Datos inválidos o contraseña actual incorrecta
      403:
        description: Acceso denegado
      404:
        description: Usuario no encontrado
      500:
        description: Error interno del servidor
    """
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

                # bcrypt para verificar la contraseña actual
                if not current_password or not bcrypt.checkpw(current_password.encode('utf-8'), user['contrasena'].encode('utf-8')):
                    return api_response(message="Contraseña actual incorrecta.", status_code=400)

            # Hashear la nueva contraseña con bcrypt
            hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt(SALT_ROUNDS)).decode('utf-8')

            update_query = "UPDATE usuarios SET contrasena = %s WHERE id_usuario = %s"
            cursor.execute(update_query, (hashed_new_password, id_usuario))

            if cursor.rowcount == 0:
                return api_response(message="No se pudo actualizar la contraseña.", status_code=500)

            return api_response(message="Contraseña actualizada exitosamente.", status_code=200)

    except Exception as e:
        return api_response(message="Error interno del servidor al actualizar contraseña.", status_code=500, error=str(e))

# ruta para actualizar los roles de los usuarios 
@usuarios_bp.route('/usuarios/<int:id_usuario>/rol', methods=['PUT'])
@jwt_required()
@admin_required() # solo el admin tiene acceso a esta ruta 
def actualiza_rol(id_usuario):
    """
    Actualiza el rol de un usuario (Solo Admin).
    ---
    parameters:
      - in: path
        name: id_usuario
        type: integer
        required: true
        description: El ID del usuario cuyo rol se va a actualizar
      - in: body
        name: body
        schema:
          required:
            - id_rol
          properties:
            id_rol:
              type: integer
              description: Nuevo ID de rol para el usuario
    security:
          - Bearer: []
    responses:
      200:
        description: Rol de usuario actualizado
        schema:
          $ref: '#/definitions/UserProfile'
      400:
        description: ID de rol no válido
      403:
        description: Acceso denegado (solo Admin)
      404:
        description: Usuario o rol no encontrado
      500:
        description: Error interno del servidor
    """
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

# ruta para obtener la lista de todos los roles de usuarios disponible 
@usuarios_bp.route('/roles', methods=['GET'])
@jwt_required()
@admin_required() # solo admin tienen acceso a esta ruta 
def lista_roles():
    """
    Obtiene una lista de todos los roles de usuario disponibles (Solo Admin).
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de roles obtenida
        schema:
          type: array
          items:
            type: object
            properties:
              id_rol:
                type: integer
              nombre_rol:
                type: string
      401:
        description: No autorizado
      403:
        description: Acceso denegado (solo Admin)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = "SELECT id_rol, nombre_rol FROM roles"
            cursor.execute(query)
            roles = cursor.fetchall()

            return api_response(data=roles, message="Lista de roles obtenida.", status_code=200)

    except Exception as e:
        return api_response(message="Error interno del servidor al obtener roles.", status_code=500, error=str(e))
