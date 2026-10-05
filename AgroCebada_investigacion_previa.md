# Reto AgroCebada FIRA 2026 — Investigación previa

**Objetivo del documento:** entender a qué se enfrenta el equipo antes de escribir una sola línea de código: qué determina el rendimiento de cebada en el Altiplano central mexicano, qué se ha hecho en el mundo para predecirlo con percepción remota, qué tipo de problema estadístico es realmente el que entregó FIRA, y qué ruta metodológica tiene mayor probabilidad de funcionar.

> **Nota (4 oct 2026).** Este documento se escribió antes de analizar los datos. Varios supuestos no se sostienen; la lista completa y la evidencia están en [docs/problema_del_dataset.md §7](docs/problema_del_dataset.md#7-supuestos-de-la-investigación-previa-que-los-datos-contradicen). Los principales:
>
> - El rendimiento no está en 1.5–3.5 t/ha: la media es 3.96 y el rango 2.0–5.6. Las parcelas no siguen los promedios del SIAP, que no sirve como prior municipal (§1.5, §6).
> - Las etiquetas vienen de dos regímenes de medición que se separan por municipio. Esa variable sola deja un RMSE de 0.49.
> - La partición oficial es aleatoria, no espacial: la validación aleatoria es la principal (§3.1, §4.8).
> - El PRO sí tiene red-edge (el LAI de Planet es función del NDRE) y cubre todo 2025 (§2.3).
> - La topografía entregada es de 120 m, no de 15 m (§3.4, §4.4 F).
> - Localmente 2024 fue tan lluvioso como 2025, y 2025 tuvo más observaciones limpias que los años previos (§1.6). Lo distintivo de 2025 fue la lluvia en siembra (mayo–junio) y en cosecha (septiembre–octubre).
> - El clima entregado es mensual: las ventanas fenológicas de §1.3 requieren datos diarios.

---

## 0. Corrección de encuadre (importante)

El planteamiento inicial del equipo hablaba de predecir *calidad*. Los documentos entregados son inequívocos: el objetivo es **rendimiento de grano en t/ha**, para 59 parcelas ocultas del conjunto PREDICCION, del ciclo **abril–octubre de 2025**.

Esto no es un detalle semántico. Calidad maltera (proteína <12 %, calibre, poder germinativo, peso hectolítrico) y rendimiento son variables **inversamente relacionadas en buena parte del rango agronómico**: más nitrógeno disponible sube rendimiento y sube proteína, lo que *degrada* la aptitud maltera. Si el equipo optimiza mentalmente para "calidad", va a seleccionar features equivocadas (índices de clorofila y nitrógeno tardío) y a interpretar mal los resultados.

**Variable objetivo: rendimiento (t/ha). Unidad de observación: la parcela. Año: 2025.**

---

## 1. El sistema productivo: cebada de temporal en Valles Altos

### 1.1 Dónde y cómo

Hidalgo, Tlaxcala y Puebla forman, junto con el Estado de México, la región del **Altiplano / Valles Altos de la Mesa Central**, que concentra alrededor del 75 % de la superficie nacional de cebada, casi toda **de temporal en el ciclo primavera–verano**. La otra región productora (Bajío: Guanajuato, Querétaro, Michoacán, Jalisco) es de riego en otoño–invierno y no aplica aquí.

Implicaciones directas:

- **No hay riego.** El agua disponible es exclusivamente la lluvia del temporal. Esto hace que la precipitación sea, en principio, el driver dominante… pero ver la sección 3.3 sobre por qué esto no se traduce automáticamente en una feature útil.
- **Altitud entre ~2,200 y ~2,700 m.** Radiación alta, amplitud térmica grande, riesgo de heladas tempranas y tardías.
- **Superficies pequeñas y fragmentadas**, con manejo heterogéneo (tracción animal en parte de la región, dosis de fertilización variables, siembra al voleo o con sembradora).

### 1.2 Calendario fenológico (lo que hay que tener en la cabeza al mirar series temporales)

| Etapa | Fecha aproximada | Relevancia para rendimiento |
|---|---|---|
| Preparación / barbecho | abril – mayo | Visible en índices de labranza y residuos (NDTI, STI, CRC) |
| **Siembra** | **1 mayo – 15 junio** (recomendación INIFAP) | La fecha real de siembra por parcela es una variable oculta de altísimo valor; se puede *estimar* de la serie de VI |
| Emergencia – amacollamiento | +10 a +35 días | Define número de tallos potenciales |
| Encañe / embuche (BBCH 30–45) | ~junio–julio | **Periodo crítico**: aquí se define el número de granos por m² |
| Espigamiento – antesis | ~julio–agosto (49–64 días a floración en variedades tipo Esmeralda) | Máximo de biomasa verde; máximo del NDVI |
| Llenado de grano | ~agosto–septiembre | Define peso del grano; sensible a golpes de calor y a sequía terminal |
| Madurez fisiológica | 91–120 días desde siembra | Senescencia: caída del VI |
| Cosecha | septiembre – octubre | |

La fisiología de cereales de grano pequeño es clara al respecto: el **número de granos por unidad de superficie** —principal componente del rendimiento— se define en la ventana que va del espiguillado terminal hasta unos pocos días después de antesis, mientras que el **peso del grano** se realiza durante el llenado efectivo, de 1–2 semanas después de antesis hasta madurez fisiológica. Un golpe de calor en embuche puede inhibir el amacollamiento y reducir espigas/m²; estrés en llenado acorta la duración del llenado (reducciones documentadas del 45–50 %) y baja el peso de mil granos.

**Traducción práctica:** las features que describen el estado del dosel en **embuche–antesis** y la **duración/pendiente de la senescencia** deberían pesar más que las del inicio del ciclo. Esto coincide con lo que reporta la literatura empírica (sección 2).

### 1.3 El periodo crítico, cuantificado (la base del feature engineering)

Conviene precisar la ventana, porque de aquí sale la mejor decisión de diseño de variables del proyecto.

En cereales de grano pequeño, el rendimiento es sobre todo **número de granos por m²**, y éste se define en una ventana estrecha: desde poco después del inicio del encañe (**~20–30 días antes de antesis**) hasta **~7–10 días después de antesis**. Es el resultado clásico de Fischer (1985) y Savin & Slafer (1991), confirmado después en decenas de estudios y genotipos. Para **cebada en particular**, Arisnabarreta y Miralles (2008) establecieron que el periodo crítico está en las fases **pre-espigamiento**, y tiende a ser **ligeramente más temprano en cebadas de dos hileras que en las de seis**. El número final de granos queda fijado inmediatamente después de antesis; el llenado ocurre en el periodo restante.

Tres derivaciones directamente utilizables:

**a) Ventanas relativas, no meses calendario.** Estimen para *cada parcela* la fecha de máximo verdor (proxy de espigamiento/antesis) desde la serie de NDVI/EVI, y construyan todas las agregaciones climáticas en ventanas relativas a esa fecha: **[−30, −10], [−10, +10], [+10, +40] días**. Dado que las siembras en la región se escalonan entre el 1 de mayo y el 30 de junio según ambiente, dos parcelas pueden estar en fases fisiológicas completamente distintas el mismo día de agosto. Agregar por mes calendario mezcla peras con manzanas. Ésta es la mejora individual con mejor relación esfuerzo/beneficio de todo el pipeline.

