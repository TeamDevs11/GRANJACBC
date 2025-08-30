from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from utils.auth_decorators import Administrador_requerido
from utils.helpers import api_response, db_session, limpiar_string

# Define el Blueprint para pedidos
pedidos_bp = Blueprint('pedidos_bp', __name__)

# --- Rutas para la gestión de pedidos (Clientes) ---

@pedidos_bp.route('/', methods=['POST'])
@jwt_required()
def crear_pedido():
    """
    Crea un nuevo pedido para el cliente autenticado.
    Decrementa el inventario de los productos y calcula el total.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: CrearPedido
          required:
            - productos
          properties:
            productos:
              type: array
              description: Lista de productos en el pedido.
              items:
                type: object
                properties:
                  id_producto:
                    type: integer
                  cantidad:
                    type: integer
            direccion_envio:
              type: string
              description: Dirección de envío del pedido (opcional, si difiere del perfil del cliente).
            ciudad_envio:
              type: string
              description: Ciudad de envío del pedido (opcional).
            telefono_contacto:
              type: string
              description: Teléfono de contacto para el pedido (opcional).
    responses:
      201:
        description: Pedido creado exitosamente
        schema:
          id: PedidoCreado
          properties:
            id_pedido:
              type: integer
            id_cliente:
              type: integer
            fecha_pedido:
              type: string
            estado_pedido:
              type: string
            total_pedido:
              type: number
            direccion_envio:
              type: string
            ciudad_envio:
              type: string
            telefono_contacto:
              type: string
            detalles:
              type: array
              items:
                type: object
                properties:
                  id_detalle_pedido:
                    type: integer
                  id_producto:
                    type: integer
                  cantidad:
                    type: integer
                  precio_unitario:
                    type: number
                  nombre_producto:
                    type: string
      400:
        description: Datos inválidos, inventario insuficiente o perfil de cliente no encontrado
      401:
        description: No autorizado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    productos_en_pedido = data.get('productos')

    if not productos_en_pedido or not isinstance(productos_en_pedido, list):
        return api_response(message="La lista de productos es requerida.", status_code=400)

    direccion_envio = limpiar_string(data.get('direccion_envio'))
    ciudad_envio = limpiar_string(data.get('ciudad_envio'))
    telefono_contacto = limpiar_string(data.get('telefono_contacto'))

    total_pedido = 0.0
    detalles_para_insertar = []

    try:
        with db_session() as (conn, cursor):
            # 1. Obtener id_cliente del usuario actual
            cursor.execute("SELECT id_cliente, direccion, ciudad, telefono FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()

            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=400)

            id_cliente = cliente_info['id_cliente']

            # Usar la dirección del perfil del cliente si no se proporciona en el pedido
            if not direccion_envio:
                direccion_envio = cliente_info['direccion']
            if not ciudad_envio:
                ciudad_envio = cliente_info['ciudad']
            if not telefono_contacto:
                telefono_contacto = cliente_info['telefono']
            
            # Validar y calcular el total del pedido, y verificar el inventario
            for item in productos_en_pedido:
                id_producto = item.get('id_producto')
                cantidad = item.get('cantidad')

                if not id_producto or not isinstance(id_producto, int) or id_producto <= 0:
                    conn.rollback()
                    return api_response(message="ID de producto inválido en la lista de productos.", status_code=400)
                if not cantidad or not isinstance(cantidad, int) or cantidad <= 0:
                    conn.rollback()
                    return api_response(message="Cantidad inválida para el producto ID " + str(id_producto) + ".", status_code=400)

                # Obtener precio y stock del producto (con bloqueo para evitar condiciones de carrera)
                cursor.execute(
                    "SELECT p.precio_venta, i.cantidad_disponible FROM productos p JOIN inventarios i ON p.id_producto = i.id_producto WHERE p.id_producto = %s FOR UPDATE",
                    (id_producto,)
                )
                product_info = cursor.fetchone()

                if not product_info:
                    conn.rollback()
                    return api_response(message=f"Producto con ID {id_producto} no encontrado.", status_code=400)

                precio_unitario = product_info['precio_venta']
                cantidad_disponible = product_info['cantidad_disponible']

                if cantidad > cantidad_disponible:
                    conn.rollback()
                    return api_response(message=f"Inventario insuficiente para el producto '{id_producto}'. Disponible: {cantidad_disponible}, Solicitado: {cantidad}.", status_code=400)

                total_pedido += (precio_unitario * cantidad)
                detalles_para_insertar.append({
                    'id_producto': id_producto,
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'nombre_producto': product_info.get('nombre_producto', 'N/A') # para la respuesta
                })

            # 2. Insertar el nuevo pedido
            insert_pedido_query = """
                INSERT INTO pedidos (id_cliente, total_pedido, direccion_envio, ciudad_envio, telefono_contacto)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_pedido_query, (id_cliente, total_pedido, direccion_envio, ciudad_envio, telefono_contacto))
            id_pedido = cursor.lastrowid

            # 3. Insertar los detalles del pedido y actualizar el inventario
            detalles_respuesta = []
            for item_detalle in detalles_para_insertar:
                id_producto = item_detalle['id_producto']
                cantidad = item_detalle['cantidad']
                precio_unitario = item_detalle['precio_unitario']

                insert_detalle_query = """
                    INSERT INTO detalle_pedidos (id_pedido, id_producto, cantidad, precio_unitario)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_detalle_query, (id_pedido, id_producto, cantidad, precio_unitario))
                id_detalle_pedido = cursor.lastrowid

                # Actualizar inventario (ya bloqueado por FOR UPDATE)
                update_inventario_query = "UPDATE inventarios SET cantidad_disponible = cantidad_disponible - %s WHERE id_producto = %s"
                cursor.execute(update_inventario_query, (cantidad, id_producto))
                
                detalles_respuesta.append({
                    'id_detalle_pedido': id_detalle_pedido,
                    'id_producto': id_producto,
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'nombre_producto': item_detalle['nombre_producto']
                })
            
            # 4. Obtener información completa del pedido para la respuesta
            cursor.execute("SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
            pedido_creado = cursor.fetchone()

            conn.commit() # Confirmar todas las transacciones

            response_data = {**pedido_creado, 'detalles': detalles_respuesta}
            return api_response(data=response_data, message="Pedido creado exitosamente.", status_code=201)

    except pymysql.Error as db_error:
        conn.rollback() # En caso de error de DB, revertir
        print(f"DEBUG_PEDIDO_DB_ERROR: {db_error}")
        return api_response(message="Error de base de datos al crear el pedido.", status_code=500, error=str(db_error))
    except Exception as e:
        # Aquí no se necesita rollback porque db_session() lo maneja si no hay commit
        print(f"DEBUG_PEDIDO_CREATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al crear el pedido.", status_code=500, error=str(e))


@pedidos_bp.route('/me', methods=['GET'])
@jwt_required()
def obtener_mis_pedidos():
    """
    Obtiene todos los pedidos realizados por el cliente autenticado, incluyendo sus detalles.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de pedidos obtenida exitosamente
        schema:
          type: array
          items:
            $ref: '#/definitions/PedidoCreado'
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

            # Obtener pedidos principales
            cursor.execute("SELECT * FROM pedidos WHERE id_cliente = %s ORDER BY fecha_pedido DESC", (id_cliente,))
            pedidos = cursor.fetchall()

            for pedido in pedidos:
                # Obtener detalles para cada pedido
                cursor.execute(
                    """
                    SELECT dp.id_detalle_pedido, dp.id_producto, dp.cantidad, dp.precio_unitario, p.nombre AS nombre_producto
                    FROM detalle_pedidos dp
                    JOIN productos p ON dp.id_producto = p.id_producto
                    WHERE dp.id_pedido = %s
                    """,
                    (pedido['id_pedido'],)
                )
                pedido['detalles'] = cursor.fetchall()

            return api_response(data=pedidos, message="Pedidos obtenidos exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PEDIDO_GET_ME_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener tus pedidos.", status_code=500, error=str(e))

