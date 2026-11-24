"""PROCESO 1: control del hardware y lógica del juego "Duelo de Memoria".

El juego: los LEDs muestran una secuencia (J1, J2, J2, J1...) y los dos
jugadores la repiten juntos, cada uno con su botón. Si la completan, la
secuencia crece un paso y se muestra más deprisa. Quien falle (pulsa cuando no
le toca o tarda demasiado) pierde la partida y su rival gana el punto.
Los modos (config.MODOS) cambian qué hay que pulsar: normal, al revés o cruzado.

Dentro de este proceso hay 5 hilos:
  - Hilo principal  : árbitro. Máquina de estados de la partida.
  - Hilo leds       : único dueño de los LEDs y del zumbador. Ejecuta las
                      animaciones y pitidos que le encarga el principal por su
                      propia cola (cola_leds), así el árbitro nunca se queda
                      bloqueado encendiendo LEDs o pitando.
  - Hilo pulsador-J1: duermen en wait_for_press hasta que la interrupción del
  - Hilo pulsador-J2:   GPIO los despierta (sin sondeo), y meten
                        (jugador, instante) en cola_pulsaciones.
  - Hilo comandos   : recibe órdenes del servidor web (otro proceso).
"""
import queue
import random
import threading
import time

import config

RIVAL = {1: 2, 2: 1}

