from flask import Blueprint, jsonify, request
import pymysql.cursors
from utils.db import conectar_db
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from utils.auth_decorators import Administrador_requerido
from utils.helpers import api_response, db_session, limpiar_string

# Define el Blueprint para ventas
ventas_bp = Blueprint('ventas_bp', __name__)

# --- Rutas para la gestión de ventas ---

# Nota: La creación de una 'venta' se dispararía lógicamente
# después de que un 'pedido' es pagado y completado.
# Por lo tanto, no hay una ruta POST directa aquí para 'ventas'.
# Las ventas se registran implícitamente a través del proceso de pedidos/pagos.
# Aquí nos centramos en la consulta y gestión de ventas ya existentes.

@ventas_bp.route('/me', methods=['GET'])
@jwt_required()
def obtener_mis_ventas():
    """
    Obtiene el historial de ventas del cliente autenticado, incluyendo sus detalles.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Historial de ventas obtenido exitosamente
        schema:
          type: array
          items:
            id: DetalleVentaCompleto
            properties:
              id_venta:
                type: integer
              id_cliente:
                type: integer
              id_usuario:
                type: integer
              nombre_cliente:
                type: string
              email_cliente:
                type: string
              fecha:
                type: string
                format: date
              total:
                type: number
              estado_venta:
                type: string
              direccion_envio:
                type: string
              id_direccion_envio:
                type: integer
              direccion_facturacion:
                type: string
              id_direccion_facturacion:
                type: integer
              detalles_productos:
                type: array
                items:
                  type: object
                  properties:
                    id_detalle_venta:
                      type: integer
                    id_producto:
                      type: integer
                    nombre_producto:
                      type: string
                    cantidad:
                      type: integer
                    precio_unitario:
                      type: number
                    subtotal:
                      type: number
      401:
        description: No autorizado
      404:
        description: Perfil de cliente o usuario no encontrado
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()

    try:
        with db_session() as (conn, cursor):
            # Obtener id_cliente del usuario actual
            cursor.execute("SELECT id_cliente FROM clientes WHERE id_usuario = %s", (current_user_id,))
            cliente_info = cursor.fetchone()
            if not cliente_info:
                return api_response(message="Perfil de cliente no encontrado. Por favor, complete su perfil.", status_code=404)
            id_cliente = cliente_info['id_cliente']

            # Obtener las ventas del cliente autenticado
            query_ventas = """
                SELECT v.id_venta, v.id_cliente, v.id_usuario, v.fecha, v.total,
                       ev.nombre_estado AS estado_venta,
                       de.direccion AS direccion_envio, dv.direccion AS direccion_facturacion,
                       v.id_direccion_envio, v.id_direccion_facturacion,
                       cl.nombre AS nombre_cliente, u.usuario AS email_cliente
                FROM ventas v
                JOIN estados_venta ev ON v.id_estado_venta = ev.id_estado_venta
                LEFT JOIN direcciones de ON v.id_direccion_envio = de.id_direccion
                LEFT JOIN direcciones dv ON v.id_direccion_facturacion = dv.id_direccion
                JOIN clientes cl ON v.id_cliente = cl.id_cliente
                JOIN usuarios u ON v.id_usuario = u.id_usuario
                WHERE v.id_cliente = %s
                ORDER BY v.fecha DESC
            """
            cursor.execute(query_ventas, (id_cliente,))
            ventas = cursor.fetchall()

            for venta in ventas:
                # Obtener detalles de productos para cada venta
                query_detalles = """
                    SELECT dtv.id_detalle_venta, dtv.id_producto, p.nombre_producto, dtv.cantidad,
                           dtv.precio_unitario, dtv.subtotal
                    FROM detalles_venta dtv
                    JOIN productos p ON dtv.id_producto = p.id_producto
                    WHERE dtv.id_venta = %s
                """
                cursor.execute(query_detalles, (venta['id_venta'],))
                venta['detalles_productos'] = cursor.fetchall()

            return api_response(data=ventas, message="Historial de ventas obtenido exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_VENTAS_GET_ME_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el historial de ventas.", status_code=500, error=str(e))

@ventas_bp.route('/<int:id_venta>', methods=['GET'])
@jwt_required()
def obtener_detalle_venta(id_venta):
    """
    Obtiene los detalles de una venta específica.
    Solo el cliente que realizó la venta o un Administrador pueden acceder.
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_venta
        type: integer
        required: true
        description: ID de la venta a obtener.
    responses:
      200:
        description: Detalles de la venta obtenidos exitosamente
        schema:
          $ref: '#/definitions/DetalleVentaCompleto'
      401:
        description: No autorizado
      403:
        description: Acceso denegado (la venta no pertenece al usuario o no es Admin)
      404:
        description: Venta no encontrada
      500:
        description: Error interno del servidor
    """
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    user_roles = claims.get("roles", [])

    try:
        with db_session() as (conn, cursor):
            # Obtener información de la venta y los usuarios asociados
            query_venta = """
                SELECT v.id_venta, v.id_cliente, v.id_usuario, v.fecha, v.total,
                       ev.nombre_estado AS estado_venta,
                       de.direccion AS direccion_envio, dv.direccion AS direccion_facturacion,
                       v.id_direccion_envio, v.id_direccion_facturacion,
                       cl.nombre AS nombre_cliente, u.usuario AS email_cliente
                FROM ventas v
                JOIN estados_venta ev ON v.id_estado_venta = ev.id_estado_venta
                LEFT JOIN direcciones de ON v.id_direccion_envio = de.id_direccion
                LEFT JOIN direcciones dv ON v.id_direccion_facturacion = dv.id_direccion
                JOIN clientes cl ON v.id_cliente = cl.id_cliente
                JOIN usuarios u ON v.id_usuario = u.id_usuario
                WHERE v.id_venta = %s
            """
            cursor.execute(query_venta, (id_venta,))
            venta = cursor.fetchone()

            if not venta:
                return api_response(message="Venta no encontrada.", status_code=404)
            
            # Verificar permisos: Admin o dueño de la venta
            if "Administrador" not in user_roles and str(venta['id_usuario']) != current_user_id:
                return api_response(message="Acceso denegado: No tienes permiso para ver esta venta.", status_code=403)
            
            # Obtener detalles de productos para la venta
            query_detalles = """
                SELECT dtv.id_detalle_venta, dtv.id_producto, p.nombre_producto, dtv.cantidad,
                       dtv.precio_unitario, dtv.subtotal
                FROM detalles_venta dtv
                JOIN productos p ON dtv.id_producto = p.id_producto
                WHERE dtv.id_venta = %s
            """
            cursor.execute(query_detalles, (id_venta,))
            venta['detalles_productos'] = cursor.fetchall()
            
            return api_response(data=venta, message="Detalles de la venta obtenidos exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_VENTAS_GET_BY_ID_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener el detalle de la venta.", status_code=500, error=str(e))

@ventas_bp.route('/admin', methods=['GET'])
@jwt_required()
@Administrador_requerido()
def obtener_todas_las_ventas_admin():
    """
    Obtiene una lista de todas las ventas registradas en el sistema (Solo Administrador).
    Permite filtrar por id_cliente, id_estado_venta y fecha.
    ---
    security:
      - Bearer: []
    parameters:
      - in: query
        name: id_cliente
        type: integer
        description: Filtrar ventas por ID de cliente.
      - in: query
        name: id_estado_venta
        type: integer
        description: Filtrar ventas por ID de estado de venta.
      - in: query
        name: fecha_inicio
        type: string
        format: date
        description: Filtrar ventas a partir de una fecha (YYYY-MM-DD).
      - in: query
        name: fecha_fin
        type: string
        format: date
        description: Filtrar ventas hasta una fecha (YYYY-MM-DD).
    responses:
      200:
        description: Lista de todas las ventas obtenida exitosamente
        schema:
          type: array
          items:
            $ref: '#/definitions/DetalleVentaCompleto'
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      500:
        description: Error interno del servidor
    """
    try:
        with db_session() as (conn, cursor):
            base_query = """
                SELECT v.id_venta, v.id_cliente, v.id_usuario, v.fecha, v.total,
                       ev.nombre_estado AS estado_venta,
                       de.direccion AS direccion_envio, dv.direccion AS direccion_facturacion,
                       v.id_direccion_envio, v.id_direccion_facturacion,
                       cl.nombre AS nombre_cliente, u.usuario AS email_cliente
                FROM ventas v
                JOIN estados_venta ev ON v.id_estado_venta = ev.id_estado_venta
                LEFT JOIN direcciones de ON v.id_direccion_envio = de.id_direccion
                LEFT JOIN direcciones dv ON v.id_direccion_facturacion = dv.id_direccion
                JOIN clientes cl ON v.id_cliente = cl.id_cliente
                JOIN usuarios u ON v.id_usuario = u.id_usuario
                WHERE 1=1
            """
            params = []
            
            id_cliente_filter = request.args.get('id_cliente')
            if id_cliente_filter:
                base_query += " AND v.id_cliente = %s"
                params.append(id_cliente_filter)
            
            id_estado_filter = request.args.get('id_estado_venta')
            if id_estado_filter:
                base_query += " AND v.id_estado_venta = %s"
                params.append(id_estado_filter)
            
            fecha_inicio_filter = request.args.get('fecha_inicio')
            if fecha_inicio_filter:
                base_query += " AND v.fecha >= %s"
                params.append(fecha_inicio_filter)
            
            fecha_fin_filter = request.args.get('fecha_fin')
            if fecha_fin_filter:
                base_query += " AND v.fecha <= %s"
                params.append(fecha_fin_filter)

            base_query += " ORDER BY v.fecha DESC"
            cursor.execute(base_query, tuple(params))
            ventas = cursor.fetchall()

            for venta in ventas:
                # Obtener detalles de productos para cada venta
                query_detalles = """
                    SELECT dtv.id_detalle_venta, dtv.id_producto, p.nombre_producto, dtv.cantidad,
                           dtv.precio_unitario, dtv.subtotal
                    FROM detalles_venta dtv
                    JOIN productos p ON dtv.id_producto = p.id_producto
                    WHERE dtv.id_venta = %s
                """
                cursor.execute(query_detalles, (venta['id_venta'],))
                venta['detalles_productos'] = cursor.fetchall()

            return api_response(data=ventas, message="Lista de todas las ventas obtenida exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_VENTAS_GET_ALL_ADMIN_ERROR: {e}")
        return api_response(message="Error interno del servidor al obtener todas las ventas.", status_code=500, error=str(e))

@ventas_bp.route('/<int:id_venta>/estado', methods=['PUT'])
@jwt_required()
@Administrador_requerido()
def actualizar_estado_venta_admin(id_venta):
    """
    Actualiza el estado de una venta específica (Solo Administrador).
    ---
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_venta
        type: integer
        required: true
        description: ID de la venta a actualizar.
      - in: body
        name: body
        schema:
          id: ActualizarEstadoVenta
          required:
            - id_estado_venta
          properties:
            id_estado_venta:
              type: integer
              description: Nuevo ID del estado de venta (referencia a la tabla 'estados_venta').
    responses:
      200:
        description: Estado de la venta actualizado exitosamente
        schema:
          $ref: '#/definitions/DetalleVentaCompleto'
      400:
        description: ID de estado de venta inválido
      401:
        description: No autorizado
      403:
        description: Acceso denegado (no es Administrador)
      404:
        description: Venta o estado no encontrado
      500:
        description: Error interno del servidor
    """
    data = request.get_json()
    new_id_estado_venta = data.get('id_estado_venta')

    if not new_id_estado_venta or not isinstance(new_id_estado_venta, int) or new_id_estado_venta <= 0:
        return api_response(message="ID de estado de venta inválido y requerido.", status_code=400)
    
    try:
        with db_session() as (conn, cursor):
            # 1. Verificar si la venta existe
            cursor.execute("SELECT id_venta FROM ventas WHERE id_venta = %s", (id_venta,))
            if not cursor.fetchone():
                return api_response(message="Venta no encontrada.", status_code=404)
            
            # 2. Verificar si el nuevo estado de venta existe
            cursor.execute("SELECT id_estado_venta FROM estados_venta WHERE id_estado_venta = %s", (new_id_estado_venta,))
            if not cursor.fetchone():
                return api_response(message="El ID de estado de venta proporcionado no existe.", status_code=400)

            update_query = "UPDATE ventas SET id_estado_venta = %s WHERE id_venta = %s"
            cursor.execute(update_query, (new_id_estado_venta, id_venta))
            conn.commit()

            # Obtener la venta actualizada para devolverla
            query_updated = """
                SELECT v.id_venta, v.id_cliente, v.id_usuario, v.fecha, v.total,
                       ev.nombre_estado AS estado_venta,
                       de.direccion AS direccion_envio, dv.direccion AS direccion_facturacion,
                       v.id_direccion_envio, v.id_direccion_facturacion,
                       cl.nombre AS nombre_cliente, u.usuario AS email_cliente
                FROM ventas v
                JOIN estados_venta ev ON v.id_estado_venta = ev.id_estado_venta
                LEFT JOIN direcciones de ON v.id_direccion_envio = de.id_direccion
                LEFT JOIN direcciones dv ON v.id_direccion_facturacion = dv.id_direccion
                JOIN clientes cl ON v.id_cliente = cl.id_cliente
                JOIN usuarios u ON v.id_usuario = u.id_usuario
                WHERE v.id_venta = %s
            """
            cursor.execute(query_updated, (id_venta,))
            updated_venta = cursor.fetchone()

            # Obtener detalles de productos para la respuesta completa
            query_detalles = """
                SELECT dtv.id_detalle_venta, dtv.id_producto, p.nombre_producto, dtv.cantidad,
                       dtv.precio_unitario, dtv.subtotal
                FROM detalles_venta dtv
                JOIN productos p ON dtv.id_producto = p.id_producto
                WHERE dtv.id_venta = %s
            """
            cursor.execute(query_detalles, (id_venta,))
            updated_venta['detalles_productos'] = cursor.fetchall()

            return api_response(data=updated_venta, message="Estado de la venta actualizado exitosamente.", status_code=200)

    except Exception as e:
        print(f"DEBUG_VENTAS_UPDATE_ADMIN_ERROR: {e}")
        conn.rollback()
        return api_response(message="Error interno del servidor al actualizar el estado de la venta.", status_code=500, error=str(e))


# --- Función para registrar una venta desde un pedido completado ---
# Esta función NO es una ruta HTTP. Es una función interna que puede ser llamada
# desde el blueprint de 'pedidos' cuando un pedido se completa y se paga.
# Por ejemplo, después de que el pago se haya procesado y el estado del pedido
# haya cambiado a 'Completado'.

# Para integrarlo, necesitarías modificar la ruta POST /pagos/procesar
# para llamar a esta función después de un pago exitoso.
# O desde la ruta PUT /pedidos/<int:id_pedido> si el admin cambia el estado a 'Completado'.
def registrar_venta_desde_pedido(id_pedido_origen, conn, cursor):
    """
    Registra una venta en las tablas 'ventas' y 'detalles_venta'
    a partir de un pedido completado.
    Esta función debe ser llamada DENTRO de una sesión de base de datos existente.
    """
    try:
        # Obtener detalles del pedido que se va a convertir en venta
        cursor.execute(
            """
            SELECT p.id_cliente, p.id_usuario, p.fecha_pedido, p.total_pedido,
                   p.direccion_envio, p.ciudad_envio, p.telefono_contacto,
                   cl.id_cliente, cl.id_usuario AS id_usuario_cliente
            FROM pedidos p
            JOIN clientes cl ON p.id_cliente = cl.id_cliente
            WHERE p.id_pedido = %s
            """,
            (id_pedido_origen,)
        )
        pedido_origen = cursor.fetchone()

        if not pedido_origen:
            print(f"DEBUG_VENTA_REGISTRO_ERROR: Pedido ID {id_pedido_origen} no encontrado para registrar venta.")
            return False

        # Obtener el ID del estado 'Completado'
        cursor.execute("SELECT id_estado_venta FROM estados_venta WHERE nombre_estado = 'Completado'")
        estado_completado_info = cursor.fetchone()
        if not estado_completado_info:
            print("DEBUG_VENTA_REGISTRO_ERROR: Estado 'Completado' no encontrado en la tabla estados_venta.")
            return False
        id_estado_completado = estado_completado_info['id_estado_venta']

        # Opcional: Obtener IDs de dirección de la tabla 'direcciones' si las manejas separadamente
        # Por ahora, asumimos que 'direccion_envio' y 'ciudad_envio' son texto plano del pedido.
        # Si usas la tabla 'direcciones', deberías buscar o insertar aquí para obtener los IDs.
        id_direccion_envio_venta = None # Lógica para obtener de la tabla 'direcciones'
        id_direccion_facturacion_venta = None # Lógica para obtener de la tabla 'direcciones'

        # Insertar en la tabla 'ventas'
        insert_venta_query = """
            INSERT INTO ventas (id_cliente, id_usuario, fecha, total, id_estado_venta,
                                id_direccion_envio, id_direccion_facturacion)
            VALUES (%s, %s, CURDATE(), %s, %s, %s, %s)
        """
        cursor.execute(insert_venta_query, (
            pedido_origen['id_cliente'],
            pedido_origen['id_usuario_cliente'], # El id_usuario asociado al cliente
            pedido_origen['total_pedido'],
            id_estado_completado,
            id_direccion_envio_venta, # Usar el ID real de la tabla 'direcciones' si lo implementas
            id_direccion_facturacion_venta # Usar el ID real de la tabla 'direcciones' si lo implementas
        ))
        id_venta_generada = cursor.lastrowid

        # Obtener detalles del pedido original
        cursor.execute("SELECT id_producto, cantidad, precio_unitario FROM detalle_pedidos WHERE id_pedido = %s", (id_pedido_origen,))
        detalles_pedido = cursor.fetchall()

        # Insertar en la tabla 'detalles_venta'
        for detalle in detalles_pedido:
            subtotal_item = detalle['cantidad'] * detalle['precio_unitario']
            insert_detalle_venta_query = """
                INSERT INTO detalles_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_detalle_venta_query, (
                id_venta_generada,
                detalle['id_producto'],
                detalle['cantidad'],
                detalle['precio_unitario'],
                subtotal_item
            ))
        
        # Opcional: Marcar el pedido como 'Convertido a Venta' o similar en la tabla 'pedidos'
        # Esto es para evitar procesar el mismo pedido dos veces como venta.
        # cursor.execute("UPDATE pedidos SET estado_pedido = 'Venta Registrada' WHERE id_pedido = %s", (id_pedido_origen,))

        print(f"DEBUG_VENTA_REGISTRO_EXITOSO: Venta ID {id_venta_generada} registrada desde Pedido ID {id_pedido_origen}.")
        return True

    except Exception as e:
        print(f"DEBUG_VENTA_REGISTRO_ERROR: Error al registrar venta desde pedido {id_pedido_origen}: {e}")
        # El rollback debe ser manejado por la sesión que llama a esta función
        return False
