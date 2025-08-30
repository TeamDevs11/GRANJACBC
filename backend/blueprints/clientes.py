from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from utils.auth_decorators import Administrador_requerido # Solo el administrador puede gestionar otros clientes
from utils.helpers import api_response, db_session, limpiar_string

# Define el Blueprint para clientes
clientes_bp = Blueprint('clientes_bp', __name__)

# --- Rutas para la gestión del perfil de cliente ---

@clientes_bp.route('/me', methods=['GET'])
@jwt_required() # Requiere un token JWT válido para acceder al perfil del cliente propio
def obtener_mi_perfil_cliente():
    """
    Obtiene el perfil completo del cliente autenticado.
    Esta ruta devolverá los datos de la tabla 'clientes'
    asociados al usuario autenticado.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Perfil de cliente obtenido exitosamente
        schema:
          id: PerfilCliente
          properties:
            id_cliente:
              type: integer
            id_usuario:
              type: integer
            nombre:
              type: string
            direccion:
              type: string
            ciudad:
              type: string
            telefono:
              type: string
            email:
              type: string
            rol:
              type: string
      401:
        description: No autorizado (token JWT inválido o ausente)
      404:
        description: Perfil de cliente no encontrado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity() # Obtiene el ID del usuario del token JWT

    try:
        with db_session() as (conn, cursor):
            # Obtenemos la información de la tabla 'clientes' vinculada al 'id_usuario'
            # y también el email y rol del usuario de la tabla 'usuarios'
            query = """
                SELECT c.id_cliente, c.id_usuario, c.nombre, c.direccion, c.ciudad, c.telefono,
                       u.usuario AS email, r.nombre_rol AS rol
                FROM clientes c
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                JOIN roles r ON u.id_rol = r.id_rol
                WHERE c.id_usuario = %s
            """
            cursor.execute(query, (current_user_id,))
            client_profile = cursor.fetchone()

            if client_profile:
                return api_response(data=client_profile, message="Perfil de cliente obtenido exitosamente.", status_code=200)
            else:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil de cliente.", status_code=404)

    except Exception as e:
        print(f"DEBUG_CLIENT_GET_PROFILE_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el perfil del cliente.", status_code=500, error=str(e))


@clientes_bp.route('/me', methods=['PUT'])
@jwt_required() # Requiere un token JWT válido para actualizar el perfil propio
def actualizar_mi_perfil_cliente():
    """
    Actualiza la información del perfil del cliente autenticado.
    Permite actualizar campos como nombre, teléfono, dirección y ciudad.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: ActualizarPerfilCliente
          properties:
            nombre:
              type: string
              description: Nuevo nombre completo del cliente para este perfil (ej. nombre de contacto)
            direccion:
              type: string
              description: Nueva dirección de envío del cliente
            ciudad:
              type: string
              description: Nueva ciudad del cliente
            telefono:
              type: string
              description: Nuevo número de teléfono del cliente para este perfil
    responses:
      200:
        description: Perfil de cliente actualizado exitosamente
        schema:
          $ref: '#/definitions/PerfilCliente'
      400:
        description: No hay campos para actualizar o datos inválidos
      401:
        description: No autorizado (token JWT inválido o ausente)
      404:
        description: Cliente no encontrado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()

    nombre = limpiar_string(data.get('nombre')) if data.get('nombre') is not None else None
    direccion = limpiar_string(data.get('direccion')) if data.get('direccion') is not None else None
    ciudad = limpiar_string(data.get('ciudad')) if data.get('ciudad') is not None else None
    telefono = limpiar_string(data.get('telefono')) if data.get('telefono') is not None else None

    update_fields = []
    update_values = []

    if nombre is not None:
        update_fields.append("nombre = %s")
        update_values.append(nombre)
    if direccion is not None:
        update_fields.append("direccion = %s")
        update_values.append(direccion)
    if ciudad is not None:
        update_fields.append("ciudad = %s")
        update_values.append(ciudad)
    if telefono is not None:
        update_fields.append("telefono = %s")
        update_values.append(telefono)

    if not update_fields:
        return api_response(message="No hay campos para actualizar.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            update_query = "UPDATE clientes SET " + ", ".join(update_fields) + " WHERE id_usuario = %s"
            update_values.append(current_user_id)

            cursor.execute(update_query, tuple(update_values))

            if cursor.rowcount == 0:
                return api_response(message="Perfil de cliente no encontrado o no se realizaron cambios. Asegúrese de que su perfil de cliente exista.", status_code=404)

            # Obtener el perfil actualizado para devolverlo en la respuesta
            query_updated = """
                SELECT c.id_cliente, c.id_usuario, c.nombre, c.direccion, c.ciudad, c.telefono,
                       u.usuario AS email, r.nombre_rol AS rol
                FROM clientes c
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                JOIN roles r ON u.id_rol = r.id_rol
                WHERE c.id_usuario = %s
            """
            cursor.execute(query_updated, (current_user_id,))
            updated_profile = cursor.fetchone()

            return api_response(data=updated_profile, message="Perfil de cliente actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CLIENT_UPDATE_PROFILE_ERROR: {e}")
        return api_response(message="Error interno del servidor al actualizar el perfil del cliente.", status_code=500, error=str(e))

# --- Rutas para que el ADMINISTRADOR gestione todos los perfiles de clientes ---

@clientes_bp.route('/', methods=['POST'])
@jwt_required()
@Administrador_requerido() # Solo administradores pueden crear perfiles de cliente para otros usuarios
def crear_perfil_cliente_admin():
    """
    Crea un nuevo perfil de cliente para un 'id_usuario' específico (Solo Administrador).
    Esto es útil si un usuario se registra pero necesita que un admin le cree su perfil de cliente inicial.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: CrearPerfilClienteAdmin
          required:
            - id_usuario
            - nombre
            - direccion
            - ciudad
            - telefono
          properties:
            id_usuario:
              type: integer
              description: ID del usuario al que se vinculará este perfil de cliente.
            nombre:
              type: string
              description: Nombre completo del cliente para este perfil.
            direccion:
              type: string
              description: Dirección de envío del cliente.
            ciudad:
              type: string
              description: Ciudad del cliente.
            telefono:
              type: string
              description: Número de teléfono del cliente para este perfil.
    responses:
      201:
        description: Perfil de cliente creado exitosamente
        schema:
          $ref: '#/definitions/PerfilCliente'
      400:
        description: Datos inválidos o usuario/rol no encontrado
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador)
      409:
        description: El usuario ya tiene un perfil de cliente.
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    id_usuario = data.get('id_usuario')
    nombre = limpiar_string(data.get('nombre'))
    direccion = limpiar_string(data.get('direccion'))
    ciudad = limpiar_string(data.get('ciudad'))
    telefono = limpiar_string(data.get('telefono'))

    if not all([id_usuario, nombre, direccion, ciudad, telefono]):
        return api_response(message="ID de usuario, nombre, dirección, ciudad y teléfono son campos requeridos.", status_code=400)
    
    if not isinstance(id_usuario, int) or id_usuario <= 0:
        return api_response(message="ID de usuario inválido.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Verificar que el id_usuario exista en la tabla usuarios
            cursor.execute("SELECT id_usuario FROM usuarios WHERE id_usuario = %s", (id_usuario,))
            if not cursor.fetchone():
                return api_response(message="El usuario especificado no existe.", status_code=400)

            # 2. Verificar si el usuario ya tiene un perfil de cliente
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (id_usuario,))
            if cursor.fetchone():
                return api_response(message="Este usuario ya tiene un perfil de cliente.", status_code=409)
            
            insert_query = """
                INSERT INTO clientes (id_usuario, nombre, direccion, ciudad, telefono)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (id_usuario, nombre, direccion, ciudad, telefono))
            new_client_id = cursor.lastrowid

            query_new_client_profile = """
                SELECT c.id_cliente, c.id_usuario, c.nombre, c.direccion, c.ciudad, c.telefono,
                       u.usuario AS email, r.nombre_rol AS rol
                FROM clientes c
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                JOIN roles r ON u.id_rol = r.id_rol
                WHERE c.id_cliente = %s
            """
            cursor.execute(query_new_client_profile, (new_client_id,))
            new_client_data = cursor.fetchone()

            return api_response(data=new_client_data, message="Perfil de cliente creado exitosamente.", status_code=201)

    except Exception as e:
        print(f"DEBUG_CLIENT_ADMIN_CREATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al crear el perfil de cliente.", status_code=500, error=str(e))

