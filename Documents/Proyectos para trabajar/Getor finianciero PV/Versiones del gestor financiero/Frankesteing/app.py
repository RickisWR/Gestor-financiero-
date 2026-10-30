from flask import Flask, render_template, jsonify, request, send_from_directory, make_response, send_file, redirect, url_for, flash, abort
import database
import sqlite3
import os
import datetime
import pandas as pd  
import io              
from fpdf import FPDF
from fpdf.enums import XPos, YPos 
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['STATIC_FOLDER'] = 'static'
app.secret_key = 'clave_secreta_puente_viejo_segura' 

# ================= CONFIGURACIÓN LOGIN =================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, rol, nombre, jefe_id):
        self.id = id
        self.username = username
        self.rol = rol
        self.nombre = nombre
        self.jefe_id = jefe_id

@login_manager.user_loader
def load_user(user_id):
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, rol, nombre, jefe_id FROM usuarios WHERE id = ?", (user_id,))
    data = cursor.fetchone()
    conn.close()
    if data:
        return User(id=data[0], username=data[1], rol=data[2], nombre=data[3], jefe_id=data[4])
    return None

# ================= RUTAS DE AUTENTICACIÓN =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_role(current_user.rol)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form
        
        conn = database.create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
        user_data = cursor.fetchone() 
        conn.close()

        if user_data and check_password_hash(user_data[2], password):
            user_obj = User(id=user_data[0], username=user_data[1], rol=user_data[4], nombre=user_data[3], jefe_id=user_data[5])
            login_user(user_obj, remember=remember)
            return redirect_role(user_obj.rol)
        else:
            flash('Usuario o contraseña incorrectos')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def redirect_role(rol):
    """Router central de seguridad"""
    if rol == 'admin': 
        return redirect(url_for('usuarios_page'))
    elif rol == 'jefe': 
        return redirect(url_for('index'))
    elif rol in ['hostess', 'inventario', 'gerente']: 
        # SOLUCIÓN: Redirigir a página de espera
        return redirect(url_for('pagina_construccion'))
    else: 
        logout_user()
        return redirect(url_for('login'))

# ================= PÁGINAS LEGALES =================
@app.route('/terminos')
def terminos():
    return render_template('terminos.html')

@app.route('/privacidad')
def privacidad():
    return render_template('privacidad.html')

# ================= PÁGINA "EN CONSTRUCCIÓN" (NUEVA) =================
@app.route('/proximamente')
@login_required
def pagina_construccion():
    # Solo permitir acceso a roles operativos
    if current_user.rol not in ['hostess', 'inventario', 'gerente']:
        return redirect_role(current_user.rol)
    return render_template('construccion.html', user=current_user)

