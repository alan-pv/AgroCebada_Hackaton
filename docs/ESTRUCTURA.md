# Estructura del repositorio

Qué hay en cada carpeta. Los resultados y los análisis se separan por modelo. `parcelas` es el modelo de las 197 parcelas del reto y `generalizable` es el modelo municipal con datos públicos.

```
app/                        aplicación web (Flask)
data/reto/                  datos entregados por FIRA, sin cambios
data/externos/              datos públicos (SIAP, INEGI, CHC, Copernicus, FIRA AgroCostos)
data/processed/             tablas generadas de las parcelas
data/processed/generalizable/  tablas generadas del modelo municipal
docs/                       documentación técnica
docs/reportes/              reportes en PDF y texto de la plataforma
models/                     modelo final de parcelas entrenado
outputs/parcelas/           predicciones de la entrega, capa de crédito y valores SHAP
outputs/generalizable/      capa municipal que muestra la app
analisis/parcelas/          validación, selección, intervalos, interpretabilidad y auditoría del modelo de parcelas
analisis/generalizable/     validación, selección y cifras del modelo municipal
scripts/parcelas/           scripts del modelo de parcelas
scripts/generalizable/      scripts del modelo municipal
scripts/descargas/          descarga de los datos públicos
scripts/auditoria/          reimplementación independiente del modelo de parcelas
src/parcelas/               código del modelo de parcelas
src/generalizable/          código del modelo municipal
tests/                      pruebas
```

Los dos modelos comparten `src/parcelas/config.py`, con las rutas del proyecto y la semilla, y `src/parcelas/intervalos.py`, con el cálculo del intervalo p10 a p90. El modelo municipal los importa de ahí. Las figuras de diagnóstico se escriben en `outputs/figuras/`, que no se versiona.

## Resultados finales

| Archivo | Contenido | Lo genera |
|---|---|---|
| `outputs/parcelas/los_bien_dotados_prediccion.csv` | CSV oficial para FIRA, 59 filas con `ID_POLIGONO`, `AREA_HA`, `RENDIMIENTO_T_HA` y `CONJUNTO` | `parcelas.predict` |
| `outputs/parcelas/predicciones_finales.csv` | Las 59 con p10, p90 y probabilidad bajo el umbral | `parcelas.predict` |
| `outputs/parcelas/predicciones.parquet` | Las 197 parcelas con todas las columnas, la tabla que lee la app | `parcelas.predict` |
| `outputs/parcelas/controles_entrega.csv` | Resultado de los controles de la entrega | `parcelas.predict` |
| `outputs/parcelas/capa_economica.csv` | Capa de crédito de las 197 parcelas | `scripts/parcelas/credito.py` |
| `outputs/parcelas/shap_values.parquet` | Aporte de cada variable a la predicción de cada parcela | `scripts/parcelas/interpretabilidad.py` |
| `outputs/generalizable/capa_municipal.parquet` y `.gpkg` | Rendimiento esperado, intervalo y confianza de cada municipio (columnas en `MUNICIPAL.md`) | `scripts/generalizable/capa_municipal.py` |

## Análisis del modelo de parcelas

