# Ensemble e intervalos de predicción

Este documento reúne dos pruebas. La primera busca si promediar modelos distintos mejora al candidato de la versión 1. La segunda construye intervalos de predicción para cada parcela y mide si cumplen lo que prometen. FIRA es una institución de crédito, así que además de la predicción le sirve saber cuánto puede equivocarse el modelo en cada parcela.

## Promedio de modelos

Un ensemble es un promedio de las predicciones de varios modelos. Aquí usamos promedio simple, con el mismo peso para cada miembro, y no entrenamos ningún meta-modelo. Si los pesos se eligieran mirando la misma validación cruzada, el resultado quedaría inflado por sesgo de selección. Por eso no probamos pesos.

Los miembros son el candidato y cuatro modelos con enfoques distintos. Todos ven el régimen de etiquetas y el rezago espacial a 400 m del mismo régimen. Las cifras de este documento ya usan el rezago corregido, cuyo relleno para parcelas sin vecinos no incluye la propia etiqueta.

| Miembro | Descripción |
|---|---|
| cand | Proceso gaussiano con régimen y rezago, el candidato de la versión 1 |
| ridge_rezago | Regresión ridge solo con régimen y rezago |
| rf_hist_het | Bosque aleatorio de profundidad 3 con 9 variables históricas y de heterogeneidad (`hist_` y `het_`) |
| lgbm_hist_het | LightGBM poco profundo con las mismas 9 variables |
| residuos_ridge | Media por régimen más un ridge sobre el residuo, con las mismas 9 variables y el rezago |

Cada ensemble se compara con el candidato de la versión 1 con la regla de decisión del proyecto. Se acepta con 7 o más victorias de 10 repeticiones en el esquema A y con prueba de permutación de p menor o igual a 0.05. La permutación solo se corre si hay 7 victorias.

| Modelo | RMSE A | RMSE B | RMSE A, régimen A | RMSE A, régimen B | Victorias | Aceptada |
|---|---|---|---|---|---|---|
| Candidato v1 (gp) | 0.4582 | 0.4888 | 0.494 | 0.389 | base | base |
| ridge_rezago (miembro) | 0.4696 | 0.4952 | 0.514 | 0.382 |  |  |
| rf_hist_het (miembro) | 0.4883 | 0.4857 | 0.524 | 0.420 |  |  |
| lgbm_hist_het (miembro) | 0.4946 | 0.4838 | 0.543 | 0.399 |  |  |
| residuos_ridge (miembro) | 0.4853 | 0.4827 | 0.536 | 0.383 |  |  |
| cand + ridge_rezago | 0.4602 | 0.4912 | 0.500 | 0.383 | 2 | no |
| cand + rf | 0.4678 | 0.4838 | 0.505 | 0.397 | 1 | no |
| cand + ridge_rezago + rf | 0.4649 | 0.4860 | 0.504 | 0.389 | 1 | no |
| cand + ridge_rezago + rf + residuos_ridge | 0.4676 | 0.4841 | 0.510 | 0.385 | 1 | no |
| cand + lgbm + residuos_ridge | 0.4700 | 0.4823 | 0.515 | 0.381 | 1 | no |

Ningún ensemble gana al candidato en el esquema A. El mejor, cand + ridge_rezago, queda 0.0020 t/ha por encima y gana en 2 de 10 repeticiones. Los ensembles con modelos de árboles sí bajan el error del esquema B, que pasa de 0.489 a entre 0.482 y 0.486, pero esa diferencia es de 0.003 a 0.007 t/ha y el esquema B no decide. Los miembros con variables satelitales y de historia son peores que el proceso gaussiano por sí solos, y promediarlos con él arrastra el resultado hacia arriba. Esto coincide con lo que vimos en la versión 1, donde esos bloques no pasaron la regla.

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
| global | 0.836 | 1.061 | 0.789 | 0.918 | 1.061 | 1.061 |
| regimen | 0.826 | 1.130 | 0.791 | 0.886 | 1.168 | 1.064 |
| regimen_tamano | 0.842 | 1.253 | 0.821 | 0.878 | 1.329 | 1.123 |
| regimen_escala | 0.826 | 1.133 | 0.802 | 0.867 | 1.163 | 1.081 |
| cvmas_global | 0.849 | 1.103 | 0.802 | 0.929 | 1.100 | 1.109 |
| cvmas_regimen | 0.849 | 1.156 | 0.798 | 0.937 | 1.186 | 1.105 |

Cobertura y ancho por cuartil de área. Los cuartiles son Q1 de 0.4 a 2.3 ha, Q2 de 2.3 a 4.9 ha, Q3 de 4.9 a 8.1 ha y Q4 de 8.3 a 64.3 ha.

| Variante | Cob. Q1 | Cob. Q2 | Cob. Q3 | Cob. Q4 | Ancho Q1 | Ancho Q2 | Ancho Q3 | Ancho Q4 |
|---|---|---|---|---|---|---|---|---|
| global | 0.766 | 0.865 | 0.800 | 0.914 | 1.058 | 1.061 | 1.062 | 1.062 |
| regimen | 0.771 | 0.835 | 0.788 | 0.909 | 1.144 | 1.129 | 1.104 | 1.142 |
| regimen_tamano | 0.777 | 0.918 | 0.776 | 0.897 | 1.329 | 1.310 | 1.163 | 1.210 |
| regimen_escala | 0.800 | 0.871 | 0.782 | 0.851 | 1.248 | 1.169 | 1.070 | 1.044 |
| cvmas_global | 0.777 | 0.876 | 0.824 | 0.920 | 1.086 | 1.098 | 1.090 | 1.139 |
| cvmas_regimen | 0.777 | 0.865 | 0.829 | 0.926 | 1.161 | 1.146 | 1.111 | 1.206 |

