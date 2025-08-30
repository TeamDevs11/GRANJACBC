from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.auth_decorators import Administrador_requerido # Solo el administrador para listar todos los carritos
from utils.helpers import api_response, db_session, limpiar_string

# Define el Blueprint para el carrito de compras
carrito_bp = Blueprint('carrito_bp', __name__)

# --- Rutas para la gestión del carrito de compras del cliente autenticado ---

@carrito_bp.route('/', methods=['POST'])
@jwt_required() # Requiere un token JWT válido para añadir al carrito
def agregar_producto_al_carrito():
    """
    Agrega un producto al carrito de compras del cliente autenticado.
    Si el producto ya está en el carrito, actualiza la cantidad.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: AgregarAlCarrito
          required:
            - id_producto
            - cantidad
          properties:
            id_producto:
              type: integer
              description: ID del producto a agregar.
            cantidad:
              type: integer
              description: Cantidad del producto a agregar.
    responses:
      201:
        description: Producto agregado/actualizado en el carrito exitosamente
        schema:
          id: ItemCarrito
          properties:
            id_item_carrito:
              type: integer
            id_cliente:
              type: integer
            id_producto:
              type: integer
            cantidad:
              type: integer
            fecha_agregado:
              type: string
            nombre_producto:
              type: string
            precio_unitario:
              type: number
            stock_disponible:
              type: integer
      400:
        description: Datos inválidos, inventario insuficiente o perfil de cliente no encontrado
      401:
        description: No autorizado
      404:
        description: Producto no encontrado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()

    id_producto = data.get('id_producto')
    cantidad = data.get('cantidad')

    if not all([id_producto, cantidad]):
        return api_response(message="El ID del producto y la cantidad son requeridos.", status_code=400)
    
    if not isinstance(id_producto, int) or id_producto <= 0:
        return api_response(message="ID de producto inválido.", status_code=400)
    if not isinstance(cantidad, int) or cantidad <= 0:
        return api_response(message="La cantidad debe ser un número entero positivo.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Obtener id_cliente del usuario actual
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=400)
            id_cliente = cliente_info['id_cliente']

            # 2. Verificar el stock disponible del producto
            cursor.execute(
                """
                SELECT p.nombre_producto, p.precio, i.cantidad_disponible 
                FROM productos p
                JOIN inventarios i ON p.id_producto = i.id_producto
                WHERE p.id_producto = %s
                """,
                (id_producto,)
            )
            product_info = cursor.fetchone()

            if not product_info:
                return api_response(message="Producto no encontrado.", status_code=404)
            
            nombre_producto = product_info['nombre_producto']
            precio_unitario = product_info['precio']
            stock_disponible = product_info['cantidad_disponible']

            if cantidad > stock_disponible:
                return api_response(message=f"Inventario insuficiente para '{nombre_producto}'. Disponible: {stock_disponible}, Solicitado: {cantidad}.", status_code=400)

            # 3. Verificar si el producto ya está en el carrito del cliente
            cursor.execute(
                "SELECT id_item_carrito, cantidad FROM carrito WHERE id_cliente = %s AND id_producto = %s",
                (id_cliente, id_producto)
            )
            item_existente = cursor.fetchone()

            if item_existente:
                # Si existe, actualizar la cantidad
                nueva_cantidad = item_existente['cantidad'] + cantidad
                if nueva_cantidad > stock_disponible:
                     return api_response(message=f"No se puede agregar más. Excede el stock disponible para '{nombre_producto}'.", status_code=400)
                
                update_query = "UPDATE carrito SET cantidad = %s WHERE id_item_carrito = %s"
                cursor.execute(update_query, (nueva_cantidad, item_existente['id_item_carrito']))
                item_id = item_existente['id_item_carrito']
                message = "Cantidad del producto actualizada en el carrito."
            else:
                # Si no existe, insertar nuevo ítem en el carrito
                insert_query = """
                    INSERT INTO carrito (id_cliente, id_producto, cantidad)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(insert_query, (id_cliente, id_producto, cantidad))
                item_id = cursor.lastrowid
                message = "Producto agregado al carrito exitosamente."
            
            # Obtener el ítem del carrito (con info de producto) para la respuesta
            cursor.execute(
                """
                SELECT c.id_item_carrito, c.id_cliente, c.id_producto, c.cantidad, c.fecha_agregado,
                       p.nombre_producto, p.precio AS precio_unitario, i.cantidad_disponible AS stock_disponible
                FROM carrito c
                JOIN productos p ON c.id_producto = p.id_producto
                JOIN inventarios i ON p.id_producto = i.id_producto
                WHERE c.id_item_carrito = %s
                """,
                (item_id,)
            )
            carrito_item_data = cursor.fetchone()
            conn.commit()
            
            return api_response(data=carrito_item_data, message=message, status_code=201)

    except Exception as e:
        print(f"DEBUG_CARRITO_AGREGAR_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al agregar producto al carrito.", status_code=500, error=str(e))

