# Ensemble e intervalos de predicción

Este documento reúne dos pruebas. La primera busca si promediar modelos distintos mejora al candidato de la versión 1. La segunda construye intervalos de predicción para cada parcela y mide si cumplen lo que prometen. FIRA es una institución de crédito, así que además de la predicción le sirve saber cuánto puede equivocarse el modelo en cada parcela.

## Promedio de modelos

Un ensemble es un promedio de las predicciones de varios modelos. Aquí usamos promedio simple, con el mismo peso para cada miembro, y no entrenamos ningún meta-modelo. Si los pesos se eligieran mirando la misma validación cruzada, el resultado quedaría inflado por sesgo de selección. Por eso no probamos pesos.

Los miembros son cuatro modelos con enfoques distintos. Todos ven el régimen de etiquetas y el rezago espacial a 400 m del mismo régimen.

| Miembro | Descripción |
|---|---|
| gp | Proceso gaussiano, el candidato de la versión 1 |
| ridge_rezago | Regresión ridge solo con régimen y rezago |
| rf_hist_het | Bosque aleatorio de profundidad 3 con 9 variables históricas y de heterogeneidad (`hist_` y `het_`) |
| lgbm_hist_het | LightGBM poco profundo con las mismas 9 variables |
| residuos_ridge | Media por régimen más un ridge sobre el residuo, con las mismas 9 variables y el rezago |

Cada ensemble se compara con el candidato de la versión 1 con la regla de decisión del proyecto. Se acepta con 7 o más victorias de 10 repeticiones en el esquema A y con prueba de permutación de p menor o igual a 0.05. La permutación solo se corre si hay 7 victorias.

| Modelo | RMSE A | RMSE B | RMSE A, régimen A | RMSE A, régimen B | Victorias | Aceptada |
|---|---|---|---|---|---|---|
| Candidato v1 (gp) | 0.4525 | 0.4889 | 0.491 | 0.379 | base | base |
| ridge_rezago (miembro) | 0.4633 | 0.4952 | 0.506 | 0.380 |  |  |
| rf_hist_het (miembro) | 0.4795 | 0.4851 | 0.515 | 0.412 |  |  |
| lgbm_hist_het (miembro) | 0.4916 | 0.4834 | 0.539 | 0.398 |  |  |
| residuos_ridge (miembro) | 0.4791 | 0.4827 | 0.528 | 0.382 |  |  |
| gp + ridge_rezago | 0.4549 | 0.4912 | 0.495 | 0.378 | 2 | no |
| gp + rf | 0.4610 | 0.4834 | 0.499 | 0.389 | 1 | no |
| gp + ridge_rezago + rf | 0.4590 | 0.4858 | 0.498 | 0.384 | 1 | no |
| gp + ridge_rezago + rf + residuos_ridge | 0.4618 | 0.4840 | 0.503 | 0.381 | 1 | no |
| gp + lgbm + residuos_ridge | 0.4659 | 0.4816 | 0.510 | 0.378 | 1 | no |

Ningún ensemble gana al candidato en el esquema A. El mejor, gp + ridge_rezago, queda 0.0024 t/ha por encima y gana en 2 de 10 repeticiones. Los ensembles con modelos de árboles sí bajan el error del esquema B, que pasa de 0.489 a entre 0.482 y 0.486, pero esa diferencia es de 0.003 a 0.007 t/ha y el esquema B no decide. Los miembros con variables satelitales y de historia son peores que el proceso gaussiano por sí solos, y promediarlos con él arrastra el resultado hacia arriba. Esto coincide con lo que vimos en la versión 1, donde esos bloques no pasaron la regla.

Decisión. El candidato de la versión 1 se queda como modelo de la versión 2. La configuración del candidato de la versión 2 guarda esa misma configuración y deja lista la estructura para un ensemble si una versión futura pasa la regla.

## Intervalos de predicción

### Método

Un intervalo p10 a p90 tiene como meta contener el rendimiento real en 80 % de las parcelas, con 10 % de probabilidad en cada cola. Lo construimos con conformal. La idea es medir cuánto se equivoca el modelo en parcelas que no vio, y sumar esos errores, con su signo, a la predicción de una parcela nueva.

