import requests
import threading
import time

# ==========================================
# 1. PON AQUÍ TU LINK ACTUAL DE TELEGRAM
# ==========================================
URL_DESTINO = " https://prime-helen-lawn-fotos.trycloudflare.com"

# Cantidad de "usuarios" falsos que entrarán al mismo tiempo
NUM_USUARIOS = 50

# Estadísticas para ver el resultado final
exitosos = 0
fallidos = 0

def simular_usuario(id_usuario):
    global exitosos, fallidos
    try:
        # Simulamos que el usuario entra a la página web
        inicio = time.time()
        respuesta = requests.get(URL_DESTINO, timeout=15)
        fin = time.time()
        
        tiempo_tardado = round(fin - inicio, 2)
        
        # Si el servidor responde con 200, significa "Todo OK"
        if respuesta.status_code == 200:
            print(f"✅ Usuario {id_usuario:02d} cargó la página en {tiempo_tardado} segs.")
            exitosos += 1
        else:
            print(f"⚠️ Usuario {id_usuario:02d} recibió un error: {respuesta.status_code}")
            fallidos += 1
            
    except Exception as e:
        print(f"❌ Usuario {id_usuario:02d} no pudo conectar: {e}")
        fallidos += 1

if __name__ == "__main__":
    print(f"🚀 Iniciando ataque simulado de {NUM_USUARIOS} usuarios a:")
    print(f"👉 {URL_DESTINO}\n")
    
    hilos = []
    tiempo_inicio_total = time.time()

    # Creamos a los 50 usuarios falsos (hilos)
    for i in range(1, NUM_USUARIOS + 1):
        hilo = threading.Thread(target=simular_usuario, args=(i,))
        hilos.append(hilo)
        hilo.start()

    # Esperamos a que todos los usuarios terminen de cargar la página
    for hilo in hilos:
        hilo.join()

    tiempo_fin_total = time.time()
    tiempo_total = round(tiempo_fin_total - tiempo_inicio_total, 2)

    print("\n" + "="*40)
    print("📊 RESULTADOS DE LA PRUEBA DE ESTRÉS")
    print("="*40)
    print(f"⏱️ Tiempo total de la prueba : {tiempo_total} segundos")
    print(f"✅ Conexiones exitosas       : {exitosos}")
    print(f"❌ Conexiones fallidas       : {fallidos}")
    print("="*40)
    print("Si tuviste 0 fallidas, ¡tu servidor Gunicorn está trabajando perfecto!")