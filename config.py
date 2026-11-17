"""Configuración del proyecto "Duelo de Reflejos".

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

# Nombres que se muestran en la web
NOMBRES = {1: "Jugador 1", 2: "Jugador 2"}

# Parámetros del juego
ESPERA_MIN = 2.0          # s mínimos antes de encender los LEDs
ESPERA_MAX = 5.0          # s máximos
TIEMPO_MAX_REACCION = 3.0 # s para pulsar tras encenderse los LEDs
REBOTE = 0.02             # s de antirrebote del pulsador

# Base de datos y servidor web
RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reflejos.db")
PUERTO_WEB = 5000

# SIMULADO=1 permite ejecutar todo en un PC sin Raspberry (pines simulados)
SIMULADO = os.environ.get("SIMULADO") == "1"
