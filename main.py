"""Duelo de Memoria - programa principal.

Crea los objetos compartidos y lanza los 3 procesos:
  P1 juego    (hardware + lógica, con 5 hilos)
  P2 web      (Flask)
  P3 registro (SQLite)

Ejecutar:  python3 main.py          (en la Raspberry Pi)
           SIMULADO=1 python3 main.py  (en un PC, sin hardware)
"""
import multiprocessing as mp
import signal
import socket
from multiprocessing.managers import SyncManager

import config
from juego import proceso_juego
from registro import crear_bd, leer_records, proceso_registro
from web import proceso_web


def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "localhost"


def main():
    crear_bd()

    # El proceso del Manager ignora Ctrl+C para que no muera antes que los demás
    gestor = SyncManager()
    gestor.start(signal.signal, (signal.SIGINT, signal.SIG_IGN))
    estado = gestor.dict()           # estado del juego (lo escribe P1, lo lee P2)
    estado["records"] = leer_records()  # récords de cada modo guardados en la BD
    cerrojo_estado = mp.Lock()       # protege lecturas/escrituras de varias claves
    cola_comandos = mp.Queue()       # P2 (web) -> P1 (juego)
    cola_resultados = mp.Queue()     # P1 (juego) -> P3 (registro)
    parar = mp.Event()               # aviso de parada para todos

    procesos = [
        mp.Process(target=proceso_juego, name="juego",
                   args=(estado, cerrojo_estado, cola_comandos, cola_resultados, parar)),
        mp.Process(target=proceso_registro, name="registro",
                   args=(cola_resultados, parar)),
        mp.Process(target=proceso_web, name="web", daemon=True,
                   args=(estado, cerrojo_estado, cola_comandos)),
    ]
    for p in procesos:
        p.start()
        print(f"[main] Proceso '{p.name}' iniciado (PID {p.pid})")

    modo = " (MODO SIMULADO)" if config.SIMULADO else ""
    print(f"[main] Dashboard{modo}: http://{ip_local()}:{config.PUERTO_WEB}  |  Ctrl+C para salir")

    try:
        for p in procesos:
            p.join()
    except KeyboardInterrupt:
        print("\n[main] Parando...")
    finally:
        parar.set()
        for p in procesos:
            p.join(timeout=3)
            if p.is_alive():
                p.terminate()
        gestor.shutdown()
        print("[main] Fin")


if __name__ == "__main__":
    main()