**b) Cociente fototérmico (PTQ).** PTQ = radiación incidente / (temperatura media − temperatura base) durante el periodo crítico. Su lógica fisiológica: el número de granos por m² es proporcional a la radiación que alimenta la fotosíntesis, e inversamente proporcional a la temperatura, que acorta la duración del periodo en que se define ese número. El rendimiento correlaciona con PTQ en la mayoría de los cultivos anuales, y la asociación PTQ–número de granos está bien descrita en trigo y cebada. Con Tmin y Tmax de CHIRTS y radiación aproximada (por estacionalidad y latitud, o traída de ERA5-Land / NASA POWER), **el PTQ del periodo crítico es una de las pocas variables climáticas con base causal real en este dataset.** Vale mucho más que "precipitación de agosto".

**c) Periodo crítico de anegamiento — muy pertinente para 2025.** Los ~20 días previos a antesis son el "periodo crítico de anegamiento" en trigo y cebada, y el momento alrededor de antesis es el más susceptible. En cebada, la caída de rendimiento por anegamiento se explica sobre todo por reducción del **número de espigas por planta** (en trigo, por granos por espiga). Dado el año que fue 2025, features del tipo *"precipitación acumulada en [−20, 0] días respecto a antesis"* o *"número de decenas con precipitación por encima del percentil 90 en la ventana pre-antesis"* tienen una justificación agronómica sólida y probablemente señal real.

**d) Temperatura en llenado.** La cebada crece entre 15 y 30 °C, pero rinde mejor cuando espigamiento y llenado ocurren con temperaturas moderadas y humedad adecuada. Altas temperaturas o heladas desde antes del espigamiento afectan tanto rendimiento como calidad industrial. Contabilicen días con Tmax por encima de umbral y días con Tmin por debajo de 0 °C en la ventana post-antesis.

### 1.4 Variedades

El material genético dominante viene del Programa Nacional de Cebada Maltera del INIFAP: **Esmeralda, Adabella, Armida, Alteña, Centinela**, entre otras, seleccionadas por tolerancia a roya y otras foliares de Valles Altos. Son de hábito primaveral y ciclo intermedio.

La variedad sembrada **no está en el dataset** y es un determinante de primer orden del rendimiento y del ciclo a floración. Es parte del error irreducible del problema. Vale la pena mencionarlo explícitamente en la presentación final: reconocer las limitaciones del dato suele puntuar bien ante jurados técnicos.

### 1.5 Rendimientos típicos — anclas para evaluar el modelo

Cifras oficiales (SIAP, cierre 2024): producción nacional de cebada grano de **827,490 t** sobre **300,558 ha cosechadas**, es decir un **rendimiento medio nacional de 2.8 t/ha** (que mezcla riego y temporal). Por estado:

| Estado | Producción 2024 | Superficie cosechada | Rendimiento implícito |
|---|---|---|---|
| Hidalgo | 195,412 t (23.6 %) | 104,050 ha | **~1.9 t/ha** |
| Guanajuato (riego) | 137,112 t | — | ~5 t/ha |
| Puebla | 133,352 t (16.1 %) | — | ~3 t/ha |
| Tlaxcala | 128,892 t (15.6 %) | — | ~2.4 t/ha |

Datos de 2022 (Cerveceros de México con base en SIAP) confirman el contraste: Hidalgo 1.8 t/ha y Tlaxcala 2.6 t/ha bajo temporal, frente a Guanajuato 5.1 y Chihuahua 5.8 bajo riego. Tlaxcala esperaba 2.36 t/ha en su intención de siembra 2024.

**Rango esperable para las 197 parcelas: aproximadamente 1.5–3.5 t/ha, con cola derecha.** Una predicción de 6 t/ha en una parcela de Apan es una alarma roja, no un acierto.

**Esto da una referencia crítica:** si la media del set de entrenamiento ronda 2.5–3 t/ha y la desviación estándar es de, digamos, 0.8–1.2 t/ha, entonces un modelo que solo prediga la media tendrá RMSE ≈ la desviación estándar. **Cualquier modelo del equipo debe compararse contra ese baseline trivial desde el primer día.** Un RMSE de 0.9 t/ha puede sonar bien y no aportar absolutamente nada.

Baselines obligatorios a reportar:
1. Media global del entrenamiento.
2. Media por estado / por clúster espacial.
3. Regresión lineal simple sobre NDVI máximo de la temporada.
4. El modelo propuesto.

### 1.6 El año 2025 en particular

Esta es probablemente la observación más importante de toda la investigación previa, y conviene que todo el equipo la tenga clara antes de mirar una sola serie temporal.

**2025 fue el año más lluvioso de México desde 1941.** Según registros de CONAGUA analizados por la UNAM, el promedio mensual de precipitación entre junio y octubre de 2025 alcanzó **155.5 mm**, frente a **61.3 mm en 2024**. La superficie nacional bajo sequía pasó de 29 % en 2024 a **13.7 % en agosto de 2025**, y doce entidades —Hidalgo entre ellas— quedaron completamente libres de sequía por primera vez en años. El almacenamiento en presas llegó a 72 %, ocho puntos por encima de 2024. La causa fue una combinación poco frecuente: fase negativa de la PDO y fase positiva de la AMO, que intensificó la formación de perturbaciones en el Pacífico.

Contexto de los años previos, que es lo que queda en el histórico 2022–2024: 2023 y buena parte de 2024 fueron secos a nivel nacional (15 estados clasificaron 2024 como año seco), aunque Puebla y Tlaxcala quedaron *dentro de lo normal* en 2024. En abril de 2025, antes del temporal, la sequía todavía abarcaba 45.8 % del territorio y había heladas negras de hasta −7 °C en el Altiplano.

