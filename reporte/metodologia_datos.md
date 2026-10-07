# Metodología de datos

## Fuentes

Usamos solo los datos entregados por los organizadores. No integramos datos externos. Las 197 parcelas son polígonos en EPSG:4326. La serie satelital del conjunto Básico trae Sentinel-2 y Landsat de 2022 a 2025. El conjunto PRO trae Planet de 2025. El clima mensual es CHIRPS (lluvia) y CHIRTS-ERA5 (temperaturas máxima y mínima), en EPSG:4326 y con celdas de 0.05 grados, unos 5 km. La topografía es el modelo de elevación de INEGI de 120 m en EPSG:6372, con la pendiente ya calculada.

## Limpieza de las series

Cada sensor se procesa por separado y no mezclamos índices homónimos entre sensores. Descartamos las observaciones con nubosidad mayor a 20 %. Con 10 % quedan 39 442 observaciones de Sentinel-2 y con 50 % quedan 41 866, contra 40 225 con 20 %, así que el umbral cambia poco el resultado. Después quitamos los picos aislados. Un pico es un valor que se aleja más de cuatro desviaciones robustas de la mediana móvil, con ventana de 10 días en Planet y de 15 días en Sentinel-2. Marcamos 218 valores de Planet y 16 296 de Sentinel-2, contando cada índice por separado. Componemos cada serie a pasos de 5 días y la suavizamos con el método de Whittaker, con lambda igual a 10 y pesos cero en los huecos. De Planet derivamos el NDRE como (LAI + 0.114) / 5.405. Del Landsat solo usamos el VI6T y lo tratamos como temperatura de superficie. Conservamos un índice de cada pareja equivalente, por ejemplo NDTI en lugar de STI.

## Agregaciones

El pico de verdor de cada parcela es el máximo del NDVI suavizado de Planet entre junio y octubre de 2025. Las ventanas de área bajo la curva se miden en días relativos a ese pico, para comparar parcelas en la misma etapa. La historia de 2022 a 2024 sale de Sentinel-2. La heterogeneidad usa la desviación estándar dentro de la parcela en la ventana del pico. El clima y la topografía se extraen con ponderación por el área que cada celda cubre de la parcela.

## Variables por bloque

La tabla final tiene 197 filas y 91 variables derivadas. Hay 52 de fenología de 2025, 3 de pico y siembra, 5 de historia, 4 de heterogeneidad, 4 de labranza, 2 de temperatura de superficie, 17 de clima y 5 de topografía. Las 197 parcelas caen en 29 celdas de clima y 25 de ellas contienen al centroide de alguna parcela, por lo que el clima describe sobre todo la zona. Los valores faltantes se dejan vacíos, con un máximo de 4.1 % en una variable.
