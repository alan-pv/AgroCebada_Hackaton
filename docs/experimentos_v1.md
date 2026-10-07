# Experimentos de la versión 1 del modelo

Este documento reúne las pruebas de la primera ronda de modelos, en el orden de la tabla de pasos del documento de contexto. Cada prueba parte de la media por régimen, que es la mejor versión aceptada al comenzar. Esa media tiene un RMSE de 0.489 t/ha en el esquema A y de 0.488 en el esquema B. Nuestra meta interna era bajar de 0.45 en el esquema A.

## Cómo se evaluó

Usamos las particiones y la regla de decisión ya fijadas. Una idea se acepta si gana a la mejor versión aceptada en al menos 7 de las 10 repeticiones del esquema A y si pasa la prueba de permutación del bloque nuevo, con 50 permutaciones y 3 repeticiones. La prueba revuelve solo las columnas que la idea agrega a la mejor versión aceptada. Si la idea no agrega columnas, como al cambiar de algoritmo, se revuelven todas las del modelo, y entonces la prueba solo confirma que el modelo usa información además del régimen. En ese caso decide la comparación emparejada. Con 50 permutaciones el menor p-valor posible es 0.0196. Las ideas que no cumplen la regla se registran como descartadas.

Todo lo que usa el rendimiento ocurre dentro del ajuste de cada fold. Esto incluye la media por régimen, la codificación del contexto, el rezago espacial, la selección de variables, la imputación y el escalado. En los modelos de residuos, la media por régimen se calcula con las parcelas de entrenamiento del fold y el regresor explica solo lo que queda.

Hay tres enfoques. El enfoque único usa un solo regresor con el régimen codificado en forma binaria y las variables. El modelo de residuos resta la media por régimen y deja al regresor el residuo. El modelo por régimen estandariza cada variable dentro de su régimen y le da una pendiente propia a cada uno.

En las tablas, "Victorias" cuenta en cuántas de 10 repeticiones el modelo supera a la mejor versión aceptada en ese momento. Las columnas "reg. A" y "reg. B" son el RMSE en las parcelas de cada régimen de etiquetas.

Una advertencia sobre la lectura. El registro tiene 73 evaluaciones con las mismas particiones. Elegir la mejor entre muchas infla su resultado, y la regla de decisión no corrige ese efecto. Además, las 10 repeticiones usan las mismas 138 parcelas, así que contar victorias sobrestima la evidencia. Con una prueba t corregida por ese traslape (Nadeau y Bengio, 2003), la mejora del candidato sobre la media por régimen no es significativa (p = 0.26). Por eso tratamos las mejoras de este documento como cotas optimistas.

Correcciones del 7 de octubre de 2026. Una auditoría encontró dos errores, y las cifras de este documento ya están corregidas. El primero es que el rezago espacial filtraba la etiqueta, porque las parcelas de entrenamiento sin vecinos dentro del radio recibían la media de su régimen calculada con su propia etiqueta. El segundo es que, al agregar un bloque, la prueba de permutación revolvía también las coordenadas del rezago, así que salía significativa aunque el bloque no aportara. Con ambas correcciones el candidato es el mismo proceso gaussiano, y su RMSE en el esquema A pasa de 0.4525 a 0.4582.

## Relación de las variables con el residuo, dentro de cada régimen

Calculamos la correlación de cada una de las 91 variables con el residuo de la media por régimen, por separado en cada régimen. Este cálculo es solo descriptivo y no entra en ningún modelo. En el régimen A la correlación más alta en valor absoluto es 0.29 y corresponde a la pendiente del terreno. En el régimen B llega a 0.35 y corresponde a la pendiente de senescencia del NDVI de Planet. Las seis variables con mayor correlación en B son pendientes de senescencia de distintos índices. Con 51 parcelas y 91 variables, una correlación de 0.35 aparece por azar con frecuencia. Las variables de clima no pasan de 0.22.

## Filas base

