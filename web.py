"""PROCESO 2: servidor web Flask (dashboard en tiempo real).

Lee el estado del juego del diccionario compartido (con cerrojo), lee el
histórico de la base de datos y envía órdenes al juego por una cola.
"""
import logging
import sqlite3

from flask import Flask, jsonify, render_template

import config


def crear_app(estado, cerrojo_estado, cola_comandos):
    app = Flask(__name__)

    def consultar(sql):
        con = sqlite3.connect(config.RUTA_BD)
        con.row_factory = sqlite3.Row
        filas = [dict(f) for f in con.execute(sql)]
        con.close()
        return filas

    @app.route("/")
    def inicio():
        return render_template("index.html", nombres=config.NOMBRES, simulado=config.SIMULADO)

    @app.route("/api/estado")
    def api_estado():
        with cerrojo_estado:              # copia coherente del estado compartido
            actual = dict(estado)
        return jsonify(actual)

    @app.route("/api/historial")
    def api_historial():
        ultimas = consultar("SELECT * FROM rondas ORDER BY id DESC LIMIT 10")
        stats = consultar(
            "SELECT "
            " (SELECT ROUND(AVG(tiempo_j1),1) FROM rondas) AS media_j1,"
            " (SELECT ROUND(AVG(tiempo_j2),1) FROM rondas) AS media_j2,"
            " (SELECT MIN(tiempo_j1) FROM rondas) AS mejor_j1,"
            " (SELECT MIN(tiempo_j2) FROM rondas) AS mejor_j2,"
            " (SELECT COUNT(*) FROM rondas) AS total"
        )[0]
        return jsonify(ultimas=ultimas, stats=stats)

    @app.route("/api/iniciar", methods=["POST"])
    def api_iniciar():
        cola_comandos.put("iniciar")
        return jsonify(ok=True)

    @app.route("/api/reiniciar", methods=["POST"])
    def api_reiniciar():
        cola_comandos.put("reiniciar_marcador")
        return jsonify(ok=True)

    @app.route("/api/simular/<int:jugador>", methods=["POST"])
    def api_simular(jugador):
        if not config.SIMULADO or jugador not in (1, 2):
            return jsonify(ok=False), 400
        cola_comandos.put(f"simular:{jugador}")
        return jsonify(ok=True)

    return app


def proceso_web(estado, cerrojo_estado, cola_comandos):
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # sin una línea por petición
    app = crear_app(estado, cerrojo_estado, cola_comandos)
    try:
        # threaded=True: Flask atiende cada petición en su propio hilo
        app.run(host="0.0.0.0", port=config.PUERTO_WEB, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        pass
