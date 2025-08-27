from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required 
from utils.auth_decorators import admin_required, admin_or_employee_required 
from utils.helpers import api_response, db_session, limpiar_string

# Define el Blueprint para productos
productos_bp = Blueprint('productos_bp', __name__)

# --- Rutas para la gestión de productos ---

@productos_bp.route('/', methods=['POST'])
@jwt_required()
@admin_or_employee_required() # administradores Y empleados pueden crear productos
def crear_producto():
    """
    Crea un nuevo producto en el sistema.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: NuevoProducto
          required:
            - nombre_producto
            - precio
            - stock
          properties:
            nombre_producto:
              type: string
              description: Nombre del producto
            descripcion:
              type: string
              description: Descripción del producto (opcional)
            precio:
              type: number
              format: float
              description: Precio del producto
            stock:
              type: integer
              description: Cantidad en stock
            # Puedes añadir más campos aquí como id_categoria, imagen_url, etc.
    responses:
      201:
        description: Producto creado exitosamente
        schema:
          id: Producto
          properties:
            id_producto:
              type: integer
            nombre_producto:
              type: string
            descripcion:
              type: string
            precio:
              type: number
              format: float
            stock:
              type: integer
      400:
        description: Error de validación o campos requeridos
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Admin ni Empleado)
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    nombre_producto = limpiar_string(data.get('nombre_producto'))
    descripcion = limpiar_string(data.get('descripcion')) if data.get('descripcion') else None
    precio = data.get('precio')
    stock = data.get('stock')

    if not all([nombre_producto, precio is not None, stock is not None]):
        return api_response(message="Nombre del producto, precio y stock son campos requeridos.", status_code=400)

    # Validaciones adicionales
    if not isinstance(precio, (int, float)) or precio <= 0:
        return api_response(message="El precio debe ser un número positivo.", status_code=400)
    if not isinstance(stock, int) or stock < 0:
        return api_response(message="El stock debe ser un número entero no negativo.", status_code=400)
    
    try:
        with db_session() as (conn, cursor):
            # Verificar si ya existe un producto con el mismo nombre
            check_query = "SELECT id_producto FROM productos WHERE nombre_producto = %s"
            cursor.execute(check_query, (nombre_producto,))
            if cursor.fetchone():
                return api_response(message="Ya existe un producto con ese nombre.", status_code=400)

            insert_query = """
                INSERT INTO productos (nombre_producto, descripcion, precio, stock)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(insert_query, (nombre_producto, descripcion, precio, stock))
            new_product_id = cursor.lastrowid

            query_new_product = "SELECT * FROM productos WHERE id_producto = %s"
            cursor.execute(query_new_product, (new_product_id,))
            new_product_data = cursor.fetchone()

            return api_response(data=new_product_data, message="Producto creado exitosamente.", status_code=201)

    except Exception as e:
        print(f"DEBUG_PRODUCT_CREATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al crear el producto.", status_code=500, error=str(e))

@productos_bp.route('/', methods=['GET'])
@jwt_required() # Requiere autenticación para listar productos
def obtener_productos():
    """
    Obtiene una lista de todos los productos disponibles.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de productos obtenida
        schema:
          type: array
          items:
            $ref: '#/definitions/Producto'
      401:
        description: No autorizado (token JWT inválido)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = "SELECT * FROM productos"
            cursor.execute(query)
            productos = cursor.fetchall()
            return api_response(data=productos, message="Lista de productos obtenida exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PRODUCT_GET_ALL_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener productos.", status_code=500, error=str(e))

@productos_bp.route('/<int:id_producto>', methods=['GET'])
@jwt_required() # Requiere autenticación para ver un producto específico
def obtener_producto_por_id(id_producto):
    """
    Obtiene los detalles de un producto específico por su ID.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_producto
        type: integer
        required: true
        description: ID del producto a obtener
    responses:
      200:
        description: Detalles del producto obtenidos
        schema:
          $ref: '#/definitions/Producto'
      401:
        description: No autorizado (token JWT inválido)
      404:
        description: Producto no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = "SELECT * FROM productos WHERE id_producto = %s"
            cursor.execute(query, (id_producto,))
            producto = cursor.fetchone()

            if producto:
                return api_response(data=producto, message="Producto obtenido exitosamente.", status_code=200)
            else:
                return api_response(message="Producto no encontrado.", status_code=404)

    except Exception as e:
        print(f"DEBUG_PRODUCT_GET_BY_ID_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el producto.", status_code=500, error=str(e))