# ================= PERFIL DE USUARIO =================
@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre')
        nuevo_username = request.form.get('username')
        password_actual = request.form.get('password_actual')
        nueva_password = request.form.get('nueva_password')
        
        conn = database.create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM usuarios WHERE id = ?", (current_user.id,))
        stored_pass = cursor.fetchone()[0]
        
        if not check_password_hash(stored_pass, password_actual):
            flash('Error: La contraseña actual es incorrecta.')
            conn.close()
            return redirect(url_for('perfil'))
            
        if nuevo_username != current_user.username:
            cursor.execute("SELECT id FROM usuarios WHERE username = ?", (nuevo_username,))
            if cursor.fetchone():
                flash('Error: Ese nombre de usuario ya está ocupado.')
                conn.close()
                return redirect(url_for('perfil'))

        try:
            cursor.execute("UPDATE usuarios SET nombre = ?, username = ? WHERE id = ?", 
                          (nuevo_nombre, nuevo_username, current_user.id))
            if nueva_password:
                hashed_pw = generate_password_hash(nueva_password)
                cursor.execute("UPDATE usuarios SET password = ? WHERE id = ?", (hashed_pw, current_user.id))
                flash('¡Perfil actualizado con éxito!')
            else:
                flash('¡Información actualizada!')
            conn.commit()
        except Exception as e:
            flash(f'Error: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('perfil'))

    return render_template('perfil_usuario.html', user=current_user)

# ================= VISTAS PRINCIPALES (FINANZAS) =================
# CORRECCIÓN DE SEGURIDAD: Solo 'jefe' puede ver esto.

@app.route('/')
@login_required
def index():
    if current_user.rol != 'jefe': return redirect_role(current_user.rol)
    return render_template('index.html', nombre=current_user.nombre)

@app.route('/registro')
@login_required
def registro():
    if current_user.rol != 'jefe': abort(403)
    return render_template('registro_movimientos.html')

@app.route('/reportes')
@login_required
def reportes():
    if current_user.rol != 'jefe': abort(403)
    return render_template('generacion_reportes.html')

@app.route('/cuentas')
@login_required
def cuentas():
    if current_user.rol != 'jefe': abort(403)
    return render_template('cuentas_por_pagar.html')

# ================= VISTA ADMIN (USUARIOS) =================
@app.route('/usuarios')
@login_required
def usuarios_page():
    if current_user.rol not in ['admin', 'jefe']: abort(403)
    return render_template('usuarios.html')

@app.route('/static/<path:filename>')
def static_files(filename): return send_from_directory(app.config['STATIC_FOLDER'], filename)


# ================= API USUARIOS =================

@app.route('/api/usuarios', methods=['GET'])
@login_required
def get_users():
    if current_user.rol not in ['admin', 'jefe']: return jsonify({"error": "No autorizado"}), 403
    conn = database.create_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    
    if current_user.rol == 'jefe':
        # Jefe solo ve a sus subordinados
        cursor.execute("SELECT id, username, nombre, rol, jefe_id FROM usuarios WHERE jefe_id = ?", (current_user.id,))
    else:
        # Admin ve a todos
        cursor.execute("""
            SELECT u.id, u.username, u.nombre, u.rol, u.jefe_id, j.nombre as nombre_jefe 
            FROM usuarios u 
            LEFT JOIN usuarios j ON u.jefe_id = j.id
        """)
    return jsonify([dict(row) for row in cursor.fetchall()])

@app.route('/api/jefes', methods=['GET'])
@login_required
def get_jefes_list():
    if current_user.rol != 'admin': return jsonify([])
    conn = database.create_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM usuarios WHERE rol = 'jefe'")
    return jsonify([dict(row) for row in cursor.fetchall()])

@app.route('/api/usuarios', methods=['POST'])
@login_required
def create_user():
    if current_user.rol not in ['admin', 'jefe']: return jsonify({"error": "No autorizado"}), 403
    datos = request.json
    rol_nuevo = datos.get('rol')
    
    if rol_nuevo == 'admin':
        return jsonify({"error": "No es posible crear más Administradores."}), 403

    jefe_asignado = None
    if current_user.rol == 'jefe':
        if rol_nuevo in ['admin', 'jefe']: return jsonify({"error": "No puedes crear jefes ni admins"}), 403
        jefe_asignado = current_user.id
    elif current_user.rol == 'admin':
        if rol_nuevo == 'jefe':
            jefe_asignado = None 
        else:
            jefe_asignado = datos.get('jefe_id')
            if not jefe_asignado:
                return jsonify({"error": "Debes asignar un Jefe a este usuario operativo"}), 400

    try:
        conn = database.create_connection(); cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE username = ?", (datos['username'],))
        if cursor.fetchone(): return jsonify({"error": "Usuario ya existe"}), 400
        
        pass_hash = generate_password_hash(datos['password'])
        cursor.execute("INSERT INTO usuarios (username, password, nombre, rol, jefe_id) VALUES (?, ?, ?, ?, ?)",
                      (datos['username'], pass_hash, datos['nombre'], rol_nuevo, jefe_asignado))
        conn.commit()
        return jsonify({"mensaje": "Usuario creado"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- RUTA PUT PARA MODIFICAR USUARIOS (SOLUCIONA ERROR 405) ---
@app.route('/api/usuarios/<int:id>', methods=['PUT'])
@login_required
def update_user(id):
    if current_user.rol not in ['admin', 'jefe']: return jsonify({"error": "No autorizado"}), 403
    datos = request.json
    
    try:
        conn = database.create_connection(); cursor = conn.cursor()
        cursor.execute("SELECT rol, jefe_id FROM usuarios WHERE id = ?", (id,))
        target = cursor.fetchone()
        if not target: return jsonify({"error": "Usuario no encontrado"}), 404
        target_rol, target_jefe_id = target
        
        if current_user.rol == 'jefe':
            if target_jefe_id != current_user.id: return jsonify({"error": "No es tu empleado"}), 403
            nuevo_jefe_id = current_user.id 
        else:
            nuevo_jefe_id = datos.get('jefe_id', target_jefe_id)

        if datos.get('password'):
            ph = generate_password_hash(datos['password'])
            cursor.execute("UPDATE usuarios SET nombre=?, username=?, rol=?, password=?, jefe_id=? WHERE id=?", 
                          (datos['nombre'], datos['username'], datos['rol'], ph, nuevo_jefe_id, id))
        else:
            cursor.execute("UPDATE usuarios SET nombre=?, username=?, rol=?, jefe_id=? WHERE id=?", 
                          (datos['nombre'], datos['username'], datos['rol'], nuevo_jefe_id, id))
        
        conn.commit()
        return jsonify({"mensaje": "Usuario actualizado"})
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: conn.close()

@app.route('/api/usuarios/<int:id>', methods=['DELETE'])
@login_required
def delete_user(id):
    if current_user.rol not in ['admin', 'jefe']: return jsonify({"error": "No autorizado"}), 403
    if id == current_user.id: return jsonify({"error": "No puedes borrarte a ti mismo"}), 400
    
    conn = database.create_connection(); cursor = conn.cursor()
    cursor.execute("SELECT rol, jefe_id FROM usuarios WHERE id = ?", (id,))
    target = cursor.fetchone()
    
    if not target: return jsonify({"error": "Usuario no encontrado"}), 404
    target_rol, target_jefe_id = target

    if target_rol == 'admin':
        conn.close(); return jsonify({"error": "Acción denegada: Admin protegido."}), 403

    if current_user.rol == 'jefe' and target_jefe_id != current_user.id:
        conn.close(); return jsonify({"error": "No es tu empleado"}), 403

    cursor.execute("DELETE FROM usuarios WHERE id = ?", (id,))
    conn.commit(); conn.close()
    return jsonify({"mensaje": "Usuario eliminado"})


# ================= API FINANZAS E HISTORIAL =================
# BLINDADA: Solo el Jefe puede consultar/modificar.

# --- FUNCIÓN AUXILIAR PARA RECALCULAR DEUDAS AL MODIFICAR ABONOS ---
def recalcular_monto_abonado(cursor, cuenta_id, usuario_id):
    # Sumar todos los abonos (que son negativos)
    cursor.execute("SELECT SUM(monto) FROM movimientos WHERE cuenta_id = ? AND usuario_id = ?", (cuenta_id, usuario_id))
    total_pagado = cursor.fetchone()[0] or 0
    total_pagado = abs(total_pagado)
    
    # Actualizar la cuenta
    cursor.execute("SELECT monto_total FROM cuentas_por_pagar WHERE id = ? AND usuario_id = ?", (cuenta_id, usuario_id))
    row = cursor.fetchone()
    if row:
        monto_total = row[0]
        estado = 'Pagado' if total_pagado >= (monto_total - 0.01) else 'Pendiente'
        cursor.execute("UPDATE cuentas_por_pagar SET monto_abonado = ?, estado = ? WHERE id = ?", (total_pagado, estado, cuenta_id))

@app.route('/api/movimientos', methods=['GET'])
@login_required
def get_movimientos():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        conn = database.create_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT * FROM movimientos WHERE usuario_id = ? ORDER BY fecha ASC, id ASC", (current_user.id,)) 
        return jsonify([dict(row) for row in cursor.fetchall()])
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/movimiento', methods=['POST'])
@login_required
def add_movimiento():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    datos = request.json
    try:
        conn = database.create_connection(); cursor = conn.cursor()
        cursor.execute("""INSERT INTO movimientos (fecha, concepto, tipo, monto, metodo, clasificacion, sucursal, comentario, usuario_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
            (datos['fecha'], datos['concepto'], datos['tipo'], datos['monto'], datos['metodo'], datos['clasificacion'], datos.get('sucursal'), datos.get('comentario'), current_user.id))
        conn.commit()
        return jsonify({"mensaje": "Guardado", "id": cursor.lastrowid}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/movimiento/<int:id>', methods=['PUT'])
@login_required
def update_movimiento(id):
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    datos = request.json
    try:
        conn = database.create_connection(); cursor = conn.cursor()
        
        # Saber si pertenecía a una cuenta para recalcular si es un abono
        cursor.execute("SELECT cuenta_id FROM movimientos WHERE id=? AND usuario_id=?", (id, current_user.id))
        row = cursor.fetchone()
        cuenta_id = row[0] if row else None

        cursor.execute("""UPDATE movimientos SET fecha=?, concepto=?, monto=?, metodo=?, clasificacion=?, tipo=?, sucursal=?, comentario=? WHERE id=? AND usuario_id=?""", 
            (datos['fecha'], datos['concepto'], datos['monto'], datos['metodo'], datos['clasificacion'], datos['tipo'], datos.get('sucursal'), datos.get('comentario'), id, current_user.id))
        
        # Si era un abono, actualizamos el saldo de su cuenta
        if cuenta_id: 
            recalcular_monto_abonado(cursor, cuenta_id, current_user.id)
            
        conn.commit()
        return jsonify({"mensaje": "Actualizado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/movimiento/<int:id>', methods=['DELETE'])
@login_required
def delete_movimiento(id):
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        conn = database.create_connection(); cursor = conn.cursor()
        
        # Saber si pertenecía a una cuenta antes de borrar
        cursor.execute("SELECT cuenta_id FROM movimientos WHERE id=? AND usuario_id=?", (id, current_user.id))
        row = cursor.fetchone()
        cuenta_id = row[0] if row else None

        cursor.execute("DELETE FROM movimientos WHERE id = ? AND usuario_id = ?", (id, current_user.id))
        
        # Si era abono, recalcular la deuda para que vuelva a subir
        if cuenta_id: 
            recalcular_monto_abonado(cursor, cuenta_id, current_user.id)
            
        conn.commit()
        return jsonify({"mensaje": "Eliminado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# ================= API CUENTAS =================
@app.route('/api/cuentas', methods=['GET'])
@login_required
def get_cuentas():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        conn = database.create_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT * FROM cuentas_por_pagar WHERE usuario_id = ? ORDER BY fecha_credito DESC", (current_user.id,))
        rows = cursor.fetchall()
        return jsonify([dict(row) for row in rows])
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/cuentas', methods=['POST'])
@login_required
def add_cuenta():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    datos = request.json
    try:
        conn = database.create_connection(); cursor = conn.cursor()
        cursor.execute("""INSERT INTO cuentas_por_pagar (proveedor, fecha_credito, monto_total, fecha_limite, usuario_id) VALUES (?, ?, ?, ?, ?)""", 
            (datos['proveedor'], datos['fecha_credito'], datos['monto_total'], datos.get('fecha_limite'), current_user.id))
        conn.commit()
        return jsonify({"mensaje": "Cuenta creada", "id": cursor.lastrowid}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- MODIFICAR CUENTA PRINCIPAL ---
@app.route('/api/cuentas/<int:id>', methods=['PUT'])
@login_required
def update_cuenta(id):
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    datos = request.json
    try:
        conn = database.create_connection(); cursor = conn.cursor()
        
        # Consultar cuánto se ha abonado hasta ahora para recalcular si ya se pagó
        cursor.execute("SELECT monto_abonado FROM cuentas_por_pagar WHERE id=? AND usuario_id=?", (id, current_user.id))
        row = cursor.fetchone()
        if not row: return jsonify({"error": "Cuenta no encontrada"}), 404
        monto_abonado = row[0]
        
        nuevo_total = float(datos['monto_total'])
        # Si el nuevo total es menor o igual a lo que ya se pagó, la cuenta pasa a estado 'Pagado'
        estado = 'Pagado' if monto_abonado >= (nuevo_total - 0.01) else 'Pendiente'
        
        cursor.execute("""UPDATE cuentas_por_pagar 
                          SET proveedor=?, fecha_credito=?, monto_total=?, fecha_limite=?, estado=? 
                          WHERE id=? AND usuario_id=?""", 
            (datos['proveedor'], datos['fecha_credito'], nuevo_total, datos.get('fecha_limite'), estado, id, current_user.id))
        conn.commit()
        return jsonify({"mensaje": "Cuenta actualizada con éxito"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- ELIMINAR CUENTA CON CASCADA ---
@app.route('/api/cuentas/<int:id>', methods=['DELETE'])
@login_required
def delete_cuenta(id):
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        conn = database.create_connection()
        cursor = conn.cursor()
        
        # NUEVO: Eliminación en cascada. Borra primero los movimientos (abonos) relacionados a esta cuenta.
        cursor.execute("DELETE FROM movimientos WHERE cuenta_id = ? AND usuario_id = ?", (id, current_user.id))
        
        # Se elimina asegurando que pertenezca al usuario activo para seguridad
        cursor.execute("DELETE FROM cuentas_por_pagar WHERE id = ? AND usuario_id = ?", (id, current_user.id))
        
        conn.commit()
        return jsonify({"mensaje": "Cuenta y abonos eliminados correctamente"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- OBTENER HISTORIAL DE ABONOS ---
@app.route('/api/cuentas/<int:id>/abonos', methods=['GET'])
@login_required
def get_abonos_cuenta(id):
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        conn = database.create_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute("SELECT * FROM movimientos WHERE cuenta_id = ? AND usuario_id = ? ORDER BY fecha DESC", (id, current_user.id))
        return jsonify([dict(row) for row in cursor.fetchall()])
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/abono', methods=['POST'])
@login_required
def add_abono():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    datos = request.json
    try:
        conn = database.create_connection(); cursor = conn.cursor()
        # Verificar propiedad antes de abonar
        cursor.execute("SELECT proveedor FROM cuentas_por_pagar WHERE id = ? AND usuario_id = ?", (datos['cuenta_id'], current_user.id))
        row = cursor.fetchone()
        if not row: return jsonify({"error": "Cuenta no encontrada"}), 404
        proveedor = row[0]

        cursor.execute("UPDATE cuentas_por_pagar SET monto_abonado = monto_abonado + ? WHERE id = ?", (datos['monto_abono'], datos['cuenta_id']))
        
        fecha_hoy = datetime.date.today().isoformat()
        concepto = f"Abono a {proveedor} (Deuda ID: {datos['cuenta_id']})"
        monto_negativo = -abs(float(datos['monto_abono']))
        
        cursor.execute("""INSERT INTO movimientos (fecha, concepto, tipo, monto, metodo, clasificacion, cuenta_id, usuario_id) VALUES (?, ?, 'egreso', ?, ?, 'compra', ?, ?)""", 
            (fecha_hoy, concepto, monto_negativo, datos['metodo'], datos['cuenta_id'], current_user.id))
        
        # Para evitar desfases, recalculamos todo con nuestra nueva función por seguridad extra
        recalcular_monto_abonado(cursor, datos['cuenta_id'], current_user.id)
        
        conn.commit()
        return jsonify({"mensaje": "Abono registrado"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/saldar', methods=['POST'])
@login_required
def saldar_cuenta():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    datos = request.json
    try:
        conn = database.create_connection(); cursor = conn.cursor()
        cursor.execute("SELECT proveedor FROM cuentas_por_pagar WHERE id = ? AND usuario_id = ?", (datos['cuenta_id'], current_user.id))
        row = cursor.fetchone()
        if not row: return jsonify({"error": "Cuenta no encontrada"}), 404
        proveedor = row[0]

        fecha_hoy = datetime.date.today().isoformat()
        concepto = f"Liquidación de deuda {proveedor} (Deuda ID: {datos['cuenta_id']})"
        monto_negativo = -abs(float(datos['saldo_a_pagar']))
        
        cursor.execute("""INSERT INTO movimientos (fecha, concepto, tipo, monto, metodo, clasificacion, cuenta_id, usuario_id) VALUES (?, ?, 'egreso', ?, ?, 'compra', ?, ?)""",
            (fecha_hoy, concepto, monto_negativo, datos['metodo'], datos['cuenta_id'], current_user.id))
        
        # Volvemos a usar la función que creamos para asegurar un cierre exacto en la DB
        recalcular_monto_abonado(cursor, datos['cuenta_id'], current_user.id)
        
        conn.commit()
        return jsonify({"mensaje": "Cuenta saldada"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

# ================= LÓGICA DE EXPORTACIÓN (FILTRADA) =================
# NOTA: Las funciones de exportación filtran por usuario_id para privacidad.

def get_filtered_movs(filters):
    conn = database.create_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = "SELECT * FROM movimientos WHERE usuario_id = ?"
    clauses, params = [], [current_user.id]

    if filters.get('fecha_inicio'): clauses.append("fecha >= ?"); params.append(filters['fecha_inicio'])
    if filters.get('fecha_fin'): clauses.append("fecha <= ?"); params.append(filters['fecha_fin'])
    if filters.get('concepto'): clauses.append("concepto LIKE ?"); params.append(f"%{filters['concepto']}%")
    if filters.get('tipos'):
        tipos = filters['tipos'].split(',')
        subclauses = []
        if 'ingreso' in tipos: subclauses.append("tipo = 'ingreso'")
        egresos = [t for t in tipos if t != 'ingreso']
        if egresos: subclauses.append(f"clasificacion IN ({','.join(['?']*len(egresos))})"); params.extend(egresos)
        if subclauses: clauses.append(f"({' OR '.join(subclauses)})")
        else: clauses.append("1=0")

    if clauses: query += " AND " + " AND ".join(clauses)
    query += " ORDER BY fecha ASC, id ASC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_filtered_cuentas(filters):
    conn = database.create_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = "SELECT * FROM cuentas_por_pagar WHERE usuario_id = ?"
    clauses, params = [], [current_user.id]

    if filters.get('fecha_inicio'): clauses.append("fecha_credito >= ?"); params.append(filters['fecha_inicio'])
    if filters.get('fecha_fin'): clauses.append("fecha_credito <= ?"); params.append(filters['fecha_fin'])
    if filters.get('proveedor'): clauses.append("proveedor LIKE ?"); params.append(f"%{filters['proveedor']}%")

    if clauses: query += " AND " + " AND ".join(clauses)
    query += " ORDER BY fecha_credito DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def fmt_curr(val):
    try: return f"${float(val):,.2f}"
    except: return "$0.00"

@app.route('/api/exportar/excel')
@login_required
def export_excel():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        data = get_filtered_movs(request.args.to_dict())
        if not data: return jsonify({"error": "No hay datos"}), 404
        
        df = pd.DataFrame(data)
        df['monto'] = pd.to_numeric(df['monto'])
        
        bal_efectivo, bal_banco = 0, 0
        col_efec, col_banco, col_acum = [], [], []
        
        for idx, row in df.iterrows():
            m = row['monto']
            if row['metodo'] == 'Efectivo': bal_efectivo += m
            elif row['metodo'] == 'Tarjeta': bal_banco += m
            col_efec.append(bal_efectivo)
            col_banco.append(bal_banco)
            col_acum.append(bal_efectivo + bal_banco)

        df['Efectivo'], df['Banco'], df['Acumulado'] = col_efec, col_banco, col_acum
        df['Ingreso'] = df.apply(lambda r: r['monto'] if r['monto'] > 0 else '', axis=1)
        df['Egreso'] = df.apply(lambda r: r['monto'] if r['monto'] < 0 else '', axis=1)
        
        final_df = df[['fecha', 'concepto', 'Ingreso', 'Egreso', 'metodo', 'Efectivo', 'Banco', 'Acumulado']]
        final_df.rename(columns={'metodo': 'Método'}, inplace=True)

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer: final_df.to_excel(writer, index=False)
        out.seek(0)
        return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='Reporte_Financiero.xlsx')
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/exportar/pdf')
@login_required
def export_pdf():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        data = get_filtered_movs(request.args.to_dict())
        if not data: return jsonify({"error": "No hay datos"}), 404

        pdf = FPDF('L', 'mm', 'Letter')
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 10, f'Flujo de Ingresos y Egresos - Usuario: {current_user.nombre}', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        pdf.ln(5)
        
        pdf.set_font('Helvetica', 'B', 8)
        w = [22, 55, 22, 22, 22, 22, 22, 22]
        headers = ['Fecha', 'Concepto', 'Ingreso', 'Egreso', '', 'Efectivo', 'Banco', 'Acumulado']
        for i, h in enumerate(headers): pdf.cell(w[i], 10, h, 1, 0, 'C' if i<2 else 'R')
        pdf.ln()

        pdf.set_font('Helvetica', '', 8)
        bal_efec, bal_banc = 0, 0
        
        for row in data:
            m = float(row['monto'])
            if row['metodo'] == 'Efectivo': bal_efec += m
            elif row['metodo'] == 'Tarjeta': bal_banc += m
            
            bal_total = bal_efec + bal_banc

            pdf.cell(w[0], 6, str(row['fecha']), 1)
            pdf.cell(w[1], 6, str(row['concepto'])[:35], 1)
            pdf.cell(w[2], 6, fmt_curr(m) if m>0 else '', 1, 0, 'R')
            pdf.cell(w[3], 6, fmt_curr(m) if m<0 else '', 1, 0, 'R')
            pdf.cell(w[4], 6, row['metodo'], 1, 0, 'C')
            pdf.cell(w[5], 6, fmt_curr(bal_efec), 1, 0, 'R')
            pdf.cell(w[6], 6, fmt_curr(bal_banc), 1, 0, 'R')
            pdf.cell(w[7], 6, fmt_curr(bal_total), 1, 0, 'R')
            pdf.ln()

        res = make_response(bytes(pdf.output()))
        res.headers['Content-Type'] = 'application/pdf'
        res.headers['Content-Disposition'] = 'attachment; filename=Reporte.pdf'
        return res
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/exportar/cuentas/excel')
@login_required
def export_cuentas_excel():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        data = get_filtered_cuentas(request.args.to_dict())
        if not data: return jsonify({"error": "No hay datos"}), 404
        
        df = pd.DataFrame(data)
        df['monto_total'] = pd.to_numeric(df['monto_total'])
        df['monto_abonado'] = pd.to_numeric(df['monto_abonado'])
        df['Saldo'] = df['monto_total'] - df['monto_abonado']
        df['Estado'] = df.apply(lambda r: 'Pagado' if r['Saldo'] <= 0.01 or r['estado'] == 'Pagado' else 'Pendiente', axis=1)
        
        final = df[['fecha_credito', 'proveedor', 'fecha_limite', 'monto_total', 'monto_abonado', 'Saldo', 'Estado']]
        final.columns = ['Fecha', 'Proveedor', 'Vencimiento', 'Total', 'Abonado', 'Saldo', 'Estado']
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer: final.to_excel(writer, index=False)
        out.seek(0)
        return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='Cuentas.xlsx')
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/exportar/cuentas/pdf')
@login_required
def export_cuentas_pdf():
    if current_user.rol != 'jefe': return jsonify({"error": "Acceso denegado"}), 403
    try:
        data = get_filtered_cuentas(request.args.to_dict())
        if not data: return jsonify({"error": "No hay datos"}), 404

        pdf = FPDF('P', 'mm', 'Letter')
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 10, 'Reporte de Cuentas por Pagar', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        pdf.ln(5)
        
        pdf.set_font('Helvetica', 'B', 9)
        w = [25, 50, 25, 25, 25, 25]
        headers = ['Fecha', 'Proveedor', 'Vence', 'Total', 'Saldo', 'Estado']
        for i, h in enumerate(headers): pdf.cell(w[i], 7, h, 1, 0, 'C')
        pdf.ln()
        
        pdf.set_font('Helvetica', '', 8)
        for row in data:
            tot = float(row['monto_total'])
            abn = float(row['monto_abonado'])
            sal = tot - abn
            est = 'Pagado' if sal <= 0.01 or row['estado'] == 'Pagado' else 'Pendiente'
            
            pdf.cell(w[0], 6, str(row['fecha_credito']), 1)
            pdf.cell(w[1], 6, str(row['proveedor'])[:25], 1)
            pdf.cell(w[2], 6, str(row.get('fecha_limite') or '-'), 1, 0, 'C')
            pdf.cell(w[3], 6, fmt_curr(tot), 1, 0, 'R')
            pdf.cell(w[4], 6, fmt_curr(sal), 1, 0, 'R')
            pdf.cell(w[5], 6, est, 1, 1, 'C')
            
        res = make_response(bytes(pdf.output()))
        res.headers['Content-Type'] = 'application/pdf'
        res.headers['Content-Disposition'] = 'attachment; filename=Cuentas.pdf'
        return res
    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    conn = database.create_connection()
    if conn: database.create_tables(conn); conn.close()
    app.run(host='0.0.0.0', port=5000, debug=True)