# Comandos de la app:
#   uv run app               levanta el servidor en http://127.0.0.1:8080 (o el puerto de .env)
#   uv run app --debug       igual, pero recarga el servidor al guardar cambios
#   uv run app --production  servidor de producción con waitress
#   uv run app --test        corre las pruebas de la app
import argparse
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1] / "tests" / "test_app.py"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="app", description="App web de AgroCebada")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--debug", action="store_true", help="modo debug: recarga al guardar y muestra los errores en el navegador")
    mode.add_argument("--production", action="store_true", help="servidor de producción con waitress")
    mode.add_argument("--test", action="store_true", help="corre las pruebas de la app y termina")
    args = parser.parse_args(argv)

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