| Modelo | RMSE A | MAE A | R² A | RMSE B | RMSE A, reg. A | RMSE A, reg. B | Victorias | p | Aceptada |
|---|---|---|---|---|---|---|---|---|---|
| Solo régimen (ridge, enfoque único) | 0.489 | 0.324 | 0.667 | 0.488 | 0.535 | 0.398 | 2 |  | no |
| Solo régimen (media por régimen) | 0.489 | 0.323 | 0.668 | 0.488 | 0.535 | 0.398 | 0 |  | no |
| Solo estado | 0.604 | 0.441 | 0.492 | 1.069 | 0.632 | 0.554 | 0 |  | no |
| Solo régimen, codificado con media de y | 0.489 | 0.325 | 0.667 | 0.488 | 0.535 | 0.399 | 0 |  | no |

El régimen codificado en un ridge reproduce la media por régimen con 0.489 de RMSE. Usar el estado en lugar del régimen sube el error a 0.604 en el esquema A y a 1.069 en el B. Codificar el régimen con la media de y por parcela, que descuenta la propia parcela, no cambia el resultado.

## Rezago espacial

El rezago espacial de una parcela es el promedio, ponderado por el inverso de la distancia, del rendimiento de las parcelas de entrenamiento cercanas. Usamos solo vecinos del mismo régimen y un radio de 400 m. Con ese radio, 52 % de las parcelas de entrenamiento tiene al menos un vecino del mismo régimen. Con 250 m es 25 %, con 600 m es 71 % y con 1 km es 85 %. Si una parcela no tiene vecinos en el radio, recibe la media de su régimen.

| Modelo | RMSE A | MAE A | R² A | RMSE B | RMSE A, reg. A | RMSE A, reg. B | Victorias | p | Aceptada |
|---|---|---|---|---|---|---|---|---|---|
| rezago_k5_r400m_residuos | 0.485 | 0.326 | 0.673 | 0.488 | 0.536 | 0.382 | 7 | 0.667 | no |
| rezago_k10_r400m_residuos | 0.485 | 0.326 | 0.673 | 0.488 | 0.536 | 0.382 | 7 | 0.667 | no |
| rezago_k10_r1000m_residuos | 0.496 | 0.331 | 0.658 | 0.489 | 0.543 | 0.402 | 1 |  | no |
| rezago_k10_r250m_residuos | 0.489 | 0.324 | 0.667 | 0.487 | 0.536 | 0.397 | 1 |  | no |
| rezago_k10_r600m_residuos | 0.495 | 0.331 | 0.659 | 0.489 | 0.541 | 0.405 | 0 |  | no |
| rezago_k10_r400m_unico | 0.478 | 0.331 | 0.682 | 0.496 | 0.526 | 0.384 | 7 | 0.039 | sí |
| rezago_k10_r1000m_unico | 0.505 | 0.345 | 0.645 | 0.491 | 0.551 | 0.414 | 0 |  | no |
| rezago_k10_r250m_unico | 0.492 | 0.331 | 0.663 | 0.487 | 0.542 | 0.392 | 1 |  | no |
| rezago_k10_r600m_unico | 0.509 | 0.351 | 0.639 | 0.494 | 0.553 | 0.424 | 0 |  | no |
| rezago_k10_r400m_unico_cualquier_regimen | 0.478 | 0.331 | 0.682 | 0.496 | 0.526 | 0.384 | 7 | 0.039 | sí |
| rezago_k10_r400m_unico_solo_valor | 0.470 | 0.324 | 0.693 | 0.495 | 0.514 | 0.382 | 9 | 0.020 | sí |
| rezago_k10_r400m_unico_ridge_a01 | 0.480 | 0.327 | 0.679 | 0.491 | 0.530 | 0.380 | 7 | 0.039 | sí |

Los resultados dan cuatro lecturas.

* El radio de 400 m funciona y los de 250 m, 600 m y 1 km no. Con 250 m hay muy pocos vecinos. Con 600 m y 1 km el promedio mezcla parcelas sin relación y el resultado empeora por debajo de la media por régimen.
* El enfoque único gana al modelo de residuos, 0.478 contra 0.485. El modelo de residuos gana en 7 repeticiones pero no pasa la prueba de permutación (p = 0.67).
* Cuando el modelo ve solo el valor del rezago, y no el número de vecinos ni la distancia al más cercano, el RMSE baja a 0.470. Es la mejor versión de este paso y gana en 9 de 10 repeticiones.
* En el esquema B, que deja fuera clusters enteros, el rezago no ayuda. El RMSE es 0.495 contra 0.488 de la media por régimen. Esperamos esto porque en ese esquema no hay vecinos cercanos en el entrenamiento.