@clientes_bp.route('/', methods=['GET'])
@jwt_required()
@Administrador_requerido() # Solo administradores pueden listar todos los clientes
def obtener_todos_clientes():
    """
    Obtiene una lista de todos los perfiles de cliente (Solo Administrador).
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de perfiles de cliente obtenida
        schema:
          type: array
          items:
            $ref: '#/definitions/PerfilCliente'
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = """
                SELECT c.id_cliente, c.id_usuario, c.nombre, c.direccion, c.ciudad, c.telefono,
                       u.usuario AS email, r.nombre_rol AS rol
                FROM clientes c
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                JOIN roles r ON u.id_rol = r.id_rol
            """
            cursor.execute(query)
            clientes = cursor.fetchall()
            return api_response(data=clientes, message="Lista de perfiles de cliente obtenida exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CLIENT_GET_ALL_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener todos los perfiles de clientes.", status_code=500, error=str(e))

@clientes_bp.route('/<int:id_cliente>', methods=['GET'])
@jwt_required()
@Administrador_requerido() # Solo administradores pueden ver perfiles de clientes por ID
def obtener_cliente_por_id(id_cliente):
    """
    Obtiene los detalles de un perfil de cliente específico por su ID (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_cliente
        type: integer
        required: true
        description: ID del perfil de cliente a obtener
    responses:
      200:
        description: Detalles del perfil de cliente obtenidos
        schema:
          $ref: '#/definitions/PerfilCliente'
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Perfil de cliente no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = """
                SELECT c.id_cliente, c.id_usuario, c.nombre, c.direccion, c.ciudad, c.telefono,
                       u.usuario AS email, r.nombre_rol AS rol
                FROM clientes c
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                JOIN roles r ON u.id_rol = r.id_rol
                WHERE c.id_cliente = %s
            """
            cursor.execute(query, (id_cliente,))
            client_profile = cursor.fetchone()

            if client_profile:
                return api_response(data=client_profile, message="Perfil de cliente obtenido exitosamente.", status_code=200)
            else:
                return api_response(message="Perfil de cliente no encontrado.", status_code=404)

    except Exception as e:
        print(f"DEBUG_CLIENT_GET_BY_ID_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el perfil del cliente.", status_code=500, error=str(e))

@clientes_bp.route('/<int:id_cliente>', methods=['PUT'])
@jwt_required()
@Administrador_requerido() # Solo administradores pueden actualizar perfiles de clientes por ID
def actualizar_cliente_por_id(id_cliente):
    """
    Actualiza los detalles de un perfil de cliente existente por su ID (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_cliente
        type: integer
        required: true
        description: ID del perfil de cliente a actualizar
      - in: body
        name: body
        schema:
          $ref: '#/definitions/ActualizarPerfilCliente'
    responses:
      200:
        description: Perfil de cliente actualizado exitosamente
        schema:
          $ref: '#/definitions/PerfilCliente'
      400:
        description: No hay campos para actualizar o datos inválidos
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Cliente no encontrado
      500:
        description: Error interno del servidor
    """
    data = request.get_json()

    nombre = limpiar_string(data.get('nombre')) if data.get('nombre') is not None else None
    direccion = limpiar_string(data.get('direccion')) if data.get('direccion') is not None else None
    ciudad = limpiar_string(data.get('ciudad')) if data.get('ciudad') is not None else None
    telefono = limpiar_string(data.get('telefono')) if data.get('telefono') is not None else None
    # No permitimos actualizar id_usuario directamente desde aquí para evitar romper la relación

    update_fields = []
    update_values = []

    if nombre is not None:
        update_fields.append("nombre = %s")
        update_values.append(nombre)
    if direccion is not None:
        update_fields.append("direccion = %s")
        update_values.append(direccion)
    if ciudad is not None:
        update_fields.append("ciudad = %s")
        update_values.append(ciudad)
    if telefono is not None:
        update_fields.append("telefono = %s")
        update_values.append(telefono)

    if not update_fields:
        return api_response(message="No hay campos para actualizar.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Verificar si el perfil de cliente existe
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_cliente = %s", (id_cliente,))
            if not cursor.fetchone():
                return api_response(message="Perfil de cliente no encontrado.", status_code=404)
            
            update_query = "UPDATE clientes SET " + ", ".join(update_fields) + " WHERE id_cliente = %s"
            update_values.append(id_cliente)

            cursor.execute(update_query, tuple(update_values))

            query_updated = """
                SELECT c.id_cliente, c.id_usuario, c.nombre, c.direccion, c.ciudad, c.telefono,
                       u.usuario AS email, r.nombre_rol AS rol
                FROM clientes c
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                JOIN roles r ON u.id_rol = r.id_rol
                WHERE c.id_cliente = %s
            """
            cursor.execute(query_updated, (id_cliente,))
            updated_profile = cursor.fetchone()

            return api_response(data=updated_profile, message="Perfil de cliente actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CLIENT_ADMIN_UPDATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al actualizar el perfil del cliente.", status_code=500, error=str(e))


@clientes_bp.route('/<int:id_cliente>', methods=['DELETE'])
@jwt_required()
@Administrador_requerido() # Solo administradores pueden eliminar perfiles de clientes
def eliminar_cliente_por_id(id_cliente):
    """
    Elimina un perfil de cliente del sistema por su ID (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_cliente
        type: integer
        required: true
        description: ID del perfil de cliente a eliminar
    responses:
      200:
        description: Perfil de cliente eliminado exitosamente
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Perfil de cliente no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            # Verificar si el perfil de cliente existe
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_cliente = %s", (id_cliente,))
            if not cursor.fetchone():
                return api_response(message="Perfil de cliente no encontrado.", status_code=404)
            
            delete_query = "DELETE FROM clientes WHERE id_cliente = %s"
            cursor.execute(delete_query, (id_cliente,))

            if cursor.rowcount == 0:
                return api_response(message="Perfil de cliente no encontrado o no se pudo eliminar.", status_code=404)

            return api_response(message="Perfil de cliente eliminado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CLIENT_ADMIN_DELETE_ERROR: {e}")
        return api_response(message="Error interno del servidor al eliminar el perfil del cliente.", status_code=500, error=str(e))
