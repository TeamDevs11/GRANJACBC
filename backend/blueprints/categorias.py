from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from utils.auth_decorators import Administrador_requerido # Solo el administrador debería gestionar categorías
from utils.helpers import api_response, db_session, limpiar_string

# Define el Blueprint para categorías
categorias_bp = Blueprint('categorias_bp', __name__)

# --- Rutas para la gestión de categorías ---

@categorias_bp.route('/', methods=['POST'])
@jwt_required()
@Administrador_requerido() # Solo administradores pueden crear categorías
def crear_categoria():
    """
    Crea una nueva categoría de producto.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: NuevaCategoria
          required:
            - nombre_categoria
          properties:
            nombre_categoria:
              type: string
              description: Nombre único de la categoría (ej. 'Frutas', 'Verduras')
            descripcion:
              type: string
              description: Descripción de la categoría (opcional)
    responses:
      201:
        description: Categoría creada exitosamente
        schema:
          id: Categoria
          properties:
            id_categoria:
              type: integer
            nombre_categoria:
              type: string
            descripcion:
              type: string
      400:
        description: Error de validación o campos requeridos
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador)
      409:
        description: Conflicto, ya existe una categoría con ese nombre.
      500:
        description: Error interno del servidor
    """
    try:
        data = request.get_json()
        nombre_categoria = limpiar_string(data.get('nombre_categoria'))
        descripcion = limpiar_string(data.get('descripcion')) if data.get('descripcion') is not None else None

        if not nombre_categoria:
            return api_response(message="El nombre de la categoría es requerido.", status_code=400)
        
        with db_session() as (conn, cursor):
            # Verificar si ya existe una categoría con el mismo nombre
            check_query = "SELECT id_categoria FROM categorias WHERE nombre_categoria = %s"
            cursor.execute(check_query, (nombre_categoria,))
            if cursor.fetchone():
                return api_response(message="Ya existe una categoría con ese nombre.", status_code=409)
            
            insert_query = """
                INSERT INTO categorias (nombre_categoria, descripcion)
                VALUES (%s, %s)
            """
            cursor.execute(insert_query, (nombre_categoria, descripcion))
            new_category_id = cursor.lastrowid

            query_new_category = "SELECT id_categoria, nombre_categoria, descripcion FROM categorias WHERE id_categoria = %s"
            cursor.execute(query_new_category, (new_category_id,))
            new_category_data = cursor.fetchone()

            return api_response(data=new_category_data, message="Categoría creada exitosamente.", status_code=201)

    except Exception as e:
        print(f"DEBUG_CATEGORIA_CREATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al crear la categoría.", status_code=500, error=str(e))

@categorias_bp.route('/', methods=['GET'])
@jwt_required() # Requiere autenticación para listar categorías
def obtener_categorias():
    """
    Obtiene una lista de todas las categorías disponibles.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de categorías obtenida
        schema:
          type: array
          items:
            $ref: '#/definitions/Categoria'
      401:
        description: No autorizado (token JWT inválido)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = "SELECT id_categoria, nombre_categoria, descripcion FROM categorias"
            cursor.execute(query)
            categorias = cursor.fetchall()
            return api_response(data=categorias, message="Lista de categorías obtenida exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CATEGORIA_GET_ALL_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener categorías.", status_code=500, error=str(e))

@categorias_bp.route('/<int:id_categoria>', methods=['GET'])
@jwt_required() # Requiere autenticación para ver una categoría específica
def obtener_categoria_por_id(id_categoria):
    """
    Obtiene los detalles de una categoría específica por su ID.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_categoria
        type: integer
        required: true
        description: ID de la categoría a obtener
    responses:
      200:
        description: Detalles de la categoría obtenidos
        schema:
          $ref: '#/definitions/Categoria'
      401:
        description: No autorizado (token JWT inválido)
      404:
        description: Categoría no encontrada
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = "SELECT id_categoria, nombre_categoria, descripcion FROM categorias WHERE id_categoria = %s"
            cursor.execute(query, (id_categoria,))
            categoria = cursor.fetchone()

            if categoria:
                return api_response(data=categoria, message="Categoría obtenida exitosamente.", status_code=200)
            else:
                return api_response(message="Categoría no encontrada.", status_code=404)

    except Exception as e:
        print(f"DEBUG_CATEGORIA_GET_BY_ID_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener la categoría.", status_code=500, error=str(e))