Los errores salen de las predicciones fuera de fold del esquema A. Para cada parcela, el residuo es el rendimiento observado menos la predicción de un modelo que no la vio. Los cuantiles se corrigen por tamaño de muestra con el factor n + 1, como pide el método.

Probamos seis variantes.

| Variante | Qué hace |
|---|---|
| global | Un solo conjunto de residuos para todas las parcelas |
| regimen | Mondrian por régimen, con cuantiles calculados dentro de cada régimen |
| regimen_tamano | Mondrian por régimen y por tamaño, con parcelas chicas y grandes separadas en la mediana del área (4.9 ha) |
| regimen_escala | Mondrian por régimen con los residuos escalados por una función del área |
| cvmas_global | CV+ (Barber y colaboradores, 2021), que desplaza la predicción de cada modelo de fold con los residuos de las parcelas que ese modelo no vio |
| cvmas_regimen | CV+ con residuos solo del mismo régimen |

### Cómo se midió la cobertura

La cobertura es la fracción de parcelas cuyo rendimiento cae dentro de su intervalo. Para que cada parcela reciba un intervalo sin haber participado en su calibración usamos validación cruzada anidada. En cada fold externo del esquema A se aparta una quinta parte de las parcelas. Con el resto se entrena el modelo y se calculan los residuos con una validación interna de 5 folds. Las parcelas apartadas reciben su intervalo y se cuenta si quedaron cubiertas. Repetimos con 5 particiones distintas. Cada cifra promedia 5 repeticiones sobre 138 parcelas.

### Resultados

Cobertura y ancho medio de p10 a p90 en t/ha. La meta de cobertura es 0.80.

| Variante | Cobertura global | Ancho global | Cobertura régimen A | Cobertura régimen B | Ancho régimen A | Ancho régimen B |
|---|---|---|---|---|---|---|
| global | 0.828 | 1.050 | 0.791 | 0.890 | 1.050 | 1.050 |
| regimen | 0.829 | 1.122 | 0.798 | 0.882 | 1.162 | 1.054 |
| regimen_tamano | 0.839 | 1.234 | 0.814 | 0.882 | 1.335 | 1.064 |
| regimen_escala | 0.825 | 1.130 | 0.802 | 0.863 | 1.161 | 1.076 |
| cvmas_global | 0.854 | 1.070 | 0.798 | 0.949 | 1.086 | 1.043 |
| cvmas_regimen | 0.855 | 1.126 | 0.802 | 0.945 | 1.181 | 1.033 |

Cobertura y ancho por cuartil de área. Los cuartiles son Q1 de 0.4 a 2.3 ha, Q2 de 2.3 a 4.9 ha, Q3 de 4.9 a 8.1 ha y Q4 de 8.3 a 64.3 ha.

| Variante | Cob. Q1 | Cob. Q2 | Cob. Q3 | Cob. Q4 | Ancho Q1 | Ancho Q2 | Ancho Q3 | Ancho Q4 |
|---|---|---|---|---|---|---|---|---|
| global | 0.760 | 0.847 | 0.794 | 0.909 | 1.047 | 1.050 | 1.053 | 1.050 |
| regimen | 0.777 | 0.829 | 0.794 | 0.914 | 1.138 | 1.119 | 1.099 | 1.132 |
| regimen_tamano | 0.766 | 0.912 | 0.782 | 0.897 | 1.324 | 1.303 | 1.117 | 1.193 |
| regimen_escala | 0.800 | 0.865 | 0.788 | 0.846 | 1.260 | 1.168 | 1.063 | 1.027 |
| cvmas_global | 0.766 | 0.865 | 0.835 | 0.949 | 1.074 | 1.063 | 1.052 | 1.092 |
| cvmas_regimen | 0.783 | 0.871 | 0.824 | 0.943 | 1.147 | 1.118 | 1.081 | 1.157 |

### Lectura

La cobertura global queda entre 0.825 y 0.855, algo por encima de 0.80. Las colas de los residuos son pesadas por las parcelas atípicas del régimen A. Los cuantiles con corrección de n + 1 también son conservadores. En el régimen A la cobertura es 0.80, que es la meta. En el régimen B es 0.88, o sea el intervalo es más ancho de lo necesario. El régimen B tiene residuos más chicos, con desviación de 0.38 t/ha contra 0.49 en A. El Mondrian por régimen reparte mejor el ancho que el intervalo global, con 1.16 t/ha en A y 1.05 en B.

