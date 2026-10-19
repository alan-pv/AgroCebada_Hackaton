# Validación

Con 138 parcelas de entrenamiento, una mejora pequeña puede ser azar. Por eso fijamos cómo medimos el error y cuándo aceptamos una idea antes de probar ninguna. Este documento describe esos acuerdos y los resultados de los modelos más sencillos, que sirven de punto de comparación.

## Métricas

La métrica oficial del reto es la raíz del error cuadrático medio (RMSE) sobre las 59 parcelas ocultas. Es la raíz del promedio de los errores elevados al cuadrado. Se expresa en t/ha y castiga más los errores grandes. Es nuestra métrica principal.

Reportamos también dos métricas de apoyo. El error absoluto medio (MAE) es el promedio de los errores sin signo y se lee directo en t/ha. El coeficiente de determinación (R²) compara el error del modelo con el de predecir siempre la media. Vale 0 si el modelo no mejora a la media y 1 si no se equivoca. Puede ser negativo.

Cada métrica se calcula con las predicciones fuera de muestra de las 138 parcelas, una repetición a la vez. Reportamos la media y la desviación estándar entre repeticiones. También reportamos el RMSE y el MAE por régimen de etiqueta y por estado.

## Dos esquemas de validación cruzada

La validación cruzada separa una parte de las parcelas, entrena con el resto y mide el error en las separadas. Repetimos el proceso hasta que cada parcela se haya predicho una vez sin haberla visto. Todas las particiones se generan con la semilla 2026 y se guardan en un archivo, de modo que todo el equipo usa exactamente las mismas.

### Esquema A, el principal

El esquema A usa 5 folds y 10 repeticiones. Cada repetición reparte las 138 parcelas al azar en 5 grupos de 27 o 28 parcelas. Cada grupo se usa una vez como prueba. La división oficial entre entrenamiento y predicción se hizo al azar y estratificada por zona. Por eso el esquema A también es aleatorio y estratificado por municipio. Estratificar significa que cada fold recibe casi la misma proporción de cada municipio.

Cuatro municipios tienen muy pocas parcelas de entrenamiento. Tepeapulco y Apan tienen 1, Nanacamilpa tiene 2 y Emiliano Zapata tiene 3. Un estrato con menos de 5 parcelas no se puede repartir entre 5 folds. Resolvemos esto con una regla fija.

1. Un municipio con menos de 5 parcelas de entrenamiento pasa a un estrato "otros" de su régimen.
2. Si ese estrato sigue con menos de 5 parcelas, se une al municipio más grande de su régimen.

En el régimen B, Apan, Nanacamilpa y Emiliano Zapata suman 5 parcelas y forman el estrato "otros_B". En el régimen A solo queda Tepeapulco con 1 parcela, así que se une a Chignahuapan. Los estratos finales son estos.

| Estrato | Parcelas |
|---|---|
| Chignahuapan (con Tepeapulco) | 72 |
| Calpulalpan | 30 |
| Singuilucan | 16 |
| Almoloya | 10 |
| Cuautepec de Hinojosa | 5 |
| otros_B (Apan, Nanacamilpa, Emiliano Zapata) | 5 |

Con esta regla, el número de parcelas de cada estrato en un fold difiere como máximo en una unidad entre folds.

### Esquema B, por clusters espaciales

El esquema B mide cuánto depende un modelo de tener vecinos cercanos en el entrenamiento. Agrupamos los centroides de las parcelas con enlace simple. En este método, dos parcelas quedan en el mismo cluster si existe una cadena de parcelas donde cada paso mide 2 km o menos. Usamos las coordenadas en metros (EPSG:6372). Salen 16 clusters con estos tamaños.

| Tamaño del cluster | 71 | 28 | 15 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|
| Número de clusters | 1 | 1 | 1 | 5 | 1 | 7 |

