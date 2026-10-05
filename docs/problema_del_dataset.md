# El problema del dataset: estructura, ruido y tamaño

**Propósito:** explicar de dónde viene el error de predicción en el Reto AgroCebada 2026, qué parte se puede reducir, cuál no, y cómo decidir qué probar. Complementa la [investigación previa](../AgroCebada_investigacion_previa.md) y el [ROADMAP](../ROADMAP.md). Donde haya conflicto, manda este documento.

Todas las cifras se reproducen con:

```bash
pip install pandas numpy pyshp rasterio scipy scikit-learn
python scripts/diagnostico_etiquetas.py            # ~5 min
python scripts/diagnostico_etiquetas.py --rapido   # sin la prueba de permutación
```

---

## Resumen

1. **El problema no es la falta de datos satelitales, sino la naturaleza de las etiquetas.** Las imágenes están completas: todas las parcelas tienen entre 19 y 34 observaciones limpias de Sentinel-2 entre mayo y octubre de 2025, y Planet cubre todo el año. Lo escaso y ruidoso son los 138 rendimientos.
2. **Las etiquetas vienen de dos regímenes de medición** que se separan por municipio. Esa sola variable explica el 67.5 % de la varianza y deja un RMSE de **0.490 t/ha**, mejor que cualquier baseline anterior.
3. **Lo que queda es una mezcla de señal no capturada y ruido.** Las 5 parcelas más atípicas concentran el 42 % del error, y las parcelas pequeñas reportan los rendimientos más extremos.
4. **Con 138 parcelas la medición del error es imprecisa.** El mismo modelo, calificado en distintos sorteos de 59 parcelas, obtiene RMSE entre 0.37 y 0.58. Mejoras de 0.01–0.02 no se distinguen de la suerte sin una comparación cuidadosa.
5. **El satélite sí contiene información útil**, aunque con variables de primera versión la ganancia es pequeña (0.490 → 0.486, p ≈ 0.03 en prueba de permutación).
6. **No existe un dataset público de rendimiento de cebada por parcela en la zona.** Los datos públicos sirven para enriquecer las variables, no para agregar etiquetas.

---

## 1. Cuatro conceptos necesarios

| Concepto | Qué significa aquí |
|---|---|
| **Error típico (RMSE)** | Cuántas t/ha se equivoca la predicción en promedio, castigando más los errores grandes. RMSE 0.5 ≈ fallar por media tonelada. Equivocarse por 1 t pesa cuatro veces más que equivocarse por 0.5 t. |
| **Examen de práctica (validación cruzada)** | Se esconde una quinta parte de las 138 parcelas, se entrena con el resto y se califica con las escondidas. Se repite con otras particiones. Simula el examen del jurado. |
| **Ruido de etiqueta** | Error que ya trae el rendimiento entregado: redondeos, reporte del productor, básculas distintas. Ningún modelo puede predecirlo; fija el piso del error. |
| **Prueba de permutación** | Se revuelven los valores de un bloque de variables entre parcelas para romper su relación con el rendimiento y se vuelve a calificar. Si el modelo sale igual de bien con datos revueltos, ese bloque no aportaba información (Ojala y Garriga, 2010). |

---

## 2. Capa 1 · Estructura: dos regímenes de medición

El rendimiento de entrenamiento tiene dos patrones que coinciden exactamente con el municipio:

| Régimen | Municipios | Parcelas (entr. / pred.) | Media t/ha | Etiquetas con dos decimales |
|---|---|---|---|---|
| **A** | Chignahuapan, Almoloya, Cuautepec de Hinojosa, Tepeapulco | 87 / 37 | 4.49 | 92 % |
| **B** | Singuilucan, Emiliano Zapata, Apan, Calpulalpan, Nanacamilpa | 51 / 22 | 3.05 | 0 % (escalones de 0.5 o 0.1) |

