# Modelo de parcelas

Este documento describe el modelo que genera las 59 predicciones de la entrega, cómo se eligió, qué tan bien funciona y para qué sirve. La forma de validar y la regla de decisión están en `VALIDACION.md`. El detalle completo está en `reportes/MODELO.pdf` y el resumen para FIRA en `reportes/REPORTE.pdf`.

## Resumen

El modelo predice el rendimiento de cebada de una parcela en t/ha a partir de dos cosas. La primera es el régimen de registro de su municipio (ver `DATOS.md`). La segunda es el rendimiento de las parcelas de entrenamiento vecinas del mismo régimen a 400 m o menos. No usa imágenes de satélite, clima ni topografía, porque ningún bloque de esas variables pasó la regla de decisión. Además de la predicción entrega un intervalo p10 a p90, la probabilidad de que el rendimiento quede bajo 2.5 t/ha y una marca de confianza por parcela.

| Medida | Valor |
|---|---|
| RMSE, esquema A (5 folds, 10 repeticiones, estratificado por municipio) | 0.458 t/ha |
| MAE y R², esquema A | 0.312 t/ha y 0.708 |
| RMSE, esquema B (grupos espaciales) | 0.489 t/ha |
| Referencia, media por régimen, esquemas A y B | 0.489 y 0.488 t/ha |
| RMSE con validación anidada del proceso de selección | 0.490 t/ha |
| Cobertura del intervalo p10 a p90 (meta 0.80) | 0.83, ancho medio 1.13 t/ha |

Esperamos un RMSE de 0.46 a 0.49 t/ha en las 59 parcelas. A un precio de unos 6,200 pesos por tonelada, 0.46 t/ha equivalen a unos 2,800 pesos por hectárea.

El modelo es una estimación de cierre de temporada. Usa el rendimiento de las parcelas vecinas de la misma temporada, que solo se conoce después de que se cosechan. Para estimar antes de sembrar en lugares sin parcelas medidas está el modelo municipal (`MUNICIPAL.md`).

## Archivos

| Archivo | Contenido |
|---|---|
| `models/modelo_final.joblib` | Modelo entrenado con las 138 parcelas |
| `outputs/los_bien_dotados_prediccion.csv` | CSV oficial para FIRA, 59 filas con `ID_POLIGONO` y `RENDIMIENTO_T_HA` |
| `outputs/predicciones_finales.csv` | Las 59 con p10, p90 y probabilidad bajo el umbral |
| `outputs/predicciones.parquet` | Las 197 parcelas con todas las columnas, la tabla que lee la app |
| `outputs/controles_entrega.csv` | Resultado de los controles de la entrega |
| `experimentos/registro.csv` | Una fila por experimento con sus métricas y su decisión |

Para regenerar todo se corre `uv run python -m agrocebada.train_final` y después `uv run python -m agrocebada.predict`. La función `agrocebada.predict.predict(df)` predice cualquier tabla con el formato de `features.parquet`.

## Cómo funciona

Es un proceso gaussiano con una entrada de régimen en forma binaria y una entrada de rezago espacial.

* El rezago espacial de una parcela es el promedio del rendimiento de las parcelas de entrenamiento del mismo régimen a 400 m o menos, hasta 10 vecinos, ponderadas por el inverso de la distancia (con una distancia mínima de 1 m). Si no hay vecinos en el radio, recibe la media de su régimen. El modelo ve solo ese valor, estandarizado, y no el número de vecinos ni la distancia.
* El proceso gaussiano usa un kernel de función de base radial más un término de ruido blanco, con la variable objetivo normalizada. Los valores iniciales son varianza 0.1, escala 3.0 y ruido 0.2. Tras el ajuste con las 138 parcelas quedan varianza 0.77 (0.876 al cuadrado), escala 1.57 y ruido 0.259. La semilla es 2026.
* Todo lo que usa el rendimiento se calcula dentro del ajuste. En entrenamiento el rezago de cada parcela excluye a la propia parcela, tanto de sus vecinos como de la media del régimen que se usa cuando no tiene vecinos.
* El intervalo se calcula con el método conformal (residuos guardados) con un grupo por régimen. Los residuos son los errores con signo del esquema A, 10 repeticiones por 138 parcelas. El p10 y el p90 suman a la predicción los cuantiles 0.1 y 0.9 de los residuos del régimen, con la corrección de n + 1. La probabilidad bajo el umbral es la fracción de residuos del régimen que cumple predicción + residuo < 2.5.

