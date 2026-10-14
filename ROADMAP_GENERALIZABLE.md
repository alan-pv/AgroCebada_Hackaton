# ROADMAP · Modelo generalizable de rendimiento (Etapa 2)

**Pregunta de FIRA.** Si siembro cebada de temporal en un lugar donde no hay parcelas medidas, ¿qué rendimiento puedo esperar y con qué riesgo?

**Por qué un modelo aparte.** El modelo de la entrega depende del régimen de la etiqueta y de vecinos ya medidos, así que no responde esa pregunta. El reporte de regímenes (`docs/reporte_regimenes`) mostró que las etiquetas del reto dependen de cómo se obtuvieron en cada municipio. Por eso este modelo se entrena con el SIAP, la única fuente con el mismo criterio para todos los municipios. Las etiquetas del reto solo se usan para comparar al final.

**Lo que no se toca.** `src/agrocebada/` fuera de `generalizable/`, `models/modelo_final.joblib` y los archivos de entrega en `outputs/`.

Rama `feat/modelo-generalizable`, creada desde `claude/fira-yield-generalization-y55qyx`.

---

## 1. Unidad, objetivo y alcance

| Concepto | Decisión |
|---|---|
| Unidad | Municipio por año |
| Objetivo principal | Rendimiento del SIAP (t/ha, producción entre superficie cosechada), cebada grano, temporal, primavera-verano |
| Objetivo de riesgo | Rendimiento sobre superficie sembrada (producción entre sembrada), que incluye la superficie siniestrada |
| Estados | Hidalgo, México, Puebla y Tlaxcala (México agregado con visto bueno del usuario, 9 oct) |
| Años | 2003 a 2025. Antes de 2003 el portal solo da totales estatales |

## 2. Datos

| Dato | Estado | Ruta |
|---|---|---|
| SIAP municipal 2003 a 2025, 4 estados | Listo, 2 658 filas, 146 municipios | `data/externos/siap/` (`scripts/descargar_siap.py`) |
| Polígonos municipales (Marco Geoestadístico) | Listo | `data/externos/inegi_marcogeo/` |
| Suelo Series I y II, 4 estados | Listo | `data/externos/inegi_edafologia/` |
| Uso de suelo Serie VII, máscara agrícola | Listo | `data/externos/inegi_usv/` |
| Lluvia CHIRPS y temperatura CHIRTS-ERA5, 2003 a 2025 | Listo | `data/externos/clima/` |
| Topografía, Copernicus DEM GLO-90 | Listo | `data/externos/topografia/` |
| Asignación municipio a DDR del SIAP | Listo, 19 distritos | `data/externos/siap/ddr_municipio.csv` |

Hallazgos de la primera revisión del SIAP (por confirmar en la tabla limpia):

- Unos 96 municipios tienen una mediana de al menos 50 ha sembradas. 90 de ellos tienen 10 años o más.
- 2009 y 2011 tuvieron siniestro alto, 30 % y 39 % de la superficie sembrada. El rendimiento oficial (sobre cosechada) los esconde.
- Rendimientos enteros exactos en algunos estados y años (Puebla 2007 a 2009, Tlaxcala 2010, 2011 y 2025). Hay que marcarlos.
- Alrededor de Pachuca hay un núcleo de rendimientos bajos (Zempoala 1.35, Epazoyucan 1.12, San Agustín Tlaxiaca 0.98 t/ha en promedio).

## 3. Plan

| Paso | Tarea | Estado |
|---|---|---|
| 0 | Inventario de datos y descargas, más la asignación municipio a DDR del SIAP (`scripts/descargar_siap_ddr.py`) | Hecho |
| 1 | Tabla municipio-año limpia con marcas de siniestro, redondeo y cifra repetida (`marca_repetido`). rend_sembrada filtra por superficie sembrada | Hecho |
| 2 | Variables por municipio: clima por ventanas, anomalías, suelo y topografía sobre la zona agrícola | Hecho |
| 3 | Validación: espacial con zona de exclusión (principal, B de 0 a 80 km), espacial de cinco folds, por DDR, sin cifras repetidas y por año. Métrica principal fijada de antemano | Hecho |
| 4 | Bases: media global y estatal, IDW, kriging, media propia | Hecho |
| 5 | Modelos simples fijados de antemano, kriging de sus residuos, ridge y lasso con validación interna agrupada, GP con ruido mínimo, LightGBM | Hecho |
| 6 | Riesgo: p10, p90, probabilidad bajo 2 t/ha y cobertura por estado, ponderada y sin ponderar | Hecho |
| 7 | Conexión con el reto (`experimentos/generalizable/reto.csv`) | Hecho |
| 8 | Importancia condicional y marginal por bloque, 99 permutaciones | Hecho |
| 9 | Capa para la app (`outputs/generalizable_municipios.parquet` y `.gpkg`) | Hecho |
| 10 | Reporte IEEE en `docs/reporte_generalizable/` | Pendiente |