Cinco consecuencias metodológicas, varias de ellas contraintuitivas:

1. **El año objetivo no es un año promedio.** Cualquier feature construida como "anomalía respecto al promedio 2022–2024" va a dar anomalías positivas extremas en prácticamente todas las parcelas, porque la referencia son años secos. Sigue siendo útil como normalización del efecto sitio, pero no como medida de estrés.

2. **El factor limitante en 2025 probablemente no fue la sequía, sino lo contrario.** Anegamiento, acame (vuelco por lluvia y viento), enfermedades foliares favorecidas por humedad persistente, y posiblemente pérdidas por lluvia sobre grano maduro en septiembre-octubre. Esto **invierte el signo esperado** de la precipitación: la relación lluvia–rendimiento en 2025 puede ser no monótona, con un óptimo intermedio. Un modelo lineal en precipitación va a fallar; los árboles capturan esto sin problema, pero solo si alguien lo mira en los gráficos parciales.

3. **En un año sin déficit hídrico generalizado, la lluvia explica poco de la variabilidad *entre parcelas*.** Lo que discrimina son fertilización, fecha de siembra, calidad de suelo, enfermedad, acame y granizo localizado — casi todos invisibles en malla de 5 km, pero varios con huella espectral detectable.

4. **Nubosidad extrema en la ventana crítica.** Un récord de lluvias entre junio y octubre significa muy pocas observaciones ópticas limpias de Sentinel-2 y Landsat justo durante el ciclo del cultivo. Es casi seguro que esa sea la razón de que los organizadores incluyeran el **Dataset PRO de Planet**: cadencia casi diaria, que sí se cuela entre nubes. Espérense huecos largos en la serie básica de julio–septiembre 2025, y revísenlo en la fase de diagnóstico.

5. **Los índices de estrés y enfermedad del diccionario cobran otro sentido.** MSI, EMSI, DSWI2–5 y NDDI están pensados para estrés hídrico y condición vegetal; en un año húmedo, lo que capturan es más probablemente **enfermedad foliar y senescencia anticipada** que sequía. Interprétenlos así en la presentación.

---

## 2. Estado del arte: cómo se predice rendimiento de cereales con satélite

### 2.1 Las tres familias de métodos

Una revisión sistemática reciente sobre Sentinel-2 para estimación de rendimiento identifica tres aproximaciones dominantes, en una transición general de la escala regional a la escala de parcela:

1. **Modelos empíricos**: índices de vegetación + aprendizaje automático (Random Forest, XGBoost, CNN). Es la familia dominante y la única viable con los datos y tiempo de un hackatón.
2. **Asimilación en modelos de cultivo basados en procesos** (WOFOST, SAFY, APSIM, DSSAT): se asimila LAI o fAPAR derivados de satélite para corregir la trayectoria simulada. Más robusto y transferible, pero requiere parametrización por variedad y suelo. Mencionable como trabajo futuro, no ejecutable en un hackatón.
3. **Fusión óptico + radar (Sentinel-1 SAR)** para superar la nubosidad. No está en el dataset entregado, pero **Sentinel-1 es público y el reto permite explícitamente incorporar datos externos documentados**. Ver sección 6.

La misma revisión advierte que el desempeño sigue limitado por tres factores que describen exactamente la situación del reto: **escasez de datos de verdad-terreno, huecos por nubes, y transferibilidad del modelo**.

### 2.2 Desempeños de referencia reportados en la literatura

Estos números sirven para calibrar expectativas y para argumentar en la presentación:

| Estudio / contexto | Método | Resultado |
|---|---|---|
| Trigo, integración óptico + radar, por etapa fenológica | Random Forest en antesis | R² = 0.90, RMSE = 0.29 t/ha en test |
| Trigo y cebada, 7 regiones cerealeras de España, 10 m, 2020–2024, monitor de cosecha | RF / XGBoost por etapa | R² = 0.77 en validación externa (año no visto) para trigo; la precisión aumenta conforme se acerca la cosecha |
| Cebada orgánica, Sentinel-2 10 m | Correlación simple por índice | GCVI en BBCH-41 (embuche): r = 0.80, la mejor de todas las fases evaluadas |
| Predicción temprana con fenología derivada de satélite | Ensembles | Ventana óptima ~DOY 160–175; **NDRE_max** fue la variable más importante por permutación, seguida de métricas de NDWI y NDVI |
| Trigo, PlanetScope vs Sentinel-2 + variables ambientales | RF | S2 ligeramente mejor (RMSE 0.325 vs 0.336 t/ha); **PlanetScope + datos ambientales fue la mejor combinación** |
| Cebada, trigo duro y blando en Argelia, datos pequeños | CNN 1D/2D vs XGBoost | Deep learning **no supera** a XGBoost cuando el dataset es pequeño |

**Conclusión operativa:** con ~138 observaciones, un R² de validación honesta entre 0.4 y 0.6 ya sería un resultado respetable. Cualquier R² > 0.9 en validación cruzada con este dataset es, casi con certeza, fuga de información o sobreajuste. Vale la pena decirlo dentro del equipo antes de que alguien lo vea en pantalla y se emocione.

### 2.3 Qué índices funcionan y cuáles no

- **NDVI satura** en doseles densos (LAI > 3). Es un mal discriminador precisamente en las parcelas de alto rendimiento, que son las que más importa distinguir.
- **Índices con red-edge (NDRE) y con SWIR** superan consistentemente a NDVI. La revisión de importancia de variables en múltiples estudios apunta a red-edge y SWIR como las bandas más informativas.
- **Índices de agua / estrés hídrico** (NDWI, MSI, DSWI) aportan señal complementaria, sobre todo en la fase de llenado.
- Los ganadores del *CGIAR Crop Yield Prediction Challenge* en Zindi construyeron features derivadas específicamente de las **tres bandas red-edge de Sentinel-2**. Es un precedente directo de que ahí está la señal.

**Advertencia específica para cebada, y viene del propio INIFAP.** Un trabajo mexicano sobre genotipos de cebada encontró una relación **inversa** entre NDVI y rendimiento de materia seca en uno de los muestreos, en contra de lo reportado para otros cultivos. Los autores lo atribuyen a la **precocidad** de la cebada frente al trigo y a su menor contenido de clorofila: el mismo estudio observó que el trigo testigo presentaba NDVI más alto (0.76–0.79) pero era más tardío y rindió menos que las cebadas. La lección no es que el NDVI no sirva, sino que **el NDVI en una fecha fija, sin alinear fenológicamente, puede tener el signo equivocado en cebada.** Refuerza el argumento de la sección 1.3: alineen todo a la fenología observada de cada parcela.

