# Reto AgroCebada

Equipo Los Bien Dotados, Facultad de Ciencias de la Computación, BUAP. Reto AgroCebada FIRA 2026.

Predecimos el rendimiento de cebada de temporal (t/ha) de 59 parcelas de Puebla, Hidalgo y Tlaxcala a partir de 138 parcelas con rendimiento conocido. El modelo usa el régimen de registro de cada municipio y el rendimiento de las parcelas vecinas, con un RMSE esperado de 0.46 a 0.49 t/ha. Un segundo modelo, entrenado con datos públicos del SIAP, estima el rendimiento esperado de cualquier municipio de Hidalgo, México, Puebla y Tlaxcala, incluso donde no hay parcelas medidas. Una capa de crédito traduce ambas estimaciones a pesos y a riesgo de no cubrir costos.

Aplicación pública: https://agrocebada.alan-pv.com

## Entrega

| Archivo | Contenido |
|---|---|
| [outputs/los_bien_dotados_prediccion.csv](outputs/los_bien_dotados_prediccion.csv) | Predicciones oficiales de las 59 parcelas (`ID_POLIGONO`, `RENDIMIENTO_T_HA`) |
| [reportes/REPORTE.pdf](reportes/REPORTE.pdf) | Reporte técnico de 4 cuartillas con la tabla de las 59 predicciones |
| [reportes/BIBLIOGRAFIA.pdf](reportes/BIBLIOGRAFIA.pdf) | Referencias del reporte |
| [reportes/PLATAFORMA.txt](reportes/PLATAFORMA.txt) | Texto del reporte por campo, tal como se captura en la plataforma |

Reportes de apoyo, con más detalle que el reporte

| Archivo | Contenido |
|---|---|
| [reportes/CONTEXTO.pdf](reportes/CONTEXTO.pdf) | El reto en contexto, supuestos e hipótesis iniciales |
| [reportes/REGIMENES.pdf](reportes/REGIMENES.pdf) | Por qué los municipios registran el rendimiento de dos formas |
| [reportes/MODELO.pdf](reportes/MODELO.pdf) | Procedimiento, arquitectura y evaluación del modelo de parcelas |
| [reportes/MUNICIPAL.pdf](reportes/MUNICIPAL.pdf) | Modelo municipal con datos públicos |

## Documentación

| Documento | Para qué sirve |
|---|---|
| [docs/DATOS.md](docs/DATOS.md) | Datos del reto, qué es la etiqueta según FIRA, datos públicos y diccionario de variables |
| [docs/VALIDACION.md](docs/VALIDACION.md) | Esquemas de validación cruzada, regla de decisión y modelos de referencia |
| [docs/MODELO.md](docs/MODELO.md) | Modelo de parcelas, cómo se eligió, métricas, uso previsto y limitaciones |
| [docs/CREDITO.md](docs/CREDITO.md) | Capa de crédito, puntos de equilibrio, probabilidades y semáforos |
| [docs/MUNICIPAL.md](docs/MUNICIPAL.md) | Modelo municipal, su validación y los archivos que usa la app |
| [docs/PROMPTS.md](docs/PROMPTS.md) | Uso de inteligencia artificial y prompts principales, como piden las bases |

## Estructura

```
app/              aplicación web (Flask)
data/reto/        datos entregados por FIRA, sin cambios
data/externos/    datos públicos (SIAP, INEGI, CHC, Copernicus, FIRA AgroCostos)
data/processed/   tablas generadas (parcelas, variables, modelo municipal)
docs/             documentación técnica
experimentos/     particiones, registro de experimentos y calibración
models/           modelo final entrenado
outputs/          predicciones y resultados de los análisis
reportes/         reportes en PDF y texto de la plataforma
scripts/          scripts de experimentos, descargas y capas
scripts/analisis/ auditoría independiente, prueba t corregida y disimilitud
src/agrocebada/   paquete con el código del modelo
tests/            pruebas
```

## Instalación

Requiere Python 3.12.

```bash
pip install -r requirements.txt
```

