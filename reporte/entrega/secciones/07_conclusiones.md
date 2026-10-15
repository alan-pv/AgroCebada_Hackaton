El modelo final es un proceso gaussiano que usa el régimen de registro del municipio y el rendimiento de las parcelas vecinas del mismo régimen a 400 m o menos. Obtiene un RMSE de 0.458 t/ha, un MAE de 0.312 t/ha y un R² de 0.71 en validación cruzada repetida. Con validación anidada, que incluye el costo de elegir, el RMSE es 0.490. Por ello esperamos un error de 0.46 a 0.49 t/ha en las 59 parcelas. La mejora sobre la media por régimen es de 0.029 t/ha y no es significativa.

Nuestros resultados sugieren que el límite de este reto está más en las etiquetas que en el algoritmo. Los municipios registran el rendimiento de dos formas, con medias de 4.49 y 3.05 t/ha, y conocer ese régimen reduce el error más que cualquier otra variable que probamos. La fuente mixta es una explicación posible que no pudimos confirmar, y no medimos el ruido de etiqueta. Datos de campo como el rendimiento medido, la fuente de cada registro y la fecha de siembra ayudarían más que un modelo más complejo.

Sobre las preguntas guía, sin el régimen el NDVI es el índice de mayor peso, pero actúa como indicador de zona. Con el régimen y los vecinos, el NDDI es el mayor, con un aporte cercano a 0.004 t/ha. La lluvia pesa sin el régimen y no aporta con él. La mejor combinación es el régimen más el rezago espacial.

Un error de 0.46 t/ha equivale a unos 2,500 $/ha, de 9 a 10 % del costo total del paquete. La herramienta ordena parcelas y abre una conversación de crédito, pero no decide sobre una parcela individual, porque el margen depende más del precio y del costo que del error de rendimiento.

El modelo de parcela es una estimación de cierre de temporada, pues usa rendimientos de vecinas de la misma temporada. Para usarlo antes de la cosecha harían falta rendimientos de ciclos anteriores y clima diario por parcela, que no probamos.

La capa de crédito entrega la probabilidad de no cubrir el crédito o el costo, un semáforo y el ingreso en el percentil 10. Puede apoyar a analistas, productores y comercializadoras. No sirve para tarificar seguros.

Como trabajo futuro proponemos validar con el rendimiento de las 59 parcelas cuando se publique, usar varias temporadas y probar la capa con datos reales de crédito.
