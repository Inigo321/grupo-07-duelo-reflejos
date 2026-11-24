"""PROCESO 3: registro de partidas en una base de datos SQLite.

Separar la escritura en disco (E/S lenta) en otro proceso evita que el juego
se retrase midiendo tiempos mientras se guarda un resultado.
"""
import queue
import sqlite3

import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS partidas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    modo TEXT NOT NULL,          -- "normal", "inverso" o "cruzado"
    longitud INTEGER NOT NULL,   -- secuencia más larga completada sin fallos
    secuencia TEXT NOT NULL,     -- la que mostraron los LEDs y se falló, p. ej. "12211"
    fallo INTEGER NOT NULL,      -- jugador que falló
    motivo TEXT NOT NULL,        -- "error" (pulsó sin tocarle) o "tiempo" (tardó)
    ganador INTEGER NOT NULL,
    aciertos_j1 INTEGER,
    aciertos_j2 INTEGER,
    media_j1 REAL,               -- ms medios entre pulsaciones correctas
    media_j2 REAL
)
"""

INSERTAR = (
    "INSERT INTO partidas (fecha, modo, longitud, secuencia, fallo, motivo, ganador, "
    "aciertos_j1, aciertos_j2, media_j1, media_j2) "
    "VALUES (:fecha, :modo, :longitud, :secuencia, :fallo, :motivo, :ganador, "
    ":aciertos_j1, :aciertos_j2, :media_j1, :media_j2)"
)


def crear_bd():
    con = sqlite3.connect(config.RUTA_BD)
    con.execute("PRAGMA journal_mode=WAL")  # permite leer (web) mientras se escribe
    con.execute(ESQUEMA)
    con.commit()
    con.close()


def leer_records():
    """Secuencia más larga conseguida en cada modo, p. ej. {"normal": 7}."""
    con = sqlite3.connect(config.RUTA_BD)
    records = dict(con.execute("SELECT modo, MAX(longitud) FROM partidas GROUP BY modo"))
    con.close()
    return records


def proceso_registro(cola_resultados, parar):
    try:
        con = sqlite3.connect(config.RUTA_BD)

        def guardar(r):
            con.execute(INSERTAR, r)
            con.commit()
            print(f"[registro] Partida guardada: {r}")

        while not parar.is_set():
            try:
                guardar(cola_resultados.get(timeout=0.5))
            except queue.Empty:
                continue
        # Antes de cerrar, se guarda lo que quede en la cola para no perder partidas
        while True:
            try:
                guardar(cola_resultados.get_nowait())
            except queue.Empty:
                break
        con.close()
    except KeyboardInterrupt:
        pass
