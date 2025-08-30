from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from utils.auth_decorators import Administrador_requerido
from utils.helpers import api_response, db_session, limpiar_string
import uuid # Para generar IDs de transacción simulados

# Define el Blueprint para pagos
pagos_bp = Blueprint('pagos_bp', __name__)

# --- Rutas para la gestión de pagos ---

@pagos_bp.route('/procesar', methods=['POST'])
@jwt_required()
def procesar_pago():
    """
    Simula el procesamiento de un pago para un pedido existente.
    Actualiza el estado del pedido y registra el pago.
    ---
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          id: ProcesarPago
          required:
            - id_pedido
            - metodo_pago
          properties:
            id_pedido:
              type: integer
              description: ID del pedido al que se asociará este pago.
            metodo_pago:
              type: string
              description: Método de pago utilizado (ej. 'Tarjeta de crédito', 'PayPal').
            detalles_pago:
              type: object
              description: Detalles específicos del método de pago (ej. últimos 4 dígitos de tarjeta).
              properties:
                tarjeta_terminacion:
                  type: string
                  description: Últimos 4 dígitos de la tarjeta.
                
                # otros detalles que podrías añadir
    responses:
      200:
        description: Pago procesado exitosamente (simulado)
        schema:
          id: PagoProcesado
          properties:
            id_pago:
              type: integer
            id_pedido:
              type: integer
            fecha_pago:
              type: string
            monto:
              type: number
            metodo_pago:
              type: string
            estado_pago:
              type: string
            transaccion_id:
              type: string
            mensaje_pedido:
              type: string
      400:
        description: Datos inválidos, pedido no encontrado o ya pagado
      401:
        description: No autorizado
      403:
        description: El pedido no pertenece al usuario
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()

    id_pedido = data.get('id_pedido')
    metodo_pago = limpiar_string(data.get('metodo_pago'))
    detalles_pago = data.get('detalles_pago', {}) # Para futuros detalles como tarjeta

    if not all([id_pedido, metodo_pago]):
        return api_response(message="ID de pedido y método de pago son requeridos.", status_code=400)
    
    if not isinstance(id_pedido, int) or id_pedido <= 0:
        return api_response(message="ID de pedido inválido.", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Obtener id_cliente del usuario actual
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=400)
            id_cliente = cliente_info['id_cliente']

            # 2. Obtener detalles del pedido y verificar que pertenece al cliente
            cursor.execute(
                "SELECT id_pedido, id_cliente, total_pedido, estado_pedido FROM pedidos WHERE id_pedido = %s AND id_cliente = %s FOR UPDATE",
                (id_pedido, id_cliente)
            )
            pedido = cursor.fetchone()

            if not pedido:
                return api_response(message="Pedido no encontrado o no pertenece a este cliente.", status_code=404)
            
            if pedido['estado_pedido'] in ['Completado', 'Cancelado']:
                return api_response(message=f"El pedido ya está en estado '{pedido['estado_pedido']}' y no puede ser procesado para pago.", status_code=400)
            
            monto_pago = pedido['total_pedido']
            
            # --- Simulación de lógica de pasarela de pago ---
            # En un sistema real, aquí interactuarías con Stripe, PayPal, etc.
            # Para esta simulación, asumimos que el pago siempre es "Aprobado".
            estado_pago = 'Aprobado'
            transaccion_id = str(uuid.uuid4()) # ID de transacción simulado
            # --- Fin de simulación ---

            # 3. Registrar el pago
            insert_pago_query = """
                INSERT INTO pagos (id_pedido, monto, metodo_pago, estado_pago, transaccion_id)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_pago_query, (id_pedido, monto_pago, metodo_pago, estado_pago, transaccion_id))
            id_pago = cursor.lastrowid

            # 4. Actualizar el estado del pedido a 'Completado' o 'En proceso'
            update_pedido_query = "UPDATE pedidos SET estado_pedido = 'Completado' WHERE id_pedido = %s"
            cursor.execute(update_pedido_query, (id_pedido,))
            
            conn.commit() # Confirmar todas las transacciones

            # 5. Obtener los detalles del pago recién registrado para la respuesta
            query_pago = "SELECT * FROM pagos WHERE id_pago = %s"
            cursor.execute(query_pago, (id_pago,))
            pago_registrado = cursor.fetchone()

            response_data = {
                **pago_registrado,
                'mensaje_pedido': "Estado del pedido actualizado a 'Completado'."
            }
            return api_response(data=response_data, message="Pago procesado exitosamente.", status_code=200)

    except pymysql.Error as db_error:
        conn.rollback()
        print(f"DEBUG_PAGO_DB_ERROR: {db_error}")
        return api_response(message="Error de base de datos al procesar el pago.", status_code=500, error=str(db_error))
    except Exception as e:
        print(f"DEBUG_PAGO_PROCESAR_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al procesar el pago.", status_code=500, error=str(e))