## Cómo se eligió

Cada idea se probó contra la mejor versión aceptada hasta ese momento, en este orden. El registro completo está en `experimentos/registro.csv` y los scripts en `scripts/baselines.py`, `scripts/experimentos.py` y `scripts/intervalos.py`.

| Paso | Resultado | Decisión |
|---|---|---|
| Media por régimen contra media por estado y por municipio | 0.489 contra 0.604 y 0.510, gana en 10 de 10, p = 0.005 | Aceptada, es la base |
| Rezago espacial de 400 m del mismo régimen, solo el valor | 0.470, gana en 9 de 10, p = 0.020 | Aceptada |
| Radios de 250 m, 600 m y 1 km | Pocos vecinos con 250 m. Con 600 m y 1 km mezcla parcelas sin relación | Descartados |
| Bloques satelitales (fenología 2025, historia, heterogeneidad, labranza, temperatura de superficie) | El mejor aporta del orden de 0.01 t/ha | Descartados |
| Clima y topografía | El clima viene en unas 25 celdas de 5 km y actúa como etiqueta de zona | Descartados |
| Entrenamiento tolerante al ruido (Huber, pesos por área, etiqueta de B como intervalo) | Sin mejora confiable | Descartado |
| Algoritmos (elastic net, PLS, bosque aleatorio, LightGBM, proceso gaussiano) | El proceso gaussiano con régimen y rezago da 0.458 | Aceptado |
| Promedios de modelos | El mejor queda 0.002 t/ha arriba y gana en 2 de 10 | Descartados |

Con los rendimientos revueltos el modelo no mejora a la media global, así que no hay fuga de información. La mejora sobre la media por régimen es de 0.031 t/ha y viene solo de los vecinos. Con la prueba t corregida por el traslape de las particiones (Nadeau y Bengio, 2003) no es significativa (p = 0.26, `scripts/analisis/prueba_t.py`). La cifra de 0.458 es optimista porque se eligió entre 73 evaluaciones con las mismas particiones, y la validación anidada estima 0.490. Una auditoría independiente reimplementó el modelo sin usar el paquete `agrocebada`, con particiones propias, y llegó a la misma conclusión. Obtuvo 0.467 contra 0.493 de la media por régimen, una diferencia que tampoco es significativa (`scripts/analisis/auditoria.py`, resultados en `outputs/auditoria/`).

## Preguntas guía del reto

Medimos la importancia con permutación agrupada, ablación y SHAP (`scripts/interpretabilidad.py`), en dos escenarios, con el régimen presente y sin él.

1. Índice satelital más importante. Sin el régimen, el NDVI, que sube el RMSE 0.106 t/ha al revolverlo. Esa importancia viene en buena parte de que el NDVI histórico distingue la zona y el régimen. El modelo solo con variables satelitales llega a 0.696 t/ha, muy lejos de las 0.489 de la media por régimen.
2. Variable climática con mayor peso. Sin el régimen, la lluvia, que sube el RMSE 0.364 t/ha al revolverla. Es una importancia de zona, no agronómica, porque las celdas de clima identifican el régimen.
3. Mejor combinación. El régimen más el rezago espacial. Una selección hacia adelante por bloques se detiene ahí, porque el siguiente candidato no pasa la prueba de permutación.

## Métricas por grupo

RMSE y MAE en t/ha, promedio de las 10 repeticiones del esquema A. La desviación del RMSE entre repeticiones es 0.018.

| Grupo | Parcelas | RMSE A | MAE A | RMSE B |
|---|---|---|---|---|
| Todas | 138 | 0.458 | 0.312 | 0.489 |
| Régimen A | 87 | 0.494 | 0.324 | 0.532 |
| Régimen B | 51 | 0.389 | 0.293 | 0.404 |
| Hidalgo | 36 | 0.332 | 0.233 | 0.339 |
| Puebla | 71 | 0.541 | 0.365 | 0.584 |
| Tlaxcala | 31 | 0.370 | 0.284 | 0.386 |

