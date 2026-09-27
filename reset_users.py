import sqlite3
from werkzeug.security import generate_password_hash
import os

# Asegurar la ruta correcta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "financiero.db")

def reset_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"conectando a: {DB_PATH}")

    # 1. Asegurar que la tabla existe
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        nombre TEXT,
        rol TEXT NOT NULL
    );
    """)

    # 2. Limpiar usuarios viejos (para evitar duplicados o errores de hash)
    cursor.execute("DELETE FROM usuarios")
    print(">> Usuarios anteriores eliminados.")

    # 3. Crear ADMIN
    pass_admin = generate_password_hash("admin123")
    cursor.execute("INSERT INTO usuarios (username, password, nombre, rol) VALUES (?, ?, ?, ?)", 
                  ('admin', pass_admin, 'Administrador General', 'admin'))
    print(">> Usuario 'admin' creado (Clave: admin123)")

    # 4. Crear JEFE
    pass_jefe = generate_password_hash("jefe123")
    cursor.execute("INSERT INTO usuarios (username, password, nombre, rol) VALUES (?, ?, ?, ?)", 
                  ('jefe', pass_jefe, 'Jefe Operativo', 'jefe'))
    print(">> Usuario 'jefe' creado (Clave: jefe123)")

    conn.commit()
    conn.close()
    print("✅ ¡RESETEO COMPLETADO! Intenta iniciar sesión ahora.")

if __name__ == "__main__":
    reset_users()