| Archivo | Contenido | Lo genera |
|---|---|---|
| `particiones.parquet` | Particiones fijas de los esquemas de validación A y B | `parcelas.cv` |
| `registro.csv` | Una fila por experimento con sus métricas, su decisión y sus notas | todos los scripts de selección |
| `lineas_base.csv` | Modelos de referencia (medias global, por estado, municipio y régimen) | `lineas_base.py` |
| `pasos_seleccion.csv` | Cada paso de la selección del modelo contra la mejor versión aceptada | `seleccion_modelo.py` |
| `prueba_fuga.csv` | RMSE con los rendimientos revueltos, para descartar fuga de información | `seleccion_modelo.py` |
| `residuos_por_grupo.csv` | Error del modelo elegido por estado, municipio, régimen, tamaño y calidad de las series | `seleccion_modelo.py` |
| `relacion_residuo_regimen.csv` | Correlación de cada variable con el residuo dentro de cada régimen | `seleccion_modelo.py` |
| `parcelas_atipicas.csv` | Las 10 parcelas con mayor residuo fuera de fold y sus variables | `seleccion_modelo.py` |
| `modelo_elegido.json` | Configuración del modelo que ganó la selección | `seleccion_modelo.py` |
| `ensambles.csv` | Promedios de modelos comparados contra el modelo elegido | `intervalos.py` |
| `cobertura_intervalos.csv` | Cobertura del p10 a p90 por método, régimen y tamaño de parcela | `intervalos.py` |
| `intervalos_cv.csv` | Intervalo de cada parcela en cada repetición de la validación anidada | `intervalos.py` |
| `residuos_calibracion.parquet` | Residuos fuera de fold con los que se calibra el intervalo del modelo final | `intervalos.py` |
| `modelo_final.json` | Configuración del modelo final con su intervalo, la que lee `parcelas.train_final` | `intervalos.py` |
| `predicciones_etapa_intervalos.csv` | Las 59 predicciones al cerrar la etapa de intervalos, contra las que se comprueba el modelo final | `intervalos.py` |
| `sanidad_predicciones.csv` | Media, dispersión y rango de las 59 predicciones contra el entrenamiento | `intervalos.py` |
| `calibracion_p10.csv` | Cobertura y cola baja del p10 por régimen, con intervalos de confianza | `calibracion.py` |
| `confianza_cv.csv` | Error y cobertura según el número de parcelas vecinas | `calibracion.py` |
| `importancias.parquet` | Importancia de cada grupo de variables por permutación, ablación y SHAP | `interpretabilidad.py` |
| `importancia_permutacion.csv`, `ablacion_grupos.csv` | Detalle de la permutación agrupada y de la ablación | `interpretabilidad.py` |
| `seleccion_bloques.csv` | Selección hacia adelante de bloques de variables | `interpretabilidad.py` |
| `clima_cantidad_y_momento.csv` | Si importa cuánto llovió o en qué bimestre | `interpretabilidad.py` |
| `prueba_t_corregida.json` | Prueba t de Nadeau y Bengio entre el modelo y la media por régimen | `prueba_t.py` |
| `margen_azar.csv` | Variación esperada del RMSE al calificar solo 59 parcelas | `parcelas.predict` |
| `auditoria/` | Resultados de la reimplementación independiente | `scripts/auditoria/` |

## Análisis del modelo municipal

| Archivo | Contenido | Lo genera |
|---|---|---|
| `resultados.csv` | RMSE de cada modelo por objetivo, esquema, zona de exclusión y ponderación | `validacion.py` |
| `resumen.txt` | Tablas clave de la validación | `validacion.py` |
| `decisiones.json` | Modelo elegido por la regla de decisión | `validacion.py` |
| `importancia.csv` | Importancia de cada bloque de variables | `validacion.py` |
| `correlaciones_bloques.csv` | Correlación entre las variables ambientales | `validacion.py` |
| `oof_rend.parquet`, `oof_rend_sembrada.parquet` | Predicciones fuera de fold sobre superficie cosechada y sembrada | `validacion.py` |
| `cobertura.csv` | Cobertura del p10 a p90 por estado y zona de exclusión | `capa_municipal.py` |
| `comparacion_reto.csv` y `.json` | Nivel del modelo en los 9 municipios del reto contra el reto y el SIAP | `capa_municipal.py` |
| `disimilitud.json` | Revisión de que los municipios sin SIAP se parecen a los que sí tienen | `disimilitud.py` |
| `cifras_reporte.json` | Cifras que cita el reporte municipal | scripts del reporte, en el historial de git |
| `resumen_mapa_reporte.json` | Resumen del mapa del reporte en Hidalgo, Puebla y Tlaxcala | scripts del reporte, en el historial de git |