# Qué hay que pulsar en cada modo, a partir de la secuencia que muestran los LEDs
ESPERADA = {
    "normal": lambda secuencia: list(secuencia),
    "inverso": lambda secuencia: list(reversed(secuencia)),
    "cruzado": lambda secuencia: [RIVAL[j] for j in secuencia],
}
INSTRUCCIONES = {
    "normal": "Repetid la secuencia",
    "inverso": "Repetidla AL REVÉS, del último paso al primero",
    "cruzado": "CRUZADO: pulsa cuando se encendió el LED de tu rival",
}


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
        self.cola_pulsaciones = queue.Queue()      # pulsadores -> principal
        self.cola_leds = queue.Queue()             # principal  -> leds
        self.peticion_inicio = threading.Event()   # comandos   -> principal
        self.marcador = {1: 0, 2: 0}

        # El hilo de comandos solo escribe 'modo_pedido'; el principal lo aplica
        # entre partidas, así el modo nunca cambia a mitad de una.
        self.modo = config.MODO_INICIAL
        self.modo_pedido = config.MODO_INICIAL
        self.records = dict(estado.get("records", {}))  # los carga main.py de la BD
        self.pitidos = 0  # contador de pitidos: la web pita cuando cambia

        self._iniciar_gpio()

    # ------------------------------------------------------------------ GPIO
    def _iniciar_gpio(self):
        # Se importa aquí para que el GPIO se abra SOLO en este proceso
        from gpiozero import LED, Button, Buzzer, Device
        if config.SIMULADO:
            from gpiozero.pins.mock import MockFactory
            Device.pin_factory = MockFactory()

        self.leds = {1: LED(config.J1_LED), 2: LED(config.J2_LED)}
        # El pulsador Grove es activo a nivel bajo (pulsado = 0 V)
        self.botones = {
            1: Button(config.J1_BOTON, pull_up=True, bounce_time=config.REBOTE),
            2: Button(config.J2_BOTON, pull_up=True, bounce_time=config.REBOTE),
        }
        # El Grove Buzzer pita mientras su señal está a nivel alto
        self.zumbador = Buzzer(config.ZUMBADOR) if config.ZUMBADOR is not None else None

    # ------------------------------------------------------------ HILO LEDS
    def hilo_leds(self):
        """Consume órdenes de cola_leds y las ejecuta una tras otra."""
        while not self.parar.is_set():
            try:
                orden = self.cola_leds.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._animar(*orden)
            finally:
                self.cola_leds.task_done()  # avisa a quien espera en cola_leds.join()

    def _animar(self, tipo, *args):
        if tipo == "fijar":          # ("fijar", jugadores, encendido)
            jugadores, encendido = args
            self._luz(jugadores, encendido)
        elif tipo == "destello":     # ("destello", jugadores, segundos)
            jugadores, segundos = args
            self._luz(jugadores, True); time.sleep(segundos)
            self._luz(jugadores, False)
        elif tipo == "parpadeo":     # ("parpadeo", jugadores, veces, periodo)
            jugadores, veces, periodo = args
            for _ in range(veces):
                self._luz(jugadores, True); time.sleep(periodo)
                self._luz(jugadores, False); time.sleep(periodo)
        elif tipo == "acierto":      # ("acierto",): secuencia completada bien
            self._luz((1, 2), True)
            self._pitar(veces=2)
            time.sleep(0.14)
            self._luz((1, 2), False)
        elif tipo == "secuencia":    # ("secuencia", secuencia, t_encendido, t_apagado)
            secuencia, t_encendido, t_apagado = args
            for paso, jugador in enumerate(secuencia, 1):
                self._luz((jugador,), True, paso=paso)
                time.sleep(t_encendido)
                self._luz((jugador,), False)
                time.sleep(t_apagado)

    def _pitar(self, veces=1, t_pitido=0.1, t_pausa=0.08):
        """Hace pitar el zumbador 'veces' veces. También avisa a la web, que
        reproduce el mismo pitido (útil en modo simulado, sin zumbador)."""
        self.pitidos += 1
        self._publicar(pitidos=self.pitidos)
        for _ in range(veces):
            if self.zumbador:
                self.zumbador.on()
            time.sleep(t_pitido)
            if self.zumbador:
                self.zumbador.off()
            time.sleep(t_pausa)

    def _luz(self, jugadores, encendido, **extra):
        """Cambia los LEDs físicos y lo refleja en la web (LEDs virtuales)."""
        for j in jugadores:
            self.leds[j].on() if encendido else self.leds[j].off()
        self._publicar(**{f"led_j{j}": encendido for j in jugadores}, **extra)

    def _leds(self, *orden, esperar=False):
        """Encarga una animación al hilo leds.

        Sin esperar, el principal sigue trabajando mientras el LED se anima.
        Con esperar=True se bloquea hasta que el hilo leds termina TODO lo que
        tenía pendiente (Queue.join + task_done).
        """
        self.cola_leds.put(orden)
        if esperar:
            self.cola_leds.join()

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
            elif orden.startswith("modo:"):
                modo = orden.split(":")[1]
                if modo in config.MODOS:
                    self.modo_pedido = modo
            elif orden.startswith("simular:") and config.SIMULADO:
                pin = self.botones[int(orden.split(":")[1])].pin
                pin.drive_low()
                time.sleep(0.1)
                pin.drive_high()

    # ------------------------------------------------------- ESTADO COMPARTIDO
    def _publicar(self, **cambios):
        """Actualiza varias claves del estado de forma atómica (con cerrojo).

        update() manda todos los cambios al Manager en un solo mensaje.
        """
        with self.cerrojo_estado:
            self.estado.update(cambios)

    # ------------------------------------------------------------ LÓGICA
    def _vaciar_pulsaciones(self):
        while not self.cola_pulsaciones.empty():
            self.cola_pulsaciones.get_nowait()

    def _esperar(self, segundos):
        """Espera 'segundos'; devuelve la primera pulsación si alguien pulsa antes."""
        try:
            return self.cola_pulsaciones.get(timeout=max(0.0, segundos))
        except queue.Empty:
            return None

    def _mensaje_espera(self, otra=False):
        para = "otra partida" if otra else "empezar"
        return (f"Modo {config.MODOS[self.modo]}: pulsad los DOS botones para {para} "
                f"(o 'Iniciar' en la web)")

    def _aplicar_modo_pedido(self):
        """Cambia de modo (solo entre partidas)."""
        pedido = self.modo_pedido
        if pedido != self.modo:
            self.modo = pedido
            self._publicar(modo=self.modo, fase="ESPERANDO", mensaje=self._mensaje_espera(),
                           nivel=None, paso=None, mostrada=None, esperada=None)

    def ejecutar(self):
        hilos = [
            threading.Thread(target=self.hilo_pulsador, args=(1,), name="pulsador-J1", daemon=True),
            threading.Thread(target=self.hilo_pulsador, args=(2,), name="pulsador-J2", daemon=True),
            threading.Thread(target=self.hilo_comandos, name="comandos", daemon=True),
            threading.Thread(target=self.hilo_leds, name="leds", daemon=True),
        ]
        for h in hilos:
            h.start()

        self._publicar(modo=self.modo, fase="ESPERANDO", mensaje=self._mensaje_espera(),
                       marcador_j1=0, marcador_j2=0, led_j1=False, led_j2=False,
                       nivel=None, paso=None, mostrada=None, esperada=None,
                       records=dict(self.records), pitidos=0)
        try:
            while not self.parar.is_set():
                if self._esperar_preparados():
                    self.jugar_partida()
        finally:
            for led in self.leds.values():
                led.off()
            if self.zumbador:
                self.zumbador.off()

    def _esperar_preparados(self):
        """Reposo. La partida empieza cuando los DOS jugadores han pulsado su
        botón (el LED de cada uno se queda encendido al estar listo) o al pulsar
        'Iniciar' en la web. Si el segundo no llega a tiempo, se cancela."""
        listos = set()
        caduca = None
        while not self.parar.is_set():
            self._aplicar_modo_pedido()
            if self.peticion_inicio.is_set() or len(listos) == 2:
                self.peticion_inicio.clear()
                return True
            pulsacion = self._esperar(0.1)
            if pulsacion and pulsacion[0] not in listos:
                j = pulsacion[0]
                listos.add(j)
                self._leds("fijar", (j,), True)
                caduca = time.perf_counter() + config.TIEMPO_PREPARADOS
                if len(listos) == 1:
                    self._publicar(mensaje=f"{config.NOMBRES[j]} está listo. "
                                           f"{config.NOMBRES[RIVAL[j]]}, ¡pulsa tu botón!")
            if len(listos) == 1 and time.perf_counter() > caduca:
                listos.clear()
                self._leds("fijar", (1, 2), False)
                self._publicar(mensaje=self._mensaje_espera())
        return False

    # ============================================================= PARTIDA
    def jugar_partida(self):
        modo = self.modo
        self._publicar(fase="CUENTA_ATRAS", nivel=None, paso=None, mostrada=None, esperada=None,
                       mensaje=f"Modo {config.MODOS[modo]}: ¡preparados para memorizar!")
        self._leds("fijar", (1, 2), False)
        self._leds("parpadeo", (1, 2), 3, 0.25, esperar=True)
        self._vaciar_pulsaciones()  # lo pulsado durante la cuenta atrás no cuenta

        secuencia = [random.choice((1, 2)) for _ in range(config.LONGITUD_INICIAL)]
        aciertos = {1: 0, 2: 0}
        tiempos = {1: [], 2: []}  # ms entre una pulsación correcta y la anterior
        longitud = 0              # secuencia más larga completada sin fallos

        while True:
            time.sleep(0.6)
            if self.parar.is_set():
                return
            self._mostrar_secuencia(secuencia)
            esperada = ESPERADA[modo](secuencia)
            fallo = self._repetir(esperada, modo, aciertos, tiempos)
            if fallo:
                break
            # Nivel superado: se encienden los dos LEDs, pita el zumbador y la
            # secuencia crece
            longitud = len(secuencia)
            self._publicar(fase="NIVEL_OK", mensaje=f"¡Correcto! Secuencia de {longitud} superada")
            self._leds("acierto", esperar=True)
            secuencia.append(random.choice((1, 2)))

        culpable, motivo, paso_fallido = fallo
        ganador = RIVAL[culpable]
        nuevo_record = longitud > self.records.get(modo, 0)
        if nuevo_record:
            self.records[modo] = longitud

        def media(valores):
            return round(sum(valores) / len(valores), 1) if valores else None

        resultado = {
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "modo": modo,
            "longitud": longitud,
            "secuencia": "".join(map(str, secuencia)),
            "fallo": culpable,
            "motivo": motivo,
            "ganador": ganador,
            "aciertos_j1": aciertos[1],
            "aciertos_j2": aciertos[2],
            "media_j1": media(tiempos[1]),
            "media_j2": media(tiempos[2]),
        }
        tocaba = esperada[paso_fallido]
        if motivo == "tiempo":
            causa = f"{config.NOMBRES[culpable]} tardó demasiado"
        else:
            causa = f"{config.NOMBRES[culpable]} pulsó cuando le tocaba a {config.NOMBRES[tocaba]}"
        texto = f"¡Fallo! {causa}. Secuencia alcanzada: {longitud}. Gana {config.NOMBRES[ganador]}"
        if nuevo_record:
            texto += f" · ¡NUEVO RÉCORD en modo {config.MODOS[modo]}!"
        self._fin_partida(ganador, resultado, texto, mostrada=secuencia, esperada=esperada,
                          paso=paso_fallido, records=dict(self.records))

    def _mostrar_secuencia(self, secuencia):
        """El hilo leds muestra la secuencia; cada nivel, más deprisa."""
        n = len(secuencia)
        niveles_superados = n - config.LONGITUD_INICIAL
        t_encendido = max(config.T_ENCENDIDO_MIN,
                          config.T_ENCENDIDO - config.ACELERACION * niveles_superados)
        self._publicar(fase="MOSTRANDO", mensaje=f"Secuencia de {n}: ¡memorizad!", nivel=n, paso=0)
        self._leds("secuencia", tuple(secuencia), t_encendido, config.T_APAGADO, esperar=True)
        self._vaciar_pulsaciones()  # lo pulsado mientras se mostraba no cuenta

    def _repetir(self, esperada, modo, aciertos, tiempos):
        """Los jugadores pulsan en el orden de 'esperada'.

        Devuelve None si la completan, o (culpable, motivo, paso) si alguien falla:
          - "error":  pulsó el jugador al que NO le tocaba -> el culpable es él.
          - "tiempo": nadie pulsó a tiempo -> el culpable es a quien le tocaba.
        """
        self._publicar(fase="REPITE", paso=0, mensaje=f"¡Vuestro turno! {INSTRUCCIONES[modo]}")
        anterior = time.perf_counter()
        for i, toca in enumerate(esperada):
            limite = anterior + config.TIEMPO_PASO
            pulsacion = self._esperar(limite - time.perf_counter())
            # Se compara el instante de la pulsación (lo toma el hilo del pulsador),
            # no el momento en que el principal la saca de la cola.
            if pulsacion is None or pulsacion[1] > limite:
                return toca, "tiempo", i
            jugador, instante = pulsacion
            if jugador != toca:
                return jugador, "error", i
            aciertos[jugador] += 1
            tiempos[jugador].append((instante - anterior) * 1000)
            anterior = instante
            self._publicar(paso=i + 1)
            # Confirmación: el hilo leds hace el destello mientras el principal
            # ya está esperando la siguiente pulsación (no se bloquea).
            self._leds("destello", (jugador,), 0.12)
        return None

    def _fin_partida(self, ganador, resultado, texto, **extra):
        self.marcador[ganador] += 1
        # Al proceso de registro (escritura en disco, lenta) sin bloquear el juego
        self.cola_resultados.put(resultado)
        self._publicar(fase="RESULTADO", mensaje=texto,
                       marcador_j1=self.marcador[1], marcador_j2=self.marcador[2], **extra)
        self._leds("parpadeo", (ganador,), 5, 0.15, esperar=True)  # parpadea el ganador
        self._vaciar_pulsaciones()
        self.peticion_inicio.clear()  # un "Iniciar" pulsado durante la partida no cuenta
        self._publicar(fase="ESPERANDO", mensaje=self._mensaje_espera(otra=True))