En el dataset entregado hay que fijarse: el Dataset Básico incluye SWIR-dependientes (NDTI, STI, MSI, EMSI, CRC, MCRC, NDSVI, SRNDI, DSWI*) y biofísicos (LAI, FAPAR). El PRO (Planet, 4 bandas) **no tiene ni red-edge ni SWIR** — solo NDVI, EVI, LAI, MSAVI. Es decir: PRO aporta **frecuencia temporal y resolución espacial**; Básico aporta **riqueza espectral**. Son complementarios, no redundantes.

### 2.4 Métricas fenológicas: el patrón de feature engineering que domina la literatura

En vez de usar el valor del índice en fechas arbitrarias (frágil ante nubes y ante fechas de siembra distintas), el enfoque estándar es **resumir la trayectoria temporal** de cada índice en un puñado de descriptores:

- Valor **máximo** del índice y **DOY del máximo**
- **Área bajo la curva (AUC)** = proxy de greenness acumulada, muy correlacionada con biomasa total
- **Pendiente de crecimiento** (emergencia → máximo) y **pendiente de senescencia** (máximo → madurez)
- **Fecha de inicio de temporada (SOS)**, fin (EOS), y **duración**
- Integral del índice restringida a **ventanas fenológicas** (p. ej. AUC solo entre embuche y antesis)

Y para el clima, en vez de promedios mensuales crudos: **agregación dentro de ventanas definidas por la fenología de cada parcela**, no por el calendario. Este es el punto donde un equipo bueno se separa de uno promedio.

---

## 3. Qué tipo de problema es realmente este (la parte que casi nadie analiza)

Vale la pena detenerse aquí, porque define toda la estrategia.

### 3.1 No es un problema de pronóstico temporal; es de interpolación espacial

Entrenamiento y predicción son **del mismo año y de la misma región**. No se pide extrapolar a 2026. Se pide: *dadas 138 parcelas con rendimiento conocido en 2025, inferir el rendimiento de otras 59 parcelas del mismo año.*

Consecuencias:

- **Se puede usar toda la temporada 2025**, incluida la señal de senescencia y la post-cosecha. No hay restricción de "lead time". Esto es una ventaja enorme respecto a la mayoría de la literatura, que se autoimpone predecir con 1–4 meses de antelación.
- **La autocorrelación espacial es el riesgo número uno.** Si dos parcelas vecinas caen en el mismo fold de validación cruzada aleatoria, el modelo va a parecer excelente y va a fallar en el leaderboard privado.
- **La historia 2022–2024 de cada parcela es utilizable como predictor legítimo**, porque también existe para las parcelas de predicción. Es, de hecho, una de las señales más potentes disponibles (sección 4.4).

### 3.2 n = 138: régimen de muestra pequeña

Con 138 filas, cada feature adicional cuesta caro. Consideraciones:

- Modelos lineales regularizados (**Ridge, LASSO, Elastic Net**) y árboles con fuerte regularización (**XGBoost/LightGBM con `max_depth` 3–4, `min_child_weight` alto, `subsample`/`colsample` < 0.8**) van a superar a redes neuronales, casi con seguridad.
- La literatura de modelado de rendimiento con muestras pequeñas recomienda **validación cruzada anidada** (el paper de leave-two-out anidado es la referencia canónica): la selección de modelo y la estimación del error deben hacerse en bucles separados, porque elegir el modelo mirando el mismo fold con el que se mide favorece sistemáticamente modelos demasiado complejos.
- **Selección de variables antes que ingeniería infinita de variables.** Es tentador generar 2,000 features (23 índices × 4 estadísticos × 20 fechas × 4 años). Con 138 filas eso es una máquina de sobreajuste. Hay que agregar agresivamente y luego seleccionar con criterio (correlación con el target evaluada *dentro* de cada fold, importancia por permutación, VIF).

### 3.3 Las variables climáticas casi no discriminan entre parcelas

CHIRPS y CHIRTS-ERA5 tienen resolución de **0.05° ≈ 5.5 km**. Las 197 parcelas están repartidas en tres estados, pero es muy probable que **grupos enteros de parcelas caigan en el mismo píxel climático**, y con certeza en el mismo si están en el mismo municipio.

Esto significa:

- Las variables climáticas van a funcionar esencialmente como **un identificador de zona geográfica**, no como una medida del ambiente de cada parcela.
- **Riesgo real de fuga espacial:** si el modelo aprende "las parcelas del píxel X rinden 3.1 t/ha", y la validación cruzada es aleatoria, el modelo memoriza zonas. Con validación espacial honesta, esa capacidad colapsa.
- Aun así **hay que usarlas**, pero como (a) gradiente regional explícito y (b) base para derivadas fenológicamente informadas: grados-día acumulados (GDD, base 0 °C hasta antesis y base 8 °C de antesis a madurez, según la literatura de cebada), días con Tmax por encima de umbral en la ventana crítica, amplitud térmica, número de meses con déficit, índice de aridez (P/ETP aproximada).

Primer diagnóstico a correr el día 1: **contar cuántos píxeles climáticos únicos cubren las 197 parcelas.** Si son menos de ~20, ya se sabe el peso real que puede tener este bloque de datos.

### 3.4 Lo que sí varía a escala de parcela

| Fuente | Resolución | ¿Discrimina entre parcelas? |
|---|---|---|
| Planet (PRO) | ~3 m, casi diario | **Sí, mucho** — la fuente más informativa a escala de parcela |
| Sentinel-2 (Básico) | 10–20 m, 5 días | **Sí** — y aporta red-edge/SWIR que Planet no tiene |
| Landsat (VI6T) | 30 m + térmica ~100 m | Parcialmente; la térmica es valiosa (estrés hídrico real) pero gruesa |
| Elevación / pendiente (CEM 15 m) | 15 m | **Sí** — y se pueden derivar variables mucho más ricas (sección 4.5) |
| CHIRPS / CHIRTS | ~5.5 km | Apenas; funciona como proxy de zona |
| Área de la parcela | exacta | Sí, y no es inocua (sección 4.6) |

**El grueso de la señal aprovechable está en las series espectrales por parcela y en la topografía derivada.** Ahí es donde hay que invertir el tiempo.

---

## 4. Estrategia metodológica propuesta

### 4.1 Diagnóstico y limpieza (no saltarse esto)

