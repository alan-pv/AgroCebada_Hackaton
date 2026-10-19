# Capa de crédito

Esta capa convierte la predicción de rendimiento en pesos y en riesgo para el analista de crédito y para el productor. No es una variable del modelo. El precio y los costos no cambian lo que produce la planta.

## Cómo se llama

```python
from parcelas.economia import capa_economica

# pred_df trae pred, p10, regimen, area_ha y CVEGEO (o estado y municipio)
tabla = capa_economica(pred_df)

# con valores propios
tabla = capa_economica(pred_df, precio=6500, costo_total={"21053": 30000},
                       siniestro="2013_2025")
```

La función devuelve una fila por parcela. Los argumentos `precio`, `costo_total` y `costo_credito` aceptan un número, un arreglo con un valor por parcela o un diccionario con la clave del municipio. La clave del municipio es el CVEGEO de 5 dígitos. Todo lo que no se cambia se toma de la tabla municipal. El argumento `siniestro` elige el periodo de pérdidas, `"2003_2025"` (por defecto) o `"2013_2025"`, o recibe un número.

El resultado ya calculado para las 197 parcelas está en `outputs/capa_economica.csv`. La tabla por municipio está en `data/externos/economia_municipal.csv` y se regenera con `uv run python scripts/credito.py`. El p10 y la marca de confianza que usa esta capa se describen en `MODELO.md`.

## Qué significa cada columna del resultado

| Columna | Unidad | En palabras sencillas |
|---|---|---|
| `precio` | $/t | Precio al que se valúa la cosecha. Por defecto, el precio medio rural del SIAP en el municipio, promedio 2023 a 2025 ponderado por producción. |
| `costo_total` | $/ha | Lo que cuesta producir una hectárea, en pesos de 2025. Incluye el interés del avío. |
| `costo_credito` | $/ha | Lo que hay que pagar del crédito por hectárea. Es el capital financiado más su interés. |
| `pe_total` | t/ha | Punto de equilibrio total. Las toneladas por hectárea que hay que cosechar para cubrir todo el costo. |
| `pe_credito` | t/ha | Punto de equilibrio del crédito. Las toneladas por hectárea que hay que cosechar para pagar el crédito. |
| `ingreso_esperado_ha` | $/ha | Predicción por precio. |
| `ingreso_conservador_ha` | $/ha | Percentil 10 de la predicción por precio. Es el ingreso en un resultado bajo dentro de la incertidumbre del modelo. |
| `ingreso_esperado_parcela` | $ | Ingreso esperado por hectárea por el área de la parcela. |
| `margen_esperado_ha` | $/ha | Ingreso esperado menos el costo total. Negativo significa que no se cubre el costo. |
| `prob_perdida` | 0 a 1 | Fracción de la superficie sembrada que históricamente se pierde en el municipio. |
| `prob_no_pagar_credito` | 0 a 1 | Probabilidad de que el rendimiento quede por debajo del punto de equilibrio del crédito. |
| `prob_no_cubrir_costos` | 0 a 1 | Probabilidad de que el rendimiento quede por debajo del punto de equilibrio total. |
| `semaforo_credito` | texto | Verde, amarillo o rojo según `prob_no_pagar_credito`. |
| `semaforo_costos` | texto | Verde, amarillo o rojo según `prob_no_cubrir_costos`. |

El semáforo es verde si la probabilidad es menor que 10 %, amarillo si está entre 10 % y 30 %, y rojo si es de 30 % o más. Los cortes se pueden cambiar con el argumento `cortes`.

## Cómo se calculan las probabilidades

Primero se toma la distribución de los errores del modelo en las parcelas de entrenamiento, separada por régimen. Con ella se calcula la probabilidad de que el rendimiento quede por debajo del punto de equilibrio de esa parcela. Después se combina con la pérdida histórica del municipio, que llamamos q.

```
P = q + (1 - q) × P(rendimiento < punto de equilibrio | hay cosecha)
```

Si el cultivo se pierde, suponemos ingreso cero. Esa parte es la que añade q.

## Qué incluye y qué no incluye la probabilidad

La probabilidad mide la incertidumbre de la predicción en un año parecido a 2025. Dicho de otro modo, de diez parcelas con esta predicción, cuántas quedarían por debajo del punto de equilibrio. No incluye la variación de un año a otro, como una sequía, una helada o un cambio de precio. Esa variación se muestra aparte como contexto del municipio con las columnas del SIAP.

Por eso la probabilidad no es una probabilidad de incumplimiento. Es una señal para ordenar parcelas y para abrir la conversación.

