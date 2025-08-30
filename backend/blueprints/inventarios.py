from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.auth_decorators import Administrador_requerido, Administrador_o_Empleado_requerido
from utils.helpers import api_response, db_session, limpiar_string


inventarios_bp = Blueprint('inventarios_bp', __name__)

# --- Rutas para la gestión de inventario ---

@inventarios_bp.route('/<int:id_producto>/stock', methods=['PATCH'])
@jwt_required()
@Administrador_o_Empleado_requerido() # Solo administradores o empleados pueden ajustar el stock
def actualizar_stock_producto(id_producto):
    """
    Actualiza el stock de un producto específico.
    Esto permite añadir o restar del stock actual.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_producto
        type: integer
        required: true
        description: ID del producto cuyo stock se va a actualizar
      - in: body
        name: body
        schema:
          id: ActualizarStock
          required:
            - cantidad
          properties:
            cantidad:
              type: integer
              description: Cantidad a añadir (positiva) o a restar (negativa) del stock actual.
    responses:
      200:
        description: Stock del producto actualizado exitosamente
        schema:
          id: ProductoStock
          properties:
            id_producto:
              type: integer
            nombre_producto:
              type: string
            stock:
              type: integer
      400:
        description: Error de validación (ej. cantidad no válida, stock negativo)
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Admin ni Empleado)
      404:
        description: Producto no encontrado
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    cantidad_ajuste = data.get('cantidad')

    if not isinstance(cantidad_ajuste, int):
        return api_response(message="La cantidad debe ser un número entero.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # Obtener el stock actual del producto
            query_current_stock = "SELECT nombre_producto, stock FROM productos WHERE id_producto = %s"
            cursor.execute(query_current_stock, (id_producto,))
            producto = cursor.fetchone()

            if not producto:
                return api_response(message="Producto no encontrado.", status_code=404)

            nuevo_stock = producto['stock'] + cantidad_ajuste

            if nuevo_stock < 0:
                return api_response(message="El stock resultante no puede ser negativo.", status_code=400)

            # Actualizar el stock
            update_stock_query = "UPDATE productos SET stock = %s WHERE id_producto = %s"
            cursor.execute(update_stock_query, (nuevo_stock, id_producto))

            if cursor.rowcount == 0: # Esto debería ser manejado por el check anterior, pero es un fallback
                return api_response(message="No se pudo actualizar el stock del producto.", status_code=500)

            # Opcional: Registrar el movimiento en una tabla de auditoría de inventario si existiera
            # (No implementado aquí para simplificar, pero es una buena práctica para el futuro)

            return api_response(data={
                "id_producto": id_producto,
                "nombre_producto": producto['nombre_producto'],
                "stock": nuevo_stock
            }, message="Stock del producto actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_INVENTORY_UPDATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al actualizar el stock.", status_code=500, error=str(e))

@inventarios_bp.route('/<int:id_producto>/stock', methods=['GET'])
@jwt_required() # Cualquier usuario autenticado puede consultar el stock
def obtener_stock_producto(id_producto):
    """
    Obtiene el stock actual de un producto específico.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_producto
        type: integer
        required: true
        description: ID del producto cuyo stock se desea obtener
    responses:
      200:
        description: Stock del producto obtenido exitosamente
        schema:
          properties:
            id_producto:
              type: integer
            nombre_producto:
              type: string
            stock:
              type: integer
      401:
        description: No autorizado (token JWT inválido)
      404:
        description: Producto no encontrado
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = "SELECT id_producto, nombre_producto, stock FROM productos WHERE id_producto = %s"
            cursor.execute(query, (id_producto,))
            producto = cursor.fetchone()

            if producto:
                return api_response(data=producto, message="Stock del producto obtenido exitosamente.", status_code=200)
            else:
                return api_response(message="Producto no encontrado.", status_code=404)

    except Exception as e:
        print(f"DEBUG_INVENTORY_GET_STOCK_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el stock.", status_code=500, error=str(e))

@inventarios_bp.route('/productos', methods=['GET'])
@jwt_required() 
def obtener_productos_con_stock():
    """
    Obtiene una lista de todos los productos con su stock actual.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de productos con stock obtenida
        schema:
          type: array
          items:
            id: ProductoStock
            properties:
              id_producto:
                type: integer
              nombre_producto:
                type: string
              stock:
                type: integer
      401:
        description: No autorizado (token JWT inválido)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = "SELECT id_producto, nombre_producto, stock FROM productos"
            cursor.execute(query)
            productos = cursor.fetchall()
            return api_response(data=productos, message="Lista de productos con stock obtenida exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_INVENTORY_GET_ALL_STOCK_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener productos con stock.", status_code=500, error=str(e))
