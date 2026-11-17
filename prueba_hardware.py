"""Prueba rápida del cableado ANTES de lanzar el proyecto.

Cada LED parpadea 2 veces y después, durante 20 s, al pulsar un botón se
enciende su LED. Si no funciona, revisa los pines de config.py.

Ejecutar:  python3 prueba_hardware.py
"""
import time

from gpiozero import LED, Button

import config

leds = {1: LED(config.J1_LED), 2: LED(config.J2_LED)}
botones = {1: Button(config.J1_BOTON, pull_up=True, bounce_time=config.REBOTE),
           2: Button(config.J2_BOTON, pull_up=True, bounce_time=config.REBOTE)}

for j in (1, 2):
    print(f"LED del jugador {j} (GPIO{leds[j].pin.number}) parpadeando...")
    leds[j].blink(on_time=0.3, off_time=0.3, n=2, background=False)

print("Pulsa los botones durante 20 s (cada uno enciende su LED)")
fin = time.time() + 20
estado_previo = {1: False, 2: False}
while time.time() < fin:
    for j in (1, 2):
        pulsado = botones[j].is_pressed
        leds[j].value = pulsado
        if pulsado != estado_previo[j]:
            print(f"Botón {j}: {'PULSADO' if pulsado else 'suelto'}")
            estado_previo[j] = pulsado
    time.sleep(0.01)
print("Prueba terminada")