El cluster de 71 parcelas es Chignahuapan completo. El de 28 junta a Calpulalpan, Nanacamilpa y Apan. El de 15 es la mayor parte de Singuilucan. Cada cluster cae entero en un solo fold. En cada repetición se barajan los clusters y se asigna cada uno, del más grande al más pequeño, al fold con menos parcelas. Los folds quedan con 71, 28, 15, 12 y 12 parcelas.

El esquema B es mucho más duro que el A porque un fold completo, el de Chignahuapan, se predice sin ninguna parcela de su zona. No lo usamos para decidir. Lo usamos para ver qué modelos se apoyan en la cercanía entre parcelas, que es lo que el esquema A permite y la predicción oficial también permite, porque las 59 parcelas ocultas están repartidas entre las mismas zonas.

## Regla de decisión

Una idea se acepta solo si cumple dos condiciones, ambas medidas con el esquema A y con las mismas particiones.

1. La comparación emparejada. El modelo nuevo tiene un RMSE menor que la mejor versión anterior en al menos 7 de las 10 repeticiones. Reportamos también la diferencia media de RMSE, que es negativa cuando el modelo nuevo mejora.
2. La prueba de permutación. El bloque de variables nuevas se revuelve de forma conjunta, con el mismo orden de filas para todas las columnas del bloque, y solo entre parcelas del mismo régimen. Esto rompe la relación de las variables con el rendimiento y conserva el efecto del régimen. Se repite 50 veces y se reevalúa el modelo cada vez. El p-valor es (1 + k) / (n + 1), donde n es el número de permutaciones y k cuántas veces el RMSE con variables revueltas fue menor o igual al RMSE real. Aceptamos con un p-valor de 0.05 o menos.

Cada evaluación completa del esquema A requiere 50 ajustes. Con 50 permutaciones serían 2500 ajustes por prueba. Para reducir el costo, la prueba usa solo las 3 primeras repeticiones del esquema A, o sea 15 ajustes por permutación, y calcula el RMSE real con esas mismas 3 repeticiones. El número de repeticiones se puede cambiar. Con 50 permutaciones, el menor p-valor posible es 1 / 51, cerca de 0.02.

Las ideas que no cumplan la regla se registran como probadas y descartadas. Cada experimento queda como una fila en `experimentos/registro.csv` con sus métricas, su decisión y sus notas. Las particiones están en `experimentos/particiones.parquet` y el código en `src/agrocebada/cv.py`.

## Piso de error por redondeo

En el régimen B los rendimientos están redondeados, y ningún modelo puede predecir el error que introduce el redondeo. Si un valor se redondea a un múltiplo de 0.5, el error de redondeo se reparte de forma pareja entre -0.25 y 0.25. Su desviación estándar es √(0.5² / 12), que vale 0.144 t/ha. Ese valor es un piso para el RMSE de las parcelas redondeadas, porque el modelo tendría que predecir el valor ya redondeado.

Revisamos cuántos rendimientos de entrenamiento son múltiplos exactos de 0.5 y de 0.1.

| Régimen | Parcelas | Múltiplos de 0.5 | Múltiplos de 0.1 |
|---|---|---|---|
| A | 87 | 1 (1.1 %) | 7 (8.0 %) |
| B | 51 | 44 (86.3 %) | 51 (100 %) |

En el régimen B todos los valores tienen un solo decimal y 86.3 % son múltiplos de 0.5. Los 7 restantes son múltiplos de 0.1 que no lo son de 0.5. En el régimen A casi ningún valor es redondo, así que el redondeo no explica su error. Si el 86.3 % de las parcelas del régimen B tiene un error de redondeo de 0.144 t/ha, ese grupo aporta un piso de unas 0.13 t/ha al RMSE del régimen. Es un piso aproximado y supone que el redondeo se aplicó sobre el rendimiento real. Cualquier otro error de registro se suma a él.

## Modelos de referencia

Las cifras salen de `scripts/baselines.py` y quedan en `experimentos/baselines_tabla.csv`.

