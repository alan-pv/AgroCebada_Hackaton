## Resultados y discusión

### Comparación con las bases

La tabla muestra el RMSE de cada modelo en los dos esquemas de validación, en t/ha. El esquema A es aleatorio y decide. El esquema B deja fuera grupos espaciales completos.

| Modelo | RMSE esquema A | RMSE esquema B |
|---|---|---|
| Media global | 0.850 | 1.143 |
| Media por estado | 0.604 | 1.055 |
| Media por municipio | 0.510 | 0.955 |
| Media por régimen de etiquetas | 0.489 | 0.488 |
| Vecinos más cercanos, k igual a 10 | 0.500 | 0.655 |
| Régimen y rezago espacial, con ridge | 0.463 | 0.495 |
| Modelo final, proceso gaussiano | 0.4525 | 0.489 |

El mayor salto viene de conocer el régimen de etiquetas. Pasar de la media global a la media por régimen baja el RMSE de 0.850 a 0.489. El estado y el municipio no lo igualan, y en el esquema B empeoran mucho porque sus categorías quedan sin datos. El régimen se conoce para cualquier parcela, así que no depende de tener vecinos.

### Qué aportó cada bloque

El rezago espacial es el rendimiento promedio de las parcelas vecinas del mismo régimen a menos de 400 m. Fue la única mejora clara sobre el régimen, con 9 victorias en 10 repeticiones. Con radios de 250 m, 600 m o 1 km no hubo mejora. Partiendo de ese modelo, agregamos cada bloque de variables y contamos en cuántas de 10 repeticiones mejoraba. Se necesitaban 7.

| Bloque agregado | RMSE esquema A | Victorias de 10 |
|---|---|---|
| Ninguno (régimen y rezago) | 0.463 | base |
| Fenología y satélite de 2025 | 0.473 | 0 |
| Historia de 2022 a 2024 | 0.464 | 5 |
| Heterogeneidad dentro de la parcela | 0.464 | 4 |
| Labranza | 0.472 | 0 |
| Temperatura de superficie | 0.466 | 1 |
| Clima | 0.471 | 0 |
| Topografía | 0.473 | 0 |

Ningún bloque cumplió la regla. Juntar todos los bloques satelitales fue peor, con 0.489. Tampoco ayudaron el entrenamiento tolerante al ruido de etiqueta ni el promedio de modelos. El mejor promedio, que incluía el proceso gaussiano, quedó 0.002 por encima de este último.

### Modelo final

El proceso gaussiano con régimen y rezago fue el único algoritmo que cumplió la regla, con 9 victorias en 10 y p-valor de 0.020. Obtiene un RMSE de 0.4525 t/ha, un error absoluto medio de 0.308 y un R² de 0.715. En el régimen A el RMSE baja de 0.535 a 0.491, y en el B de 0.398 a 0.379. En el esquema B empata con la media por régimen, porque sin vecinos cercanos no hay rezago que aprovechar. Las 59 predicciones tienen media de 4.49 t/ha en el régimen A y de 3.05 en el B, con rangos de 3.71 a 4.60 y de 2.71 a 3.69.

Esta cifra es optimista. Probamos unas 50 variantes con las mismas particiones y elegimos la mejor. Además, una calificación sobre 59 parcelas varía por azar. Al sortear 5000 grupos de 59 parcelas entre los errores de validación, el RMSE tiene desviación de 0.052, y el 90 % de los sorteos cae entre 0.365 y 0.534.

### Intervalos de predicción

Cada predicción trae un intervalo del percentil 10 al 90 que apunta a cubrir 80 % de los casos. Con validación anidada la cobertura es 0.83, con 0.80 en el régimen A y 0.88 en el B, y el ancho medio es 1.12 t/ha. El intervalo es más corto de lo debido en las parcelas pequeñas, donde cubre 0.78, contra 0.91 en las más grandes. La probabilidad de quedar bajo 2.5 t/ha supera 0.10 en 18 de las 59 parcelas, todas del régimen B.

### Preguntas guía

Para el índice más importante, la respuesta depende de si el modelo conoce el régimen. Sin él, el NDVI domina, pues revolver sus variables sube el RMSE 0.106 t/ha. Pero en parte indica el régimen y la zona, y el modelo solo con satélite llega a 0.696, muy lejos de 0.489. Con el régimen presente, el índice de sequía NDDI es el mayor, con 0.004 t/ha, una magnitud dentro del ruido.

Para el clima, sin régimen la lluvia pesa más, con 0.364 t/ha, porque las celdas de 5 km identifican la zona. Con el régimen presente ninguna variable climática aporta. En 2025 llovió el doble en mayo y junio que en los tres años previos, y los datos mensuales no miden la lluvia cercana al espigamiento.

Para la mejor combinación, la selección hacia adelante por bloques se detuvo en el régimen más el rezago. El siguiente candidato, la labranza, mejoró en 10 repeticiones pero su prueba de permutación dio p de 0.216.

### Las tres capas del error

La primera capa es la estructura de las etiquetas. Cuatro municipios reportan con dos decimales y rondan 4.5 t/ha, y cinco lo hacen en escalones de media tonelada y rondan 3 t/ha. Conocer el régimen explica la mayor parte de lo que se puede explicar. La segunda es el ruido de etiqueta. El productor declaró el rendimiento sin validación oficial, y el redondeo del régimen B pone un piso de unas 0.13 t/ha. La tercera es el tamaño de la muestra. Con 138 parcelas, diferencias de una o dos centésimas son azar.

Estas capas explican el encogimiento de las predicciones. La desviación predicha es 0.42 de la observada en el régimen A y 0.44 en el B. Las parcelas con rendimientos extremos quedan cerca de la media de su régimen.
