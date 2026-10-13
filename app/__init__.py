import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory

from .modules import parcels, predictions

ROOT = Path(__file__).resolve().parent

# Lee .env de la raíz del repo; si AGRCBDA_HOST o AGRCBDA_PORT ya están definidas en la terminal, ganan sobre el archivo
load_dotenv(ROOT.parent / ".env")
HOST = os.getenv("AGRCBDA_HOST", "127.0.0.1")
PORT = int(os.getenv("AGRCBDA_PORT", "8080"))


class AgroCebadaApp:

    def __init__(self, config=None):
        self.server = Flask(
            __name__,
            static_folder=str(ROOT / "styles"),
            static_url_path="/styles",
        )
        self.server.config.update(config or {})
        self._path_register()

    def _path_register(self):
        self.server.add_url_rule("/", "index", self.index)
        self.server.add_url_rule("/health", "health", self.health)
        self.server.add_url_rule("/scripts/<path:filename>", "scripts", self.scripts)
        self.server.register_blueprint(parcels.bp)
        self.server.register_blueprint(predictions.bp)

    def index(self):
        return render_template("index.html")

    def health(self):
        return {"status": "ok"}

    def scripts(self, filename):
        return send_from_directory(ROOT / "scripts", filename)

    def run(self, host=HOST, port=PORT, debug=False):
        self.server.run(host=host, port=port, debug=debug)

    def serve(self, host=HOST, port=PORT):
        # Servidor de producción
        from waitress import serve
        serve(self.server, host=host, port=port)


def create_app(config=None):
    return AgroCebadaApp(config).server
