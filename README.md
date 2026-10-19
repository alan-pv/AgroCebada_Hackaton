# Reto AgroCebada

Equipo Los Bien Dotados, Facultad de Ciencias de la Computación, BUAP. Reto AgroCebada FIRA 2026.

Predecimos el rendimiento de cebada de temporal (t/ha) de 59 parcelas de Puebla, Hidalgo y Tlaxcala a partir de 138 parcelas con rendimiento conocido. El modelo usa el régimen de registro de cada municipio y el rendimiento de las parcelas vecinas, con un RMSE esperado de 0.46 a 0.49 t/ha. Un segundo modelo, entrenado con datos públicos del SIAP, estima el rendimiento esperado de cualquier municipio de Hidalgo, Puebla y Tlaxcala, incluso donde no hay parcelas medidas. Una capa de crédito traduce la predicción de cada parcela a pesos y a riesgo de no pagar el crédito.

Aplicación pública: https://agrocebada.alan-pv.com

## Entrega

| Archivo | Contenido |
|---|---|
| [outputs/los_bien_dotados_prediccion.csv](outputs/los_bien_dotados_prediccion.csv) | Predicciones oficiales de las 59 parcelas (`ID_POLIGONO`, `RENDIMIENTO_T_HA`) |
| [docs/reportes/REPORTE.pdf](docs/reportes/REPORTE.pdf) | Reporte técnico de 4 cuartillas con la tabla de las 59 predicciones |
| [docs/reportes/BIBLIOGRAFIA.pdf](docs/reportes/BIBLIOGRAFIA.pdf) | Referencias del reporte |
| [docs/reportes/PLATAFORMA.txt](docs/reportes/PLATAFORMA.txt) | Texto del reporte por campo, tal como se captura en la plataforma |

Reportes de apoyo, con más detalle que el reporte

| Archivo | Contenido |
|---|---|
| [docs/reportes/CONTEXTO.pdf](docs/reportes/CONTEXTO.pdf) | El reto en contexto, supuestos e hipótesis iniciales |
| [docs/reportes/REGIMENES.pdf](docs/reportes/REGIMENES.pdf) | Por qué los municipios registran el rendimiento de dos formas |
| [docs/reportes/MODELO.pdf](docs/reportes/MODELO.pdf) | Procedimiento, arquitectura y evaluación del modelo de parcelas |
| [docs/reportes/MUNICIPAL.pdf](docs/reportes/MUNICIPAL.pdf) | Modelo municipal con datos públicos |

## Documentación

| Documento | Para qué sirve |
|---|---|
| [docs/ESTRUCTURA.md](docs/ESTRUCTURA.md) | Qué hay en cada carpeta del repositorio |
| [docs/INSTALACION.md](docs/INSTALACION.md) | Cómo instalar el entorno |
| [docs/REPRODUCIR.md](docs/REPRODUCIR.md) | Pasos para regenerar la entrega, comprobaciones independientes y uso desde Python |
| [docs/APLICACION.md](docs/APLICACION.md) | Rutas de la aplicación web y su API |
| [docs/DATOS.md](docs/DATOS.md) | Datos del reto, qué es la etiqueta según FIRA, datos públicos y diccionario de variables |
| [docs/VALIDACION.md](docs/VALIDACION.md) | Esquemas de validación cruzada, regla de decisión y modelos de referencia |
| [docs/MODELO.md](docs/MODELO.md) | Modelo de parcelas, cómo se eligió, métricas, uso previsto y limitaciones |
| [docs/CREDITO.md](docs/CREDITO.md) | Capa de crédito, puntos de equilibrio, probabilidades y semáforos |
| [docs/MUNICIPAL.md](docs/MUNICIPAL.md) | Modelo municipal, su validación y los archivos que usa la app |
| [docs/PROMPTS.md](docs/PROMPTS.md) | Uso de inteligencia artificial y prompts principales, como piden las bases |
