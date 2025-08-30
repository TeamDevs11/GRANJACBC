from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db  # Asegurate de que esto esta bien configurado
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from utils.auth_decorators import Administrador_requerido
from utils.helpers import api_response, db_session, limpiar_string

# Define el Blueprint para resenas de productos
resenas_bp = Blueprint('resenas_bp', __name__)

# --- Rutas para la gestion de resenas (Clientes) ---

@resenas_bp.route('/', methods=['POST'])
@jwt_required()
def crear_resena():
    """
    Crea una nueva resena para un producto por parte del cliente autenticado.
    La resena se crea como 'no aprobada' por defecto (aprobada=0).
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: CrearResena
          required:
            - id_producto
            - calificacion
          properties:
            id_producto:
              type: integer
              description: ID del producto que se esta resenando.
            calificacion:
              type: integer
              description: Calificacion del producto (1 a 5).
            comentario:
              type: string
              description: Comentario opcional sobre el producto.
    responses:
      201:
        description: Resena creada exitosamente
        schema:
          id: ResenaCreada
          properties:
            id_resena:
              type: integer
            id_producto:
              type: integer
            id_cliente:
              type: integer
            calificacion:
              type: integer
            comentario:
              type: string
            fecha_resena:
              type: string
            aprobada:
              type: integer # 0 o 1
      400:
        description: Datos invalidos, producto no encontrado o calificacion fuera de rango.
      401:
        description: No autorizado
      404:
        description: Perfil de cliente no encontrado
      409:
        description: El cliente ya ha resenado este producto (se puede implementar o permitir multiples)
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()

    id_producto = data.get('id_producto')
    calificacion = data.get('calificacion')
    comentario = limpiar_string(data.get('comentario'))

    if not all([id_producto, calificacion is not None]):
        return api_response(message="ID de producto y calificacion son requeridos.", status_code=400)
    
    if not isinstance(id_producto, int) or id_producto <= 0:
        return api_response(message="ID de producto invalido.", status_code=400)
    
    if not isinstance(calificacion, int) or not (1 <= calificacion <= 5):
        return api_response(message="Calificacion invalida. Debe ser un numero entero entre 1 y 5.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Obtener id_cliente del usuario actual
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            # 2. Verificar si el producto existe
            cursor.execute("SELECT id_producto FROM productos WHERE id_producto = %s", (id_producto,))
            if not cursor.fetchone():
                return api_response(message=f"Producto con ID {id_producto} no encontrado.", status_code=400)
            
            # Opcional: Verificar si el cliente ya ha resenado este producto (para evitar duplicados)
            cursor.execute("SELECT id_resena FROM resenas_productos WHERE id_producto = %s AND id_cliente = %s", (id_producto, id_cliente))
            if cursor.fetchone():
                return api_response(message="Ya has resenado este producto.", status_code=409)

            # 3. Insertar la resena 
            insert_resena_query = """
                INSERT INTO resenas_productos (id_producto, id_cliente, calificacion, comentario, aprobada)
                VALUES (%s, %s, %s, %s, 0)
            """
            cursor.execute(insert_resena_query, (id_producto, id_cliente, calificacion, comentario))
            id_resena = cursor.lastrowid
            conn.commit()

            # 4. Obtener la resena recien creada para la respuesta
            cursor.execute("SELECT id_resena, id_producto, id_cliente, calificacion, comentario, fecha_resena, aprobada FROM resenas_productos WHERE id_resena = %s", (id_resena,))
            resena_creada = cursor.fetchone()
            
            return api_response(data=resena_creada, message="Resena creada exitosamente. Pendiente de aprobacion.", status_code=201)

    except pymysql.Error as db_error:
        conn.rollback()
        print(f"DEBUG_RESENA_DB_ERROR: {db_error}")
        return api_response(message="Error de base de datos al crear la resena.", status_code=500, error=str(db_error))
    except Exception as e:
        print(f"DEBUG_RESENA_CREATE_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al crear la resena.", status_code=500, error=str(e))

@resenas_bp.route('/producto/<int:id_producto>', methods=['GET'])
def obtener_resenas_por_producto(id_producto):  # Aquí se espera 'id_producto' como argumento
    """
    Obtiene todas las resenas APROBADAS para un producto especifico.
    ---
    parameters:
      - in: path
        name: id_producto
        type: integer
        required: true
        description: ID del producto cuyas resenas se desean obtener.
    responses:
      200:
        description: Resenas obtenidas exitosamente
        schema:
          type: array
          items:
            $ref: '#/definitions/ResenaCreada'
      404:
        description: Producto no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            # Verificar si el producto existe
            cursor.execute("SELECT id_producto FROM productos WHERE id_producto = %s", (id_producto,))
            if not cursor.fetchone():
                return api_response(message=f"Producto con ID {id_producto} no encontrado.", status_code=404)

            # Seleccionar solo resenas aprobadas (aprobada = 1)
            query = """
                SELECT rp.id_resena, rp.id_producto, rp.calificacion, rp.comentario, rp.fecha_resena, rp.aprobada,
                       c.nombre AS nombre_cliente, u.usuario AS username_cliente
                FROM resenas_productos rp
                JOIN clientes c ON rp.id_cliente = c.id_cliente
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                WHERE rp.id_producto = %s AND rp.aprobada = 1
                ORDER BY rp.fecha_resena DESC
            """
            cursor.execute(query, (id_producto,))
            resenas = cursor.fetchall()
            return api_response(data=resenas, message="Resenas obtenidas exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_RESENA_GET_BY_PRODUCT_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener las resenas del producto.", status_code=500, error=str(e))

