# AgroCebada

Código del equipo para el Reto AgroCebada FIRA 2026: predecir el rendimiento de cebada (t/ha) de 59 parcelas de Puebla, Hidalgo y Tlaxcala a partir de 138 parcelas de entrenamiento, con series satelitales (Sentinel-2, Landsat, Planet), clima (CHIRPS, CHIRTS-ERA5) y topografía (INEGI CEM).

- Plan, hallazgos y reparto de trabajo: [ROADMAP.md](ROADMAP.md)
- Documento de contexto del equipo: [AgroCebada_contexto.pdf](AgroCebada_contexto.pdf)
- Ficha del modelo final: [docs/model_card.md](docs/model_card.md)

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
uv run python -m agrocebada.build_features   # series, variables satelitales, clima, topografía y features.parquet (~2 min)
uv run pytest                          # pruebas
uv run python scripts/diagnostico_inicial.py   # reproduce las cifras del ROADMAP (requiere pyshp)
```

Los ZIP de rásteres se descomprimen bajo demanda en `data/interim/` (`agrocebada.io.extraer_rasteres()`).

## Reproducir la entrega

Secuencia completa desde los datos del reto, en orden. Los tiempos son aproximados, medidos en una máquina de 8 núcleos.

```bash
uv sync
uv run python -m agrocebada.parcelas            # parcelas.parquet y .gpkg (segundos)
uv run python -m agrocebada.build_features      # features.parquet (~2 min)
uv run python scripts/baselines.py              # baselines y regla de decisión (unos minutos)
uv run python scripts/experimentos_v1.py        # candidato_v1.json y registro (~35 min)
uv run python scripts/ensemble_intervalos.py    # candidato_v2.json y calibracion_v2.parquet (~10 min)
uv run python scripts/interpretabilidad.py      # preguntas guía, importancias y SHAP (varios minutos)
uv run python -m agrocebada.train_final         # models/modelo_final.joblib (~10 s)
uv run python -m agrocebada.predict             # archivos de entrega y controles (~5 s)
uv run pytest                                   # pruebas
```

Los experimentos son deterministas (semilla 2026 en `config.SEED`). `train_final` vuelve a correr la validación cruzada y se detiene si los residuos de `experimentos/calibracion_v2.parquet` no coinciden con los del modelo, es decir, si se cambió el modelo sin recalibrar. Para solo regenerar la entrega bastan los dos últimos comandos, porque `models/modelo_final.joblib` y los archivos de `experimentos/` están versionados.

Los tags `features-v1.0` y `modelo-v1.0` marcan las versiones congeladas de las variables y del modelo.

Archivos de entrega

| Archivo | Contenido |
|---|---|
| `outputs/equipo_buap_fcc_prediccion.csv` | CSV para FIRA, `ID_POLIGONO` y `RENDIMIENTO_T_HA` de las 59 parcelas (el nombre sale de `config.NOMBRE_EQUIPO`) |
| `outputs/predicciones_finales.csv` | Las 59 con p10, p90 y probabilidad de rendimiento bajo 2.5 t/ha |
| `outputs/predicciones.parquet` | Las 197 parcelas con observado, predicción (fuera de fold en las de entrenamiento) e intervalo, para la app |
| `outputs/controles_entrega.csv` | Resultado de los controles. Si alguno falla, `predict` termina con error |
| `outputs/margen_azar.csv` | Variación esperada del RMSE de una calificación sobre 59 parcelas |
| `models/modelo_final.joblib` | Modelo, calibrador, umbral, columnas requeridas, versión y métricas |
| `reporte/anexo_predicciones.md` | Tabla compacta de las 59 predicciones para los anexos |
| `reporte/figuras/mapa_predicciones.png` | Mapa de coherencia espacial |
| `docs/model_card.md` | Ficha del modelo, con limitaciones y controles por régimen |

Uso desde Python

```python
from agrocebada.predict import cargar_modelo, predict
tabla = predict(features_df)   # ID_POLIGONO, pred, p10, p90, prob_bajo_umbral
```

`features_df` tiene el formato de `features.parquet`. Para parcelas del entrenamiento devuelve la predicción fuera de fold, porque el modelo final las vería como vecinas de sí mismas (ver `docs/model_card.md`).

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
