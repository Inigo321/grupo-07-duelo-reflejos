"""PROCESO 1: control del hardware y lógica del juego.

Dentro de este proceso hay 4 hilos:
  - Hilo principal  : máquina de estados del juego (único dueño de los LEDs).
  - Hilo pulsador-J1: espera (bloqueado) a que se pulse el botón 1.
  - Hilo pulsador-J2: espera (bloqueado) a que se pulse el botón 2.
  - Hilo comandos   : recibe órdenes del servidor web (otro proceso).

Los hilos de pulsadores no tocan el juego: solo meten (jugador, instante)
en una queue.Queue, que es segura entre hilos.
"""
import queue
import random
import threading
import time

import config


def proceso_juego(estado, cerrojo_estado, cola_comandos, cola_resultados, parar):
    try:
        Juego(estado, cerrojo_estado, cola_comandos, cola_resultados, parar).ejecutar()
    except KeyboardInterrupt:
        pass


class Juego:
    def __init__(self, estado, cerrojo_estado, cola_comandos, cola_resultados, parar):
        # Objetos compartidos con otros PROCESOS
        self.estado = estado                  # Manager().dict()
        self.cerrojo_estado = cerrojo_estado  # multiprocessing.Lock
        self.cola_comandos = cola_comandos    # web -> juego
        self.cola_resultados = cola_resultados  # juego -> registro
        self.parar = parar                    # multiprocessing.Event

        # Objetos compartidos entre HILOS de este proceso
        self.cola_pulsaciones = queue.Queue()      # pulsadores -> lógica
        self.peticion_inicio = threading.Event()   # comandos -> lógica
        self.marcador = {1: 0, 2: 0}

        self._iniciar_gpio()

    # ------------------------------------------------------------------ GPIO
    def _iniciar_gpio(self):
        # Se importa aquí para que el GPIO se abra SOLO en este proceso
        from gpiozero import Button, Device, LED
        if config.SIMULADO:
            from gpiozero.pins.mock import MockFactory
            Device.pin_factory = MockFactory()

        self.leds = {1: LED(config.J1_LED), 2: LED(config.J2_LED)}
        # El pulsador Grove es activo a nivel bajo (pulsado = 0 V)
        self.botones = {
            1: Button(config.J1_BOTON, pull_up=True, bounce_time=config.REBOTE),
            2: Button(config.J2_BOTON, pull_up=True, bounce_time=config.REBOTE),
        }

    def _leds(self, encendido):
        for led in self.leds.values():
            led.on() if encendido else led.off()

    # ----------------------------------------------------------------- HILOS
    def hilo_pulsador(self, jugador):
        """Bloqueado en wait_for_press (lo despierta la interrupción del GPIO)."""
        boton = self.botones[jugador]
        while not self.parar.is_set():
            if boton.wait_for_press(timeout=0.5):
                self.cola_pulsaciones.put((jugador, time.perf_counter()))
                boton.wait_for_release()

    def hilo_comandos(self):
        """Recibe órdenes del proceso web a través de una multiprocessing.Queue."""
        while not self.parar.is_set():
            try:
                orden = self.cola_comandos.get(timeout=0.5)
            except queue.Empty:
                continue
            if orden == "iniciar":
                self.peticion_inicio.set()
            elif orden == "reiniciar_marcador":
                self.marcador = {1: 0, 2: 0}
                self._publicar(marcador_j1=0, marcador_j2=0)
            elif orden.startswith("simular:") and config.SIMULADO:
                pin = self.botones[int(orden.split(":")[1])].pin
                pin.drive_low()
                time.sleep(0.1)
                pin.drive_high()

    # ------------------------------------------------------- ESTADO COMPARTIDO
    def _publicar(self, **cambios):
        """Actualiza varias claves del estado de forma atómica (con cerrojo)."""
        with self.cerrojo_estado:
            for clave, valor in cambios.items():
                self.estado[clave] = valor

    # ------------------------------------------------------------ LÓGICA
    def _vaciar_pulsaciones(self):
        while not self.cola_pulsaciones.empty():
            self.cola_pulsaciones.get_nowait()

    def _esperar(self, segundos):
        """Espera 'segundos'; devuelve la primera pulsación si alguien pulsa antes."""
        try:
            return self.cola_pulsaciones.get(timeout=segundos)
        except queue.Empty:
            return None

    def ejecutar(self):
        hilos = [
            threading.Thread(target=self.hilo_pulsador, args=(1,), name="pulsador-J1", daemon=True),
            threading.Thread(target=self.hilo_pulsador, args=(2,), name="pulsador-J2", daemon=True),
            threading.Thread(target=self.hilo_comandos, name="comandos", daemon=True),
        ]
        for h in hilos:
            h.start()

        self._publicar(fase="ESPERANDO", mensaje="Pulsa cualquier botón o 'Iniciar' en la web",
                       marcador_j1=0, marcador_j2=0, ultima=None)
        try:
            while not self.parar.is_set():
                # En reposo: empieza una ronda si llega una petición web o una pulsación
                if self.peticion_inicio.wait(timeout=0.1) or not self.cola_pulsaciones.empty():
                    self.peticion_inicio.clear()
                    self.jugar_ronda()
        finally:
            self._leds(False)

    def jugar_ronda(self):
        # 1) Cuenta atrás: los LEDs parpadean 3 veces
        self._publicar(fase="CUENTA_ATRAS", mensaje="¡Preparados!")
        for _ in range(3):
            self._leds(True); time.sleep(0.25)
            self._leds(False); time.sleep(0.25)
        self._vaciar_pulsaciones()

        # 2) Espera aleatoria: quien pulse aquí hace falsa salida y pierde
        self._publicar(fase="ESPERA", mensaje="Atentos... no pulséis todavía")
        falsa = self._esperar(random.uniform(config.ESPERA_MIN, config.ESPERA_MAX))
        if falsa:
            infractor = falsa[0]
            ganador = 2 if infractor == 1 else 1
            self._terminar_ronda(ganador, {1: None, 2: None}, falsa_salida=infractor)
            return

        # 3) ¡YA! Se encienden los LEDs y se mide el tiempo de reacción
        self._leds(True)
        t0 = time.perf_counter()
        self._publicar(fase="YA", mensaje="¡¡YA!!")
        tiempos = {1: None, 2: None}
        limite = t0 + config.TIEMPO_MAX_REACCION
        while None in tiempos.values():
            restante = limite - time.perf_counter()
            if restante <= 0:
                break
            pulsacion = self._esperar(restante)
            if pulsacion and tiempos[pulsacion[0]] is None:
                tiempos[pulsacion[0]] = round((pulsacion[1] - t0) * 1000, 1)  # ms
        self._leds(False)

        validos = {j: t for j, t in tiempos.items() if t is not None}
        ganador = min(validos, key=validos.get) if validos else None
        self._terminar_ronda(ganador, tiempos, falsa_salida=None)

    def _terminar_ronda(self, ganador, tiempos, falsa_salida):
        if ganador:
            self.marcador[ganador] += 1
        resultado = {
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ganador": ganador,
            "tiempo_j1": tiempos[1],
            "tiempo_j2": tiempos[2],
            "falsa_salida": falsa_salida,
        }
        # Al proceso de registro (escritura en disco, lenta) sin bloquear el juego
        self.cola_resultados.put(resultado)

        if falsa_salida:
            texto = f"¡Falsa salida de {config.NOMBRES[falsa_salida]}! Gana {config.NOMBRES[ganador]}"
        elif ganador:
            texto = f"Gana {config.NOMBRES[ganador]} ({tiempos[ganador]} ms)"
        else:
            texto = "Nadie ha pulsado a tiempo"
        self._publicar(fase="RESULTADO", mensaje=texto, ultima=resultado,
                       marcador_j1=self.marcador[1], marcador_j2=self.marcador[2])

        # El LED del ganador parpadea
        if ganador:
            self.leds[ganador].blink(on_time=0.15, off_time=0.15, n=5, background=False)
        else:
            time.sleep(1.5)
        self._vaciar_pulsaciones()
        self._publicar(fase="ESPERANDO", mensaje="Pulsa cualquier botón o 'Iniciar' para otra ronda")
