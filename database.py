import sqlite3
from sqlite3 import Error
import os 
from werkzeug.security import generate_password_hash

# Definir ruta absoluta para la base de datos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "financiero.db")

def create_connection():
    """ Crea conexión a la base de datos SQLite """
    conn = None
    try:
        # SOLUCIÓN RENDIMIENTO: Agregamos timeout=15.0
        # Si la base de datos se traba, a los 15 segundos se libera sola en lugar de congelar la app.
        conn = sqlite3.connect(DB_PATH, timeout=15.0) 
        # Habilitar claves foráneas (Vital para la integridad de datos)
        conn.execute("PRAGMA foreign_keys = ON;")
    except Error as e:
        print(f"Error al conectar con SQLite: {e}")
    return conn

def create_tables(conn):
    cursor = conn.cursor()

    # 1. Tabla USUARIOS (Con Jerarquía)
    # jefe_id: Permite saber quién creó a este usuario (Ej: Admin -> Jefe -> Gerente)
    sql_create_users = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        nombre TEXT,
        rol TEXT NOT NULL,
        jefe_id INTEGER, 
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (jefe_id) REFERENCES usuarios (id) ON DELETE SET NULL
    );
    """
    
    # 2. Tabla Cuentas por Pagar (Ahora con Dueño)
    sql_create_cuentas = """
    CREATE TABLE IF NOT EXISTS cuentas_por_pagar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor TEXT NOT NULL,
        fecha_credito DATE NOT NULL,
        monto_total REAL NOT NULL,
        monto_abonado REAL DEFAULT 0.0,
        estado TEXT NOT NULL DEFAULT 'Pendiente',
        fecha_limite DATE,
        usuario_id INTEGER, -- CRUCIAL: Para separar las deudas de cada Jefe
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
    );
    """
    
    # 3. Tabla Movimientos (Finanzas)
    sql_create_movimientos = """
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATE NOT NULL,
        concepto TEXT NOT NULL,
        tipo TEXT NOT NULL,
        monto REAL NOT NULL,
        metodo TEXT NOT NULL,
        clasificacion TEXT DEFAULT 'N/A',
        sucursal TEXT,
        comentario TEXT,
        cuenta_id INTEGER,
        usuario_id INTEGER, -- El dueño del movimiento
        FOREIGN KEY (cuenta_id) REFERENCES cuentas_por_pagar (id) ON DELETE SET NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
    );
    """

    # 4. Tabla Inventario (Preparada para el futuro)
    sql_create_inventario = """
    CREATE TABLE IF NOT EXISTS inventario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_producto TEXT NOT NULL,
        fecha_caducidad DATE,
        cantidad_existencia INTEGER NOT NULL DEFAULT 0,
        cantidad_minima INTEGER NOT NULL DEFAULT 5,
        usuario_id INTEGER NOT NULL, -- Dueño del inventario (Jefe)
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
    );
    """

    # 5. Tabla Reservaciones (Preparada para el futuro)
    sql_create_reservaciones = """
    CREATE TABLE IF NOT EXISTS reservaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_hora DATETIME NOT NULL,
        mesa INTEGER,
        num_personas INTEGER NOT NULL,
        responsable TEXT NOT NULL,
        cumpleanos BOOLEAN DEFAULT 0,
        usuario_id INTEGER NOT NULL, -- Dueño de la reserva (Jefe)
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
    );
    """

    try:
        # Ejecutar creación de tablas
        cursor.execute(sql_create_users)
        cursor.execute(sql_create_cuentas)
        cursor.execute(sql_create_movimientos)
        cursor.execute(sql_create_inventario)
        cursor.execute(sql_create_reservaciones)
        
        # --- CREACIÓN DE USUARIOS POR DEFECTO ---
        
        # 1. Crear Administrador (Si no existe)
        cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
        if not cursor.fetchone():
            pass_hash = generate_password_hash("admin123")
            # El Admin no tiene jefe (None)
            cursor.execute("INSERT INTO usuarios (username, password, nombre, rol, jefe_id) VALUES (?, ?, ?, ?, ?)", 
                          ('admin', pass_hash, 'Administrador General', 'admin', None))
            print(">> Usuario 'admin' creado (Pass: admin123)")

        # 2. Crear Jefe (Si no existe)
        cursor.execute("SELECT * FROM usuarios WHERE username = 'jefe'")
        if not cursor.fetchone():
            pass_hash = generate_password_hash("jefe123")
            # El Jefe tampoco tiene jefe superior en este modelo base (None)
            cursor.execute("INSERT INTO usuarios (username, password, nombre, rol, jefe_id) VALUES (?, ?, ?, ?, ?)", 
                          ('jefe', pass_hash, 'Jefe Operativo', 'jefe', None))
            print(">> Usuario 'jefe' creado (Pass: jefe123)")
            
    except Error as e:
        print(f"Error creando tablas: {e}")

if __name__ == '__main__':
    # Opcional: Descomenta esto si quieres que el script borre la DB vieja automáticamente
    # if os.path.exists(DB_PATH): os.remove(DB_PATH); print("Base de datos anterior eliminada.")

    conn = create_connection()
    if conn:
        create_tables(conn)
        conn.commit()
        print(f"Base de datos actualizada correctamente en: {DB_PATH}")
        conn.close()