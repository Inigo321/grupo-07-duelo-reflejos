# Duelo de Memoria — Raspberry Pi 5

Juego de memoria para dos jugadores con dos módulos Grove LED Button: los LEDs
muestran una secuencia que crece y se acelera en cada nivel, los dos jugadores
la repiten juntos y **pierde quien falle**. Tiene tres modos (normal, al revés y
cruzado), dashboard web en tiempo real (Flask) e histórico en SQLite.
Proyecto de Arquitectura de Computadores (paralelismo y E/S).

## Estructura

| Fichero | Qué es |
|---|---|
| `main.py` | Crea los objetos compartidos y lanza los 3 procesos |
| `juego.py` | **Proceso 1**: hardware + lógica del juego (5 hilos) |
| `web.py` + `templates/index.html` | **Proceso 2**: servidor web Flask |
| `registro.py` | **Proceso 3**: guarda cada partida en SQLite (`memoria.db`) |
| `config.py` | Pines GPIO, modos y parámetros del juego |
| `prueba_hardware.py` | Prueba del cableado |
| `diagrama_bloques.png` | Procesos, hilos y cómo se comunican |

## 1. Conexión del hardware

> ⚠️ Haz las conexiones con la Raspberry **apagada y desenchufada**.
> Alimenta los módulos LED Button a **3,3 V, nunca a 5 V**: los GPIO de la
> Raspberry no toleran 5 V y el pulsador devolvería 5 V al pin.

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

**Zumbador (Grove Buzzer):** pita cuando los jugadores completan bien una
secuencia. Amarillo (SIG) al **pin 18 (GPIO24)**, rojo (VCC) al **pin 4 (5 V)**,
negro al **pin 20 (GND)** y el blanco sin conectar. Al zumbador sí se le puede
dar 5 V (suena más fuerte): solo recibe la señal de la Raspberry y no le
devuelve tensión, al contrario que los pulsadores. Si no tenéis zumbador, poned
`ZUMBADOR = None` en `config.py` y el juego funciona igual.

```
              Conector GPIO (vista superior, USB/Ethernet abajo)
     3V3  [ 1] [ 2] 5V        <- pin 1: rojo J1   (¡no usar 5V!)
          [ 3] [ 4] 5V        <- pin 4: rojo zumbador (el zumbador sí admite 5V)
          [ 5] [ 6] GND
          [ 7] [ 8]
     GND  [ 9] [10]           <- pin 9: negro J1
  GPIO17  [11] [12]           <- pin 11: amarillo J1 (LED)
  GPIO27  [13] [14] GND       <- pin 13: blanco J1 (botón) | pin 14: negro J2
  GPIO22  [15] [16] GPIO23    <- pin 15: amarillo J2 (LED) | pin 16: blanco J2 (botón)
     3V3  [17] [18] GPIO24    <- pin 17: rojo J2 | pin 18: amarillo zumbador
          [19] [20] GND       <- pin 20: negro zumbador
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
python3 prueba_hardware.py   # 1º: comprobar LEDs, pulsadores y zumbador
python3 main.py              # 2º: el proyecto
```

Abre en el navegador del portátil o del móvil `http://raspberrypi.local:5000`
(o la IP que imprime `main.py`). Para parar: `Ctrl+C`.

### Cómo se juega

1. **Preparados:** cada jugador pulsa su botón y su LED se queda encendido.
   Cuando están **los dos**, empieza la partida (si el segundo no pulsa en 5 s,
   se cancela). También se puede empezar con "Iniciar partida" en la web.
2. Tras la cuenta atrás (los LEDs parpadean 3 veces), los LEDs muestran una
   secuencia, p. ej. `J1, J2, J2` (empieza con 2 pasos).
3. Los dos jugadores la repiten **juntos y en orden**, cada uno con su botón,
   según el modo elegido. Al acertar, el LED de quien ha pulsado da un destello.
4. Si la completan, se encienden los dos LEDs y **el zumbador da un doble
   pitido**; la secuencia crece un paso y se vuelve a mostrar **cada vez más
   rápido** (de 0,5 s a 0,2 s por LED).
5. La partida acaba cuando alguien falla, y **el otro jugador gana el punto**:
   - pulsar cuando le tocaba al rival → falla quien pulsó;
   - nadie pulsa en 2,5 s → falla aquel a quien le tocaba.