1. Distribución del rendimiento: histograma, outliers, ¿hay ceros o parcelas siniestradas? En temporal, las parcelas con pérdida total existen y pueden justificar un tratamiento aparte o una transformación.
2. **Comparar la distribución espacial de ENTRENAMIENTO vs PREDICCION.** ¿Están intercaladas o las de predicción están en una zona distinta? Esto determina si el problema es interpolación (fácil) o extrapolación (difícil) y define la estrategia de validación. Es lo primero que haría yo.
3. Distribución de áreas de parcela en ambos conjuntos.
4. Cobertura temporal real por parcela después de filtrar nubes: ¿cuántas observaciones útiles quedan por parcela en 2025? ¿Hay parcelas con huecos de 4–6 semanas en pleno periodo crítico?
5. Número de píxeles climáticos únicos.
6. Verificar CRS, alineación y que los estadísticos zonales entregados correspondan al polígono completo (¿incluyen píxeles de borde?).

### 4.2 Filtrado de nubes

El dataset conserva el porcentaje de nubosidad **deliberadamente**, para que cada equipo defina su criterio. Recomendación:

- Umbral principal razonable: descartar observaciones con nubosidad > 10–20 %, y hacer **análisis de sensibilidad** con 2–3 umbrales. Documentarlo es parte de la evaluación.
- No descartar sin más: un umbral muy estricto deja parcelas sin observaciones en la ventana crítica. Considerar un umbral adaptativo por parcela (relajarlo si quedan menos de N observaciones).
- Señales físicas de contaminación residual: caídas abruptas y aisladas del NDVI seguidas de recuperación inmediata. Filtro de mediana móvil o detección de outliers sobre la serie antes de suavizar.

### 4.3 Reconstrucción de la serie temporal

Este es el corazón técnico del pipeline. Método estándar y bien documentado:

1. **Compositar** a intervalos regulares (5, 8 o 10 días) tomando el máximo o la mediana del periodo.
2. **Rellenar huecos** por interpolación (lineal o spline) para huecos cortos; dejar sin rellenar huecos > 4–6 semanas y marcarlos con un indicador de calidad.
3. **Suavizar** con **Savitzky-Golay** (polinomio de orden 2, ventana ~5–7 periodos) o **Whittaker** (penalized least squares — el "perfect smoother" de Eilers). Whittaker maneja mejor muestreo irregular; SG es más simple y está en `scipy.signal.savgol_filter`.
4. Alternativa: **regresión armónica de segundo orden** ajustada a todas las observaciones de la temporada. Es lo que usan los trabajos que evalúan modelos fundacionales geoespaciales, y tiene la ventaja de dar una representación compacta y robusta a huecos (coeficientes = features directamente).
5. Cuidado: métodos armónicos y HANTS **subajustan transiciones fenológicas rápidas**. Para cebada, con un ciclo de ~100–120 días y senescencia abrupta, esto importa. Comparar al menos dos métodos.

### 4.4 Ingeniería de variables — el catálogo

**A. Métricas fenológicas 2025 (por índice, para los índices más informativos):**
`max`, `DOY_max`, `min`, `AUC_total`, `AUC_[ventana_crítica]`, `pendiente_crecimiento`, `pendiente_senescencia`, `SOS`, `EOS`, `duración_ciclo`, `amplitud (max−min)`.

Aplicar prioritariamente a: NDVI, EVI, LAI, FAPAR, SAVI (dosel/biomasa); NDWI, MSI, DSWI2-5, NDDI (estrés hídrico); VI6T (térmico).

**B. Fecha de siembra estimada.** Derivarla del SOS de la serie de 2025. Es una variable oculta de primer orden y se puede recuperar. De ahí: **días desde siembra hasta el máximo de VI**, que aproxima la precocidad de la variedad.

**C. Variables de manejo y suelo desnudo (subestimadas por la mayoría de los equipos).** Los índices de labranza y residuos — **NDTI, STI, CRC, MCRC, NDSVI** — en el periodo pre-siembra (abril–mayo) describen el sistema de labranza y la cobertura de residuos de la parcela. Eso es un proxy directo de manejo y de materia orgánica del suelo, y por tanto de productividad potencial. Prácticamente nadie los usará. Aquí hay una ventaja competitiva real.

**D. Historia 2022–2024 como prior de productividad del sitio.** Para cada parcela, calcular el NDVI máximo medio, el AUC medio y la desviación estándar interanual de los tres años previos. Es, en esencia, una estimación empírica de la **capacidad productiva del sitio**, y captura implícitamente suelo, manejo habitual del productor y posición en el paisaje. Es legítima (existe también para las parcelas de predicción) y probablemente sea de las features más fuertes del modelo. También permite construir **anomalías 2025 vs. su propia historia**, que es una forma de normalizar el efecto sitio.

**E. Heterogeneidad intra-parcela.** El dataset incluye `std`, `max` y `min` por parcela y fecha. La **desviación estándar del NDVI en la ventana crítica** es una medida de uniformidad del cultivo: parcelas heterogéneas (fallas de emergencia, manchones de estrés, acame parcial) rinden menos. Es una feature barata y muy poco usada. También: `(max − min)` y el coeficiente de variación.

**F. Topografía derivada del CEM.** No quedarse en elevación y pendiente crudas. Del ráster de 15 m se pueden derivar, con `richdem`, `whitebox` o `gdaldem`:
- **Orientación (aspect)** y su descomposición en seno/coseno → exposición solar y evapotranspiración.
- **TWI (Topographic Wetness Index)** → acumulación de humedad, muy relevante en temporal.
- **Curvatura** (plana y de perfil) → zonas cóncavas acumulan agua y sedimento.
- **TPI / posición relativa en la ladera**.
- Estadísticos zonales de todo lo anterior: media, std, rango dentro de la parcela.

**G. Clima con ventanas fenológicas.** GDD acumulados por fase, precipitación acumulada entre SOS y antesis, entre antesis y EOS, número de meses secos, anomalía respecto al promedio 2022–2024 del mismo píxel.

**H. Geográficas.** Latitud, longitud, estado, distancia a centroides regionales. Usar **con cuidado**: mejoran el ajuste y destruyen la generalización si la validación no es espacial. Probarlas con y sin.

### 4.5 Fusión Básico ↔ PRO

El diccionario advierte explícitamente: **no fusionar automáticamente** índices homónimos de fuentes distintas. Es correcto — Planet y Sentinel-2 difieren en respuesta espectral, calibración radiométrica y corrección atmosférica, y aunque Planet ofrece una opción de armonización a Sentinel-2, sigue habiendo sesgo sistemático.