@pedidos_bp.route('/me/<int:id_pedido>', methods=['GET'])
@jwt_required()
def obtener_detalle_mi_pedido(id_pedido):
    """
    Obtiene los detalles de un pedido específico realizado por el cliente autenticado.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_pedido
        type: integer
        required: true
        description: ID del pedido a obtener.
    responses:
      200:
        description: Detalles del pedido obtenidos exitosamente
        schema:
          $ref: '#/definitions/PedidoCreado'
      400:
        description: ID de pedido inválido
      401:
        description: No autorizado
      403:
        description: No tienes permiso para ver este pedido
      404:
        description: Pedido no encontrado o no pertenece al usuario
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()

    try:
        with db_session() as (conn, cursor):
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            # Obtener el pedido y verificar que pertenezca al cliente autenticado
            cursor.execute("SELECT * FROM pedidos WHERE id_pedido = %s AND id_cliente = %s", (id_pedido, id_cliente))
            pedido = cursor.fetchone()

            if not pedido:
                return api_response(message="Pedido no encontrado o no tienes permiso para verlo.", status_code=404)

            # Obtener detalles del pedido
            cursor.execute(
                """
                SELECT dp.id_detalle_pedido, dp.id_producto, dp.cantidad, dp.precio_unitario, p.nombre AS nombre_producto
                FROM detalle_pedidos dp
                JOIN productos p ON dp.id_producto = p.id_producto
                WHERE dp.id_pedido = %s
                """,
                (id_pedido,)
            )
            pedido['detalles'] = cursor.fetchall()

            return api_response(data=pedido, message="Detalles del pedido obtenidos exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PEDIDO_GET_MY_ID_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el detalle de tu pedido.", status_code=500, error=str(e))

# --- Rutas para la gestión de pedidos (Administrador) ---

@pedidos_bp.route('/', methods=['GET'])
@jwt_required()
@Administrador_requerido()
def obtener_todos_pedidos_admin():
    """
    Obtiene una lista de todos los pedidos del sistema, incluyendo sus detalles (Solo Administrador).
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de todos los pedidos obtenida exitosamente
        schema:
          type: array
          items:
            $ref: '#/definitions/PedidoCreado'
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            cursor.execute("SELECT * FROM pedidos ORDER BY fecha_pedido DESC")
            pedidos = cursor.fetchall()

            for pedido in pedidos:
                cursor.execute(
                    """
                    SELECT dp.id_detalle_pedido, dp.id_producto, dp.cantidad, dp.precio_unitario, p.nombre AS nombre_producto
                    FROM detalle_pedidos dp
                    JOIN productos p ON dp.id_producto = p.id_producto
                    WHERE dp.id_pedido = %s
                    """,
                    (pedido['id_pedido'],)
                )
                pedido['detalles'] = cursor.fetchall()
            return api_response(data=pedidos, message="Todos los pedidos obtenidos exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PEDIDO_GET_ALL_ADMIN_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener todos los pedidos.", status_code=500, error=str(e))