Hidalgo tiene municipios en ambos regímenes. Por eso agrupar por estado mezcla dos poblaciones: el estado explica el 50 % de la varianza y el régimen el 67.5 %.

| Predictor | RMSE (CV 5×10, t/ha) |
|---|---|
| Media global | 0.854 |
| Media por estado | 0.614 |
| Promedio de los 10 vecinos más cercanos | 0.503 |
| **Media por régimen** | **0.490** |

**¿Diferencia agronómica o forma de medir?** Hay evidencia en ambos sentidos:

- *A favor de la forma de medir:* el patrón de decimales; las parcelas del régimen B tienen un NDVI máximo **más alto** (0.77 frente a 0.72 en Planet); y la estadística oficial municipal de 2025 va en sentido contrario:

  | Municipio | Régimen | Media en el reto | SIAP 2025, temporal |
  |---|---|---|---|
  | Chignahuapan | A | 4.48 | 3.22 |
  | Almoloya | A | 4.52 | 1.91 |
  | Cuautepec de Hinojosa | A | 4.60 | 2.35 |
  | Calpulalpan | B | 3.00 | 4.00 |
  | Singuilucan | B | 3.08 | 1.88 |

- *A favor de una diferencia real:* el ciclo del cultivo en el régimen B es más corto (≈ 97 frente a ≈ 119 días de NDVI por encima de la mitad de su amplitud, con fin de ciclo ~15 días antes). Puede reflejar otra variedad o fecha de siembra.

Para predecir da igual la causa: el jurado califica con etiquetas medidas de la misma forma, y el municipio es conocido para las 59 parcelas. Para el reporte sí importa; se consulta al comité en #21. Se implementa en #19.

---

## 3. Capa 2 · Ruido: atípicos y parcelas pequeñas

Después de separar los regímenes queda un RMSE de 0.49. Hay tres indicios de que una parte importante es ruido de etiqueta:

- **Atípicos.** Las 5 parcelas con mayor error concentran el 42 % del error cuadrático total.
- **Parcelas pequeñas.** El rendimiento baja con el área (correlación con log(área): −0.26 en A, −0.12 en B). Cuatro de los cinco rendimientos ≥ 5.4 t/ha son parcelas de 0.4–1.4 ha. Gourlay, Kilic y Lobell (2019) documentan el mismo patrón: los productores sobreestiman el rendimiento sobre todo en parcelas pequeñas.
- **Redondeo.** En el régimen B, redondear a 0.5 agrega por sí solo ~0.14 t/ha de error irreducible.

**Estimación del piso.** Dos parcelas a menos de 300 m comparten clima, suelo y a menudo productor. En 26 pares de ese tipo (mismo régimen, rendimiento distinto), la diferencia equivale a un RMSE de ≈ 0.34 t/ha. Es una estimación débil por el número de pares, y los vecinos pueden diferir en cosas reales que el satélite sí ve. El piso probablemente está entre ~0.30 y 0.49, sin poder precisarlo más.

Si los atípicos tienen causa visible (acame, cosecha tardía, anegamiento), son la mayor oportunidad de mejora: ver #20. Si no la tienen, se atenúan con pérdida robusta y ponderación: ver #19.

---

## 4. Capa 3 · Tamaño: la regla de medir es imprecisa

138 parcelas alcanzan para aprender los dos regímenes, pero no para distinguir mejoras pequeñas de la suerte.

- El mismo modelo (media por régimen), calificado en 5,000 sorteos de 59 parcelas, obtiene RMSE de **0.37 a 0.58** (percentiles 5 y 95). El puntaje oficial lleva ese margen de suerte encima. Varoquaux (2018) muestra que con ~100 casos las barras de error de la validación cruzada rondan ±10 % y que el cálculo habitual entre particiones las subestima.
- Probar muchas ideas y quedarse con la mejor según el mismo examen produce modelos que parecen mejores de lo que son (Cawley y Talbot, 2010).