## 3.1 Métrica principal y regla

La métrica principal se fijó antes de correr la versión con pesos y zona de exclusión (docstring de `validacion.py`). Es el RMSE de nivel municipal ponderado por superficie sembrada, en el esquema espacial con zona de exclusión, a 0 km (lugar con SIAP cerca) y a 50 km (lugar sin datos cerca). La regla del repositorio se aplica sobre esa métrica. El contendiente principal se fijó de antemano (Tmax jul-ago más lluvia may-oct). El "mejor simple" de cada distancia se eligió mirando el resultado y se reporta como tal.

## 3.2 Hallazgos (corrida del 9 de octubre, `experimentos/generalizable/resumen.md`)

La auditoría independiente mostró que la conclusión anterior ("el ambiente no supera a los vecinos") dependía de una métrica sin pesos, de vecinos a 17 km en la validación y de modelos de 14 variables. Con esas tres cosas corregidas el resultado cambia, pero no en todos los escenarios.

| Escenario (RMSE de nivel, t/ha) | Kriging | Tmax jul-ago | Tmax y lluvia | Kriging de residuos de Tmax |
|---|---|---|---|---|
| B = 0, ponderado (principal) | 0.309 | 0.334 (2 de 10) | 0.272 (10 de 10, p = 0.01) | 0.293 (7 de 10, p = 0.02) |
| B = 0, sin ponderar | 0.343 | 0.457 (0 de 10) | 0.426 (0 de 10) | 0.411 (0 de 10) |
| B = 50, ponderado (principal) | 0.566 | 0.490 (10 de 10, p = 0.01) | 0.506 (10 de 10, p = 0.01) | 0.438 (10 de 10) |
| B = 50, sin ponderar | 0.518 | 0.511 (8 de 10) | 0.515 (7 de 10) | 0.459 (10 de 10) |
| Por DDR, ponderado | 0.503 | 0.373 | 0.305 | 0.393 |
| Sin cifras repetidas, B = 0, ponderado | 0.402 | 0.422 | 0.365 | 0.383 |