La media por régimen da 0.535 en el régimen A y 0.398 en el B. El modelo mejora en ambos, con 0.494 y 0.389, sobre todo en el A.

Intervalos p10 a p90 con validación cruzada anidada. En cada fold externo la parcela de prueba no participa en el ajuste ni en la calibración. La meta de cobertura es 0.80.

| Grupo | Cobertura | Ancho medio (t/ha) |
|---|---|---|
| Todas | 0.826 | 1.13 |
| Régimen A | 0.791 | 1.17 |
| Régimen B | 0.886 | 1.06 |
| Cuartil de área menor (0.4 a 2.3 ha) | 0.771 | 1.14 |
| Cuartil de área mayor (8.3 a 64.3 ha) | 0.909 | 1.14 |

En las 59 parcelas el ancho medio es 1.06 t/ha. La probabilidad media de quedar bajo 2.5 t/ha es 0.003 en el régimen A y 0.171 en el B. En 18 parcelas, todas del régimen B, supera 0.10.

### Calibración del p10

Para el crédito importa el lado bajo del intervalo. Con la misma validación anidada medimos qué fracción de las parcelas reales queda por debajo de su p10. Lo ideal es 0.10. Los intervalos de confianza de 95 % salen de un bootstrap de parcelas, porque las 5 repeticiones de una parcela no son independientes.

| Grupo | Parcelas bajo su p10 | Pinball 0.1 del modelo | Pinball 0.1 de la media por régimen |
|---|---|---|---|
| Todas | 0.078 [0.039, 0.120] | 0.0934 | 0.1012 |
| Régimen A | 0.099 [0.041, 0.163] | 0.1079 | 0.1215 |
| Régimen B | 0.043 [0.000, 0.098] | 0.0686 | 0.0667 |

La línea base es la media del régimen más el cuantil inferior de sus residuos. La diferencia global de pinball es -0.008 con intervalo [-0.025, 0.004]. No es significativa, igual que la diferencia de RMSE. Ningún régimen se distingue de 0.10 en la cola baja, así que no ajustamos la escala del intervalo. El p10 ya es el cuantil inferior unilateral de nivel 0.10 de los residuos del régimen, de modo que un conformal unilateral daría el mismo valor. Las cifras salen de `scripts/calibracion.py` y quedan en `outputs/calibracion_p10.csv`.

Una auditoría anterior reportó una cobertura de 0.76 en el régimen B. Esa cifra salía de una sola repetición de 51 parcelas, con los desplazamientos ya entregados aplicados a las predicciones fuera de fold. Con los mismos desplazamientos la cobertura de B varía de 0.67 a 0.94 entre las 10 repeticiones, con media de 0.81. La validación anidada de 5 repeticiones da 0.886 [0.816, 0.949]. Con 51 parcelas el error estándar de una cobertura es de 0.05 a 0.06, y por eso reportamos el intervalo y no solo el punto.

Qué significa el p10. Los residuos vienen de un solo año, 2025, y comparan parcelas distintas bajo el mismo clima. Por eso el p10 dice que 9 de cada 10 parcelas en condiciones como las de 2025 rinden más que ese valor. No dice que 9 de cada 10 años. No incluye la variabilidad entre años por sequía, helada o plaga, que además afecta a todas las parcelas de un municipio a la vez. Para una cartera de crédito el p10 subestima ese riesgo común.

### Marca de confianza por parcela

`predict()` devuelve las columnas `confianza`, `vecinos_400m`, `dist_vecino_m` y `motivo_confianza`. Se calculan con las parcelas de entrenamiento del mismo régimen.

| Confianza | Regla |
|---|---|
| alta | Al menos una parcela medida a 400 m o menos |
| media | Ninguna a 400 m, pero la más cercana está a 800 m o menos |
| baja | La más cercana está a más de 800 m, o el área queda fuera del rango de su régimen |

