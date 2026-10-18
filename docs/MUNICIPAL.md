# Modelo municipal con datos públicos

Este modelo responde una pregunta que el modelo de parcelas no puede responder. Si se siembra cebada de temporal en un lugar donde no hay parcelas medidas, ¿qué rendimiento se puede esperar y con qué riesgo? El modelo de parcelas depende del régimen de registro y de vecinos ya cosechados. Este se entrena con el SIAP, la única fuente con el mismo criterio para todos los municipios, y usa el clima promedio, así que sirve antes de sembrar. No distingue una parcela de otra dentro de un municipio. El reporte completo está en `reportes/MUNICIPAL.pdf` y el resumen en la sección VI de `reportes/REPORTE.pdf`.

## Alcance

| Concepto | Decisión |
|---|---|
| Unidad | Municipio por año |
| Objetivo | Rendimiento del SIAP en t/ha (producción entre superficie cosechada), cebada grano de temporal, primavera-verano |
| Objetivo de riesgo | Producción entre superficie sembrada, que incluye la superficie siniestrada |
| Estados | Hidalgo, México, Puebla y Tlaxcala |
| Años | 2003 a 2025. Antes de 2003 el portal solo da totales estatales |

Los datos de entrada se describen en `DATOS.md`. El SIAP tiene 2,658 filas de 146 municipios. 2009 y 2011 tuvieron siniestros altos (30 % y 39 % de la superficie sembrada), y el SIAP repite a veces la cifra de un municipio en sus vecinos del mismo Distrito de Desarrollo Rural.

## Validación

La métrica principal se fijó antes de correr los modelos. Es el RMSE del nivel municipal ponderado por superficie sembrada, en un esquema espacial con zona de exclusión. A 0 km mide un lugar con datos del SIAP cerca y a 50 km un lugar sin datos cerca. También se validó por distrito, sin las cifras repetidas y por año. La regla de decisión es la del proyecto (7 de 10 repeticiones y permutación con p de 0.05 o menos, ver `VALIDACION.md`).

| Escenario, RMSE de nivel en t/ha | Kriging de vecinos | Tmax jul-ago | Tmax y lluvia | Kriging de residuos de Tmax |
|---|---|---|---|---|
| Con datos cerca (0 km), ponderado | 0.309 | 0.334 | 0.272 | 0.293 |
| Sin datos cerca (50 km), ponderado | 0.566 | 0.490 | 0.506 | 0.438 |
| Por distrito, ponderado | 0.503 | 0.373 | 0.305 | 0.393 |

* Sin datos cerca el clima le gana a interpolar vecinos en todas las versiones. Con 80 km el kriging de residuos de Tmax da 0.445 contra 0.584 del kriging.
* La variable que más pesa es la temperatura máxima de julio y agosto. Cada grado más se asocia con unas 0.79 t/ha menos. Es una asociación entre municipios, no un efecto causal.
* La lluvia y la topografía ayudan con datos cerca, pero casi todo lo comparten con la temperatura (elevación contra Tmax, r = −0.80). El suelo no muestra efecto detectable.
* Los modelos de 14 variables no le ganan al de una o dos variables y se degradan rápido con la distancia.
* El clima de un año no permite pronosticar ese año. Las anomalías mensuales no mejoran la media propia con tendencia.

## Modelo final

Por la regla fijada de antemano, el modelo final es un kriging de los residuos de una regresión sobre la Tmax de julio y agosto. Lejos de los datos se comporta como el modelo de clima y cerca corrige con el SIAP observado. Tiene el menor promedio de la métrica principal en 0 y 50 km (0.366, contra 0.412 de Tmax sola y 0.438 del kriging).

El intervalo p10 a p90 cubre 0.815 de los municipios con datos cerca y 0.797 a 0.815 sin datos cerca (meta 0.80). Puebla subcubría con una escala global, así que se usa una escala local. Detalle en `experimentos/generalizable/cobertura.csv`.

## Comparación con el reto

En los 9 municipios del reto el modelo da para 2025 unas 2.7 a 2.8 t/ha. El régimen B del reto (3.05) se parece a ese nivel y al SIAP 2025 de esos municipios (3.0 a 3.2). El régimen A (4.49) queda 1.5 a 1.7 t/ha arriba. Es consistente con que el régimen A mide otra cosa, aunque no prueba la causa (`experimentos/generalizable/reto.csv`).

## Archivos para la app

La app solo lee resultados ya generados. No corre el modelo.

| Archivo | Contenido |
|---|---|
| `outputs/generalizable_municipios.parquet` | 486 municipios. 268 tienen estimación (`esperado`, `p10`, `p90`, `prob_bajo_2`) con `confianza`, `dentro_rango_ambiental`, `dentro_dominio`, `con_siap`, `dist_siap_km` y la historia del SIAP (`siap_media`, `siap_anios`, `siap_frac_bajo_2`, `tendencia`). Las columnas `*_sembrada` ponderan por superficie sembrada |
| `outputs/generalizable_municipios.gpkg` | Lo mismo con los polígonos, capa `municipios` |
| `outputs/municipal_mapa_clases.json` | Resumen del mapa del reporte en Hidalgo, Puebla y Tlaxcala (municipios con valor, confianza y rango) |
| `outputs/municipal_cifras.json` | Cifras del reporte municipal, para repetirlas igual en la página de metodología |
| `outputs/disimilitud.json` | Revisión de que los municipios sin SIAP se parecen en conjunto a los que sí tienen |

Solo los 268 municipios dentro del rango ambiental de los que tienen SIAP reciben valores. Los demás son tierras bajas y calientes donde un modelo lineal extrapola. `dentro_dominio` (229 municipios) pide además SIAP a no más de 50 km y al menos 100 ha de temporal.

## Cómo se regenera

1. `uv run python scripts/descargar_siap.py`, `descargar_ddr.py`, `descargar_clima.py`, `descargar_topografia.py` y `descargar_inegi.py` bajan los datos públicos.
2. `uv run python -m agrocebada.generalizable.variables` arma las tablas de `data/processed/generalizable/`.
3. `uv run python scripts/municipal_experimentos.py` corre la validación y elige el modelo (unos 85 minutos). Escribe `experimentos/generalizable/`, con un resumen en `resumen.txt`.
4. `uv run python scripts/municipal_capa.py` genera la capa de la app en `outputs/`.

El código está en `src/agrocebada/generalizable/`.