Evaluamos cada modelo con los dos esquemas. Los modelos son los siguientes.

* Media global. Predice la media de las parcelas de entrenamiento.
* Media por estado, por municipio y por régimen. Predice la media del grupo de la parcela.
* kNN espacial. Promedia el rendimiento de las k parcelas de entrenamiento más cercanas, ponderadas por el inverso de la distancia, con k igual a 3, 5 y 10.
* Ridge. Regresión lineal con penalización sobre el estado codificado, la longitud, la latitud y el área.

La tabla muestra el RMSE de cada esquema, su desviación entre las 10 repeticiones del esquema A, el MAE y el R², y el RMSE por régimen.

| Modelo | RMSE A | sd A | MAE A | R² A | RMSE A, reg. A | RMSE A, reg. B | RMSE B | MAE B | R² B | RMSE B, reg. A | RMSE B, reg. B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Media global | 0.850 | 0.001 | 0.750 | -0.004 | 0.754 | 0.992 | 1.143 | 1.055 | -0.815 | 1.136 | 1.154 |
| Media por estado | 0.604 | 0.003 | 0.440 | 0.492 | 0.632 | 0.554 | 1.055 | 0.920 | -0.549 | 1.189 | 0.777 |
| Media por municipio | 0.510 | 0.003 | 0.331 | 0.639 | 0.540 | 0.454 | 0.955 | 0.785 | -0.268 | 1.110 | 0.605 |
| Media por régimen | 0.489 | 0.003 | 0.323 | 0.668 | 0.535 | 0.398 | 0.488 | 0.323 | 0.669 | 0.533 | 0.400 |
| kNN espacial, k = 3 | 0.525 | 0.020 | 0.386 | 0.617 | 0.553 | 0.471 | 0.609 | 0.419 | 0.484 | 0.539 | 0.712 |
| kNN espacial, k = 5 | 0.517 | 0.012 | 0.380 | 0.628 | 0.558 | 0.440 | 0.632 | 0.431 | 0.444 | 0.536 | 0.770 |
| kNN espacial, k = 10 | 0.500 | 0.009 | 0.363 | 0.652 | 0.541 | 0.423 | 0.655 | 0.454 | 0.403 | 0.542 | 0.813 |
| Ridge, estado, lon, lat y área | 0.538 | 0.008 | 0.379 | 0.598 | 0.576 | 0.464 | 0.715 | 0.568 | 0.290 | 0.662 | 0.796 |

Tres observaciones se desprenden de la tabla.

* La media por régimen es el mejor baseline, con un RMSE de 0.489 t/ha en el esquema A. Mejora a la media por municipio en 0.021 t/ha y a la media por estado en 0.115 t/ha.
* En el esquema B, la media por estado y la media por municipio empeoran mucho, porque los municipios completos quedan fuera del entrenamiento. La media por régimen casi no cambia. El régimen se conoce para cualquier parcela y no depende de tener vecinos.
* Los kNN espaciales empeoran de 0.50 a 0.65 al pasar del esquema A al B. Esa diferencia mide cuánto aportan los vecinos cercanos.

### Regla de decisión aplicada al régimen

Aplicamos la regla de decisión a la media por régimen contra la media por estado y contra la media por municipio. Para la prueba de permutación usamos 200 permutaciones y las 10 repeticiones. Revolvimos la columna del régimen entre todas las parcelas, porque revolverla solo dentro del régimen no la modifica. Las particiones se mantienen fijas.

| Comparación | Victorias en 10 | Diferencia media de RMSE | p-valor | Decisión |
|---|---|---|---|---|
| Régimen contra estado | 10 | -0.115 | 0.005 | Aceptada |
| Régimen contra municipio | 10 | -0.021 | 0.005 | Aceptada |

Con 200 permutaciones, 0.005 es el menor p-valor posible. El régimen cumple la regla contra ambas bases. La diferencia contra el municipio es pequeña en t/ha, pero se repite en las 10 repeticiones.