@carrito_bp.route('/', methods=['GET'])
@jwt_required()
def obtener_mi_carrito():
    """
    Obtiene todos los productos en el carrito del cliente autenticado.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Contenido del carrito obtenido exitosamente
        schema:
          type: object
          properties:
            id_cliente:
              type: integer
            items:
              type: array
              items:
                $ref: '#/definitions/ItemCarrito'
            total_carrito:
              type: number
      401:
        description: No autorizado
      404:
        description: Perfil de cliente no encontrado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    total_carrito = 0.0

    try:
        with db_session() as (conn, cursor):
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            query = """
                SELECT c.id_item_carrito, c.id_producto, c.cantidad, c.fecha_agregado,
                       p.nombre_producto, p.precio AS precio_unitario, i.cantidad_disponible AS stock_disponible
                FROM carrito c
                JOIN productos p ON c.id_producto = p.id_producto
                JOIN inventarios i ON p.id_producto = i.id_producto
                WHERE c.id_cliente = %s
            """
            cursor.execute(query, (id_cliente,))
            items_carrito = cursor.fetchall()

            for item in items_carrito:
                item['subtotal'] = item['cantidad'] * item['precio_unitario']
                total_carrito += item['subtotal']
            
            response_data = {
                "id_cliente": id_cliente,
                "items": items_carrito,
                "total_carrito": total_carrito
            }

            return api_response(data=response_data, message="Contenido del carrito obtenido exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CARRITO_GET_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el carrito.", status_code=500, error=str(e))

@carrito_bp.route('/<int:id_producto>', methods=['PUT'])
@jwt_required()
def actualizar_cantidad_producto_en_carrito(id_producto):
    """
    Actualiza la cantidad de un producto específico en el carrito del cliente autenticado.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_producto
        type: integer
        required: true
        description: ID del producto cuya cantidad se actualizará en el carrito.
      - in: body
        name: body
        schema:
          id: ActualizarCantidadCarrito
          required:
            - cantidad
          properties:
            cantidad:
              type: integer
              description: Nueva cantidad deseada del producto en el carrito.
    responses:
      200:
        description: Cantidad del producto en el carrito actualizada exitosamente
        schema:
          $ref: '#/definitions/ItemCarrito'
      400:
        description: Datos inválidos, inventario insuficiente o perfil de cliente/producto no encontrado
      401:
        description: No autorizado
      403:
        description: El producto no está en tu carrito
      404:
        description: Ítem de carrito o producto no encontrado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    nueva_cantidad = data.get('cantidad')

    if nueva_cantidad is None or not isinstance(nueva_cantidad, int) or nueva_cantidad < 0:
        return api_response(message="La cantidad debe ser un número entero no negativo.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Obtener id_cliente del usuario actual
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            # 2. Verificar que el ítem exista en el carrito de ESTE cliente
            cursor.execute(
                "SELECT id_item_carrito, cantidad FROM carrito WHERE id_cliente = %s AND id_producto = %s",
                (id_cliente, id_producto)
            )
            item_carrito = cursor.fetchone()

            if not item_carrito:
                return api_response(message="Producto no encontrado en tu carrito.", status_code=404)
            
            id_item_carrito = item_carrito['id_item_carrito']

            if nueva_cantidad == 0:
                # Si la nueva cantidad es 0, eliminamos el producto del carrito
                cursor.execute("DELETE FROM carrito WHERE id_item_carrito = %s", (id_item_carrito,))
                conn.commit()
                return api_response(message="Producto eliminado del carrito exitosamente.", status_code=200)

            # 3. Verificar stock disponible si la cantidad es > 0
            cursor.execute(
                """
                SELECT p.nombre_producto, i.cantidad_disponible 
                FROM productos p
                JOIN inventarios i ON p.id_producto = i.id_producto
                WHERE p.id_producto = %s
                """,
                (id_producto,)
            )
            product_info = cursor.fetchone()
            stock_disponible = product_info['cantidad_disponible']

            if nueva_cantidad > stock_disponible:
                return api_response(message=f"No se puede actualizar. Excede el stock disponible para '{product_info['nombre_producto']}'.", status_code=400)

            # 4. Actualizar la cantidad en el carrito
            update_query = "UPDATE carrito SET cantidad = %s WHERE id_item_carrito = %s"
            cursor.execute(update_query, (nueva_cantidad, id_item_carrito))
            conn.commit()

            # Obtener el ítem del carrito actualizado para la respuesta
            cursor.execute(
                """
                SELECT c.id_item_carrito, c.id_cliente, c.id_producto, c.cantidad, c.fecha_agregado,
                       p.nombre_producto, p.precio AS precio_unitario, i.cantidad_disponible AS stock_disponible
                FROM carrito c
                JOIN productos p ON c.id_producto = p.id_producto
                JOIN inventarios i ON p.id_producto = i.id_producto
                WHERE c.id_item_carrito = %s
                """,
                (id_item_carrito,)
            )
            carrito_item_data = cursor.fetchone()

            return api_response(data=carrito_item_data, message="Cantidad del producto en el carrito actualizada exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CARRITO_ACTUALIZAR_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al actualizar el carrito.", status_code=500, error=str(e))

@carrito_bp.route('/<int:id_producto>', methods=['DELETE'])
@jwt_required()
def eliminar_producto_del_carrito(id_producto):
    """
    Elimina un producto específico del carrito del cliente autenticado.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_producto
        type: integer
        required: true
        description: ID del producto a eliminar del carrito.
    responses:
      200:
        description: Producto eliminado del carrito exitosamente
      401:
        description: No autorizado
      403:
        description: El producto no está en tu carrito
      404:
        description: Ítem de carrito o producto no encontrado en el carrito del cliente
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
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            # 2. Verificar que el ítem exista en el carrito de ESTE cliente
            delete_query = "DELETE FROM carrito WHERE id_cliente = %s AND id_producto = %s"
            cursor.execute(delete_query, (id_cliente, id_producto))
            conn.commit()

            if cursor.rowcount == 0:
                return api_response(message="Producto no encontrado en tu carrito.", status_code=404)

            return api_response(message="Producto eliminado del carrito exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CARRITO_ELIMINAR_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al eliminar producto del carrito.", status_code=500, error=str(e))

@carrito_bp.route('/vaciar', methods=['DELETE'])
@jwt_required()
def vaciar_mi_carrito():
    """
    Vacía completamente el carrito de compras del cliente autenticado.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Carrito vaciado exitosamente
      401:
        description: No autorizado
      404:
        description: Perfil de cliente no encontrado o carrito ya vacío
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
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            delete_query = "DELETE FROM carrito WHERE id_cliente = %s"
            cursor.execute(delete_query, (id_cliente,))
            conn.commit()

            if cursor.rowcount == 0:
                return api_response(message="Tu carrito ya estaba vacío.", status_code=200)

            return api_response(message="Carrito vaciado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CARRITO_VACIAR_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al vaciar el carrito.", status_code=500, error=str(e))


# --- Rutas para la gestión de carritos (Administrador) ---
# Un administrador podría necesitar ver los carritos de todos los clientes o carritos específicos.

@carrito_bp.route('/admin', methods=['GET'])
@jwt_required()
@Administrador_requerido()
def obtener_todos_los_carritos_admin():
    """
    Obtiene todos los carritos de compras de todos los clientes (Solo Administrador).
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de carritos obtenida exitosamente
        schema:
          type: array
          items:
            type: object
            properties:
              id_cliente:
                type: integer
              nombre_cliente:
                type: string
              email_cliente:
                type: string
              items:
                type: array
                items:
                  $ref: '#/definitions/ItemCarrito'
    """
    try:
        with db_session() as (conn, cursor):
            # Obtener todos los clientes que tienen un carrito
            cursor.execute(
                """
                SELECT DISTINCT c.id_cliente, cl.nombre AS nombre_cliente, u.usuario AS email_cliente
                FROM carrito c
                JOIN clientes cl ON c.id_cliente = cl.id_cliente
                JOIN usuarios u ON cl.id_usuario = u.id_usuario
                """
            )
            clientes_con_carrito = cursor.fetchall()
            
            all_carritos = []
            for cliente in clientes_con_carrito:
                # Obtener los ítems del carrito para cada cliente
                query_items = """
                    SELECT car.id_item_carrito, car.id_producto, car.cantidad, car.fecha_agregado,
                           p.nombre_producto, p.precio AS precio_unitario, i.cantidad_disponible AS stock_disponible
                    FROM carrito car
                    JOIN productos p ON car.id_producto = p.id_producto
                    JOIN inventarios i ON p.id_producto = i.id_producto
                    WHERE car.id_cliente = %s
                """
                cursor.execute(query_items, (cliente['id_cliente'],))
                cliente['items'] = cursor.fetchall()
                all_carritos.append(cliente)

            return api_response(data=all_carritos, message="Carritos de todos los clientes obtenidos exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CARRITO_ADMIN_GET_ALL_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener todos los carritos.", status_code=500, error=str(e))

@carrito_bp.route('/admin/<int:id_cliente>', methods=['GET'])
@jwt_required()
@Administrador_requerido()
def obtener_carrito_de_cliente_admin(id_cliente):
    """
    Obtiene el carrito de compras de un cliente específico por su ID (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_cliente
        type: integer
        required: true
        description: ID del cliente cuyo carrito se desea obtener.
    responses:
      200:
        description: Carrito del cliente obtenido exitosamente
        schema:
          type: object
          properties:
            id_cliente:
              type: integer
            nombre_cliente:
              type: string
            email_cliente:
              type: string
            items:
              type: array
              items:
                $ref: '#/definitions/ItemCarrito'
            total_carrito:
              type: number
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Cliente o su carrito no encontrado
    """
    try:
        with db_session() as (conn, cursor):
            # Verificar si el cliente existe
            cursor.execute(
                "SELECT cl.nombre AS nombre_cliente, u.usuario AS email_cliente FROM clientes cl JOIN usuarios u ON cl.id_usuario = u.id_usuario WHERE cl.id_cliente = %s",
                (id_cliente,)
            )
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Cliente no encontrado.", status_code=404)

            query = """
                SELECT car.id_item_carrito, car.id_producto, car.cantidad, car.fecha_agregado,
                       p.nombre_producto, p.precio AS precio_unitario, i.cantidad_disponible AS stock_disponible
                FROM carrito car
                JOIN productos p ON car.id_producto = p.id_producto
                JOIN inventarios i ON p.id_producto = i.id_producto
                WHERE car.id_cliente = %s
            """
            cursor.execute(query, (id_cliente,))
            items_carrito = cursor.fetchall()
            
            total_carrito = sum(item['cantidad'] * item['precio_unitario'] for item in items_carrito)

            response_data = {
                "id_cliente": id_cliente,
                "nombre_cliente": cliente_info['nombre_cliente'],
                "email_cliente": cliente_info['email_cliente'],
                "items": items_carrito,
                "total_carrito": total_carrito
            }

            return api_response(data=response_data, message=f"Carrito del cliente {id_cliente} obtenido exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CARRITO_ADMIN_GET_BY_ID_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el carrito del cliente.", status_code=500, error=str(e))
