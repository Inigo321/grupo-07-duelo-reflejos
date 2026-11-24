"""Configuración del proyecto "Duelo de Memoria".

Pines en numeración BCM (GPIOxx), NO en número físico del conector.
Módulo Grove LED Button: cable amarillo (SIG1) = LED, cable blanco (SIG2) = pulsador.
"""
import os

# --- Jugador 1 (módulo LED-pulsador 1) ---
J1_LED = 17      # cable amarillo -> pin físico 11
J1_BOTON = 27    # cable blanco   -> pin físico 13

# --- Jugador 2 (módulo LED-pulsador 2) ---
J2_LED = 22      # cable amarillo -> pin físico 15
J2_BOTON = 23    # cable blanco   -> pin físico 16

# --- Zumbador (módulo Grove Buzzer): pita al completar bien una secuencia ---
ZUMBADOR = 24    # cable amarillo -> pin físico 18. Poned None si no hay zumbador

# Nombres que se muestran en la web
NOMBRES = {1: "Jugador 1", 2: "Jugador 2"}

# Modos de juego (se eligen en la web). En todos, los LEDs muestran una
# secuencia y los jugadores la repiten; lo que cambia es QUÉ hay que pulsar:
#   "normal" : la misma secuencia, en el mismo orden
#   "inverso": la secuencia al revés, del último paso al primero
#   "cruzado": cada jugador pulsa cuando se encendió el LED de su RIVAL
MODOS = {"normal": "Normal", "inverso": "Al revés", "cruzado": "Cruzado"}
MODO_INICIAL = "normal"

# Parámetros de la partida
LONGITUD_INICIAL = 2      # pasos de la primera secuencia (luego +1 en cada nivel)
T_ENCENDIDO = 0.5         # s que se enciende cada LED al mostrar la secuencia
T_ENCENDIDO_MIN = 0.2     # s mínimos: la secuencia se muestra más rápido en cada nivel
ACELERACION = 0.03        # s que se recorta el encendido por cada nivel superado
T_APAGADO = 0.25          # s de pausa entre dos LEDs de la secuencia
TIEMPO_PASO = 2.5         # s máximos entre una pulsación y la siguiente
TIEMPO_PREPARADOS = 5.0   # s que se espera al segundo jugador antes de cancelar el inicio
REBOTE = 0.02             # s de antirrebote del pulsador

# Base de datos y servidor web
RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria.db")
PUERTO_WEB = 5000

# SIMULADO=1 permite ejecutar todo en un PC sin Raspberry (pines simulados)
SIMULADO = os.environ.get("SIMULADO") == "1"
