# Comandos de la app:
#   uv run app               levanta el servidor en http://127.0.0.1:8090 (o el puerto de .env)
#   uv run app --debug       igual, pero recarga el servidor al guardar cambios
#   uv run app --production  servidor de producción con waitress; carga datos y modelo antes de aceptar peticiones
#   uv run app --test        corre las pruebas de la app
#   uv run app install       crea .env a partir de .env.example si no existe e instala las dependencias
#                            ejecuta: [ -f .env ] || cp .env.example .env; uv sync --inexact
import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests" / "test_app.py"
# --inexact no quita lo que se instaló aparte, como el extra tabpfn
SYNC = ["sync", "--inexact"]


def install():
    env = ROOT / ".env"
    if env.exists():
        print(".env ya existe, no se modifica", flush=True)
    else:
        shutil.copyfile(ROOT / ".env.example", env)
        print("Se creó .env a partir de .env.example", flush=True)
    # uv run deja en UV la ruta del uv que lo lanzó
    uv = os.environ.get("UV", "uv")
    return subprocess.run([uv, *SYNC], cwd=ROOT).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(prog="app", description="App web de AgroCebada")
    parser.add_argument("command", nargs="?", choices=["install"], help="install: crea .env si no existe e instala las dependencias")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--debug", action="store_true", help="modo debug: recarga al guardar y muestra los errores en el navegador")
    mode.add_argument("--production", action="store_true", help="servidor de producción con waitress")
    mode.add_argument("--test", action="store_true", help="corre las pruebas de la app y termina")
    args = parser.parse_args(argv)

    if args.command == "install":
        if args.debug or args.production or args.test:
            parser.error("install no se combina con --debug, --production ni --test")
        return install()

    if args.test:
        # pytest solo hace falta para las pruebas
        import pytest
        return pytest.main([str(TESTS), "-q"])

    from app import AgroCebadaApp
    if args.production:
        AgroCebadaApp().serve()
    else:
        AgroCebadaApp().run(debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