El rezago de 400 m pasa la regla y es la primera mejora aceptada. Las 59 parcelas ocultas están repartidas entre las mismas zonas que las de entrenamiento, así que sí tendrán vecinos, y por eso el esquema A es el que decide.

## Bloques satelitales

Probamos cada bloque por separado y todos juntos sobre el modelo con rezago. El bloque de fenología y satélites de 2025 tiene 55 variables, así que usamos una selección dentro del fold de las 15 variables más correlacionadas con el residuo de la media por régimen. También probamos selecciones de 5 y 10 variables, y variables estandarizadas dentro de cada régimen con una pendiente propia por régimen.

| Modelo | RMSE A | MAE A | R² A | RMSE B | RMSE A, reg. A | RMSE A, reg. B | Victorias | p | Aceptada |
|---|---|---|---|---|---|---|---|---|---|
| +sat25_fen | 0.477 | 0.339 | 0.683 | 0.513 | 0.514 | 0.408 | 2 |  | no |
| +hist | 0.470 | 0.334 | 0.693 | 0.488 | 0.513 | 0.385 | 5 |  | no |
| +het | 0.468 | 0.329 | 0.695 | 0.511 | 0.512 | 0.381 | 7 | 0.627 | no |
| +lab | 0.478 | 0.335 | 0.682 | 0.505 | 0.513 | 0.410 | 0 |  | no |
| +tsup | 0.472 | 0.330 | 0.690 | 0.497 | 0.517 | 0.382 | 3 |  | no |
| +todos_los_bloques_sat_k15 | 0.499 | 0.361 | 0.653 | 0.509 | 0.539 | 0.422 | 0 |  | no |
| +todos_los_bloques_sat_k10 | 0.498 | 0.356 | 0.655 | 0.499 | 0.541 | 0.413 | 0 |  | no |
| +sat25_fen_k5 | 0.486 | 0.339 | 0.671 | 0.502 | 0.531 | 0.398 | 0 |  | no |
| +sat25_fen_por_regimen_k10 | 0.481 | 0.348 | 0.678 | 0.509 | 0.523 | 0.397 | 3 |  | no |
| +todos_por_regimen_k10 | 0.502 | 0.363 | 0.648 | 0.503 | 0.548 | 0.411 | 0 |  | no |

Ningún bloque cumple la regla. El mejor RMSE es 0.468, que se obtiene al añadir las variables de heterogeneidad. Ganan en 7 repeticiones, pero su prueba de permutación da p = 0.63, así que la mejora no se distingue de revolverlas al azar. El bloque histórico queda en 0.470 con 5 victorias. Salvo el histórico, todos los bloques empeoran el esquema B. Juntar todos los bloques es peor que cualquiera por separado, 0.499 con 15 variables seleccionadas. Las variables satelitales de 2025 no mejoran lo que ya explican el régimen y los vecinos cercanos.

## Clima y topografía

El clima viene en pocas celdas de 5 km, unas 25 para las 197 parcelas, así que actúa como una etiqueta de zona. Lo añadimos al modelo con rezago y también estandarizado dentro de cada régimen.

| Modelo | RMSE A | MAE A | R² A | RMSE B | RMSE A, reg. A | RMSE A, reg. B | Victorias | p | Aceptada |
|---|---|---|---|---|---|---|---|---|---|
| +clima | 0.474 | 0.338 | 0.688 | 0.540 | 0.511 | 0.402 | 3 |  | no |
| +topo | 0.480 | 0.340 | 0.679 | 0.502 | 0.518 | 0.406 | 0 |  | no |
| +clima+topo | 0.486 | 0.353 | 0.671 | 0.565 | 0.520 | 0.422 | 0 |  | no |
| +clima_k5 | 0.476 | 0.336 | 0.685 | 0.537 | 0.512 | 0.407 | 2 |  | no |
| +clima_por_regimen_k5 | 0.474 | 0.333 | 0.686 | 0.524 | 0.514 | 0.398 | 3 |  | no |

