from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt # Importar get_jwt para depuración
from utils.auth_decorators import Administrador_requerido, Administrador_o_Empleado_requerido
from utils.helpers import api_response, db_session, limpiar_string

# Define el Blueprint para productos
productos_bp = Blueprint('productos_bp', __name__)

# --- Rutas para la gestión de productos ---

@productos_bp.route('/', methods=['POST'])
# @jwt_required() # Se elimina porque Administrador_o_Empleado_requerido() ya lo gestiona
@Administrador_o_Empleado_requerido() # Administradores Y empleados pueden crear productos
def crear_producto():
    """
    Crea un nuevo producto.
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
            - id_categoria
            - precio
            - stock
          properties:
            nombre_producto:
              type: string
              description: Nombre del producto
            descripcion:
              type: string
              description: Descripción del producto (opcional)
            id_categoria:
              type: integer
              description: ID de la categoría a la que pertenece el producto
            precio:
              type: number
              format: float
              description: Precio del producto
            stock:
              type: integer
              description: Cantidad en stock
            unidad_medida:
              type: string
              description: Unidad de medida del producto (ej. kg, unidad, litro)
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
            id_categoria:
              type: integer
            precio:
              type: number
              format: float
            stock:
              type: integer
            unidad_medida:
              type: string
      400:
        description: Error de validación o campos requeridos (ej. categoría no existente)
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador o Empleado)
      409:
        description: Conflicto, ya existe un producto con ese nombre.
      500:
        description: Error interno del servidor
    """
    try:
        data = request.get_json()
        nombre_producto = limpiar_string(data.get('nombre_producto'))
        descripcion = limpiar_string(data.get('descripcion')) if data.get('descripcion') is not None else None
        id_categoria = data.get('id_categoria')
        precio = data.get('precio') # Usamos 'precio' como en la BD
        stock = data.get('stock')
        unidad_medida = limpiar_string(data.get('unidad_medida')) if data.get('unidad_medida') is not None else None

        # Validaciones de campos requeridos
        if not all([nombre_producto, id_categoria is not None, precio is not None, stock is not None]):
            return api_response(message="Nombre del producto, ID de categoría, precio y stock son campos requeridos.", status_code=400)

        # Validaciones adicionales de tipos y valores
        if not isinstance(id_categoria, int) or id_categoria <= 0:
            return api_response(message="El ID de categoría es obligatorio y debe ser un número entero positivo.", status_code=400)
        if not isinstance(precio, (int, float)) or precio <= 0:
            return api_response(message="El precio debe ser un número positivo.", status_code=400)
        if not isinstance(stock, int) or stock < 0:
            return api_response(message="El stock debe ser un número entero no negativo.", status_code=400)
        # Puedes añadir validación para unidad_medida si es un campo con valores fijos

        with db_session() as (conn, cursor):
            # 1. Verificar si el nombre del producto ya existe
            check_name_query = "SELECT id_producto FROM productos WHERE nombre_producto = %s"
            cursor.execute(check_name_query, (nombre_producto,))
            if cursor.fetchone():
                return api_response(message="Ya existe un producto con ese nombre.", status_code=409)

            # 2. Verificar si la id_categoria existe en la tabla categorias
            check_category_query = "SELECT id_categoria FROM categorias WHERE id_categoria = %s"
            cursor.execute(check_category_query, (id_categoria,))
            if not cursor.fetchone():
                return api_response(message="La categoría especificada no existe.", status_code=400)

            # 3. INSERTAR el nuevo producto con todas las columnas
            insert_query = """
                INSERT INTO productos (nombre_producto, descripcion, id_categoria, precio, stock, unidad_medida)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (nombre_producto, descripcion, id_categoria, precio, stock, unidad_medida))
            new_product_id = cursor.lastrowid

            # 4. OBTENER y devolver los datos del producto recién creado
            query_new_product = """
                SELECT id_producto, nombre_producto, descripcion, id_categoria, precio, stock, unidad_medida
                FROM productos WHERE id_producto = %s
            """
            cursor.execute(query_new_product, (new_product_id,))
            new_product_data = cursor.fetchone()

            return api_response(data=new_product_data, message="Producto creado exitosamente.", status_code=201)

    except Exception as e:
        print(f"DEBUG_PRODUCT_CREATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al crear el producto.", status_code=500, error=str(e))

# --- GET (obtener todos los productos) ---
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
            # Selecciona todas las columnas relevantes
            query = "SELECT id_producto, nombre_producto, descripcion, id_categoria, precio, stock, unidad_medida FROM productos"
            cursor.execute(query)
            productos = cursor.fetchall()
            return api_response(data=productos, message="Lista de productos obtenida exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PRODUCT_GET_ALL_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener productos.", status_code=500, error=str(e))

# --- GET por ID (obtener un producto específico) ---
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
            # Selecciona todas las columnas relevantes
            query = "SELECT id_producto, nombre_producto, descripcion, id_categoria, precio, stock, unidad_medida FROM productos WHERE id_producto = %s"
            cursor.execute(query, (id_producto,))
            producto = cursor.fetchone()

            if producto:
                return api_response(data=producto, message="Producto obtenido exitosamente.", status_code=200)
            else:
                return api_response(message="Producto no encontrado.", status_code=404)

    except Exception as e:
        print(f"DEBUG_PRODUCT_GET_BY_ID_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el producto.", status_code=500, error=str(e))

# --- PUT (actualizar un producto) ---
@productos_bp.route('/<int:id_producto>', methods=['PUT'])
# @jwt_required() # Se elimina porque Administrador_requerido() ya lo gestiona
@Administrador_requerido() # Solo administradores pueden actualizar productos
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
            id_categoria:
              type: integer
              description: Nuevo ID de la categoría a la que pertenece el producto
            precio:
              type: number
              format: float
              description: Nuevo precio del producto
            stock:
              type: integer
              description: Nueva cantidad en stock
            unidad_medida:
              type: string
              description: Nueva unidad de medida del producto (ej. kg, unidad, litro)
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
        description: Acceso denegado (no es Administrador)
      404:
        description: Producto no encontrado
      409:
        description: Conflicto, ya existe un producto con el nombre proporcionado.
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    nombre_producto = limpiar_string(data.get('nombre_producto')) if data.get('nombre_producto') is not None else None
    descripcion = limpiar_string(data.get('descripcion')) if data.get('descripcion') is not None else None
    id_categoria = data.get('id_categoria')
    precio = data.get('precio') # Usamos 'precio' como en la BD
    stock = data.get('stock')
    unidad_medida = limpiar_string(data.get('unidad_medida')) if data.get('unidad_medida') is not None else None

    update_fields = []
    update_values = []

    if nombre_producto is not None:
        update_fields.append("nombre_producto = %s")
        update_values.append(nombre_producto)
    if descripcion is not None:
        update_fields.append("descripcion = %s")
        update_values.append(descripcion)
    if id_categoria is not None:
        if not isinstance(id_categoria, int) or id_categoria <= 0:
            return api_response(message="El ID de categoría debe ser un número entero positivo.", status_code=400)
        update_fields.append("id_categoria = %s")
        update_values.append(id_categoria)
    if precio is not None:
        if not isinstance(precio, (int, float)) or precio <= 0:
            return api_response(message="El precio debe ser un número positivo.", status_code=400)
        update_fields.append("precio = %s") # Nombre de columna 'precio'
        update_values.append(precio)
    if stock is not None:
        if not isinstance(stock, int) or stock < 0:
            return api_response(message="El stock debe ser un número entero no negativo.", status_code=400)
        update_fields.append("stock = %s")
        update_values.append(stock)
    if unidad_medida is not None:
        update_fields.append("unidad_medida = %s")
        update_values.append(unidad_medida)

    if not update_fields:
        return api_response(message="No hay campos para actualizar.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Verificar si el producto existe
            check_product_query = "SELECT id_producto FROM productos WHERE id_producto = %s"
            cursor.execute(check_product_query, (id_producto,))
            if not cursor.fetchone():
                return api_response(message="Producto no encontrado.", status_code=404)

            # 2. Si se está actualizando el nombre, verificar que no haya duplicados (excluyendo el propio producto)
            if nombre_producto:
                check_name_query = "SELECT id_producto FROM productos WHERE nombre_producto = %s AND id_producto != %s"
                cursor.execute(check_name_query, (nombre_producto, id_producto))
                if cursor.fetchone():
                    return api_response(message="Ya existe otro producto con ese nombre.", status_code=409)

            # 3. Si se está actualizando la id_categoria, verificar que exista
            if id_categoria is not None:
                check_category_query = "SELECT id_categoria FROM categorias WHERE id_categoria = %s"
                cursor.execute(check_category_query, (id_categoria,))
                if not cursor.fetchone():
                    return api_response(message="La categoría especificada no existe.", status_code=400)

            update_query = "UPDATE productos SET " + ", ".join(update_fields) + " WHERE id_producto = %s"
            update_values.append(id_producto)

            cursor.execute(update_query, tuple(update_values))

            # Obtener el producto actualizado para devolverlo en la respuesta
            query_updated = """
                SELECT id_producto, nombre_producto, descripcion, id_categoria, precio, stock, unidad_medida
                FROM productos WHERE id_producto = %s
            """
            cursor.execute(query_updated, (id_producto,))
            updated_product = cursor.fetchone()

            return api_response(data=updated_product, message="Producto actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PRODUCT_UPDATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al actualizar el producto.", status_code=500, error=str(e))

# --- DELETE (eliminar un producto) ---
@productos_bp.route('/<int:id_producto>', methods=['DELETE'])
@Administrador_requerido() # Solo administradores pueden eliminar productos
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
        description: Acceso denegado (no es Administrador)
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