@resenas_bp.route('/my_reviews', methods=['GET'])
@jwt_required()
def obtener_mis_resenas():
    """
    Obtiene todas las reseas realizadas por el cliente autenticado.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Resenas obtenidas exitosamente
        schema:
          type: array
          items:
            $ref: '#/definitions/ResenaCreada'
      401:
        description: No autorizado
      404:
        description: Perfil de cliente no encontrado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()

    try:
        with db_session() as (conn, cursor):
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            query = """
                SELECT rp.id_resena, rp.id_producto, rp.calificacion, rp.comentario, rp.fecha_resena, rp.aprobada,
                       p.nombre AS nombre_producto, c.nombre AS nombre_cliente, u.usuario AS username_cliente
                FROM resenas_productos rp
                JOIN productos p ON rp.id_producto = p.id_producto
                JOIN clientes c ON rp.id_cliente = c.id_cliente
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                WHERE rp.id_cliente = %s
                ORDER BY rp.fecha_resena DESC
            """
            cursor.execute(query, (id_cliente,))
            resenas = cursor.fetchall()
            return api_response(data=resenas, message="Tus resenas obtenidas exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_RESENA_GET_ME_ALL_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener tus resenas.", status_code=500, error=str(e))

@resenas_bp.route('/my_reviews/<int:id_resena>', methods=['PUT'])
@jwt_required()
def actualizar_mi_resena(id_resena):
    """
    Actualiza una resena especifica realizada por el cliente autenticado.
    (Solo puede actualizar calificacion y comentario, no su estado de aprobacion).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_resena
        type: integer
        required: true
        description: ID de la resena a actualizar.
      - in: body
        name: body
        schema:
          id: ActualizarResena
          properties:
            calificacion:
              type: integer
              description: Nueva calificacion (1 a 5).
            comentario:
              type: string
              description: Nuevo comentario opcional.
    responses:
      200:
        description: Resena actualizada exitosamente
        schema:
          $ref: '#/definitions/ResenaCreada'
      400:
        description: Datos invalidos, calificacion fuera de rango o ningun campo para actualizar.
      401:
        description: No autorizado
      403:
        description: Acceso denegado (la resena no pertenece al usuario)
      404:
        description: Resena no encontrada
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()

    calificacion = data.get('calificacion')
    comentario = limpiar_string(data.get('comentario'))

    if calificacion is not None and (not isinstance(calificacion, int) or not (1 <= calificacion <= 5)):
        return api_response(message="Calificacion invalida. Debe ser un numero entero entre 1 y 5.", status_code=400)
    
    if calificacion is None and comentario is None:
        return api_response(message="Al menos la calificacion o el comentario deben ser proporcionados para actualizar.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Obtener id_cliente del usuario actual
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            # 2. Verificar que la resena existe y pertenece al cliente autenticado
            cursor.execute("SELECT id_resena FROM resenas_productos WHERE id_resena = %s AND id_cliente = %s", (id_resena, id_cliente))
            if not cursor.fetchone():
                return api_response(message="Resena no encontrada o no tienes permiso para actualizarla.", status_code=404)
            
            # 3. Construir la consulta de actualizacion dinamicamente
            update_fields = []
            update_values = []

            if calificacion is not None:
                update_fields.append("calificacion = %s")
                update_values.append(calificacion)
            if comentario is not None:
                update_fields.append("comentario = %s")
                update_values.append(comentario)
            
            if not update_fields:
                return api_response(message="No hay campos validos para actualizar.", status_code=400)

            update_query = f"UPDATE resenas_productos SET {', '.join(update_fields)} WHERE id_resena = %s"
            update_values.append(id_resena)

            cursor.execute(update_query, tuple(update_values))
            conn.commit()

            # 4. Obtener la resena actualizada para la respuesta
            cursor.execute("SELECT id_resena, id_producto, id_cliente, calificacion, comentario, fecha_resena, aprobada FROM resenas_productos WHERE id_resena = %s", (id_resena,))
            updated_resena = cursor.fetchone()

            return api_response(data=updated_resena, message="Resena actualizada exitosamente.", status_code=200)

    except pymysql.Error as db_error:
        conn.rollback()
        print(f"DEBUG_RESENA_UPDATE_DB_ERROR: {db_error}")
        return api_response(message="Error de base de datos al actualizar la resena.", status_code=500, error=str(db_error))
    except Exception as e:
        print(f"DEBUG_RESENA_UPDATE_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al actualizar la resena.", status_code=500, error=str(e))

@resenas_bp.route('/my_reviews/<int:id_resena>', methods=['DELETE'])
@jwt_required()
def eliminar_mi_resena(id_resena):
    """
    Elimina una resena especifica realizada por el cliente autenticado.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_resena
        type: integer
        required: true
        description: ID de la resena a eliminar.
    responses:
      200:
        description: Resena eliminada exitosamente
      401:
        description: No autorizado
      403:
        description: Acceso denegado (la resena no pertenece al usuario)
      404:
        description: Resena no encontrada
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()

    try:
        with db_session() as (conn, cursor):
            # 1. Obtener id_cliente del usuario actual
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            # 2. Verificar que la resena existe y pertenece al cliente autenticado
            cursor.execute("SELECT id_resena FROM resenas_productos WHERE id_resena = %s AND id_cliente = %s", (id_resena, id_cliente))
            if not cursor.fetchone():
                return api_response(message="Resena no encontrada o no tienes permiso para eliminarla.", status_code=404)
            
            # 3. Eliminar la resena
            delete_query = "DELETE FROM resenas_productos WHERE id_resena = %s"
            cursor.execute(delete_query, (id_resena,))
            conn.commit()

            return api_response(message="Resena eliminada exitosamente.", status_code=200)

    except pymysql.Error as db_error:
        conn.rollback()
        print(f"DEBUG_RESENA_DELETE_DB_ERROR: {db_error}")
        return api_response(message="Error de base de datos al eliminar la resena.", status_code=500, error=str(db_error))
    except Exception as e:
        print(f"DEBUG_RESENA_DELETE_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al eliminar la resena.", status_code=500, error=str(e))


# --- Rutas para la gestion de resenas (Administrador) ---

@resenas_bp.route('/admin', methods=['GET'])
@jwt_required()
@Administrador_requerido()
def obtener_resenas():
    """
    Obtiene una lista de todas las resenas de productos en el sistema (Solo Administrador).
    Incluye resenas aprobadas y no aprobadas.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de resenas obtenida exitosamente
        schema:
          type: array
          items:
            $ref: '#/definitions/ResenaCreada'
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = """
                SELECT rp.id_resena, rp.id_producto, rp.calificacion, rp.comentario, rp.fecha_resena, rp.aprobada,
                       p.nombre AS nombre_producto, c.nombre AS nombre_cliente, u.usuario AS username_cliente
                FROM resenas_productos rp
                JOIN productos p ON rp.id_producto = p.id_producto
                JOIN clientes c ON rp.id_cliente = c.id_cliente
                JOIN usuarios u ON c.id_usuario = u.id_usuario
                ORDER BY rp.fecha_resena DESC
            """
            cursor.execute(query)
            resenas = cursor.fetchall()
            return api_response(data=resenas, message="Lista de todas las resenas obtenida exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_RESENA_GET_ALL_ADMIN_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener todas las resenas.", status_code=500, error=str(e))

@resenas_bp.route('/admin/<int:id_resena>/aprobar', methods=['PUT'])
@jwt_required()
@Administrador_requerido()
def aprobar_resena(id_resena):
    """
    Aprueba una resena especifica para que sea visible publicamente (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_resena
        type: integer
        required: true
        description: ID de la resena a aprobar.
      - in: body
        name: body
        schema:
          id: AprobarResena
          required:
            - aprobada
          properties:
            aprobada:
              type: integer
              description: 1 para aprobar, 0 para desaprobar.
    responses:
      200:
        description: Estado de aprobacion de la resena actualizado exitosamente
        schema:
          $ref: '#/definitions/ResenaCreada'
      400:
        description: Valor de aprobacion invalido
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Resena no encontrada
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    estado_aprobacion = data.get('aprobada')

    if estado_aprobacion is None or not isinstance(estado_aprobacion, int) or estado_aprobacion not in [0, 1]:
        return api_response(message="El valor de 'aprobada' debe ser 0 o 1.", status_code=400)
    
    try:
        with db_session() as (conn, cursor):
            # 1. Verificar si la resena existe
            cursor.execute("SELECT id_resena FROM resenas_productos WHERE id_resena = %s", (id_resena,))
            if not cursor.fetchone():
                return api_response(message="Resena no encontrada.", status_code=404)
            
            update_query = "UPDATE resenas_productos SET aprobada = %s WHERE id_resena = %s"
            cursor.execute(update_query, (estado_aprobacion, id_resena))
            conn.commit()

            # Obtener la resena actualizada para la respuesta
            cursor.execute("SELECT id_resena, id_producto, id_cliente, calificacion, comentario, fecha_resena, aprobada FROM resenas_productos WHERE id_resena = %s", (id_resena,))
            updated_resena = cursor.fetchone()

            return api_response(data=updated_resena, message="Estado de aprobacion de la resena actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_RESENA_APROBAR_ADMIN_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al actualizar el estado de aprobacion de la resena.", status_code=500, error=str(e))

@resenas_bp.route('/admin/<int:id_resena>', methods=['DELETE'])
@jwt_required()
@Administrador_requerido()
def eliminar_resena(id_resena):
    """
    Elimina una resena especifica por su ID (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_resena
        type: integer
        required: true
        description: ID de la resena a eliminar.
    responses:
      200:
        description: Resena eliminada exitosamente
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Resena no encontrada
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            # Verificar si la resena existe
            cursor.execute("SELECT id_resena FROM resenas_productos WHERE id_resena = %s", (id_resena,))
            if not cursor.fetchone():
                return api_response(message="Resena no encontrada.", status_code=404)
            
            delete_query = "DELETE FROM resenas_productos WHERE id_resena = %s"
            cursor.execute(delete_query, (id_resena,))
            conn.commit()

            return api_response(message="Resena eliminada exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_RESENA_DELETE_ADMIN_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al eliminar la resena.", status_code=500, error=str(e))

definitions = {
    "CrearResena": {
        "type": "object",
        "properties": {
            "id_producto": {"type": "integer"},
            "calificacion": {"type": "integer"},
            "comentario": {"type": "string"}
        },
        "required": ["id_producto", "calificacion"]
    },
    "ResenaCreada": {
        "type": "object",
        "properties": {
            "id_resena": {"type": "integer"},
            "id_producto": {"type": "integer"},
            "id_cliente": {"type": "integer"},
            "calificacion": {"type": "integer"},
            "comentario": {"type": "string"},
            "fecha_resena": {"type": "string"},
            "aprobada": {"type": "integer"}
        }
    }
}