Estrategias, en orden de ambición:

1. **Mantenerlos como bloques de features separados.** Es lo seguro y probablemente suficiente. `NDVI_max_S2` y `NDVI_max_Planet` son dos columnas distintas.
2. **Armonización lineal por regresión** entre pares de observaciones cuasi-simultáneas (mismo día ±1) de la misma parcela, para estimar sesgo y escala. Es el procedimiento que recomienda la literatura de fusión multi-sensor antes de integrar series.
3. **Fusión temporal** tras armonizar: serie combinada a 5 días que aprovecha la frecuencia de Planet y la profundidad espectral de S2. Mayor riesgo, mayor recompensa.

La opción 2, bien documentada, es un excelente diferenciador y es defendible ante un jurado.

### 4.6 Área de parcela: úsala, pero entiende por qué

El área está disponible para las 197. Puede correlacionar con rendimiento por razones socioeconómicas (parcelas grandes → productores más capitalizados → mecanización y fertilización), y por razones puramente técnicas (parcelas pequeñas → mayor proporción de píxeles de borde contaminados → estadísticos zonales ruidosos).

Vale la pena:
- Incluir el área y el **perímetro/área** (compacidad) como features.
- Verificar si las parcelas pequeñas tienen residuos sistemáticamente mayores. Si sí, considerar ponderar el entrenamiento o reportar el desempeño por estrato de tamaño.

### 4.7 Modelado

Orden sugerido, de menos a más:

1. **Baselines** (media, media por zona, NDVI_max lineal).
2. **Ridge / Elastic Net** sobre features estandarizadas. Con n=138 esto es competitivo de verdad, no un trámite.
3. **Random Forest** y **Gradient Boosting regularizado** (XGBoost / LightGBM / CatBoost), profundidad baja.
4. **Ensemble por promedio o stacking simple** de 2–3 modelos diversos. Suele dar una mejora modesta pero consistente, y la evidencia indica que los ensembles son más robustos a la elección de la fecha de corte.
5. **PLS regression** — conviene tenerla en el radar: está diseñada exactamente para el caso de muchas variables colineales y pocas observaciones, que es este caso.
6. **TabPFN** — apuesta oportunista con muy buena relación costo/beneficio en este régimen. Es un transformer preentrenado para datos tabulares pequeños y medianos que hace inferencia en un solo paso, **sin ajuste de hiperparámetros**. En pronóstico de rendimiento subnacional en Sudáfrica (maíz, soya, girasol) con series decadales de FAPAR, humedad de suelo y clima, superó a SVR, CatBoost, XGBoost y LightGBM en datasets pequeños sin tuning extensivo, y también al conjunto de modelos afinados de AutoGluon. Con 138 filas y ~40 features corre en segundos. Vale la pena incluirlo en el ensemble aunque sea solo para comparar.
7. **Gaussian Process Regression** — da **incertidumbre de forma nativa**, que es justo lo que le interesa a una institución financiera, y fue el modelo con mejor desempeño en el trabajo suizo de pronóstico intra-parcelario de cereales con series de Sentinel-2.

Sobre el ensemble: con n = 138, **promedio simple o ponderado de 3–4 modelos diversos** es lo razonable. **No hagan stacking con meta-modelo entrenado** — no hay datos suficientes y es una fuente clásica de fuga.

Descartar: redes profundas, LSTM, transformers temporales. La evidencia con datasets pequeños de rendimiento es consistente en que **no superan a los boosted trees** y consumen todo el tiempo del hackatón.

Consideraciones adicionales:
- Evaluar transformación del target (log o raíz cuadrada) si la distribución es sesgada.
- Evaluar un modelo en dos etapas si hay parcelas siniestradas: clasificador de pérdida total + regresor sobre las demás.
- **Intervalos de predicción** (regresión cuantílica o bootstrap). Entregar incertidumbre junto con la predicción distingue una solución profesional de una demo, especialmente ante FIRA, cuyo interés de fondo es la gestión de riesgo crediticio y agrícola.

### 4.8 Validación — donde se gana o se pierde el reto

Esta es la sección más importante del documento.

**No usar K-fold aleatorio.** Con datos espaciales autocorrelacionados, la validación cruzada aleatoria produce estimaciones sistemáticamente optimistas; la literatura es contundente en que el CV espacial debe ser el estándar, no la excepción, cuando el objetivo es predecir fuera del dominio espacial de entrenamiento.

Esquema recomendado:

1. **CV por bloques espaciales**: agrupar parcelas con K-means sobre coordenadas (o por municipio / píxel climático) y hacer *leave-one-group-out*. Esto simula el escenario real.
2. **CV anidada** para separar selección de hiperparámetros de estimación de error.
3. Reportar **ambas** métricas (CV aleatoria y CV espacial). La brecha entre las dos *es en sí misma un resultado presentable*: cuantifica cuánta de la aparente precisión del modelo viene de memorizar ubicaciones. Muy pocos equipos harán esto y se nota.
4. Métricas: **RMSE** (principal, en t/ha, interpretable), **MAE**, **R²**, **sesgo medio**. Graficar observado vs predicho con línea 1:1 y examinar residuos contra elevación, área, estado y nubosidad.

**Fugas de información a vigilar:**
- Calcular estadísticas de normalización, imputación o selección de variables sobre el dataset completo antes de dividir. Todo dentro del pipeline, dentro del fold.
- Features geográficas que actúan como identificadores de zona.
- Parcelas colindantes del mismo productor repartidas entre train y validación.

---

## 5. Riesgos y modos de fallo típicos

| Riesgo | Señal de alarma | Mitigación |
|---|---|---|
| Sobreajuste por exceso de features | R² CV > 0.85 | CV espacial anidada, regularización fuerte, límite explícito de features (~15–30) |
| Fuga espacial | El modelo empeora mucho al cambiar de CV aleatoria a espacial | Validación por bloques desde el principio |
| Nubosidad concentrada en la ventana crítica | Parcelas sin observaciones julio–agosto | Suavizado + armónicos; indicador de calidad como feature; considerar Sentinel-1 externo |
| Confundir señal de otro cultivo | NDVI con dos picos, o ciclo que no corresponde a cebada | Inspección visual de series anómalas; verificar contra el calendario esperado |
| Ruido de píxeles de borde en parcelas pequeñas | Residuos mayores en parcelas chicas | Buffer negativo si se re-extrae; ponderación; reportar por estrato |
| Optimizar el leaderboard público | Mejoras que no se sostienen | Confiar en la CV espacial propia por encima del leaderboard |
| Modelo sin baseline | Nadie sabe si el modelo aporta algo | Reportar siempre el baseline de la media |

