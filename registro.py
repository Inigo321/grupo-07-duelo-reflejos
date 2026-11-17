"""PROCESO 3: registro de resultados en una base de datos SQLite.

Separar la escritura en disco (E/S lenta) en otro proceso evita que el juego
se retrase midiendo tiempos de reacción mientras se guarda un resultado.
"""
import queue
import sqlite3

import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS rondas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    ganador INTEGER,
    tiempo_j1 REAL,
    tiempo_j2 REAL,
    falsa_salida INTEGER
)
"""


def crear_bd():
    con = sqlite3.connect(config.RUTA_BD)
    con.execute("PRAGMA journal_mode=WAL")  # permite leer (web) mientras se escribe
    con.execute(ESQUEMA)
    con.commit()
    con.close()


def proceso_registro(cola_resultados, parar):
    try:
        con = sqlite3.connect(config.RUTA_BD)
        while not parar.is_set():
            try:
                r = cola_resultados.get(timeout=0.5)
            except queue.Empty:
                continue
            con.execute(
                "INSERT INTO rondas (fecha, ganador, tiempo_j1, tiempo_j2, falsa_salida) "
                "VALUES (?, ?, ?, ?, ?)",
                (r["fecha"], r["ganador"], r["tiempo_j1"], r["tiempo_j2"], r["falsa_salida"]),
            )
            con.commit()
            print(f"[registro] Ronda guardada: {r}")
        con.close()
    except KeyboardInterrupt:
        pass
