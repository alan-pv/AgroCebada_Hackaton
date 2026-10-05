## Modelado y validación

Medimos el error con el RMSE, que es la raíz del promedio de los errores elevados al cuadrado y se expresa en t/ha. Es la métrica oficial del reto. Todas las cifras salen de predicciones fuera de muestra de las 138 parcelas de entrenamiento.

Usamos dos esquemas de validación cruzada con particiones fijas. El esquema A reparte las parcelas al azar en 5 grupos, estratificado por municipio, y se repite 10 veces. Imita la división oficial y es el que decide. El esquema B deja fuera grupos espaciales completos. Mide cuánto depende un modelo de tener parcelas vecinas en el entrenamiento y no decide.

Antes de probar ninguna idea fijamos una regla de decisión. Una idea se acepta solo si tiene un RMSE menor que la mejor versión anterior en al menos 7 de las 10 repeticiones y si pasa una prueba de permutación. En esa prueba se revuelven juntas las variables nuevas dentro de cada régimen y se exige un p-valor de 0.05 o menos. Todo lo que usa el rendimiento, como el rezago espacial, se calcula dentro de cada partición para evitar fugas de información.

El orden de las pruebas fue el siguiente. Primero el régimen de etiquetas como variable base. Después el rezago espacial, que es el rendimiento promedio de las parcelas vecinas del mismo régimen a menos de 400 m. Luego los bloques satelitales, de clima y de topografía, el entrenamiento tolerante al ruido y, al final, el algoritmo y el promedio de modelos.

El modelo elegido es un proceso gaussiano que recibe el régimen y el rezago espacial, sin variables satelitales ni climáticas. Fue el único algoritmo que cumplió la regla. Probamos unas 50 variantes con las mismas particiones, así que su resultado es una cota optimista.

Los intervalos de predicción usan el método conformal. Se guardan los errores con signo del modelo en parcelas que no vio, separados por régimen, y se suman a la predicción de una parcela nueva. Así se obtiene un intervalo del percentil 10 al 90, que apunta a contener el rendimiento real en 80 % de las parcelas. Medimos su cobertura con una validación anidada, en la que la parcela de prueba no participa en el ajuste ni en la calibración.
