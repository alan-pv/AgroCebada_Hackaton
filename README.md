# AgroCebada

Código del equipo para el Reto AgroCebada FIRA 2026: predecir el rendimiento de cebada (t/ha) de 59 parcelas de Puebla, Hidalgo y Tlaxcala a partir de 138 parcelas de entrenamiento, con series satelitales (Sentinel-2, Landsat, Planet), clima (CHIRPS, CHIRTS-ERA5) y topografía (INEGI CEM).

- Plan, hallazgos y reparto de trabajo: [ROADMAP.md](ROADMAP.md)
- Documento de contexto del equipo: [AgroCebada_contexto.pdf](AgroCebada_contexto.pdf)
- Ficha del modelo final: [docs/model_card.md](docs/model_card.md)

## Instalación

Requiere [uv](https://docs.astral.sh/uv/). Python 3.12 se instala solo.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync                    # dependencias base (incluye flask y plotly para la app) y grupo dev
uv sync --extra tabpfn     # además tabpfn
```

En ARM de 64 bits (aarch64) no se instala `exactextract`, que no tiene versión para esa arquitectura. Ahí funciona la app, pero no `agrocebada.build_features`.

## Comandos

```bash
uv run python -m agrocebada.parcelas   # genera data/processed/parcelas.parquet y .gpkg
uv run python -m agrocebada.validar    # comprueba IDs, duplicados, rangos y fechas del dataset
uv run python -m agrocebada.build_features   # series, variables satelitales, clima, topografía y features.parquet (~2 min)
uv run scripts/exportar_serie_ficha.py   # serie NDVI y NDDI para la ficha (unos 50 s)
uv run pytest                          # pruebas
uv run scripts/diagnostico_inicial.py   # reproduce las cifras del ROADMAP (requiere pyshp)
```

Los ZIP de rásteres se descomprimen bajo demanda en `data/interim/` (`agrocebada.io.extraer_rasteres()`).

## App

Servidor Flask en `app/`. Se ejecuta desde la raíz del repo; el comando está en `scripts/cli.py`.

```bash
uv run app install       # una sola vez: crea .env a partir de .env.example si no existe e instala las dependencias
uv run app               # servidor de desarrollo en http://127.0.0.1:8090
uv run app --debug       # igual, pero recarga al guardar y muestra los errores en el navegador
uv run app --production  # servidor de producción con waitress; carga datos y modelo antes de aceptar peticiones
uv run app --test        # pruebas de la app (tests/test_app*.py)
```

`install` ejecuta `[ -f .env ] || cp .env.example .env` y luego `uv sync --inexact`. Con `--inexact` no se quitan paquetes instalados aparte, como el extra `tabpfn`.

Usa `--debug` solo en local: la página de errores permite ejecutar código en el servidor.

La configuración va en `.env`, que no se versiona; `.env.example` trae los valores por defecto:

| Variable | Por defecto | Qué controla |
|---|---|---|
| `AGRCBDA_PORT` | `8090` | Puerto del servidor |
| `AGRCBDA_HOST` | `127.0.0.1` | Solo acepta conexiones de esta máquina; con `0.0.0.0` acepta las de otras |
| `AGRCBDA_MAX_CONTENT_LENGTH` | `1048576` (1 MB) | Tamaño máximo del cuerpo de una petición, en bytes; si se pasa, la app responde 413 |

Si falta una variable en `.env` se usa su valor por defecto, y una variable `AGRCBDA_*` definida en la terminal gana sobre el archivo. `install` no agrega variables nuevas a un `.env` que ya existe.

Las plantillas Jinja van en `app/templates`, el JavaScript en `app/scripts` (servido en `/scripts`), los estilos en `app/styles` (servidos en `/styles`) y cada sección de la app en un módulo de `app/modules`. `main.css` es común a todas: trae los tokens (el acento verde de la interfaz en `--acento`, separado del azul de los datos en `--dato`), la barra superior y los componentes compartidos (tarjetas, botones, tablas, indicadores, acordeón e índice). Cada página tiene además su CSS (`map.css`, `run.css`, `methodology.css` y `parcel.css`), cargado después de `main.css`. Su JavaScript, si tiene, es `map.js` (el mapa, con Leaflet desde unpkg) o `run.js` (Ejecutar el modelo); la metodología y la ficha no llevan JavaScript. Las gráficas de la ficha son SVG generados en Python (`app/modules/charts.py`), sin librerías de JavaScript.

| Ruta | Qué devuelve |
|---|---|
| `GET /` | Página inicial con el mapa de las parcelas, coloreado por conjunto, rendimiento observado, predicción del modelo o riesgo (semáforo de no cubrir costos y de no pagar el crédito). Filtra por estado y municipio; el clic en una parcela abre su ficha. Hay enlaces para descargar en CSV las predicciones (con los filtros de estado y municipio) y la economía de las 197 parcelas |
| `GET /health` | `{"status": "ok"}`, para comprobar que el servidor está arriba |
| `GET /api/parcels` | Las 197 parcelas en GeoJSON: ID, estado, municipio, conjunto, rendimiento observado y área |
| `GET /api/predictions` | Predicción, intervalo p10 a p90, probabilidad bajo 2.5 t/ha y rendimiento observado (`observed`, `null` en las 59 por predecir) de las 197 parcelas (fuera de fold en las de entrenamiento). Filtros `set` (ENTRENAMIENTO o PREDICCION), `state` y `municipality`; con `format=csv` descarga un CSV |
| `POST /api/predict` | Corre el modelo final en vivo. Cuerpo JSON `{"ids": ["AGC_001", "AGC_002"], "threshold": 2.5}`, con el umbral opcional entre 1 y 6 t/ha. Devuelve la versión del modelo, el umbral y, por parcela, predicción, p10, p90 y probabilidad bajo el umbral. Con `"include_confidence": true` cada parcela añade `confidence` (alta, media o baja), `neighbors_400m`, `nearest_neighbor_m` y `confidence_reason`; sin esa clave, o con `false`, la respuesta no cambia (si el valor no es `true` o `false`, responde 400). Hasta 59 parcelas por petición |
| `POST /api/predict/new` | Predice parcelas que no están en el conjunto de datos. Cuerpo JSON `{"parcels": [{"lon": -98.37, "lat": 19.82, "area_ha": 5.2, "regime": "A"}]}`, de 1 a 59 parcelas por petición. Cada una puede llevar `id` (de 1 a 40 letras, números, `_` o `-`, sin repetirse ni coincidir con una parcela del conjunto de datos; si falta, se asigna `NUEVA_1`, `NUEVA_2`…). El punto debe quedar en la zona de estudio, el rectángulo de las 197 parcelas con 0.5 grados de margen (con los datos actuales, lon de -99.11 a -97.70 y lat de 19.03 a 20.48). `area_ha` debe ser mayor que 0 y como máximo 1000, y `regime` debe ser `A` o `B`. El umbral opcional va entre 1 y 6 t/ha. Devuelve `model_version`, `threshold` y, por parcela, `id` (el asignado si no se mandó), `lon`, `lat`, `area_ha`, `regime`, `pred`, `p10`, `p90`, `prob_below`, `confidence`, `neighbors_400m`, `nearest_neighbor_m` y `confidence_reason`, siempre (no depende de `include_confidence`) |
| `GET /ejecutar` | Página «Ejecutar el modelo»: elige parcelas del conjunto de datos (filtros por estado, municipio, conjunto e ID, o «Las 59 por predecir») y las calcula en vivo con `POST /api/predict`. Prueba una parcela nueva con longitud, latitud, superficie y régimen (`POST /api/predict/new`), o varias desde un CSV con las columnas `id` (opcional), `lon`, `lat`, `area_ha` y `regimen`, hasta 59 filas. Descarga los resultados en CSV |
| `GET /metodologia` | Página de metodología y desempeño: cómo se obtiene la predicción, validación de los esquemas A y B, cobertura del intervalo p10 a p90, confianza frente a error, margen de azar de la calificación y qué pesa en el número. Sus cifras salen del modelo y de `outputs/`; si falta un archivo, su sección muestra un aviso en lugar de la cifra |
| `GET /parcela/<id>` | Ficha de la parcela en HTML: rendimiento esperado con su intervalo p10 a p90 y el punto de equilibrio, confianza, economía (ingresos, costos, semáforos y probabilidades), contexto municipal, desglose del modelo (solo en las parcelas por predecir), entradas del modelo, serie de NDVI y NDDI, y variables de 2025. Query opcional `price` (en $/t, de 500 a 30000) y `breakeven` (en t/ha, de 0.5 a 15); con un valor fuera de rango, o que no sea número, responde 400 con la economía por defecto y un aviso. ID desconocido: 404 |
| `GET /api/parcels/<id>` | La misma ficha en JSON: identificación, predicción con su intervalo, umbral, probabilidad bajo el umbral, confianza, `breakdown` (`null` en las parcelas de entrenamiento), entradas del modelo, contexto de 2025 y `series` (`null` si falta `serie_ficha.parquet`). ID desconocido: 404 |
| `GET /api/economics` | Economía de las 197 parcelas con los valores por defecto del municipio, ordenada por ID: precio, punto de equilibrio, ingresos, margen, probabilidades de no cubrir costos y de no pagar el crédito, y sus semáforos. `format=csv` descarga la misma tabla en CSV; otro formato responde 400 |
| `GET /api/economics/<id>` | Detalle económico de una parcela con su contexto municipal (siniestralidad, años con pérdidas, rendimiento del SIAP, precios y zona de AgroCostos). Incluye `model_error`, el error típico del modelo (RMSE de validación del modelo entregado, en t/ha) pasado a pesos por hectárea con el precio usado, y qué parte es del costo total y del crédito por hectárea. Query opcional `price` (en $/t, de 500 a 30000; sustituye el precio del municipio) y `breakeven` (en t/ha, de 0.5 a 15; el costo total es `breakeven × price`). Sin `breakeven`, el punto de equilibrio sale de costo ÷ precio. ID desconocido: 404; un parámetro que no es número o está fuera de rango: 400 |
| `GET /api/methodology` | Las cifras de `/metodologia` en JSON: modelo (versión, fecha de entrenamiento, parcelas, umbral y nivel del intervalo), validación, cobertura, confianza frente a error, margen de azar, aportes del modelo final y otros grupos de variables. Cada sección vale `null` si falta su archivo o el modelo |

### En el servidor

La app corre en una Raspberry Pi 4 (aarch64, Debian 13) detrás de un túnel de Cloudflare, que da el HTTPS. Escucha solo en `127.0.0.1` y en el puerto 8090, porque ahí el 8080 está ocupado. `exactextract` no tiene versión para ARM y la app no la usa; `pyproject.toml` la omite en aarch64, así que en la Pi no hacen falta `--no-sync` ni `--no-install-package`:

```bash
uv run app install       # crea .env e instala las dependencias
uv run app --production  # servidor de producción
```

- Solo lee archivos ya generados: `data/processed/parcelas.gpkg`, `data/processed/features.parquet`, `outputs/predicciones.parquet`, `outputs/shap_values.parquet`, `outputs/importancias.parquet`, `outputs/calibracion_p10.csv`, `outputs/confianza_cv.csv`, `outputs/margen_azar.csv`, `data/externos/economia_municipal.csv` y `models/modelo_final.joblib`. No usa `tabpfn` ni `exactextract`, no descarga rásteres y ninguna ruta reentrena el modelo. `tests/test_app.py` corre la app con esos módulos bloqueados.
- `data/processed/serie_ficha.parquet` lo regenera `.venv/bin/python scripts/exportar_serie_ficha.py` (unos 50 s). No se usa `python -m agrocebada.series` completo, porque sobrescribe `data/processed/calidad_series.parquet`, que sí está versionado. Si el archivo falta, la ficha sale sin gráficas de serie.
- `pyproj` lo importa `app/modules/run.py` para pasar lon y lat a metros (EPSG:6372). No está en `pyproject.toml`: llega como dependencia de geopandas.
- Límites por petición: en `POST /api/predict`, hasta 59 parcelas y umbral entre 1 y 6 t/ha; en `POST /api/predict/new`, hasta 59 parcelas nuevas, superficie mayor que 0 y como máximo 1000 ha, coordenadas dentro de la zona de estudio y umbral entre 1 y 6 t/ha. El cuerpo de una petición no puede pasar de `AGRCBDA_MAX_CONTENT_LENGTH` bytes (1 MB por defecto; si se pasa, responde 413). Las últimas 256 selecciones de `POST /api/predict` se guardan en memoria y una repetida no vuelve a correr el modelo; `POST /api/predict/new` corre el modelo en cada petición.
- Las rutas salen de `url_for` y el JavaScript las toma de la página, así que la app funciona en la raíz del subdominio sin rutas escritas a mano.
- Al arrancar en producción carga datos y modelo (unos segundos) y luego muestra `Sirviendo en http://127.0.0.1:8090`.
- Los datos y el modelo quedan en memoria mientras el servicio está arriba, y el navegador reutiliza `/api/parcels` y el JSON de `/api/economics` durante una hora. Si cambian las predicciones, las variables o el modelo hay que reiniciar el servicio.

#### Despliegue en la Pi

La app pública está en https://agrocebada.alan-pv.com. En la Pi (host `server` de `~/.ssh/config`, por Tailscale) el repo vive en `/home/pi/agrocebada`. No se clona desde GitHub, porque el repo es privado: se copia desde una PC con acceso.

Para actualizarla, con los cambios ya en `main`, desde la raíz del repo en la PC:

```bash
scripts/desplegar.sh
```

El script clona `main` en una carpeta temporal, la copia con `rsync` (sin `.venv` ni `.env`), corre `uv run app install` en la Pi, reinicia el servicio y espera a que `/health` responda. Lo mismo a mano:

```bash
rsync -az --delete --exclude .venv --exclude .env <clonación limpia de main>/ server:/home/pi/agrocebada/
ssh server 'cd ~/agrocebada && ~/.local/bin/uv run app install && sudo systemctl restart agrocebada'
```

No se copia el directorio de trabajo directamente, porque llevaría `.claude/worktrees` y cambios sin commit.

Cómo quedó montada, por si hay que rehacerla:

- `uv` está en `~/.local/bin`, que no entra al `PATH` de `ssh server '...'`; por eso se llama con la ruta completa.
- Servicio `/etc/systemd/system/agrocebada.service`, con `User=pi`, `WorkingDirectory=/home/pi/agrocebada`, `ExecStart=/home/pi/agrocebada/.venv/bin/app --production` y `Restart=on-failure`. Arranca solo al prender la Pi. Logs: `journalctl -u agrocebada -f`.
- Túnel de Cloudflare `memorandum-relay`, que comparte con otros servicios de la Pi. En `/etc/cloudflared/config.yml` hay una regla antes de la de cierre, `hostname: agrocebada.alan-pv.com` hacia `service: http://127.0.0.1:8090`. El DNS se creó con `cloudflared tunnel route dns memorandum-relay agrocebada.alan-pv.com`. Si se cambia la regla hay que correr `sudo systemctl restart cloudflared`, y los demás servicios del túnel se cortan unos segundos.
- Si el subdominio no resuelve justo después de crearlo, suele ser la caché de DNS de la PC. Se comprueba con `dig +short agrocebada.alan-pv.com @1.1.1.1` y se limpia con `resolvectl flush-caches`.

## CLI

Un comando por cada archivo de `scripts/`, desde la raíz del repo.

```bash
uv run app                                   # scripts/cli.py: servidor de la app en http://127.0.0.1:8090
uv run app --debug                           # scripts/cli.py: servidor en modo debug (solo en local)
uv run app --production                      # scripts/cli.py: servidor de producción con waitress
uv run app --test                            # scripts/cli.py: pruebas de la app
uv run app install                           # scripts/cli.py: crea .env si no existe e instala las dependencias
uv run scripts/baselines.py                  # baselines de validación y regla de decisión del régimen (unos minutos)
uv run scripts/experimentos_v1.py            # experimentos del modelo v1, registro y candidato_v1.json (~35 min)
uv run scripts/ensemble_intervalos.py        # ensemble, intervalos p10 a p90 y candidato_v2.json (~10 min)
uv run scripts/interpretabilidad.py          # preguntas guía, importancias y SHAP (varios minutos)
uv run scripts/interpretabilidad.py --rapido # lo mismo con menos repeticiones, para probar
uv run scripts/exportar_serie_ficha.py       # serie NDVI y NDDI para la ficha (unos 50 s)
scripts/desplegar.sh                         # actualiza la app en la Pi con main (ver "Despliegue en la Pi")
uv pip install pyshp                         # solo para el diagnóstico; pyshp no es dependencia del proyecto
uv run scripts/diagnostico_inicial.py        # cifras del diagnóstico inicial del ROADMAP
```

## Reproducir la entrega

Secuencia completa desde los datos del reto, en orden. Los tiempos son aproximados, medidos en una máquina de 8 núcleos.

```bash
uv sync
uv run python -m agrocebada.parcelas            # parcelas.parquet y .gpkg (segundos)
uv run python -m agrocebada.build_features      # features.parquet (~2 min)
uv run scripts/baselines.py                     # baselines y regla de decisión (unos minutos)
uv run scripts/experimentos_v1.py               # candidato_v1.json y registro (~35 min)
uv run scripts/ensemble_intervalos.py           # candidato_v2.json y calibracion_v2.parquet (~10 min)
uv run scripts/interpretabilidad.py             # preguntas guía, importancias y SHAP (varios minutos)
uv run python -m agrocebada.train_final         # models/modelo_final.joblib (~10 s)
uv run python -m agrocebada.predict             # archivos de entrega y controles (~5 s)
uv run pytest                                   # pruebas
```

Los experimentos son deterministas (semilla 2026 en `config.SEED`). `train_final` vuelve a correr la validación cruzada y se detiene si los residuos de `experimentos/calibracion_v2.parquet` no coinciden con los del modelo, es decir, si se cambió el modelo sin recalibrar. Para solo regenerar la entrega bastan los dos últimos comandos, porque `models/modelo_final.joblib` y los archivos de `experimentos/` están versionados.

Los tags `features-v1.0` y `modelo-v1.0` marcan las versiones congeladas de las variables y del modelo.

Archivos de entrega

| Archivo | Contenido |
|---|---|
| `outputs/los_bien_dotados_prediccion.csv` | CSV para FIRA, `ID_POLIGONO` y `RENDIMIENTO_T_HA` de las 59 parcelas (el nombre sale de `config.NOMBRE_EQUIPO`) |
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