Ninguna variante cumple la regla. El clima empeora el esquema A, de 0.470 a 0.474 en la mejor variante, y empeora de forma clara el esquema B, hasta 0.557. La topografía no mejora. El clima no aporta más de lo que ya aportan el régimen y el rezago.

## Enfoque único contra modelo de residuos

| Modelo | RMSE A | MAE A | R² A | RMSE B | RMSE A, reg. A | RMSE A, reg. B | Victorias | p | Aceptada |
|---|---|---|---|---|---|---|---|---|---|
| enfoque_unico | 0.470 | 0.324 | 0.693 | 0.495 | 0.514 | 0.382 | 0 |  | no |
| enfoque_residuos | 0.476 | 0.323 | 0.685 | 0.488 | 0.524 | 0.380 | 2 |  | no |

Con el rezago de solo valor, el enfoque único (0.470) queda por debajo del modelo de residuos (0.476). Los dos son parecidos en el régimen B, 0.382 y 0.380, y el enfoque único es mejor en el A, 0.514 contra 0.524. Conservamos el enfoque único.

## Algoritmos

Comparamos algoritmos con dos conjuntos de entrada. El primero es el mejor conjunto aceptado, que contiene solo el régimen y el rezago. El segundo es un conjunto rico y exploratorio con el rezago y todos los bloques satelitales, con una selección de 10 variables. Probamos elastic net, PLS de 2 y 3 componentes, bosque aleatorio, LightGBM y proceso gaussiano. El proceso gaussiano usa un kernel RBF más un término de ruido blanco. El PLS de 3 componentes no se corrió con el conjunto de 3 columnas porque no cabe.

| Modelo | RMSE A | MAE A | R² A | RMSE B | RMSE A, reg. A | RMSE A, reg. B | Victorias | p | Aceptada |
|---|---|---|---|---|---|---|---|---|---|
| alg_elasticnet_cv_mejor | 0.469 | 0.324 | 0.693 | 0.493 | 0.514 | 0.380 | 4 |  | no |
| alg_pls_2_mejor | 0.472 | 0.322 | 0.690 | 0.492 | 0.520 | 0.378 | 2 |  | no |
| alg_rf_mejor | 0.501 | 0.359 | 0.651 | 0.490 | 0.539 | 0.428 | 0 |  | no |
| alg_lgbm_mejor | 0.491 | 0.339 | 0.665 | 0.489 | 0.537 | 0.401 | 0 |  | no |
| alg_gp_mejor | 0.458 | 0.312 | 0.708 | 0.489 | 0.494 | 0.389 | 9 | 0.020 | sí |
| alg_ridge_cv_rico | 0.498 | 0.356 | 0.655 | 0.499 | 0.541 | 0.413 | 0 |  | no |
| alg_elasticnet_cv_rico | 0.486 | 0.346 | 0.670 | 0.511 | 0.529 | 0.404 | 0 |  | no |
| alg_pls_2_rico | 0.510 | 0.379 | 0.637 | 0.551 | 0.547 | 0.439 | 0 |  | no |
| alg_pls_3_rico | 0.478 | 0.344 | 0.682 | 0.501 | 0.517 | 0.401 | 1 |  | no |
| alg_rf_rico | 0.480 | 0.346 | 0.679 | 0.488 | 0.517 | 0.410 | 0 |  | no |
| alg_lgbm_rico | 0.493 | 0.355 | 0.663 | 0.489 | 0.540 | 0.399 | 0 |  | no |
| alg_gp_rico | 0.483 | 0.348 | 0.675 | 0.499 | 0.523 | 0.404 | 0 |  | no |

Solo el proceso gaussiano con el régimen y el rezago cumple la regla. Su RMSE es 0.4582 en el esquema A y gana en 9 de 10 repeticiones. En el esquema B tiene 0.489, igual que la media por régimen. Mejora la predicción en el régimen A, de 0.535 a 0.494, y en el B, de 0.398 a 0.389. El p-valor de 0.0196 viene de revolver el rezago, porque el cambio de algoritmo no agrega columnas. Dice que el modelo usa el rezago, no que el proceso gaussiano supere al ridge. Con la prueba t corregida, el proceso gaussiano y el ridge con las mismas entradas no se distinguen. Con el conjunto rico ningún algoritmo gana en más de una repetición. El bosque aleatorio y LightGBM tampoco mejoran con el rezago solo.