---

## 6. Datos públicos adicionales que vale la pena evaluar

El reto **permite explícitamente** incorporar información pública documentada. Candidatos ordenados por relación valor/esfuerzo:

1. **Sentinel-1 (SAR, GEE, 10 m, ~6–12 días).** Penetra nubes. El backscatter VV/VH y la razón VH/VV son sensibles a la estructura del dosel y a la biomasa, y son la solución estándar a los huecos ópticos en época de lluvias. Alto valor en una región con temporal de verano.
2. **SoilGrids 250 m** (ISRIC): carbono orgánico, textura, pH, capacidad de retención de agua. Ninguna variable edáfica está en el dataset entregado, y el suelo es determinante del rendimiento de temporal. Alternativa nacional: cartografía edafológica de INEGI serie VII.
3. **ERA5-Land (~9 km, horario)**: humedad de suelo, evapotranspiración potencial, radiación. Permite construir un **balance hídrico simple** y un índice de satisfacción de necesidades de agua, mucho más informativo que la precipitación cruda.
4. **Bandas crudas de Sentinel-2 vía GEE** para calcular NDRE / red-edge, que la literatura señala como las más predictivas y que **no vienen en el dataset entregado**. Requiere procesamiento propio, pero el diferencial esperado es alto.
5. **SIAP** (rendimientos municipales históricos de cebada de temporal): permiten construir un prior por municipio y contextualizar los resultados.
6. **Estadística agrícola municipal / marco censal agropecuario INEGI**: tamaño medio de unidad de producción, nivel de mecanización.
7. **Monitor de Sequía de México (CONAGUA)**: índice categórico por municipio y quincena.

Prioridad realista si el tiempo es corto: **SoilGrids (barato, alto valor) y Sentinel-1 (caro, alto valor)**. El resto, si sobra tiempo.

---

## 7. Plan de trabajo sugerido

**Fase 1 — Comprensión (20 % del tiempo).**
Diagnóstico completo (4.1). Salida: un notebook de EDA con las respuestas a las 6 preguntas de diagnóstico, distribución espacial train/test, y el baseline de la media ya calculado.

**Fase 2 — Construcción de la tabla de features (35 %).**
Filtrado de nubes → compositado → suavizado → métricas fenológicas → topografía derivada → clima por ventanas → historia 2022–2024. Salida: una tabla de 197 filas × N features, con un script reproducible y un diccionario de datos propio.

**Fase 3 — Modelado y validación (30 %).**
Baselines → lineales regularizados → boosting → ensemble. Todo bajo CV espacial anidada. Salida: tabla comparativa de modelos con RMSE bajo ambos esquemas de CV.

**Fase 4 — Interpretación y entrega (15 %).**
Importancia por permutación, SHAP, gráficas observado-vs-predicho, mapa de predicciones, intervalos de incertidumbre, discusión de limitaciones. Salida: predicciones finales + presentación.

Reservar la Fase 4 de verdad. En hackatones de datos, la diferencia entre el tercer y el primer lugar casi nunca es el RMSE; es la calidad del razonamiento mostrado, la honestidad de la validación y la claridad de la narrativa agronómica. El jurado de FIRA está compuesto por gente que entiende de crédito agrícola y de campo, no solo de modelos.

---

## 8. Cinco ideas diferenciadoras (resumen)

1. **Explotar los índices de residuos y labranza pre-siembra (NDTI, STI, CRC, NDSVI)** como proxy de manejo y calidad de suelo. Casi nadie lo hará.
2. **Usar la historia 2022–2024 de cada parcela como prior de productividad del sitio** y modelar 2025 como anomalía respecto a ese prior.
3. **Estimar la fecha de siembra por parcela** desde el SOS y usarla para alinear fenológicamente todas las demás variables, incluidas las climáticas.
4. **Reportar explícitamente la brecha entre CV aleatoria y CV espacial** como medida de fuga y de honestidad del modelo.
5. **Entregar intervalos de predicción**, no solo puntos — es lo que una institución financiera realmente necesita para tomar decisiones de riesgo.

---

## 9. Lista de verificación antes de entregar

- [ ] ¿Verificaron si la partición ENTRENAMIENTO/PREDICCIÓN es espacial o aleatoria? *(cambia toda la estrategia de validación)*
- [ ] ¿Su validación cruzada es espacial, o están inflando el score?
- [ ] ¿Reportan la brecha entre CV aleatoria y CV espacial?
- [ ] ¿La selección de variables ocurre **dentro** de cada fold?
- [ ] ¿Escalado e imputación se ajustan solo con los datos de entrenamiento del fold?
- [ ] ¿Están fusionando Sentinel-2, Landsat y Planet sin armonizar? *(el diccionario lo desaconseja explícitamente)*
- [ ] ¿Usan meses calendario en vez de ventanas fenológicas por parcela?
- [ ] ¿Asumen que más lluvia = más rendimiento, en el año más lluvioso desde 1941?
- [ ] ¿Cuántos píxeles climáticos únicos hay realmente? ¿Están tratando 20 valores como si fueran 197?
- [ ] ¿Filtraron píxeles de borde, o el `std` de la parcela es ruido de linderos?
- [ ] ¿Compararon contra el baseline de "predecir la media"? ¿Lo superan de forma clara?
- [ ] ¿Cuántas variables tiene el modelo final por cada muestra de entrenamiento?
- [ ] ¿Las predicciones caen en el rango agronómicamente plausible (~1.5–3.5 t/ha)? ¿Hay negativos?
- [ ] ¿La distribución de las 59 predicciones se parece a la de las 138 de entrenamiento, o el modelo está prediciendo la media con pasos extra?
- [ ] ¿El mapa de predicciones es espacialmente coherente?
- [ ] ¿Están usando el leaderboard público para seleccionar modelo? *(no lo hagan: 59 parcelas se sobreajustan con facilidad)*
- [ ] ¿Documentaron CRS, reproyecciones, criterios de nubosidad y reglas de agregación?
- [ ] ¿Entregan intervalos de predicción, no solo puntos?

---

## 10. Preguntas que conviene hacerle a los organizadores

Vale la pena preguntarlas el primer día; varias cambian decisiones de diseño importantes.