Los 400 m son el radio del rezago espacial. En las 59 parcelas hay 35 con confianza alta, 14 media y 10 baja. Por régimen, el A tiene 27, 6 y 4 y el B tiene 8, 8 y 6. La única parcela marcada por área es AGC_091 (0.35 ha, bajo el mínimo de 0.38 ha del régimen A).

Validamos la marca en la validación anidada, contando los vecinos en el entrenamiento de cada fold externo.

| Vecinos a 400 m | Filas | MAE (t/ha) | Parcelas bajo su p10 |
|---|---|---|---|
| 0 | 353 | 0.372 | 0.076 |
| 1 a 2 | 306 | 0.252 | 0.075 |
| 3 o más | 31 | 0.215 | 0.129 |

Sin vecinos el error absoluto sube 0.123 t/ha con intervalo [0.022, 0.228]. La marca señala menor precisión y no una cola baja peor, porque la tasa bajo el p10 no empeora sin vecinos. El rango de área casi no aporta en la validación (MAE 0.319 contra 0.311), y lo conservamos como control de extrapolación. La marca no cambia el intervalo. Los resultados quedan en `outputs/confianza_cv.csv`.

### Margen de azar de una calificación sobre 59 parcelas

La calificación oficial es un solo RMSE sobre 59 parcelas, y con tan pocas parcelas varía por azar aunque el modelo sea el mismo. Para estimar esa variación tomamos los errores fuera de fold del esquema A y sorteamos 5000 grupos de 59 parcelas, con 37 del régimen A y 22 del B como en la predicción oficial. El RMSE medio de los sorteos es 0.455, con desviación de 0.053. El 90 % de los sorteos cae entre 0.369 y 0.541. Es decir que un RMSE oficial entre 0.37 y 0.54 es compatible con el mismo modelo. Es una estimación aproximada, porque los sorteos salen de las mismas 138 parcelas y no de una población nueva. La diferencia entre dos modelos cercanos, como las 0.031 t/ha que ganamos a la media por régimen, es mucho menor que este margen.

## Uso previsto

El modelo está pensado para dos usos.

* FIRA, para apoyar decisiones de crédito y de riesgo. La predicción da un rendimiento esperado de referencia. El p10 da un rendimiento conservador que superan 9 de cada 10 parcelas en condiciones como las de 2025. No cubre la variabilidad entre años. La marca de confianza indica en qué parcelas la predicción tiene menos respaldo local. La probabilidad bajo 2.5 t/ha marca las parcelas donde el rendimiento podría ser bajo. Conviene usar el intervalo y no solo el valor puntual.
* Productores, para tener una referencia del rendimiento esperado de una parcela cercana a otras ya medidas.

No está pensado para decidir solo un crédito ni para reemplazar la verificación en campo. Tampoco para parcelas fuera de las tres entidades, para otros cultivos ni para otras temporadas, porque se entrenó con una sola temporada. Una parcela sin vecinos cercanos del mismo régimen recibe casi la media de su régimen.

## Limitaciones