@productos_bp.route('/<int:id_producto>', methods=['PUT'])
@jwt_required()
@admin_required() # Solo administradores pueden actualizar productos
def actualizar_producto(id_producto):
    """
    Actualiza los detalles de un producto existente.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_producto
        type: integer
        required: true
        description: ID del producto a actualizar
      - in: body
        name: body
        schema:
          id: ActualizarProducto
          properties:
            nombre_producto:
              type: string
              description: Nuevo nombre del producto
            descripcion:
              type: string
              description: Nueva descripción del producto
            precio:
              type: number
              format: float
              description: Nuevo precio del producto
            stock:
              type: integer
              description: Nueva cantidad en stock
    responses:
      200:
        description: Producto actualizado exitosamente
        schema:
          $ref: '#/definitions/Producto'
      400:
        description: Error de validación o no hay campos para actualizar
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Admin)
      404:
        description: Producto no encontrado
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    nombre_producto = limpiar_string(data.get('nombre_producto')) if data.get('nombre_producto') else None
    descripcion = limpiar_string(data.get('descripcion')) if data.get('descripcion') else None
    precio = data.get('precio')
    stock = data.get('stock')

    update_fields = []
    update_values = []

    if nombre_producto:
        update_fields.append("nombre_producto = %s")
        update_values.append(nombre_producto)
    if descripcion is not None: # Permite actualizar a una descripción vacía
        update_fields.append("descripcion = %s")
        update_values.append(descripcion)
    if precio is not None:
        if not isinstance(precio, (int, float)) or precio <= 0:
            return api_response(message="El precio debe ser un número positivo.", status_code=400)
        update_fields.append("precio = %s")
        update_values.append(precio)
    if stock is not None:
        if not isinstance(stock, int) or stock < 0:
            return api_response(message="El stock debe ser un número entero no negativo.", status_code=400)
        update_fields.append("stock = %s")
        update_values.append(stock)

    if not update_fields:
        return api_response(message="No hay campos para actualizar.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            update_query = "UPDATE productos SET " + ", ".join(update_fields) + " WHERE id_producto = %s"
            update_values.append(id_producto)

            cursor.execute(update_query, tuple(update_values))

            if cursor.rowcount == 0:
                return api_response(message="Producto no encontrado o no se realizaron cambios.", status_code=404)

            query_updated = "SELECT * FROM productos WHERE id_producto = %s"
            cursor.execute(query_updated, (id_producto,))
            updated_product = cursor.fetchone()

            return api_response(data=updated_product, message="Producto actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PRODUCT_UPDATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al actualizar el producto.", status_code=500, error=str(e))

@productos_bp.route('/<int:id_producto>', methods=['DELETE'])
@jwt_required()
@admin_required() # Solo administradores pueden eliminar productos
def eliminar_producto(id_producto):
    """
    Elimina un producto del sistema por su ID.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_producto
        type: integer
        required: true
        description: ID del producto a eliminar
    responses:
      200:
        description: Producto eliminado exitosamente
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Admin)
      404:
        description: Producto no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            delete_query = "DELETE FROM productos WHERE id_producto = %s"
            cursor.execute(delete_query, (id_producto,))

            if cursor.rowcount == 0:
                return api_response(message="Producto no encontrado.", status_code=404)

            return api_response(message="Producto eliminado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PRODUCT_DELETE_ERROR: {e}")
        return api_response(message="Error interno del servidor al eliminar el producto.", status_code=500, error=str(e))