- Donde se siembra mucho (ponderado) un modelo de dos variables de clima le gana al kriging aun con vecinos cerca. En un municipio promedio, sin ponderar, el kriging sigue ganando con vecinos cerca. Los municipios chicos tienen medias ruidosas que se parecen a las de sus vecinos y el clima no las explica.
- Sin datos cerca (50 km o más) el ambiente gana en todas las versiones. Con 80 km el kriging de residuos de Tmax queda en 0.445 contra 0.584 del kriging.
- Al validar por DDR el kriging pierde mucho (0.503). Parte de su ventaja venía de que el SIAP copia la cifra dentro del distrito. Sin las cifras repetidas (862 filas, 83 municipios) el orden se mantiene.
- Los modelos de 14 variables (ridge y lasso con validación interna agrupada) no le ganan al de dos variables y se degradan rápido con la distancia. Los modelos con dúrica o con efecto de estado tampoco ayudan con B = 50.
- La variable que más pesa es la Tmax de julio y agosto. Cada grado más de Tmax media en jul-ago baja el rendimiento medio unos 0.8 t/ha (0.67 junto con la lluvia, que suma unos 0.15 t/ha por cada 100 mm entre mayo y octubre). Es una asociación entre municipios, no un efecto causal.
- Importancia con B = 0 (99 permutaciones, ridge con cuatro bloques). Condicional, lo que agrega cada bloque dado el resto: temperatura +0.120 (p = 0.01), lluvia +0.106 (p = 0.01), topografía +0.038 (p = 0.02), suelo −0.005 (p = 0.64). Marginal, cada bloque solo contra la media global: temperatura mejora 0.167, lluvia 0.100, topografía 0.070 (las tres p = 0.01), suelo empeora 0.049. La topografía sí tiene efecto por sí sola, pero casi todo lo comparte con la temperatura (elevación contra Tmax jul-ago, r = −0.80). El suelo no muestra efecto detectable con estos datos municipales.
- Con B = 50 solo la temperatura sirve por sí sola (mejora marginal 0.032, p = 0.01). El modelo de cuatro bloques sin datos cerca queda peor que la media global (0.607 contra 0.594), señal de que más variables extrapolan mal.
- Clima del año. En el esquema espacial las anomalías ganan a lgbm_ubicacion en 10 de 10, pero las indicadoras de año dan lo mismo (anomalías 0.611, indicadoras 0.608, gana solo 3 de 10). Esa mejora es reconocer el año y copiar la cosecha de los vecinos, no clima. En el esquema por año, que es la prueba de pronóstico, las anomalías empeoran la media propia con tendencia (0.636 y 0.647 contra 0.632). Con clima mensual no se puede pronosticar un año nuevo.
- Exploratorio, fuera del plan. En el esquema de cinco folds un LightGBM sobre coordenadas da 0.229 ponderado contra 0.295 del kriging. No se evaluó con zona de exclusión.

**Modelo final.** Por la regla fijada de antemano, el kriging de los residuos del modelo de Tmax jul-ago (`kriging_residuos_simple_a_tmax`). Tmax pasa la regla contra el kriging con B = 50 (10 de 10, p = 0.01) y su versión con kriging de residuos tiene el menor promedio de la métrica principal en 0 y 50 km (0.366, contra 0.412 de Tmax sola y 0.438 del kriging). Con B = 0 también pasa la regla (7 de 10, p = 0.02). Lejos de datos se comporta como el modelo de clima y cerca corrige con el SIAP observado. Con vecinos cerca, el de dos variables sería un poco mejor (0.269), pero la regla prioriza el caso sin datos cerca.

**Riesgo.** Cobertura del intervalo p10 a p90 (nominal 0.8) con B = 0 y escala global de 0.797 sin ponderar y 0.828 ponderada. Puebla subcubre con escala global (0.740), así que se usó la escala local (Puebla 0.819, todos 0.815). Con B = 50 la cobertura es 0.815 sin ponderar y 0.797 ponderada, con Hidalgo bajo (0.740). Detalle en `cobertura.csv`.

**Capa.** 486 municipios. 268 están dentro del rango ambiental de los municipios con SIAP y solo esos tienen valores. Los demás son tierras bajas y calientes donde el modelo lineal extrapola. `dentro_dominio` (229) pide además SIAP a no más de 50 km y al menos 100 ha de temporal.

**Reto.** Nivel 2025 fuera de muestra de los 9 municipios del reto, promediado por parcelas. Régimen A: reto 4.49, modelo 2.78, diferencia +1.71 t/ha. Régimen B: reto 3.05, modelo 2.70, diferencia +0.35. El SIAP 2025 de esos municipios da 3.01 y 3.17. El régimen B se parece al nivel del SIAP y el A queda 1.5 a 1.7 t/ha arriba. Es descriptivo, consistente con que A mide otra cosa, no prueba causa.

**Pendientes.** Reporte IEEE. Índices diarios de helada y sequía para el pronóstico por año. Confirmar el modelo de Tmax con las parcelas del reto o con un esquema anidado, porque Tmax ya se conocía como variable fuerte antes de este plan. Evaluar el LightGBM de coordenadas con zona de exclusión.

## 4. Reglas

- Una mejora se acepta si gana en al menos 7 de 10 repeticiones y pasa la prueba de permutación con p ≤ 0.05.
- La base que importa es la interpolación de vecinos. Si el ambiente no la supera, se reporta así.
- El modelo predice el promedio municipal, no el de una parcela.
- Confirmar con el usuario antes de descargar fuentes nuevas, cambiar el alcance o hacer push.