También funciona con [uv](https://docs.astral.sh/uv/), que instala Python 3.12 por su cuenta, con `uv sync`. Los comandos de abajo usan `uv run`. Con pip basta quitar ese prefijo. En ARM de 64 bits no se instala `exactextract`, así que ahí no corre `agrocebada.build_features`.

## Reproducir la entrega

Para regenerar solo las predicciones bastan los dos últimos pasos, porque el modelo y los archivos de `experimentos/` están versionados.

```bash
uv run python -m agrocebada.parcelas         # data/processed/parcelas.parquet y .gpkg
uv run python -m agrocebada.build_features   # data/processed/features.parquet (unos 2 min)
uv run python scripts/baselines.py           # modelos de referencia y regla de decisión del régimen
uv run python scripts/experimentos.py        # experimentos del modelo y registro (unos 35 min)
uv run python scripts/intervalos.py          # promedios de modelos e intervalos p10 a p90 (unos 10 min)
uv run python scripts/calibracion.py         # calibración del p10 y marca de confianza
uv run python scripts/interpretabilidad.py   # preguntas guía, importancias y SHAP
uv run python scripts/credito.py             # capa de crédito
uv run python -m agrocebada.train_final      # models/modelo_final.joblib
uv run python -m agrocebada.predict          # archivos de entrega y controles
uv run pytest                                # pruebas
```

Los experimentos son deterministas (semilla 2026). `train_final` se detiene si la calibración guardada no coincide con el modelo, es decir, si se cambió el modelo sin recalibrar. Las figuras de diagnóstico se escriben en `outputs/figuras/`, que no se versiona. Los pasos del modelo municipal están en [docs/MUNICIPAL.md](docs/MUNICIPAL.md).

Comprobaciones independientes

```bash
uv run python scripts/analisis/auditoria.py . outputs/auditoria          # reimplementa el modelo sin el paquete
uv run python scripts/analisis/auditoria_regimen.py . outputs/auditoria  # sensibilidad al régimen y cobertura
uv run python scripts/analisis/prueba_t.py                               # prueba t corregida de Nadeau y Bengio
uv run python scripts/analisis/disimilitud.py                            # municipios sin SIAP contra los que sí tienen
```

Uso desde Python

```python
from agrocebada.predict import predict
tabla = predict(features_df)   # ID_POLIGONO, pred, p10, p90, prob_bajo_umbral y confianza
```

`features_df` tiene el formato de `features.parquet`. Para parcelas del entrenamiento devuelve la predicción fuera de fold, porque el modelo final las vería como vecinas de sí mismas.

## Aplicación

La aplicación está publicada en https://agrocebada.alan-pv.com y no hace falta instalarla para revisarla. Solo lee archivos ya generados y nunca reentrena el modelo. El código está en `app/`, con un módulo por sección en `app/modules/`, y sus pruebas en `tests/test_app*.py`.

| Ruta | Qué muestra |
|---|---|
| `/` | Mapa con dos modelos. El de parcelas (datos de FIRA) colorea las 197 parcelas por conjunto, régimen, rendimiento, predicción o riesgo de no pagar el crédito, con la lista de las 59 ordenada por riesgo. El municipal (SIAP y clima) colorea los 361 municipios de Hidalgo, Puebla y Tlaxcala por rendimiento esperado, confianza, temperatura o elevación, con su propia lista y un resumen por municipio que separa de dónde sale cada estimación |
| `/parcela/<id>` | Ficha de la parcela con su intervalo, confianza, economía, desglose del modelo y serie de NDVI |
| `/ejecutar` | Corre el modelo en vivo sobre parcelas del conjunto o parcelas nuevas por coordenadas o CSV |
| `/metodologia` | Validación, cobertura, confianza, margen de azar e importancia de las variables |
| `/api/parcels`, `/api/predictions`, `/api/economics`, `/api/methodology`, `/api/municipal` | Los mismos datos en JSON, y en CSV con `format=csv` donde aplica |
| `POST /api/predict` y `POST /api/predict/new` | Predicción en vivo de parcelas del conjunto o nuevas |