El modelo candidato es este proceso gaussiano. Sus entradas son el régimen en forma binaria y el rezago de 400 m del mismo régimen. No usa variables satelitales, de clima ni de topografía. No alcanza la meta de 0.45 y queda a 0.008 de ella.

## Ruido de etiqueta (H2)

Probamos tres ideas sobre un ridge con las mismas entradas, que sirve de control. La primera es una pérdida robusta, con el estimador de Huber en el ridge y con la pérdida de Huber en LightGBM. La segunda es ponderar las parcelas por su área o por el logaritmo de 1 más el área. La tercera trata la etiqueta del régimen B como un intervalo de más y menos 0.25 t/ha. En esta última ajustamos el modelo en tres iteraciones. En cada iteración se predice sobre el entrenamiento y la etiqueta de cada parcela de B se acerca a la predicción hasta 0.25 t/ha, de modo que el residuo queda en cero cuando la predicción cae dentro del intervalo. Las parcelas del régimen A no cambian. Toda la evaluación usa la etiqueta original.

| Modelo | RMSE A | MAE A | R² A | RMSE B | RMSE A, reg. A | RMSE A, reg. B | Victorias | p | Aceptada |
|---|---|---|---|---|---|---|---|---|---|
| H2_control_ridge | 0.471 | 0.322 | 0.692 | 0.491 | 0.517 | 0.378 | 1 |  | no |
| H2_huber | 0.469 | 0.321 | 0.694 | 0.493 | 0.513 | 0.382 | 1 |  | no |
| H2_control_lgbm | 0.491 | 0.339 | 0.665 | 0.489 | 0.537 | 0.401 | 0 |  | no |
| H2_lgbm_huber | 0.487 | 0.332 | 0.670 | 0.493 | 0.532 | 0.400 | 0 |  | no |
| H2_peso_area | 0.467 | 0.328 | 0.696 | 0.489 | 0.512 | 0.378 | 3 |  | no |
| H2_peso_log_area | 0.470 | 0.326 | 0.693 | 0.490 | 0.516 | 0.377 | 1 |  | no |
| H2_intervalo_B_025_ridge | 0.483 | 0.328 | 0.675 | 0.490 | 0.531 | 0.386 | 1 |  | no |
| H2_intervalo_B_025_mejor | 0.459 | 0.314 | 0.707 | 0.494 | 0.496 | 0.389 | 5 |  | no |

Como todas estas variantes se comparan con la mejor versión aceptada, que ya es el proceso gaussiano, ninguna pasa la regla. La comparación pertinente es contra su control, y se muestra aquí.

| Variante | RMSE A | Control | Victorias contra el control | Diferencia media contra el control |
|---|---|---|---|---|
| H2_huber | 0.469 | H2_control_ridge | 8 de 10 | -0.0016 |
| H2_lgbm_huber | 0.487 | H2_control_lgbm | 8 de 10 | -0.0038 |
| H2_peso_area | 0.467 | H2_control_ridge | 5 de 10 | -0.0035 |
| H2_peso_log_area | 0.470 | H2_control_ridge | 4 de 10 | -0.0011 |
| H2_intervalo_B_025_ridge | 0.483 | H2_control_ridge | 0 de 10 | +0.0123 |
| H2_intervalo_B_025_mejor | 0.459 | alg_gp_mejor | 5 de 10 | +0.0008 |

* El estimador de Huber casi no cambia. Con RMSE 0.4691 contra 0.4707, gana al control en 8 repeticiones por 0.002 t/ha.
* La pérdida de Huber en LightGBM mejora un poco, de 0.491 a 0.487.
* Ponderar por el área mejora poco, de 0.4707 a 0.4672, y gana al control en 5 de 10 repeticiones. Ponderar por el logaritmo del área gana en 4. Antes de la corrección del rezago la ponderación por área ganaba en 7, así que aquel indicio no se sostiene.
* El intervalo de más y menos 0.25 empeora al control en las 10 repeticiones, de 0.471 a 0.483. Aplicado al proceso gaussiano queda igual, 0.4591 contra 0.4582, con 5 victorias de 10. Una explicación es que la media por régimen del B ya está cerca de las etiquetas y el intervalo encoge la variación que sí es real.

