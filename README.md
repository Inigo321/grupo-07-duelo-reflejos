# Duelo de Reflejos — Raspberry Pi 5

Juego de tiempo de reacción para dos jugadores con dos módulos Grove LED Button,
dashboard web en tiempo real (Flask) e histórico en SQLite.
Proyecto de Arquitectura de Computadores (paralelismo y E/S).

## Estructura

| Fichero | Qué es |
|---|---|
| `main.py` | Crea los objetos compartidos y lanza los 3 procesos |
| `juego.py` | **Proceso 1**: hardware + lógica del juego (4 hilos) |
| `web.py` + `templates/index.html` | **Proceso 2**: servidor web Flask |
| `registro.py` | **Proceso 3**: guarda cada ronda en SQLite |
| `config.py` | Pines GPIO y parámetros |
| `prueba_hardware.py` | Prueba del cableado |

## 1. Conexión del hardware

> ⚠️ Haz las conexiones con la Raspberry **apagada y desenchufada**.
> Alimenta los módulos a **3,3 V, nunca a 5 V**: los GPIO de la Raspberry no
> toleran 5 V y el pulsador devolvería 5 V al pin.

Cada módulo Grove LED Button tiene 4 cables:

| Cable Grove | Señal | Función |
|---|---|---|
| Amarillo | SIG1 | LED (salida) |
| Blanco | SIG2 | Pulsador (entrada, 0 V al pulsar) |
| Rojo | VCC | Alimentación 3,3 V |
| Negro | GND | Masa |

Conexión al conector de 40 pines (número de **pin físico** y nombre **BCM**):

| Módulo | Amarillo (LED) | Blanco (pulsador) | Rojo (3V3) | Negro (GND) |
|---|---|---|---|---|
| Jugador 1 | pin 11 (GPIO17) | pin 13 (GPIO27) | pin 1 | pin 9 |
| Jugador 2 | pin 15 (GPIO22) | pin 16 (GPIO23) | pin 17 | pin 14 |

```
              Conector GPIO (vista superior, USB/Ethernet abajo)
     3V3  [ 1] [ 2] 5V        <- pin 1: rojo J1   (¡no usar 5V!)
          [ 3] [ 4] 5V
          [ 5] [ 6] GND
          [ 7] [ 8]
     GND  [ 9] [10]           <- pin 9: negro J1
  GPIO17  [11] [12]           <- pin 11: amarillo J1 (LED)
  GPIO27  [13] [14] GND       <- pin 13: blanco J1 (botón) | pin 14: negro J2
  GPIO22  [15] [16] GPIO23    <- pin 15: amarillo J2 (LED) | pin 16: blanco J2 (botón)
     3V3  [17] [18]           <- pin 17: rojo J2
```

El pin 1 es el del cuadrado en la serigrafía, en la esquina más alejada de los
puertos USB. Si los cables Grove acaban en conector hembra, se enchufan
directamente al pin; si acaban en macho, usad los cables jumper macho-hembra o
una protoboard.

## 2. Preparar la Raspberry Pi 5

1. Con **Raspberry Pi Imager** graba en la microSD **Raspberry Pi OS (64-bit)**.
   En "Editar ajustes" pon nombre de host (`raspberrypi`), usuario y contraseña,
   la WiFi y en "Servicios" activa **SSH**.
2. Mete la tarjeta, conecta los módulos y alimenta la Pi con la fuente oficial
   USB-C de 27 W.
3. Desde el portátil: `ssh usuario@raspberrypi.local`
   - Si la red de la universidad no deja ver la Pi, usad el **hotspot del móvil**
     para los dos equipos, o conectad la Pi al portátil con el cable Ethernet.
4. Instala las dependencias (gpiozero y lgpio ya vienen con el sistema; en la
   Pi 5 **no funciona RPi.GPIO**, por eso usamos gpiozero):

   ```bash
   sudo apt update
   sudo apt install -y python3-gpiozero python3-lgpio python3-flask git
   ```

5. Copia el proyecto a la Pi (con `git clone <url-del-repo>` o desde el portátil
   con `scp -r reflejos usuario@raspberrypi.local:~`).

## 3. Ejecutar

```bash
cd ~/reflejos
python3 prueba_hardware.py   # 1º: comprobar LEDs y pulsadores
python3 main.py              # 2º: el proyecto
```

Abre en el navegador del portátil o del móvil `http://raspberrypi.local:5000`
(o la IP que imprime `main.py`). Para parar: `Ctrl+C`.

**Cómo se juega:** pulsa cualquier botón (o "Iniciar ronda" en la web). Los LEDs
parpadean 3 veces, se apagan y tras un tiempo aleatorio de 2 a 5 s se encienden:
gana quien pulse antes. Si alguien pulsa con los LEDs apagados, es falsa salida
y pierde la ronda.

**Sin Raspberry** (para programar en el portátil): `pip install flask gpiozero` y
`SIMULADO=1 python3 main.py`. La web muestra botones para simular los pulsadores.

## Problemas típicos

| Síntoma | Solución |
|---|---|
| El LED no se enciende pero el botón sí responde (o al revés) | Intercambia amarillo y blanco o los números en `config.py` |
| `GPIO busy` | Hay otro programa usando los pines: ciérralo (`pkill -f main.py`) |
| `Address already in use` | El puerto 5000 está ocupado: cambia `PUERTO_WEB` en `config.py` |
| No se abre la web | Revisa que portátil y Pi estén en la misma red |

## Concurrencia (resumen)

- **P1 juego**: hilo principal (máquina de estados, dueño único de los LEDs),
  hilos `pulsador-J1` y `pulsador-J2` (bloqueados en `wait_for_press`,
  despertados por la interrupción del GPIO) e hilo `comandos` (órdenes de la web).
  Se comunican con una `queue.Queue` y un `threading.Event`.
- **P2 web**: Flask con `threaded=True`.
- **P3 registro**: escribe en SQLite sin bloquear el juego.
- Entre procesos: `multiprocessing.Queue` (web→juego y juego→registro),
  `Manager().dict()` + `multiprocessing.Lock` para el estado del juego, y un
  `multiprocessing.Event` para la parada ordenada.