### Lectura

La cobertura global queda entre 0.826 y 0.849, algo por encima de 0.80. Las colas de los residuos son pesadas por las parcelas atípicas del régimen A, y los cuantiles con corrección de n + 1 son conservadores. Con el Mondrian por régimen la cobertura es 0.79 en el régimen A, cerca de la meta, y 0.89 en el B, o sea el intervalo de B es más ancho de lo necesario. El régimen B tiene residuos más chicos, con desviación de 0.39 t/ha contra 0.50 en A. El Mondrian por régimen reparte mejor el ancho que el intervalo global, con 1.17 t/ha en A y 1.06 en B.

Las parcelas chicas quedan peor cubiertas. En el primer cuartil de área la cobertura es 0.77 con Mondrian por régimen, contra 0.91 en el cuarto cuartil. Es decir, el intervalo es corto para las parcelas chicas y largo para las grandes. Partir cada régimen por tamaño no lo arregla. Escalar los residuos por el área sí mueve la cobertura donde corresponde. Sube el primer cuartil a 0.80 y baja el cuarto a 0.85, con ancho de 1.25 t/ha en las parcelas más chicas y 1.04 en las más grandes. También acerca el régimen B a la meta, de 0.89 a 0.87.

Antes de ver los resultados fijamos un criterio. Se usa el Mondrian por régimen salvo que otra variante con residuos guardados reduzca en más de 0.02 la desviación máxima de la cobertura por régimen respecto a 0.80. Con el Mondrian por régimen esa desviación es 0.086 y con la escala por área es 0.067. La diferencia, 0.019, no supera el umbral. Con 138 parcelas una diferencia así equivale a pocas parcelas por repetición.

El CV+ cubre algo más que el conformal con residuos guardados, con 0.849 contra 0.826 de forma global, sobre todo en el régimen B (0.93). Su ventaja es teórica, pues requiere conservar un modelo por fold. Para producción es más simple guardar los residuos, y la cobertura medida con ese método es la que reportamos.

Método elegido. Conformal con residuos guardados y Mondrian por régimen. Es el más simple de los que quedan cerca de la meta en ambos regímenes. La escala por área queda documentada como alternativa si FIRA prioriza que las parcelas chicas no queden subcubiertas.

### Probabilidad de rendimiento bajo un umbral

Para una parcela con predicción p y régimen g, la probabilidad de que el rendimiento quede por debajo de un umbral u es la fracción de residuos de calibración del régimen g que cumplen p + r < u. El umbral por defecto es 2.5 t/ha. La probabilidad crece con el umbral y baja cuando sube la predicción. En las 59 parcelas a predecir el promedio es 0.003 para el régimen A y 0.171 para el B, y supera 0.10 en 18 parcelas, todas del régimen B. Esto se debe a que la media del régimen B es 3.0 t/ha y sus residuos llegan a -1.1.

## Controles de sanidad de las 59 parcelas

Entrenamos el modelo elegido con las 138 parcelas y predijimos las 59 de predicción.

| Régimen | Media observada | Media predicha | Desviación observada | Desviación predicha | Razón pred/obs | Razón fuera de fold/obs |
|---|---|---|---|---|---|---|
| A | 4.489 | 4.485 | 0.533 | 0.217 | 0.407 | 0.262 |
| B | 3.045 | 3.055 | 0.396 | 0.165 | 0.417 | 0.211 |
| Todas | 3.955 | 3.952 | 0.851 | 0.725 | 0.852 | 0.824 |

El rango predicho en A es de 3.72 a 4.58 t/ha y en B de 2.75 a 3.66 t/ha. Ninguna predicción sale del rango observado en entrenamiento (2.0 a 5.6 t/ha) ni del rango de su régimen (2.15 a 5.59 en A y 2.0 a 3.7 en B). Las medias predichas coinciden con las observadas por régimen.

Hay encogimiento fuerte dentro de cada régimen. La desviación de las predicciones es 0.41 de la observada en A y 0.42 en B, y con todas las parcelas juntas es 0.85 porque la diferencia entre regímenes se conserva. En la validación cruzada la razón es todavía menor, 0.26 en A y 0.21 en B. Esto es esperable. Dentro de cada régimen el modelo explica poco de la variación y casi todo el poder viene del nivel del régimen. No lo corregimos. Una corrección artificial ampliaría la dispersión sin información que la respalde y subiría el error.

## Para usar los intervalos

Con el modelo entrenado en las 138 parcelas y la tabla de residuos de calibración guardada, `PrediccionIntervalo(modelo, calibrador, umbral).predecir(X)` devuelve para cada parcela nueva la predicción, el p10, el p90 y la probabilidad de rendimiento bajo el umbral. La tabla de entrada debe traer, además de las columnas que usa el modelo, el régimen y el área de la parcela.