1. Dos regímenes de medición probables. Los rendimientos parecen provenir de dos formas de medir o reportar que se separan por municipio. Lo inferimos de los patrones de redondeo y de los niveles. FIRA confirmó que la fuente es mixta pero no qué parcela viene de cada una. El modelo depende de esa variable. Una parcela con un municipio nuevo no tendría régimen asignado.
2. Ruido de la etiqueta. El rendimiento viene de báscula sin ajuste por humedad, impurezas ni mermas, y de dos fuentes que FIRA no distingue por parcela. Una parte del error de predicción es ruido de etiqueta que ningún modelo puede explicar.
3. Redondeo en el régimen B. Con 86.3 % de los valores en múltiplos de 0.5, el error de redondeo aporta una desviación de 0.144 t/ha por parcela redondeada. Eso fija un piso de unas 0.13 t/ha para el RMSE del régimen B. Nuestro 0.389 está por encima de ese piso, y la diferencia incluye el resto del ruido.
4. Posible sobrerreporte en parcelas pequeñas. Las parcelas del cuartil de menor área tienen el mayor error fuera de muestra (0.558 contra 0.330 a 0.484 en los demás cuartiles) y el intervalo las cubre menos (0.771). Sospechamos que sus rendimientos son más ruidosos. No lo podemos confirmar con estos datos.
5. Encogimiento hacia la media del régimen. Dentro de cada régimen las predicciones varían mucho menos que los rendimientos. La razón entre la desviación predicha y la observada es 0.41 en el régimen A y 0.42 en el B para las 59 parcelas, y 0.26 y 0.21 fuera de fold. El modelo acierta el nivel del régimen y corrige poco dentro de él. Las parcelas con rendimientos extremos, por ejemplo las de 5.4 a 5.6 t/ha de Chignahuapan, quedan siempre cerca de 4.5 t/ha. No corregimos el encogimiento porque ampliar la dispersión sin información que la respalde subiría el error.
6. Variedad y fecha de siembra desconocidas. Son factores agronómicos de peso y no están en los datos. Una parte de la variación entre parcelas vecinas viene de ellos y no puede capturarse.
7. Satélite y clima sin aporte estable. Una vez conocidos el régimen y los vecinos, el mejor bloque de variables aporta del orden de 0.01 t/ha y no pasa la regla. El clima viene en celdas de unos 5 km, así que describe la zona y no la parcela. Las variables que parecen importantes cuando el régimen no está presente lo son porque lo identifican.
8. Cifra optimista y margen de azar. El RMSE de validación se obtuvo eligiendo entre 73 evaluaciones con las mismas particiones. La validación anidada estima 0.490 t/ha, y la calificación sobre 59 parcelas tiene una desviación de unas 0.05 t/ha por azar.
9. Parcelas de entrenamiento. Para una parcela que ya está en el entrenamiento el modelo final no sirve tal cual. Su rezago incluiría a ella misma a distancia cero y la predicción saldría pegada a su propia etiqueta. Con el modelo final las 138 parcelas dan un RMSE de 0.278 t/ha contra 0.453 fuera de fold. Por eso la función de predicción devuelve para esas parcelas la predicción fuera de fold promediada en las 10 repeticiones del esquema A. Esa es la cifra que usa la aplicación. La cifra de 0.453 es menor que 0.458 porque promediar las repeticiones reduce algo el error, y no es una medida de desempeño nueva.

## Controles de la entrega

Los controles se ejecutan al generar la entrega y detienen el proceso si fallan. Los primeros ocho aplican a las 59 parcelas, y los demás solo se reportan.

| Control | Régimen A (37 parcelas) | Régimen B (22 parcelas) | Resultado |
|---|---|---|---|
| Rango de la predicción | 3.72 a 4.58 t/ha | 2.75 a 3.66 t/ha | Cumple |
| Rango observado en entrenamiento | 2.15 a 5.59 t/ha | 2.00 a 3.70 t/ha | Cumple |
| Media predicha contra media de entrenamiento | 4.485 contra 4.489 | 3.055 contra 3.045 | Cumple, diferencia menor a 0.25 |
| Razón de desviaciones (predicha entre observada) | 0.41 | 0.42 | Se reporta |
| Intervalo medio p10 a p90 | 3.98 a 5.06 | 2.51 a 3.54 | Cumple p10 ≤ pred ≤ p90 |
| Cobertura del intervalo (validación anidada) | 0.791 | 0.886 | Se reporta |
| RMSE esquema A | 0.494 | 0.389 | Se reporta |

Los controles que aplican a las 59 en conjunto son estos. Hay 59 filas, los IDs son exactamente los de PREDICCION, no hay nulos ni duplicados, y todas las predicciones están entre 2.0 y 5.6 t/ha. La razón de desviaciones con todas las parcelas juntas es 0.85, porque la diferencia entre regímenes se conserva. El resultado de cada control queda en la tabla de controles de la entrega. La coherencia espacial se revisa con un mapa y con la correlación entre cada predicción y el rendimiento medio de sus vecinos del mismo régimen a 400 m, que es 0.972 en las 36 parcelas que tienen vecinos. Esa correlación es alta porque el rezago es la entrada principal del modelo, así que sirve para detectar errores de código y no como evidencia de desempeño.