Concluimos que, en los datos disponibles, el entrenamiento tolerante al ruido no mejora de forma confiable el RMSE.

## Prueba de fuga

Permutamos el vector de rendimientos entre las parcelas, lo que rompe cualquier relación real, y evaluamos el modelo candidato con 3 repeticiones del esquema A. Repetimos 20 veces. El RMSE medio es 0.861. La media global con esos mismos rendimientos permutados da 0.855, y con los rendimientos reales da 0.850. El modelo queda en promedio 0.006 t/ha por encima de la media global. En una de las 20 permutaciones el modelo da 0.830, que es 0.023 por debajo de la media global en esa permutación. Esa variación es la esperada al evaluar con solo 3 repeticiones, y en promedio el modelo no mejora. No hay evidencia de fuga.

## Parcelas atípicas

De las 10 parcelas con mayor error absoluto fuera de muestra, 9 son de Chignahuapan y 1 de Singuilucan. Nueve son del régimen A. Los errores van de 0.93 a 1.91 t/ha. Cinco de ellas tienen rendimientos observados de 5.4 a 5.6 t/ha y áreas de 0.4 a 4.9 ha, y el modelo predice 4.5 t/ha, la media de su zona. Las otras cinco tienen rendimientos observados bajos, de 2.0 a 3.6 t/ha, en áreas de 2.0 a 11.6 ha. La calidad de sus series no es inusual. Tienen entre 14 y 18 observaciones válidas de Sentinel-2 en el verano y entre 29 y 42 de Planet. Su vecino más cercano de entrenamiento está entre 130 m y 1 km, con una mediana cercana a 460 m. Solo 3 de las 10 tienen un vecino del mismo régimen a 400 m o menos, así que el rezago casi no las ayuda.

Cada parcela se describe con su municipio, régimen, área, rendimiento, predicción, residuo, variables clave, calidad de serie y distancia al vecino más cercano.

## Residuos por grupo

| Agrupación | Grupo | n | RMSE | Sesgo |
|---|---|---|---|---|
| Estado | Puebla | 71 | 0.535 | 0.006 |
| Estado | Hidalgo | 36 | 0.328 | -0.042 |
| Estado | Tlaxcala | 31 | 0.367 | 0.064 |
| Régimen | A | 87 | 0.489 | -0.001 |
| Régimen | B | 51 | 0.385 | 0.018 |
| Área | Cuartil 1, la menor | 35 | 0.558 | -0.055 |
| Área | Cuartil 2 | 34 | 0.330 | -0.114 |
| Área | Cuartil 3 | 34 | 0.484 | 0.144 |
| Área | Cuartil 4, la mayor | 35 | 0.407 | 0.051 |
| Calidad de Planet | Alta | 46 | 0.528 | 0.052 |
| Calidad de Planet | Media | 46 | 0.395 | 0.051 |
| Calidad de Planet | Baja | 46 | 0.426 | -0.085 |

Los errores se concentran en Chignahuapan, que es todo Puebla en este conjunto, con 0.535 de RMSE. Las parcelas del cuartil de menor área tienen el mayor error, 0.558, lo que coincide con la sospecha de que los rendimientos de parcelas pequeñas son más ruidosos. La calidad de las series no explica el error, ya que las parcelas con más observaciones tienen un error igual o mayor. Los sesgos son pequeños en todos los grupos. La figura de residuos muestra el mismo patrón, con las predicciones agrupadas cerca de 4.5 t/ha en el régimen A.

## Resumen

* La mejor versión es un proceso gaussiano con el régimen y el rezago espacial de 400 m. Obtiene 0.4582 de RMSE en el esquema A, contra 0.489 de la media por régimen, y 0.489 en el esquema B, igual que la media por régimen.
* Las variables satelitales, el clima y la topografía no mejoran la predicción bajo la regla de decisión.
* El entrenamiento tolerante al ruido no mejora de forma confiable la predicción.
* La mejora viene de que las parcelas vecinas del mismo régimen se parecen. No depende de las imágenes.
* El resultado es una cota optimista porque se eligió entre muchas variantes con las mismas particiones. Con la prueba t corregida, la mejora sobre la media por régimen no es significativa.
