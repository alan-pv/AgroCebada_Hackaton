import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory

from .modules import detail, economics, formatting, methodology, model, parcels, predictions, run

ROOT = Path(__file__).resolve().parent

# Lee .env de la raíz del repo; si una variable AGRCBDA_* ya está definida en la terminal, gana sobre el archivo
load_dotenv(ROOT.parent / ".env")
HOST = os.getenv("AGRCBDA_HOST", "127.0.0.1")
PORT = int(os.getenv("AGRCBDA_PORT", "8090"))
# Tamaño máximo del cuerpo de una petición, en bytes (1 MB por defecto); si se pasa, Flask responde 413
MAX_CONTENT_LENGTH = int(os.getenv("AGRCBDA_MAX_CONTENT_LENGTH", str(1024 * 1024)))


class AgroCebadaApp:

    def __init__(self, config=None):
        self.server = Flask(
            __name__,
            static_folder=str(ROOT / "styles"),
            static_url_path="/styles",
        )
        self.server.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
        self.server.config.update(config or {})
        # Filtros de plantilla: {{ valor | number }}, {{ valor | money }} y {{ valor | percent }}
        self.server.add_template_filter(formatting.number, "number")
        self.server.add_template_filter(formatting.money, "money")
        self.server.add_template_filter(formatting.percent, "percent")
        self._path_register()

    def _path_register(self):
        self.server.add_url_rule("/", "index", self.index)
        self.server.add_url_rule("/health", "health", self.health)
        self.server.add_url_rule("/scripts/<path:filename>", "scripts", self.scripts)
        self.server.register_blueprint(parcels.bp)
        self.server.register_blueprint(predictions.bp)
        self.server.register_blueprint(model.bp)
        self.server.register_blueprint(economics.bp)
        self.server.register_blueprint(detail.bp)
        self.server.register_blueprint(methodology.bp)
        self.server.register_blueprint(run.bp)

    def index(self):
        return render_template("index.html")

    def health(self):
        return {"status": "ok"}

    def scripts(self, filename):
        return send_from_directory(ROOT / "scripts", filename)

    def run(self, host=HOST, port=PORT, debug=False):
        self.server.run(host=host, port=port, debug=debug)

    def warm_up(self):
        # Carga datos y modelo antes de aceptar peticiones: la primera visita no espera
        # y los hilos de waitress no los cargan varias veces a la vez
        parcels.parcels_geojson()
        predictions.predictions_table()
        model.warm_up()
        economics.warm_up()
        detail.warm_up()
        methodology.warm_up()
        run.warm_up()

    def serve(self, host=HOST, port=PORT):
        # Servidor de producción
        from waitress import serve
        print("Cargando datos y modelo...", flush=True)
        self.warm_up()
        print(f"Sirviendo en http://{host}:{port}", flush=True)
        serve(self.server, host=host, port=port)


def create_app(config=None):
    return AgroCebadaApp(config).server
