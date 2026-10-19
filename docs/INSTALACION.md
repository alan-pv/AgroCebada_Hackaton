# Instalación

Requiere Python 3.12.

```bash
pip install -r requirements.txt
```

También funciona con [uv](https://docs.astral.sh/uv/), que instala Python 3.12 por su cuenta, con `uv sync`. Los comandos de [REPRODUCIR.md](REPRODUCIR.md) usan `uv run`. Con pip basta quitar ese prefijo. En ARM de 64 bits no se instala `exactextract`, así que ahí no corre `parcelas.build_features`.