@pagos_bp.route('/<int:id_pago>', methods=['GET'])
@jwt_required()
def obtener_detalle_pago(id_pago):
    """
    Obtiene los detalles de un pago específico.
    Solo el cliente que hizo el pedido o un Administrador pueden acceder.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_pago
        type: integer
        required: true
        description: ID del pago a obtener.
    responses:
      200:
        description: Detalles del pago obtenidos exitosamente
        schema:
          $ref: '#/definitions/PagoProcesado'
      401:
        description: No autorizado
      403:
        description: Acceso denegado (el pago no pertenece al usuario o no es Admin)
      404:
        description: Pago no encontrado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    user_roles = claims.get("roles", [])

    try:
        with db_session() as (conn, cursor):
            # Obtener información del pago y el pedido asociado
            query = """
                SELECT pgs.*, pd.id_cliente, cl.id_usuario
                FROM pagos pgs
                JOIN pedidos pd ON pgs.id_pedido = pd.id_pedido
                JOIN clientes cl ON pd.id_cliente = cl.id_cliente
                WHERE pgs.id_pago = %s
            """
            cursor.execute(query, (id_pago,))
            pago_info = cursor.fetchone()

            if not pago_info:
                return api_response(message="Pago no encontrado.", status_code=404)
            
            # Verificar permisos: Admin o dueño del pedido
            if "Administrador" not in user_roles and str(pago_info['id_usuario']) != current_user_id:
                return api_response(message="Acceso denegado: No tienes permiso para ver este pago.", status_code=403)
            
            return api_response(data=pago_info, message="Detalles del pago obtenidos exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PAGO_GET_BY_ID_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el detalle del pago.", status_code=500, error=str(e))

@pagos_bp.route('/admin', methods=['GET'])
@jwt_required()
@Administrador_requerido()
def obtener_todos_los_pagos_admin():
    """
    Obtiene una lista de todos los pagos registrados en el sistema (Solo Administrador).
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de pagos obtenida exitosamente
        schema:
          type: array
          items:
            $ref: '#/definitions/PagoProcesado'
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            query = "SELECT * FROM pagos ORDER BY fecha_pago DESC"
            cursor.execute(query)
            pagos = cursor.fetchall()
            return api_response(data=pagos, message="Lista de todos los pagos obtenida exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PAGO_GET_ALL_ADMIN_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener todos los pagos.", status_code=500, error=str(e))

@pagos_bp.route('/<int:id_pago>/estado', methods=['PUT'])
@jwt_required()
@Administrador_requerido()
def actualizar_estado_pago_admin(id_pago):
    """
    Actualiza el estado de un pago específico (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_pago
        type: integer
        required: true
        description: ID del pago a actualizar.
      - in: body
        name: body
        schema:
          id: ActualizarEstadoPago
          required:
            - estado_pago
          properties:
            estado_pago:
              type: string
              description: Nuevo estado del pago (ej. 'Pendiente', 'Aprobado', 'Rechazado', 'Reembolsado').
    responses:
      200:
        description: Estado del pago actualizado exitosamente
        schema:
          $ref: '#/definitions/PagoProcesado'
      400:
        description: Estado de pago inválido
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Pago no encontrado
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    nuevo_estado = limpiar_string(data.get('estado_pago'))

    if not nuevo_estado:
        return api_response(message="El campo 'estado_pago' es requerido.", status_code=400)
    
    estados_validos = ['Pendiente', 'Aprobado', 'Rechazado', 'Reembolsado']
    if nuevo_estado not in estados_validos:
        return api_response(message=f"Estado de pago inválido. Los estados permitidos son: {', '.join(estados_validos)}", status_code=400)

    try:
        with db_session() as (conn, cursor):
            # 1. Verificar si el pago existe
            cursor.execute("SELECT id_pago FROM pagos WHERE id_pago = %s", (id_pago,))
            if not cursor.fetchone():
                return api_response(message="Pago no encontrado.", status_code=404)
            
            update_query = "UPDATE pagos SET estado_pago = %s WHERE id_pago = %s"
            cursor.execute(update_query, (nuevo_estado, id_pago))
            conn.commit()

            query_updated = "SELECT * FROM pagos WHERE id_pago = %s"
            cursor.execute(query_updated, (id_pago,))
            updated_pago = cursor.fetchone()

            # Opcional: Si el pago se marca como 'Reembolsado', podrías querer revertir el stock
            # o si se marca como 'Rechazado', cambiar el estado del pedido asociado.
            # Esta lógica adicional dependería de tus reglas de negocio.

            return api_response(data=updated_pago, message="Estado del pago actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_PAGO_UPDATE_ADMIN_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al actualizar el estado del pago.", status_code=500, error=str(e))