@pedidos_bp.route('/<int:id_pedido>', methods=['GET'])
@jwt_required()
@Administrador_requerido()
def obtener_pedido_por_id_admin(id_pedido):
    """
    Obtiene los detalles de un pedido específico por su ID (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_pedido
        type: integer
        required: true
        description: ID del pedido a obtener.
    responses:
      200:
        description: Detalles del pedido obtenidos exitosamente
        schema:
          $ref: '#/definitions/PedidoCreado'
      400:
        description: ID de pedido inválido
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Pedido no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            cursor.execute("SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
            pedido = cursor.fetchone()

            if not pedido:
                return api_response(message="Pedido no encontrado.", status_code=404)

            cursor.execute(
                """
                SELECT dp.id_detalle_pedido, dp.id_producto, dp.cantidad, dp.precio_unitario, p.nombre AS nombre_producto
                FROM detalle_pedidos dp
                JOIN productos p ON dp.id_producto = p.id_producto
                WHERE dp.id_pedido = %s
                """,
                (id_pedido,)
            )
            pedido['detalles'] = cursor.fetchall()
            return api_response(data=pedido, message="Detalles del pedido obtenidos exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PEDIDO_GET_BY_ID_ADMIN_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el pedido.", status_code=500, error=str(e))

@pedidos_bp.route('/<int:id_pedido>', methods=['PUT'])
@jwt_required()
@Administrador_requerido()
def actualizar_estado_pedido_admin(id_pedido):
    """
    Actualiza el estado de un pedido específico (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_pedido
        type: integer
        required: true
        description: ID del pedido a actualizar.
      - in: body
        name: body
        schema:
          id: ActualizarEstadoPedido
          required:
            - estado_pedido
          properties:
            estado_pedido:
              type: string
              description: Nuevo estado del pedido (ej. 'Pendiente', 'En proceso', 'Completado', 'Cancelado').
    responses:
      200:
        description: Estado del pedido actualizado exitosamente
        schema:
          $ref: '#/definitions/PedidoCreado'
      400:
        description: Estado de pedido inválido o no hay campos para actualizar
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Pedido no encontrado
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    estado_pedido = limpiar_string(data.get('estado_pedido'))

    if not estado_pedido:
        return api_response(message="El campo 'estado_pedido' es requerido para actualizar.", status_code=400)
    
    # Opcional: Validar que el estado sea uno de los permitidos
    estados_validos = ['Pendiente', 'En proceso', 'Completado', 'Cancelado']
    if estado_pedido not in estados_validos:
        return api_response(message=f"Estado de pedido inválido. Los estados permitidos son: {', '.join(estados_validos)}", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Verificar si el pedido existe
            cursor.execute("SELECT id_pedido FROM pedidos WHERE id_pedido = %s", (id_pedido,))
            if not cursor.fetchone():
                return api_response(message="Pedido no encontrado.", status_code=404)
            
            update_query = "UPDATE pedidos SET estado_pedido = %s WHERE id_pedido = %s"
            cursor.execute(update_query, (estado_pedido, id_pedido))

            # Obtener el pedido actualizado para devolverlo
            cursor.execute("SELECT * FROM pedidos WHERE id_pedido = %s", (id_pedido,))
            updated_pedido = cursor.fetchone()

            # Obtener detalles del pedido para la respuesta completa
            cursor.execute(
                """
                SELECT dp.id_detalle_pedido, dp.id_producto, dp.cantidad, dp.precio_unitario, p.nombre AS nombre_producto
                FROM detalle_pedidos dp
                JOIN productos p ON dp.id_producto = p.id_producto
                WHERE dp.id_pedido = %s
                """,
                (id_pedido,)
            )
            updated_pedido['detalles'] = cursor.fetchall()

            return api_response(data=updated_pedido, message="Estado del pedido actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PEDIDO_UPDATE_ADMIN_ERROR: {e}")
        return api_response(message="Error interno del servidor al actualizar el estado del pedido.", status_code=500, error=str(e))

@pedidos_bp.route('/<int:id_pedido>', methods=['DELETE'])
@jwt_required()
@Administrador_requerido()
def eliminar_pedido_admin(id_pedido):
    """
    Elimina un pedido del sistema, incluyendo sus detalles (Solo Administrador).
    Importante: Esto es solo para casos específicos como testing.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_pedido
        type: integer
        required: true
        description: ID del pedido a eliminar.
    responses:
      200:
        description: Pedido eliminado exitosamente
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Pedido no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            # Verificar si el pedido existe
            cursor.execute("SELECT id_pedido FROM pedidos WHERE id_pedido = %s", (id_pedido,))
            if not cursor.fetchone():
                return api_response(message="Pedido no encontrado.", status_code=404)
            
            # La eliminación en cascada en `detalle_pedidos` se encargará de los detalles
            delete_query = "DELETE FROM pedidos WHERE id_pedido = %s"
            cursor.execute(delete_query, (id_pedido,))

            return api_response(message="Pedido eliminado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PEDIDO_DELETE_ADMIN_ERROR: {e}")
        return api_response(message="Error interno del servidor al eliminar el pedido.", status_code=500, error=str(e))
