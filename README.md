# AgroCebada

Código del equipo para el Reto AgroCebada FIRA 2026: predecir el rendimiento de cebada (t/ha) de 59 parcelas de Puebla, Hidalgo y Tlaxcala a partir de 138 parcelas de entrenamiento, con series satelitales (Sentinel-2, Landsat, Planet), clima (CHIRPS, CHIRTS-ERA5) y topografía (INEGI CEM).

- Plan, hallazgos y reparto de trabajo: [ROADMAP.md](ROADMAP.md)
- Documento de contexto del equipo: [AgroCebada_contexto.pdf](AgroCebada_contexto.pdf)

## Instalación

Requiere [uv](https://docs.astral.sh/uv/). Python 3.12 se instala solo.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync                    # dependencias base y grupo dev
uv sync --extra app        # además streamlit, plotly y folium
uv sync --extra tabpfn     # además tabpfn
```

## Comandos

```bash
uv run python -m agrocebada.parcelas   # genera data/processed/parcelas.parquet y .gpkg
uv run python -m agrocebada.validar    # comprueba IDs, duplicados, rangos y fechas del dataset
uv run pytest                          # pruebas
uv run python scripts/diagnostico_inicial.py   # reproduce las cifras del ROADMAP (requiere pyshp)
```

Los ZIP de rásteres se descomprimen bajo demanda en `data/interim/` (`agrocebada.io.extraer_rasteres()`).

## Estructura

```
DATASET_RETO_AGRO_2026/   datos oficiales del reto (solo lectura)
src/agrocebada/           código reutilizable (config, io, parcelas, validar)
notebooks/                exploración numerada (01_...)
data/interim/             rásteres descomprimidos (no se versiona)
data/processed/           tablas generadas; parcelas.parquet y .gpkg sí se versionan, series_*.parquet no
models/  outputs/         artefactos del modelo y predicciones
experimentos/             registro de corridas
app/                      aplicación
docs/  reporte/           documentación y reporte final
scripts/                  scripts sueltos
tests/                    pruebas
```
