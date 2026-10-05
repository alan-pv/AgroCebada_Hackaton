# Ficha del modelo final

Esta ficha describe el modelo que genera las 59 predicciones de la entrega. Dice con qué datos se entrenó, cómo se validó, qué tan bien funciona, para qué sirve y qué no debe esperarse de él. La versión del modelo es 1.0 (tag `modelo-v1.0`) y la de las variables es `features-v1.0`.

## Resumen

El modelo predice el rendimiento de cebada de una parcela en toneladas por hectárea (t/ha) a partir de dos cosas. La primera es el régimen de etiquetas de su municipio. La segunda es el rendimiento de las parcelas de entrenamiento vecinas del mismo régimen a menos de 400 m. No usa imágenes de satélite, clima ni topografía, porque ningún bloque de esas variables pasó la regla de decisión del equipo. Además de la predicción entrega un intervalo p10 a p90 y la probabilidad de que el rendimiento quede bajo 2.5 t/ha.

| Medida | Valor |
|---|---|
| RMSE, esquema A (5 folds, 10 repeticiones, estratificado por municipio) | 0.4525 t/ha |
| MAE y R², esquema A | 0.308 t/ha y 0.715 |
| RMSE, esquema B (grupos espaciales) | 0.489 t/ha |
| Referencia, media por régimen, esquemas A y B | 0.489 y 0.488 t/ha |
| Cobertura del intervalo p10 a p90 (meta 0.80) | 0.83, ancho medio 1.12 t/ha |

## Datos

Usamos solo los datos entregados por los organizadores del reto. Son 197 parcelas de Puebla, Hidalgo y Tlaxcala. Las 138 de ENTRENAMIENTO traen el rendimiento de la temporada 2025. Las 59 de PREDICCION no lo traen y son las que califica FIRA. La división oficial se hizo al azar y estratificada por zona, así que las 59 están repartidas entre las mismas zonas que las 138.

Las fuentes disponibles son Sentinel-2 y Landsat de 2022 a 2025, Planet de 2025, lluvia CHIRPS, temperaturas CHIRTS-ERA5 y la topografía del CEM de INEGI. El modelo final usa solo cuatro columnas de la tabla de variables.

| Columna | Uso |
|---|---|
| `regimen` | Régimen de etiquetas del municipio, A o B. Entra codificado en forma binaria |
| `x_m`, `y_m` | Centroide en metros (EPSG:6372). Sirve para calcular las distancias del rezago espacial |
| `area_ha` | Solo para el intervalo. El modelo no la usa para predecir |

El régimen de etiquetas es una variable que construimos al notar que los rendimientos se dividen por municipio en dos formas de reportar. En cuatro municipios (Chignahuapan, Almoloya, Cuautepec de Hinojosa y Tepeapulco, régimen A) los valores tienen dos decimales y rondan 4.5 t/ha. En cinco (Singuilucan, Emiliano Zapata, Apan, Calpulalpan y Nanacamilpa, régimen B) los valores están redondeados a 0.5 o a 0.1 y rondan 3.0 t/ha. En el entrenamiento hay 87 parcelas del régimen A y 51 del B. En las 59 hay 37 y 22.

## Modelo

Es un proceso gaussiano con una entrada de régimen en forma binaria y una entrada de rezago espacial.

* El rezago espacial de una parcela es el promedio del rendimiento de las parcelas de entrenamiento del mismo régimen a 400 m o menos, hasta 10 vecinos, ponderadas por el inverso de la distancia (con una distancia mínima de 1 m). Si no hay vecinos en el radio, recibe la media de su régimen. El modelo ve solo ese valor, estandarizado, y no el número de vecinos ni la distancia.
* El proceso gaussiano usa un kernel de función de base radial más un término de ruido blanco, con la variable objetivo normalizada. Los valores iniciales son varianza 0.1, escala 3.0 y ruido 0.2. Tras el ajuste con las 138 parcelas quedan varianza 0.81 (0.902 al cuadrado), escala 1.65 y ruido 0.256. La semilla es 2026.
* Todo lo que usa el rendimiento se calcula dentro del ajuste. En entrenamiento el rezago de cada parcela excluye a la propia parcela.
* El intervalo se calcula con el método conformal (residuos guardados) con un grupo por régimen. Los residuos son los errores con signo del esquema A, 10 repeticiones por 138 parcelas. El p10 y el p90 suman a la predicción los cuantiles 0.1 y 0.9 de los residuos del régimen, con la corrección de n + 1. La probabilidad bajo el umbral es la fracción de residuos del régimen que cumple predicción + residuo < 2.5.

## Validación

Usamos dos esquemas de validación cruzada con particiones fijas y guardadas.