@categorias_bp.route('/<int:id_categoria>', methods=['PUT'])
@jwt_required()
@Administrador_requerido() # Solo administradores pueden actualizar categorías
def actualizar_categoria(id_categoria):
    """
    Actualiza los detalles de una categoría existente.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_categoria
        type: integer
        required: true
        description: ID de la categoría a actualizar
      - in: body
        name: body
        schema:
          id: ActualizarCategoria
          properties:
            nombre_categoria:
              type: string
              description: Nuevo nombre de la categoría
            descripcion:
              type: string
              description: Nueva descripción de la categoría
    responses:
      200:
        description: Categoría actualizada exitosamente
        schema:
          $ref: '#/definitions/Categoria'
      400:
        description: Error de validación o no hay campos para actualizar
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Categoría no encontrada
      409:
        description: Conflicto, ya existe una categoría con el nombre proporcionado.
      500:
        description: Error interno del servidor
    """
    try:
        data = request.get_json()
        nombre_categoria = limpiar_string(data.get('nombre_categoria')) if data.get('nombre_categoria') is not None else None
        descripcion = limpiar_string(data.get('descripcion')) if data.get('descripcion') is not None else None

        update_fields = []
        update_values = []

        if nombre_categoria:
            update_fields.append("nombre_categoria = %s")
            update_values.append(nombre_categoria)
        if descripcion is not None:
            update_fields.append("descripcion = %s")
            update_values.append(descripcion)
        
        if not update_fields:
            return api_response(message="No hay campos para actualizar.", status_code=400)

        with db_session() as (conn, cursor):
            # 1. Verificar si la categoría existe
            cursor.execute("SELECT id_categoria FROM categorias WHERE id_categoria = %s", (id_categoria,))
            if not cursor.fetchone():
                return api_response(message="Categoría no encontrada.", status_code=404)
            
            # 2. Si se está actualizando el nombre, verificar que no haya duplicados (excluyendo la propia categoría)
            if nombre_categoria:
                check_name_query = "SELECT id_categoria FROM categorias WHERE nombre_categoria = %s AND id_categoria != %s"
                cursor.execute(check_name_query, (nombre_categoria, id_categoria))
                if cursor.fetchone():
                    return api_response(message="Ya existe otra categoría con ese nombre.", status_code=409)

            update_query = "UPDATE categorias SET " + ", ".join(update_fields) + " WHERE id_categoria = %s"
            update_values.append(id_categoria)

            cursor.execute(update_query, tuple(update_values))

            query_updated = "SELECT id_categoria, nombre_categoria, descripcion FROM categorias WHERE id_categoria = %s"
            cursor.execute(query_updated, (id_categoria,))
            updated_category = cursor.fetchone()

            return api_response(data=updated_category, message="Categoría actualizada exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CATEGORIA_UPDATE_ERROR: {e}")
        return api_response(message="Error interno del servidor al actualizar la categoría.", status_code=500, error=str(e))

@categorias_bp.route('/<int:id_categoria>', methods=['DELETE'])
@jwt_required()
@Administrador_requerido() # Solo administradores pueden eliminar categorías
def eliminar_categoria(id_categoria):
    """
    Elimina una categoría del sistema por su ID.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_categoria
        type: integer
        required: true
        description: ID de la categoría a eliminar
    responses:
      200:
        description: Categoría eliminada exitosamente
      400:
        description: Error, la categoría tiene productos asociados
      401:
        description: No autorizado (token JWT inválido)
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Categoría no encontrada
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            # Verificar si la categoría existe
            cursor.execute("SELECT id_categoria FROM categorias WHERE id_categoria = %s", (id_categoria,))
            if not cursor.fetchone():
                return api_response(message="Categoría no encontrada.", status_code=404)
            
            # Verificar si la categoría tiene productos asociados
            cursor.execute("SELECT COUNT(*) FROM productos WHERE id_categoria = %s", (id_categoria,))
            if cursor.fetchone()['COUNT(*)'] > 0:
                return api_response(message="No se puede eliminar la categoría porque tiene productos asociados.", status_code=400)

            delete_query = "DELETE FROM categorias WHERE id_categoria = %s"
            cursor.execute(delete_query, (id_categoria,))

            if cursor.rowcount == 0:
                # Esto no debería pasar si la verificación de existencia fue exitosa, pero es una buena práctica
                return api_response(message="Categoría no encontrada o no se pudo eliminar.", status_code=404)

            return api_response(message="Categoría eliminada exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_CATEGORIA_DELETE_ERROR: {e}")
        return api_response(message="Error interno del servidor al eliminar la categoría.", status_code=500, error=str(e))