**Regla de decisión** (ver #2): una idea se acepta solo si:

1. le gana a la mejor anterior en al menos **70 % de los mismos exámenes de práctica** (particiones fijas, 5×10, balanceadas por régimen), **y**
2. su bloque de variables **supera la prueba de permutación** frente a versiones barajadas.

Lo que no pasa la regla se documenta como probado y descartado.

**Validación aleatoria, no espacial.** La partición oficial es aleatoria e intercalada (0.36 km al vecino de entrenamiento más cercano). Cuando los puntos a predecir se eligieron al azar, la validación aleatoria es la que imita el examen; la espacial mide otra cosa y penaliza información legítima (Wadoux et al., 2021). La espacial se reporta solo como medida de dependencia de los vecinos.

---

## 5. El satélite

Con 47 variables de primera versión (fenología de Planet y Sentinel-2 en 2025 e historia 2022–2024) agregadas al régimen:

| Configuración | RMSE (CV 5×4) |
|---|---|
| Solo régimen | 0.490 |
| Régimen + satélite barajado (60 versiones, media) | 0.509 |
| **Régimen + satélite real** | **0.486** |

El satélite real le gana a las versiones barajadas (p ≈ 0.03) y gana en 12 de 20 particiones a "solo régimen". La información existe, pero estas variables no alinean el ciclo de cada parcela, no incluyen labranza, uniformidad interna ni radar. Es el bloque con más espacio de mejora (#6).

Cuidado al interpretar correlaciones: variables como la duración del ciclo correlacionan r ≈ 0.4 con el rendimiento en conjunto, pero casi 0 dentro de cada régimen. Son un reflejo del régimen, no señal adicional. **Toda variable se evalúa dentro de cada régimen.**

---

## 6. El año 2025

La investigación previa anticipaba un año extremo por ser el más lluvioso del país desde 1941. Los datos locales matizan esa expectativa.

**Precipitación mensual media sobre las 197 parcelas (CHIRPS, mm):**

| Año | abr | may | jun | jul | ago | sep | oct | nov |
|---|---|---|---|---|---|---|---|---|
| 2022 | 31 | 24 | 82 | 99 | 147 | 79 | 69 | 29 |
| 2023 | 35 | 95 | 27 | 93 | 138 | 51 | 103 | 69 |
| 2024 | 18 | 45 | 162 | 283 | 144 | 228 | 59 | 29 |
| **2025** | 12 | **138** | **246** | 149 | 132 | 162 | **124** | 15 |

Lo que distingue a 2025 en la zona no es el total (junio–octubre, 813 mm, similar a 2024 con 876 mm), sino **cuándo llovió**:

- **Mayo–junio muy lluviosos** (384 mm, el doble que cualquier año previo). Favorece siembras tempranas y uniformes, pero también el anegamiento durante emergencia y amacollamiento.
- **Julio–agosto normales.** El periodo crítico de llenado no tuvo exceso extraordinario.
- **Septiembre–octubre lluviosos** (286 mm). Coincide con madurez y cosecha: riesgo de acame, germinación en espiga y retraso de cosecha.
- **Temperatura máxima más fresca** (23.6 °C de mayo a septiembre, frente a 24.5–25.1 °C en 2023–2024). Un llenado más fresco favorece el peso del grano y es coherente con rendimientos altos en el régimen A.
- El régimen B recibió más lluvia de junio a octubre (903 frente a 761 mm).

**Consecuencias para el modelo:**

1. **La lluvia casi no distingue entre parcelas del mismo régimen** (|r| ≤ 0.16 con el residuo para mayo–junio, julio–agosto y septiembre–octubre). En un año sin déficit hídrico, la lluvia deja de ser el factor limitante.
2. **El clima de 5 km funciona como identificador de zona.** Las parcelas caen en ~24–26 píxeles y el clima está confundido con el régimen.
3. **Los efectos del exceso de agua son locales y de parcela** (acame, anegamiento en zonas bajas, cosecha tardía). No se ven en el clima mensual de 5 km; se pueden ver con radar (#20) y relieve fino (#9).
4. **El clima entregado es mensual.** Las ventanas relativas a la antesis que propone la investigación previa (−20 a 0 días, etc.) requieren datos diarios (#7, #9).
5. **2025 no fue un año especialmente nublado para el satélite en esta zona.** La mediana de observaciones limpias de Sentinel-2 entre mayo y octubre fue 25 por parcela en 2025, frente a 17–20 en 2022–2024.

---

## 7. Supuestos de la investigación previa que los datos contradicen

| Supuesto previo | Lo que muestran los datos | Consecuencia |
|---|---|---|
| Rendimiento esperado 1.5–3.5 t/ha (promedios SIAP) | Media 3.96, rango 2.0–5.6 | Las parcelas no representan el promedio municipal; el SIAP no sirve como prior |
| Un prior municipal del SIAP ayudaría | El SIAP 2025 va en sentido contrario a las etiquetas | SIAP solo como contexto en el reporte |
| El PRO (Planet) no tiene red-edge | Su LAI es una función exacta del NDRE | Se recupera el NDRE sin datos externos |
| La topografía es de 15 m | Es de 120 m | Para TWI y curvatura hace falta un DEM más fino (#9) |
| 2024 fue seco | Localmente 2024 fue tan lluvioso como 2025 | Las anomalías de 2025 contra 2022–2024 no son extremas |
| Nubosidad extrema en la ventana crítica de 2025 | 2025 tuvo más observaciones limpias que los años previos | La reconstrucción de series es un problema moderado |
| Validación espacial obligatoria; no usar K-fold aleatorio | La partición oficial es aleatoria e intercalada | La validación aleatoria es la principal (Wadoux et al., 2021) |
| Ventanas fenológicas de clima a partir de CHIRPS/CHIRTS | El clima entregado es mensual | Requiere CHIRPS y CHIRTS diarios |
| Las etiquetas de Tlaxcala están redondeadas (ROADMAP) | El redondeo sigue al municipio, no al estado; incluye tres municipios de Hidalgo | El régimen sustituye al estado como variable base |
| El factor limitante de 2025 sería el anegamiento generalizado | La lluvia casi no discrimina dentro de régimen | El exceso de agua importa a escala de parcela, no de zona |

---

## 8. Información nueva que influye en el resultado

1. **Dos regímenes de medición** en las etiquetas (sección 2).
2. **Las parcelas pequeñas reportan rendimientos extremos** (sección 3).
3. **El margen de suerte del examen oficial** es de ±0.1 t/ha (sección 4).
4. **El satélite aporta información**, comprobada con prueba de permutación (sección 5).
5. **Los regímenes difieren en fenología:** ciclo más corto y NDVI más alto en el régimen B.
6. **El PRO cubre todo 2025** (311 fechas, de enero a diciembre), incluida la senescencia y la cosecha. Calcular el rango de fechas comparando texto `DD/MM/AAAA` da por error "31/08/2025" como máximo.
7. **La lluvia de 2025 se concentró en siembra y en cosecha** (sección 6).
8. El campo `porcentaje_nubosidad` es casi binario y, cuando vale 100, los índices vienen nulos. El "≈ 35 % de datos faltantes" corresponde a observaciones con nubosidad > 20 %, no a parcelas sin datos.

---

## 9. ¿Existen otros datasets que podamos usar?

**Etiquetas (rendimiento por parcela): no.** No hay un dataset público de rendimiento de cebada por parcela en la zona. Lo revisado:

| Fuente | Qué ofrece | Uso |
|---|---|---|
| SIAP, cierre agrícola municipal 2003–2025 | Rendimiento promedio por municipio, ciclo y modalidad | Contexto. No sirve como variable: contradice las etiquetas |
| CIMMYT, ensayos de variedades en Valles Altos (p. ej. PV 2017) | Parcelas experimentales, otros años, parte con riego | Referencias de fenología por variedad; no son comparables con parcelas comerciales |
| CIMMYT MasAgro, bitácoras electrónicas | Registros por parcela de productores | No están publicados a nivel parcela |
| Literatura (INIFAP, revistas) | Resultados agregados de estudios | Referencias para el reporte |

**Datos previos dentro del propio dataset: sí.** El Básico trae Sentinel-2 y Landsat de 2022–2024 para las mismas 197 parcelas. No tiene rendimiento de esos años, pero describe el historial de cada sitio y se usa como variable (#6).

**Variables (no etiquetas): sí, varias fuentes públicas** (#9 y #20): Sentinel-1, Sentinel-2 L2A con bandas crudas y máscara de nubes por píxel, CHIRPS y CHIRTS diarios, SoilGrids, un DEM más fino y los embeddings anuales AlphaEarth (disponibles de 2017 a 2024).

---

## 10. Plan de pruebas

En orden de probabilidad de éxito y costo. Cada paso pasa por la regla de decisión de la sección 4.

| Paso | Hipótesis | Issue |
|---|---|---|
| 0 | Fijar particiones, comparación emparejada y prueba de permutación | #2 |
| 1 | Régimen como base (hecho, RMSE 0.490) | #19 |
| 2 | Satélite bien construido: ciclo alineado, NDRE, Planet completo, historia, labranza, uniformidad | #5, #6 |
| 3 | Los atípicos tienen causa visible (acame, cosecha) | #20 |
| 4 | Entrenar con ruido: pérdida robusta, ponderación por área, intervalos en el régimen B | #19 |
| 5 | Vecinos a menos de ~400 m | #8 |
| 6 | Clima diario, suelo y relieve fino | #7, #9 |
| 7 | Elección de modelo y ensemble, con las variables congeladas | #8, #10 |

Si los pasos 2 y 3 no superan la regla, habrá evidencia de que el modelo está cerca del piso del ruido. Eso también es un resultado para el reporte.

---

## Referencias

- Cawley, G. C. y Talbot, N. L. C. (2010). On over-fitting in model selection and subsequent selection bias in performance evaluation. *Journal of Machine Learning Research*, 11, 2079–2107.
- Chauhan, S., Darvishzadeh, R., Lu, Y., Boschetti, M. y Nelson, A. (2020). Understanding wheat lodging using multi-temporal Sentinel-1 and Sentinel-2 data. *Remote Sensing*, 12(23), 3885. https://www.mdpi.com/2072-4292/12/23/3885
- Gourlay, S., Kilic, T. y Lobell, D. B. (2019). A new spin on an old debate: Errors in farmer-reported production and their implications for inverse scale-productivity relationship in Uganda. *Journal of Development Economics*, 141. https://openknowledge.worldbank.org/handle/10986/28369
- Lobell, D. B., Azzari, G., Burke, M., Gourlay, S., Jin, Z., Kilic, T. y Murray, S. (2020). Eyes in the sky, boots on the ground: Assessing satellite- and ground-based approaches to crop yield measurement and analysis. *American Journal of Agricultural Economics*, 102(1), 202–219.
- Ojala, M. y Garriga, G. C. (2010). Permutation tests for studying classifier performance. *Journal of Machine Learning Research*, 11, 1833–1863. https://www.jmlr.org/papers/v11/ojala10a.html
- SIAP (2026). Producción agrícola municipal, cierre 2025. Datos abiertos, consultado el 4 de octubre de 2026. https://nube.agricultura.gob.mx/datosAbiertos/Agricola.php
- Varoquaux, G. (2018). Cross-validation failure: Small sample sizes lead to large error bars. *NeuroImage*, 180, 68–77. https://arxiv.org/abs/1706.07581
- Wadoux, A. M. J.-C., Heuvelink, G. B. M., de Bruin, S. y Brus, D. J. (2021). Spatial cross-validation is not the right way to evaluate map accuracy. *Ecological Modelling*, 457, 109692.