* El esquema A reparte las parcelas al azar en 5 folds, estratificado por municipio, y se repite 10 veces. Imita la división oficial y es el que decide.
* El esquema B deja grupos espaciales completos fuera. Mide cuánto depende un modelo de tener vecinos cercanos. No decide.

Una idea se acepta solo si gana a la mejor versión anterior en al menos 7 de las 10 repeticiones del esquema A y si pasa una prueba de permutación con p de 0.05 o menos. El orden de las pruebas fue régimen, rezago espacial, bloques satelitales, clima y topografía, entrenamiento tolerante al ruido, algoritmos y promedios de modelos.

Hay un sesgo de selección. Probamos unas 50 variantes con las mismas particiones y elegimos la mejor. Por eso el RMSE de 0.4525 es una cifra optimista. No sabemos cuánto, pero la prueba con rendimientos permutados no mostró fuga de información (el modelo no mejora a la media global cuando las etiquetas se revuelven). La mejora sobre la media por régimen es de 0.036 t/ha en el esquema A, y el modelo solo la logra gracias a los vecinos. En el esquema B, sin vecinos cercanos, empata con la media por régimen.

## Métricas

RMSE y MAE en t/ha, promedio de las 10 repeticiones del esquema A. La desviación del RMSE entre repeticiones es 0.018.

| Grupo | Parcelas | RMSE A | MAE A | RMSE B |
|---|---|---|---|---|
| Todas | 138 | 0.4525 | 0.308 | 0.4889 |
| Régimen A | 87 | 0.491 | 0.322 | 0.533 |
| Régimen B | 51 | 0.379 | 0.284 | 0.404 |
| Hidalgo | 36 | 0.317 | 0.224 | 0.339 |
| Puebla | 71 | 0.536 | 0.362 | 0.584 |
| Tlaxcala | 31 | 0.370 | 0.282 | 0.386 |

La media por régimen da 0.535 en el régimen A y 0.398 en el B. El modelo mejora en ambos, con 0.491 y 0.379.

Intervalos p10 a p90 con validación cruzada anidada. En cada fold externo la parcela de prueba no participa en el ajuste ni en la calibración. La meta de cobertura es 0.80.

| Grupo | Cobertura | Ancho medio (t/ha) |
|---|---|---|
| Todas | 0.829 | 1.12 |
| Régimen A | 0.798 | 1.16 |
| Régimen B | 0.882 | 1.05 |
| Cuartil de área menor (0.4 a 2.3 ha) | 0.777 | 1.14 |
| Cuartil de área mayor (8.3 a 64.3 ha) | 0.914 | 1.13 |

En las 59 parcelas el ancho medio es 1.06 t/ha. La probabilidad media de quedar bajo 2.5 t/ha es 0.003 en el régimen A y 0.161 en el B. En 18 parcelas, todas del régimen B, supera 0.10.

### Margen de azar de una calificación sobre 59 parcelas

La calificación oficial es un solo RMSE sobre 59 parcelas, y con tan pocas parcelas varía por azar aunque el modelo sea el mismo. Para estimar esa variación tomamos los errores fuera de fold del esquema A y sorteamos 5000 grupos de 59 parcelas, con 37 del régimen A y 22 del B como en la predicción oficial. El RMSE medio de los sorteos es 0.450, con desviación de 0.052. El 90 % de los sorteos cae entre 0.365 y 0.534. Es decir que un RMSE oficial entre 0.37 y 0.53 es compatible con el mismo modelo. Es una estimación aproximada, porque los sorteos salen de las mismas 138 parcelas y no de una población nueva. La diferencia entre dos modelos cercanos, como las 0.036 t/ha que ganamos a la media por régimen, es mucho menor que este margen.

## Uso previsto

El modelo está pensado para dos usos.

* FIRA, para apoyar decisiones de crédito y de riesgo. La predicción da un rendimiento esperado de referencia. El p10 da un rendimiento conservador que se supera en 9 de cada 10 casos si el intervalo está bien calibrado. La probabilidad bajo 2.5 t/ha marca las parcelas donde el rendimiento podría ser bajo. Conviene usar el intervalo y no solo el valor puntual.
* Productores, para tener una referencia del rendimiento esperado de una parcela cercana a otras ya medidas.

No está pensado para decidir solo un crédito ni para reemplazar la verificación en campo. Tampoco para parcelas fuera de las tres entidades, para otros cultivos ni para otras temporadas, porque se entrenó con una sola temporada. Una parcela sin vecinos cercanos del mismo régimen recibe casi la media de su régimen.

## Limitaciones