## Contexto del municipio

La tabla municipal trae datos para mostrar junto a la ficha.

| Columna | Qué es |
|---|---|
| `siniestralidad_2003_2025` y `siniestralidad_2013_2025` | Fracción de la superficie sembrada que se pierde, en cada periodo. |
| `anios_perdida_20` y `anios_perdida_50` | Número de años, de 23, con más de 20 % y más de 50 % de la superficie perdida. |
| `siap_rend_media`, `siap_rend_sd`, `siap_rend_p10` | Rendimiento oficial por hectárea sembrada, 2003 a 2025. Incluye las pérdidas. |
| `siap_frac_rend_repetido` | Fracción de años en que el SIAP repite la cifra de un municipio vecino. Cuanto más alta, menos confiable es la serie municipal. |
| `precio_min` y `precio_max` | Precio más bajo y más alto del periodo 2023 a 2025. |
| `rendimiento_paquete_probable` | Rendimiento que supone el paquete tecnológico de FIRA para la zona. |

## Costo económico y probabilidades extremas

El costo total del paquete incluye renta de la tierra y otros conceptos que el crédito no financia. Por ejemplo, la renta en Tlaxcala es de 3,500 $/ha. Por eso cubrir el costo total es un criterio económico y no es lo mismo que pagar el crédito.

Las probabilidades salen de una distribución empírica de errores con un número finito de parcelas. Por eso pueden dar exactamente 0 o 1. Sugerimos mostrar "menos de 1 %" cuando la probabilidad sea menor que 0.01 y "más de 99 %" cuando sea mayor que 0.99, y no mostrar un 0 % ni un 100 % que sugiera certeza.

## Cosas que hay que tener presentes

1. Las etiquetas del reto son grano pesado en báscula entre la superficie del polígono, reportado sobre todo por la comercializadora. El SIAP mide otra cosa.
2. Los rendimientos esperados de los paquetes de FIRA, de 3.5 a 5.5 t/ha, están cerca de nuestras etiquetas. Los promedios municipales del SIAP, de 2 a 2.6 t/ha, no lo están. Por eso el punto de equilibrio se compara con la predicción y no con los datos del SIAP. El SIAP queda como contexto y no es comparable en nivel.
3. Los costos son los del paquete de FIRA del ciclo primavera-verano 2022, el más reciente público, actualizados a 2025 con el índice de precios al consumidor general de INEGI (factor 1.147). El índice general no sigue el precio de los insumos agrícolas, así que el costo real puede ser distinto. Conviene dejarlo editable.
4. El paquete de Hidalgo supone 3.5 t/ha y cuesta unos 28,400 $/ha en 2025. Por eso el punto de equilibrio total queda cerca o por encima del rendimiento esperado. Singuilucan es el caso extremo, con precio de 4,300 $/t y un punto de equilibrio total de 6.6 t/ha.
5. En Tlaxcala el paquete financia solo una parte pequeña del costo, porque una buena parte es aportación del productor y gasto no financiable. Por eso el punto de equilibrio del crédito de Calpulalpan y Nanacamilpa es bajo, alrededor de 1 t/ha, y el del costo total es alto, alrededor de 3.9 t/ha. Con el semáforo de costos casi todas las parcelas salen en rojo, y con el del crédito salen en verde.
6. Chignahuapan usa por defecto el paquete de Agencias Hidalgo, que es el mismo altiplano cebadero. Es un supuesto nuestro. El paquete de Sierra Norte de Puebla es de alta productividad, supone 5.5 t/ha y 8,000 $/t e incluye renta de la tierra, así que no cuadra con el precio del SIAP. Queda como alternativa en la tabla municipal, con un punto de equilibrio total de 6.9 t/ha. Se puede probar pasando `costo_total` y `costo_credito` de esa alternativa.
7. El percentil 10 no es un mal año. Es el límite inferior de la incertidumbre del modelo y cada intervalo deja 10 % de la probabilidad por debajo.
8. El precio del SIAP mezcla ventas de grano aceptado y de grano rechazado o vendido como forraje. Los contratos reportados en la prensa para 2024 y 2026 fueron de 6,800 a 7,400 $/t. Singuilucan y Chignahuapan quedan abajo de eso porque el SIAP les asigna 4,300 y 5,100 $/t.
9. La actualización de costos y la elección de zona se pueden revisar con FIRA. Si FIRA entrega paquetes de 2025 o 2026, basta sustituir los costos al llamar la función.