Las parcelas chicas sí quedan peor cubiertas. En el primer cuartil de área la cobertura es 0.78 con Mondrian por régimen, contra 0.91 en el cuarto cuartil. Es decir, el intervalo es corto para las parcelas chicas y largo para las grandes. Partir cada régimen por tamaño no lo arregla. Con la separación en mediana, el primer cuartil queda en 0.77 y el segundo sube a 0.91, porque la mediana parte el grupo a la mitad y deja pocos residuos en cada lado. Escalar los residuos por el área sí mueve la cobertura donde corresponde. Sube el primer cuartil a 0.80 y baja el cuarto de 0.91 a 0.85, con ancho de 1.26 t/ha en las parcelas más chicas y 1.03 en las más grandes. A cambio, la cobertura del régimen B baja a 0.86. La desviación máxima de la cobertura por régimen respecto a 0.80 es 0.082 con el Mondrian por régimen y 0.063 con la escala, una diferencia menor al umbral de 0.02 que fijamos de antemano para cambiar de método. Con 138 parcelas, la diferencia de 0.02 en cobertura de un cuartil equivale a menos de 1 parcela por repetición, así que no la tratamos como una diferencia firme.

El CV+ cubre algo más que el conformal con residuos guardados, con 0.854 contra 0.829 de forma global, y con ancho parecido. En el régimen A queda en 0.80, igual que los demás. Su ventaja es teórica, pues requiere conservar un modelo por fold. Para producción es más simple guardar los residuos, y la cobertura medida con ese método es la que reportamos.

Método elegido. Conformal con residuos guardados y Mondrian por régimen. Es el más simple de los que quedan cerca de la meta en ambos regímenes. La escala por área queda documentada como alternativa si FIRA prioriza que las parcelas chicas no queden subcubiertas.

### Probabilidad de rendimiento bajo un umbral

Para una parcela con predicción p y régimen g, la probabilidad de que el rendimiento quede por debajo de un umbral u es la fracción de residuos de calibración del régimen g que cumplen p + r < u. El umbral por defecto es 2.5 t/ha. La probabilidad crece con el umbral y baja cuando sube la predicción. En las 59 parcelas a predecir el promedio es 0.003 para el régimen A y 0.161 para el B. Esto se debe a que la media del régimen B es 3.0 t/ha y sus residuos llegan a -1.1.

## Controles de sanidad de las 59 parcelas

Entrenamos el modelo elegido con las 138 parcelas y predijimos las 59 de predicción.

| Régimen | Media observada | Media predicha | Desviación observada | Desviación predicha | Razón pred/obs | Razón fuera de fold/obs |
|---|---|---|---|---|---|---|
| A | 4.489 | 4.487 | 0.533 | 0.222 | 0.417 | 0.294 |
| B | 3.045 | 3.055 | 0.396 | 0.174 | 0.440 | 0.240 |
| Todas | 3.955 | 3.953 | 0.851 | 0.728 | 0.855 | 0.828 |

El rango predicho en A es de 3.71 a 4.60 t/ha y en B de 2.71 a 3.69 t/ha. Ninguna predicción sale del rango observado en entrenamiento (2.0 a 5.6 t/ha) ni del rango de su régimen (2.15 a 5.59 en A y 2.0 a 3.7 en B). Las medias predichas coinciden con las observadas por régimen.

Hay encogimiento fuerte dentro de cada régimen. La desviación de las predicciones es 0.42 de la observada en A y 0.44 en B, y con todas las parcelas juntas es 0.86 porque la diferencia entre regímenes se conserva. En la validación cruzada la razón es todavía menor, 0.29 en A y 0.24 en B. Esto es esperable. Dentro de cada régimen el modelo explica poco de la variación y casi todo el poder viene del nivel del régimen. No lo corregimos. Una corrección artificial ampliaría la dispersión sin información que la respalde y subiría el error.

## Para usar los intervalos

Con el modelo entrenado en las 138 parcelas y la tabla de residuos de calibración guardada, `PrediccionIntervalo(modelo, calibrador, umbral).predecir(X)` devuelve para cada parcela nueva la predicción, el p10, el p90 y la probabilidad de rendimiento bajo el umbral. La tabla de entrada debe traer, además de las columnas que usa el modelo, el régimen y el área de la parcela.