| Modo | Qué hay que pulsar | Ejemplo: se encienden `J1, J2, J2` |
|---|---|---|
| **Normal** | La secuencia tal cual | J1, J2, J2 |
| **Al revés** | La secuencia del último paso al primero | J2, J2, J1 |
| **Cruzado** | Cada uno pulsa cuando se encendió el LED de su **rival** | J2, J1, J1 |

El modo se elige en la web y se aplica al acabar la partida en curso. Se guarda
en la base de datos la secuencia alcanzada, quién falló y por qué, los aciertos
de cada uno y su tiempo medio por pulsación. La web muestra el récord de cada
modo y, al acabar, revela la secuencia marcando el paso fallado. Durante la
partida la web refleja los LEDs (LEDs virtuales) pero no la secuencia: solo
cuántos pasos llevan. La casilla "Pitar también en la web" hace que el navegador
reproduzca el mismo pitido al acertar (activada en modo simulado, donde no hay
zumbador). Los tiempos se ajustan en `config.py`.

**Sin Raspberry** (para programar en el portátil): `pip install flask gpiozero` y
`SIMULADO=1 python3 main.py`. La web muestra botones para simular los pulsadores
(o las teclas **A** y **L**; **Espacio** inicia la partida) y los LEDs virtuales.

## Problemas típicos

| Síntoma | Solución |
|---|---|
| El LED no se enciende pero el botón sí responde (o al revés) | Intercambia amarillo y blanco o los números en `config.py` |
| `GPIO busy` | Hay otro programa usando los pines: ciérralo (`pkill -f main.py`) |
| `Address already in use` | El puerto 5000 está ocupado: cambia `PUERTO_WEB` en `config.py` |
| No se abre la web | Revisa que portátil y Pi estén en la misma red |

## Concurrencia

### Proceso 1 (juego): 5 hilos

| Hilo | Qué hace | Cómo se comunica |
|---|---|---|
| `principal` | Árbitro: máquina de estados de la partida (preparados → mostrar → repetir → resultado) | Lee `cola_pulsaciones`, escribe en `cola_leds`, publica el estado |
| `leds` | **Único dueño de los LEDs y del zumbador**: ejecuta las animaciones (secuencia, destellos, parpadeos) y el pitido de acierto | Consume `cola_leds`; avisa con `task_done()` |
| `pulsador-J1`, `pulsador-J2` | Duermen en `wait_for_press` hasta que la **interrupción** del GPIO los despierta | Meten `(jugador, instante)` en `cola_pulsaciones` |
| `comandos` | Recibe las órdenes de la web | `threading.Event` (iniciar) y `modo_pedido` |

- **Dos colas, en sentidos opuestos.** Los pulsadores *producen* pulsaciones
  que consume el principal; el principal *produce* órdenes de LEDs que consume
  el hilo `leds`. Así el árbitro no se bloquea mientras un LED se anima: tras un
  acierto encarga el destello y sigue esperando la siguiente pulsación.
- **`Queue.join()` + `task_done()`** para sincronizar: cuando el principal
  necesita que la secuencia haya terminado de mostrarse antes de dejar pulsar,
  llama a `cola_leds.join()` y se bloquea hasta que el hilo `leds` ha procesado
  todo lo pendiente.
- **Instante de cada pulsación:** lo toma el hilo del pulsador al despertar, no
  el principal al sacarla de la cola, así el límite de 2,5 s y los tiempos por
  pulsación son exactos aunque el principal esté ocupado.
- El hilo `comandos` solo *pide* el cambio de modo (`modo_pedido`); lo aplica el
  principal entre partidas, para que nunca cambie a mitad de una.

### Entre procesos

- **P2 web**: Flask con `threaded=True` (un hilo por petición).
- **P3 registro**: escribe en SQLite sin bloquear el juego; al parar, guarda lo
  que quede en la cola antes de cerrar.
- `multiprocessing.Queue` (web → juego y juego → registro), `Manager().dict()`
  \+ `multiprocessing.Lock` para el estado del juego (fase, LEDs, marcador,
  récords), y un `multiprocessing.Event` para la parada ordenada.