1. Dos regímenes de medición probables. Los rendimientos parecen provenir de dos formas de medir o reportar que se separan por municipio. Lo inferimos de los patrones de redondeo y de los niveles, y no está confirmado por los organizadores. El modelo depende de esa variable. Una parcela con un municipio nuevo no tendría régimen asignado.
2. Rendimiento declarado por el productor. Los organizadores aclararon que el rendimiento lo declaró cada productor sin validación oficial. Una parte del error de predicción es ruido de etiqueta que ningún modelo puede explicar.
3. Redondeo en el régimen B. Con 86.3 % de los valores en múltiplos de 0.5, el error de redondeo aporta una desviación de 0.144 t/ha por parcela redondeada. Eso fija un piso de unas 0.13 t/ha para el RMSE del régimen B. Nuestro 0.379 está por encima de ese piso, y la diferencia incluye el resto del ruido.
4. Posible sobrerreporte en parcelas pequeñas. Las parcelas del cuartil de menor área tienen el mayor error fuera de muestra (0.558 contra 0.327 a 0.481 en los demás cuartiles) y el intervalo las cubre menos (0.777). Sospechamos que sus rendimientos son más ruidosos. No lo podemos confirmar con estos datos.
5. Encogimiento hacia la media del régimen. Dentro de cada régimen las predicciones varían mucho menos que los rendimientos. La razón entre la desviación predicha y la observada es 0.42 en el régimen A y 0.44 en el B para las 59 parcelas, y 0.29 y 0.24 fuera de fold. El modelo acierta el nivel del régimen y corrige poco dentro de él. Las parcelas con rendimientos extremos, por ejemplo las de 5.4 a 5.6 t/ha de Chignahuapan, quedan siempre cerca de 4.5 t/ha. No corregimos el encogimiento porque ampliar la dispersión sin información que la respalde subiría el error.
6. Variedad y fecha de siembra desconocidas. Son factores agronómicos de peso y no están en los datos. Una parte de la variación entre parcelas vecinas viene de ellos y no puede capturarse.
7. Satélite y clima sin aporte estable. Una vez conocidos el régimen y los vecinos, el mejor bloque de variables aporta del orden de 0.01 t/ha y no pasa la regla. El clima viene en celdas de unos 5 km, así que describe la zona y no la parcela. Las variables que parecen importantes cuando el régimen no está presente lo son porque lo identifican.
8. Cifra optimista y margen de azar. El RMSE de validación se obtuvo eligiendo entre unas 50 variantes con las mismas particiones, y la calificación sobre 59 parcelas tiene una desviación de unas 0.05 t/ha por azar.
9. Parcelas de entrenamiento. Para una parcela que ya está en el entrenamiento el modelo final no sirve tal cual. Su rezago incluiría a ella misma a distancia cero y la predicción saldría pegada a su propia etiqueta. Con el modelo final las 138 parcelas dan un RMSE de 0.265 t/ha contra 0.447 fuera de fold. Por eso la función de predicción devuelve para esas parcelas la predicción fuera de fold promediada en las 10 repeticiones del esquema A. Esa es la cifra que usa la aplicación. La cifra de 0.447 es menor que 0.4525 porque promediar las repeticiones reduce algo el error, y no es una medida de desempeño nueva.

## Controles de la entrega por régimen

Los controles se ejecutan al generar la entrega y detienen el proceso si fallan. Los primeros ocho aplican a las 59 parcelas, y los demás solo se reportan.

| Control | Régimen A (37 parcelas) | Régimen B (22 parcelas) | Resultado |
|---|---|---|---|
| Rango de la predicción | 3.71 a 4.60 t/ha | 2.71 a 3.69 t/ha | Cumple |
| Rango observado en entrenamiento | 2.15 a 5.59 t/ha | 2.00 a 3.70 t/ha | Cumple |
| Media predicha contra media de entrenamiento | 4.487 contra 4.489 | 3.055 contra 3.045 | Cumple, diferencia menor a 0.25 |
| Razón de desviaciones (predicha entre observada) | 0.42 | 0.44 | Se reporta |
| Intervalo medio p10 a p90 | 3.98 a 5.06 | 2.51 a 3.54 | Cumple p10 ≤ pred ≤ p90 |
| Cobertura del intervalo (validación anidada) | 0.798 | 0.882 | Se reporta |
| RMSE esquema A | 0.491 | 0.379 | Se reporta |

Los controles que aplican a las 59 en conjunto son estos. Hay 59 filas, los IDs son exactamente los de PREDICCION, no hay nulos ni duplicados, y todas las predicciones están entre 2.0 y 5.6 t/ha. La razón de desviaciones con todas las parcelas juntas es 0.86, porque la diferencia entre regímenes se conserva. El resultado de cada control queda en la tabla de controles de la entrega. La coherencia espacial se revisa con un mapa y con la correlación entre cada predicción y el rendimiento medio de sus vecinos del mismo régimen a 400 m, que es 0.975 en las 36 parcelas que tienen vecinos. Esa correlación es alta porque el rezago es la entrada principal del modelo, así que sirve para detectar errores de código y no como evidencia de desempeño.