1. **¿Cómo se midió el rendimiento?** (báscula de acopio, reporte del productor, muestreo en campo) → determina el techo de precisión alcanzable. Con etiqueta reportada, un error del ±10–20 % es normal y ningún modelo lo puede superar.
2. **¿La partición ENTRENAMIENTO/PREDICCIÓN es aleatoria o espacial?** Es la pregunta más importante del reto.
3. **¿Cuál es la métrica oficial de evaluación y cuántos envíos se permiten?**
4. **¿Todas las parcelas son de temporal, o hay alguna bajo riego?** Una sola parcela de riego mal identificada distorsiona el ajuste.
5. **¿El rendimiento reportado es grano limpio y seco a 13–14 % de humedad, o grano de campo?**
6. **¿Hay parcelas siniestradas o con pérdida parcial** que expliquen valores muy bajos?
7. **¿Se conoce variedad, fecha de siembra o dosis de fertilización**, aunque no estén en el dataset entregado?
8. **¿Se penaliza el uso de datos externos, o solo se exige documentarlos?**

---

## 11. Referencias principales

**Cultivo y región**
- INIFAP. *Cebada maltera de temporal en Valles Altos de México*. gob.mx/inifap
- Zamora Díaz, M. et al. (2008). Adabella: variedad de cebada maltera para valles altos de la mesa central de México. *Agricultura Técnica en México*, 34(4).
- Zamora Díaz, M. et al. (2010). Armida, nueva variedad de cebada maltera. *Rev. Mex. Cienc. Agríc.*, 1(5).
- INIFAP. *Agenda Técnica Agrícola de Hidalgo* (2017).
- SIAP — estadística de producción agrícola por estado y municipio.

**Fisiología del rendimiento**
- Slafer, G. et al. — periodo crítico para la determinación del número de granos en cereales de grano pequeño.
- Estudios sobre olas de calor pre y post-antesis en trigo y cebada: *Field Crops Research* (2024, 2025).
- Modelo de tiempo térmico para llenado de grano en cebada: *Field Crops Research* (2021).

**Percepción remota y rendimiento**
- *Sentinel-2 for crop yield estimation: A systematic review*. ScienceDirect (2026).
- *High-Resolution Wheat and Barley Yield Forecasting Using Multi-Temporal Satellite Time Series and Machine Learning*. Agriculture, 16(5), 516 (2026).
- *Wheat yield prediction using integrated optical and radar remote sensing with machine learning across key phenological stages*. Scientific Reports (2026).
- *Evaluation of Sentinel-2 Deep Resolution 3.0 Data for Winter Crop Identification and Organic Barley Yield Prediction*. Remote Sensing, 17(6), 957 (2025).
- *Field-Aware and Explainable Modelling for Early-Season Crop Yield Prediction Using Satellite-Derived Phenology*. Remote Sensing, 18(6), 890 (2026).
- *Combining PlanetScope and Sentinel-2 images with environmental data for improved wheat yield estimation*. Int. J. Digital Earth (2023).
- *Enhancing Rice Yield Prediction Through Cross-Sensor Time-Series Integration*. AgriEngineering, 8(8), 316 (2026).
- *A review of crop yield estimation on pixel and field scales from remotely sensed data* (2025).

**Series temporales y reconstrucción**
- Chen, J. et al. (2004). A simple method for reconstructing a high-quality NDVI time-series data set based on the Savitzky–Golay filter. *RSE*, 91.
- Eilers, P.H.C. (2003). A perfect smoother. *Analytical Chemistry*, 75.
- *A practical approach to reconstruct high-quality Landsat NDVI time-series data by gap filling and the Savitzky–Golay filter*. ISPRS J. (2021).

**Validación y muestras pequeñas**
- Dinh, T.L.A. & Aires, F. (2022). Nested leave-two-out cross-validation for the optimal crop yield model selection. *Geoscientific Model Development*, 15, 3519.
- Le Rest, K. et al. (2014). Spatial leave-one-out cross-validation for variable selection in the presence of spatial autocorrelation. *Global Ecology and Biogeography*, 23.
- *Critical evaluation of the effects of a cross-validation strategy and machine learning optimization on the prediction accuracy and transferability of a soybean yield prediction model* (2024).
- *Is deeper always better? Evaluating deep learning models for yield forecasting with small data* (cebada y trigo en Argelia).

**Datos climáticos**
- Funk, C. et al. (2015). CHIRPS. *Scientific Data*, 2, 150066.
- Climate Hazards Center (2025). CHIRTS-ERA5 Data Repository.
- INEGI (2025). Continuo de Elevaciones Mexicano 4.0.

**Periodo crítico y fisiología de la cebada (añadido)**
- Arisnabarreta, S. & Miralles, D.J. (2008). *Critical period for grain number establishment of near isogenic lines of two- and six-rowed barley*. Field Crops Research. https://www.sciencedirect.com/science/article/pii/S0378429008000373
- *Influence of photothermal quotient in the critical period on yield potential of cereals – A comparison of wheat and barley*. Field Crops Research (2024). https://www.sciencedirect.com/science/article/pii/S0378429024004118
- de San Celedonio, R.P. et al. (2014). *Identifying the critical period for waterlogging on yield and its components in wheat and barley*. Plant and Soil. https://link.springer.com/article/10.1007/s11104-014-2028-6
- *Yield and biomass in wheat and barley under a range of conditions in a Mediterranean site*. Field Crops Research (2009).
- INIFAP. *Cebada sin arista, rendimiento de materia seca, NDVI* — relación NDVI-rendimiento en cebada. https://cienciasagricolas.inifap.gob.mx/index.php/agricolas/article/download/1606/2477

**Modelos para muestras pequeñas (añadido)**
- *From rows to yields: how foundation models for tabular data simplify crop yield prediction* (TabPFN). Scientific Reports (2026). https://www.nature.com/articles/s41598-026-50338-z
- *In-season forecasting of within-field grain yield from Sentinel-2 time series data* (GPR, Suiza). https://www.sciencedirect.com/science/article/pii/S1569843223004600

**Contexto climático 2025 (añadido)**
- CONAGUA / SMN — Monitor de Sequía de México y reportes de temporada de lluvias 2024-2025.
- UNAM, Instituto de Ciencias de la Atmósfera y Cambio Climático — análisis de la temporada de lluvias 2025 (la más intensa desde 1941).
- SIAP — *Estadísticas de producción de cebada grano en México*, cierre 2024.

**Competencias análogas**
- Zindi — *CGIAR Crop Yield Prediction Challenge* (maíz, África Oriental, Sentinel-2 + clima).
- Zindi — *CGIAR Wheat Growth Stage Challenge*.
