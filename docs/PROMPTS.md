# Prompts principales

Las bases del Reto AgroCebada FIRA 2026 permiten usar inteligencia artificial siempre que se indique dónde se usó y se
anexen los prompts. Este archivo reúne los prompts más útiles del proyecto, no todos. El anexo técnico lo cita en su
sección de aportaciones y uso de inteligencia artificial, y resume los prompts en su Tabla IV.

Usamos Claude Code, de Anthropic, para programar, auditar y redactar. Ningún resultado se usó sin revisarlo. Las
cifras de los reportes salen del código del repositorio, no del texto que generó la herramienta.

Los prompts se copian como se escribieron, con sus errores de dedazo. Los fragmentos que no tienen que ver con el
método se omiten y se marcan con [...].

## Resumen

| Tema | Resultado y uso |
|---|---|
| Identificar el problema del dataset | Diagnóstico del ruido de las etiquetas y de los dos regímenes de registro. |
| Proponer un plan de validación | Regla de decisión fijada de antemano (7 de 10 repeticiones y prueba de permutación). |
| Auditar el código del modelo | Se encontró que el relleno del rezago usaba la propia etiqueta, y se corrigió. |
| Auditar de forma independiente | Motivó el modelo municipal con datos públicos. |
| Investigar qué explica los regímenes | Hipótesis de fuente mixta, no confirmada. |
| Diseñar la capa de crédito | Capa con supuestos revisados (precio, costos, siniestro y semáforo). |
| Atender al asesor | Auditoría sin fuga y correcciones de los reportes. |

## Prompts

### 1. Plan de trabajo e investigación inicial (23 de septiembre de 2026)

Generó el `ROADMAP.md`, el script de diagnóstico inicial y los issues de cada integrante.

> Crea un ROADMAP indicando todos los pasos que debemos de realizar para tener un entregable. Estamos trabajando en
> equipo en github, por ende requiero que abras issues para cada integrante, somos tres. No te agregues como co author.
>
> Revisa el dataset y la documentación de los datos. Si es necesario (hay gaps de información) investiga el estado del
> arte en internet.

### 2. Identificar el problema del dataset (4 de octubre de 2026)

Resultado: el documento de contexto, con los dos regímenes de registro y el ruido de las etiquetas.

> Necesito que leas la documentación y los issues de github. Ya dividimos el trabajo, nada más que me gustaría empezar
> con lo que sea para adelantar porque no nos queda mucho tiempo. Lo que más me preocupa como garantizamos el mejor
> trabajo posible que nosotros podamos realizar. Ya identificamos que el problema principal será el dataset, está muy
> escazo, asi que la pregunta es, como podemos mejorar nuestro dataset? Hay datos públicos que podamos aprovechar? [...]
>
> Primero empieza leyendo la documentación e investigación existente de nuestro proyecto [...]. Luego necesito que
> identifiques el problema central, obviamente es el dataset, pero la pregunta es, como lo podemos resolver? No necesito
> que modifiques nada de momento, simplemente será un trabajo de investigación aún más intensivo y extenso.

### 3. Plan de validación y regla de decisión (4 y 5 de octubre de 2026)

Resultado: validación cruzada repetida, esquema por zonas y la regla de 7 de 10 repeticiones con prueba de
permutación (`src/parcelas/cv.py`).

> Soy bastante escéptico de tu investigación. Me gustaría tener un plan a prueba de balas que garantice acercarnos al
> mejor resultado. Entiendo que el objetivo es disminuir los más posible el RMSE, con los datos públicos y los datos que
> nos dan, estimas que en el mejor caso llegaremos a 0.42-0.46. Como puedes estar tan seguro de eso? Como estás tan
> seguro que no se puede mejorar?. Por donde podemos comenzar para saber que vamos en el camino correcto? En mi
> experiencia lo que más me ha funcionado ha sido probar todas las posibilidades y empezar por las más probables. El
> problema es que me parece que todavía no logro entender del todo la problemática. Entiendo que entonces la
> problemática no es el tamaño del dataset ni la contaminación dentro de esta, es la estructura?
>
> Tal vez lo único que me falta es entender la problemática, necesito que me la expliques de manera dinámica y
> defiendas cada paso con referencias. No estoy muy bañado con el tecnisismo asi que preferiría que no lo utilices
> tanto, pero si hay conceptos que es de vital importancia entender, primero explicamelo antes de utilizarlo.

Al día siguiente se pidió implementar el plan.

> Revisa los issues de github, me parece que ya está todo estructurado para nada más empezar a implementar. [...]
>
> Necesito que entres en modo plan después de haber identificado toda la documentación. [...]
>
> La implementación debe de ser ordenada ya que más a futuro se tendrán que realizar varias entregas como se especifica
> en un documento. Puedes instanciar varios agentes Sonnet asíncronos para la implementación.
>
> Si tienes alguna duda me puedes consultar.

### 4. Auditoría del código del modelo (7 de octubre de 2026)

Resultado: el relleno del rezago espacial usaba la propia etiqueta. Se corrigió y se repitieron todos los
experimentos.

> Me gustaría validar el procedimiento que realizamos para crear el modelo. Puedes consultar todos los pasos que
> realizamos en el repo de github en todos los pull request. Encontré este repo que ayuda para todo el proceso de
> publicación de un paper, nosé si nos sirva... Sé que no es el mejor pero no se me ocurre como podemos verificar un
> trabajo hecho por una IA y validar que esté correcot, que lo haga otra IA me parece irresponsable pero honestamente ni
> yo aún estando entrenando en el área logro entender todo el proceso, me pasa bastante por encima la calidad y el
> trabajo de la IA. Por ende, la mejor soluciónque se me ocurre es utilizar otra IA para evaluar el trabajo. El viernes
> también vamos a consultar el trabajo con nuestro asesor que está dedicado al área, pero me gustaría entregar un
> trabajo bien hecho antes.
>
> No śe que opines? Entras en modo plan y evaluas el trabajo? O prefieres buscar un repo con skill y subagentes
> dedicados a esto? Pero no se me ocurre que podría funcionar.
>
> https://github.com/imbad0202/academic-research-skills

Después de revisar el plan de auditoría.

> Perfecto. Realiza la auditoría, me gustaría que al final realices un reporte del modelo con el formato LaTeX que está
> en main.tex.

### 5. Auditoría independiente y modelo municipal (9 de octubre de 2026)

Resultado: el modelo municipal con datos públicos del SIAP de 2003 a 2025.

> Aunque no lo indico en el siguiente prompt, el objetivo es identificar las variables que más influyen en el
> rendimiento de la cebada. Asi, utilizando los datos públicos podemos decir en estás áreas hay una mayor probabilidad
> de mejor rendimiento de la cebada. Ya extrajimos mucha información pública, pero si necesitas más me avisas.

Junto con ese texto se pasó el prompt de abajo, que fija el objetivo, los datos, el método de validación y los
entregables.

<details>
<summary>Prompt completo del modelo generalizable</summary>

```markdown
Aunque no lo indico en el siguiente prompt, el objetivo es identificar las variables que más influyen en el rendimiento de la cebada. Asi, utilizando los datos públicos podemos decir en estás áreas hay una mayor probabilidad de mejor rendimiento de la cebada. Ya extrajimos mucha información pública, pero si necesitas más me avisas. 

# Prompt: modelo de rendimiento de cebada generalizable con datos públicos

Repositorio: `alan-pv/AgroCebada_Hackaton`. Parte de la rama `claude/fira-yield-generalization-y55qyx` (tiene el reporte de regímenes y los datos externos). Trabaja en una rama nueva creada desde ahí. Todo el código, los comentarios, los commits y los documentos van en español, con el mismo estilo del repositorio.

## Contexto

Somos un equipo de la BUAP en el Reto AgroCebada FIRA 2026. Hay que predecir el rendimiento de cebada de temporal (t/ha) de 59 parcelas de Puebla, Hidalgo y Tlaxcala, a partir de 138 parcelas de entrenamiento del ciclo primavera-verano 2025. La entrega vence el 19 de octubre de 2026. Las variables se congelaron el 10 de octubre y el modelo de la entrega el 14. **No modifiques el modelo de la entrega** (`src/agrocebada/`, `models/modelo_final.joblib`, `outputs/`). Este trabajo es un complemento para la app, el reporte y la presentación (Etapa 2).

Antes de empezar, lee en este orden:

1. `README.md` y `ROADMAP.md`: estructura, comandos (`uv`) y reglas del equipo.
2. `docs/model_card.md`: el modelo de la entrega, un proceso gaussiano con el régimen de la etiqueta y el rezago espacial de vecinos a 400 m. RMSE de 0.458 en validación cruzada.
3. `docs/reporte_regimenes/main.pdf` y sus fuentes en `secciones/`: el hallazgo que motiva este trabajo.
4. `data/externos/README.md`: los datos públicos que ya tenemos.

### Lo que encontramos (resumen del reporte de regímenes)

- Las etiquetas se dividen por municipio en dos regímenes. **A**: Chignahuapan, Almoloya, Cuautepec de Hinojosa y Tepeapulco, con dos decimales y media de 4.49 t/ha. **B**: Singuilucan, Apan, Emiliano Zapata (Hgo.), Calpulalpan y Nanacamilpa, redondeados a 0.5 o 0.1, con media de 3.05.
- La brecha de 1.44 t/ha **no es del lugar**. Descartamos el clima, la altitud, la fenología observada por Planet, el suelo de INEGI (con el mismo suelo la brecha sigue siendo de 1.5) y la ceniza del Popocatépetl. Singuilucan (B) colinda con Cuautepec (A), con el mismo suelo y el mismo clima, y rinde 1.5 t/ha menos.
- **SIAP 2023–2025** (cierre agrícola municipal): los municipios A y B promedian lo mismo, 2.51 contra 2.48 t/ha. Todo el régimen A está de 1.3 a 2.6 t/ha por arriba del promedio oficial de su municipio. La correlación entre la media del reto y la del SIAP por municipio es negativa.
- Conclusión: las etiquetas del reto dependen de cómo se obtuvieron en cada municipio (medición o selección de productores), así que **no sirven para aprender la relación entre ambiente y rendimiento**. Dejando fuera un municipio completo, el ambiente predice el reto con un RMSE de 0.69, contra 0.49 si se conoce el régimen.

### La pregunta de FIRA que queremos responder

"Si siembro en un lugar donde no hay parcelas medidas, ¿qué rendimiento puedo esperar y con qué riesgo?" El modelo de la entrega no responde esto, porque depende del régimen y de vecinos ya medidos.

## Objetivo

Construir un **modelo de rendimiento esperado a nivel municipio y año**, entrenado con el SIAP, que es la única fuente con el mismo criterio para todos los municipios. Las variables deben poder calcularse para cualquier punto o municipio, como clima, suelo y topografía. El resultado debe incluir:

1. **El rendimiento esperado** de un municipio o lugar nuevo, con su intervalo.
2. **El riesgo**: la variabilidad entre años y la probabilidad de quedar bajo un umbral, por ejemplo 2 t/ha. Para crédito y seguro agrícola, esto es lo más útil para FIRA.
3. **La relación con el reto**: el modelo da el nivel base del lugar, y el reto muestra cuánto se desvía de ese nivel cada grupo de productores. Interprétalo con cuidado: no sabemos si la desviación del régimen A es medición o selección.

Unidad de análisis: municipio por año. Variable objetivo: rendimiento del SIAP (t/ha), cebada grano, temporal, primavera-verano.

## Datos

### Ya disponibles en el repositorio

- `data/externos/siap/`: SIAP municipal 2023–2025 de Hidalgo (27 municipios), Puebla (30 a 33) y Tlaxcala (26). Son tablas HTML con extensión `.xls`; `docs/reporte_regimenes/scripts/figuras.py` tiene un lector. También está el consolidado `cebada_temporal_pv_municipal_2023_2025.csv`.
- `DATASET_RETO_AGRO_2026/`: lluvia mensual CHIRPS y temperaturas máxima y mínima CHIRTS-ERA5 de 2022 a 2025, en rásteres de 0.05° que cubren de 99.95° a 96.7° O y de 17.8° a 21.4° N, es decir, toda la región. También la topografía de INEGI a 120 m (elevación y pendiente, EPSG:6372). `agrocebada.io.extraer_rasteres()` los descomprime.
- `data/externos/inegi_edafologia/`: suelos 1:250 000, **solo la hoja E14-2** (19–20° N, 98–100° O). Los municipios del este de Puebla (Cuyoaco, Libres, Oriental y otros) y el norte de Hidalgo caen en otras hojas.

### Faltan (si la red de la sesión los bloquea, pídeselos al usuario con el enlace y los filtros exactos)

1. **Polígonos municipales**: INEGI, Marco Geoestadístico (shapefile de municipios). Imprescindible.
2. **Historia del SIAP**: misma consulta, todos los años disponibles (idealmente 2003–2025), en https://nube.agricultura.gob.mx/cierre_agricola/. Filtros: "Por ubicación geográfica", "Por Municipio", ciclo primavera-verano, modalidad temporal, cultivo cebada grano, un archivo por estado y año. Agrega el Estado de México si hay tiempo, para tener más municipios.
3. **Clima histórico**: CHIRPS mensual y temperatura (CHIRTS o ERA5) para los años del SIAP anteriores a 2022, en la misma rejilla.
4. **Suelo**: hojas E14-3, F14-11 y F14-12 de la carta edafológica Serie II, en https://www.inegi.org.mx/temas/edafologia/.
5. **Máscara agrícola**, opcional: INEGI, Uso de suelo y vegetación Serie VII, para calcular las variables solo sobre superficie agrícola.

Si se puede cambiar la red del entorno, los dominios a permitir son `[www.inegi.org.mx](https://www.inegi.org.mx)`, `nube.agricultura.gob.mx` y `data.chc.ucsb.edu` (CHIRPS).

## Método

1. **Tabla municipio-año.** Lee y limpia el SIAP. Excluye los municipios con superficie cosechada muy pequeña (por ejemplo, menos de 50 ha) y marca los años con superficie siniestrada alta. Revisa valores sospechosos: redondeos (Tlaxcala 2025 trae 4.00 y 5.00 exactos) y municipios del sur de Hidalgo por debajo de 1 t/ha.
2. **Variables por municipio**, ponderadas por área agrícola si hay máscara y, si no, por el polígono completo:
   - Clima por año en ventanas del ciclo: siembra (may–jun), crecimiento (jul–ago), llenado y cosecha (sep–oct). Lluvia total y por ventana, Tmax, Tmin, amplitud, grados-día y anomalías contra el promedio del municipio. Reutiliza las ventanas de `src/agrocebada/features_env.py`.
   - Variables fijas del municipio: elevación, pendiente, fracción de cada grupo de suelo (WRB), fracción con fase dúrica (tepetate) y textura.
3. **Validación.** Esta es la parte crítica; respeta las reglas del repositorio: particiones fijas, semilla 2026, todo preprocesamiento dentro del fold, y la regla de decisión de ganar en al menos 7 de 10 repeticiones más una prueba de permutación con p ≤ 0.05.
   - **Esquema principal: dejar fuera un municipio**, o grupos espaciales de municipios vecinos para evitar fuga por autocorrelación espacial. Simula un lugar nuevo.
   - **Esquema secundario: dejar fuera un año.** Simula un año nuevo.
   - **Bases que hay que superar:** (a) la media estatal; (b) la interpolación espacial de los municipios vecinos (IDW o kriging del rendimiento medio). La (b) es la más importante: si el ambiente no la supera, el modelo no aporta sobre "mirar a los vecinos". Para un municipio con historia, compara además contra su propia media histórica.
4. **Modelos.** Empieza simple: ridge o un modelo mixto con efecto aleatorio de municipio. Después prueba un bosque aleatorio o LightGBM poco profundo y un proceso gaussiano con kernel espacial más variables. Hay pocos municipios (unos 80), así que regulariza y evita decenas de variables.
5. **Riesgo.** Por municipio: media, desviación entre años y probabilidad de quedar bajo un umbral, a partir de los residuos del esquema "dejar fuera un año" o de un modelo con varianza. Verifica la cobertura de los intervalos como en `src/agrocebada/intervalos.py`.
6. **Conexión con el reto.** Predice el nivel base de los 9 municipios del reto y compáralo con las medias del reto por régimen. Reporta la diferencia del régimen A y del B contra el nivel base, sin interpretarla como causal.
7. **Interpretación.** Importancia por permutación agrupada (clima, suelo, topografía) en el esquema "dejar fuera un municipio". Responde qué variables explican la diferencia entre municipios, con evidencia fuera de muestra.

## Entregables

- Código en `src/agrocebada/generalizable/`, o en `scripts/` si es exploratorio, con pruebas en `tests/`.
- Datos nuevos en `data/externos/`, con fuente, fecha de consulta y filtros en su `README.md`.
- Tabla de resultados con todos los modelos y bases en ambos esquemas: RMSE, MAE, R² y cobertura de los intervalos.
- Capa para la app: `outputs/generalizable_municipios.parquet` con municipio, rendimiento esperado, p10, p90 y probabilidad bajo el umbral, más un GeoPackage para el mapa.
- Un reporte corto en `docs/reporte_generalizable/`, con el mismo formato IEEE en LaTeX que `docs/reporte_regimenes` (portada, `secciones/`, figuras generadas por script, compilado con xelatex). Si no hay LaTeX, instala `texlive-xetex`, `texlive-lang-spanish`, `texlive-latex-extra`, `texlive-pictures` y `fonts-texgyre` con apt.

## Criterios y advertencias

- **Sé honesto con las cifras.** Si el ambiente no supera la interpolación espacial, dilo: también es un resultado útil.
- El SIAP es una estimación agregada, no una medición de campo. El modelo predice el **promedio municipal**, no el de una parcela.
- No uses las etiquetas del reto para entrenar este modelo; solo para comparar al final.
- Con pocos municipios, una mejora pequeña puede ser azar. Aplica la regla de decisión y reporta la variación entre repeticiones.
- **Pide confirmación al usuario** antes de descargar fuentes nuevas, de cambiar el alcance (por ejemplo, agregar estados) y antes de hacer push. El usuario revisa el reporte antes de subirlo.
- Primer paso sugerido: haz el inventario de datos y dile al usuario qué falta. Después arma la tabla municipio-año con 2023–2025 y las bases. Solo entonces modela.
```

</details>

Con los primeros resultados se pidió una auditoría independiente del código.

> Me gustaría que instancies un modelo Opus para que haga auditoría a todo el código que implementaste, me sorprende
> muchísimo que con tanta data no haya ningún patrón claro.

### 6. Qué explica los regímenes (14 de octubre de 2026)

Resultado: se descartó que el riego explique el régimen A. La mejor explicación es la fuente mixta de las etiquetas,
porque la segunda sesión de preguntas dijo que unos rendimientos los reporta la comercializadora y otros el productor.
FIRA no compartió la fuente de cada parcela, así que la hipótesis queda sin confirmar.

> Ah bueno, sé que no se puede comparar pero el t/ha de el dataset que FIRA nos proporcionó decía que producía
> ~4.5t/ha en Puebla y algunas regiones de Hidalgo, con los datos de temporal esto me apunta que no utilizaron una
> técnica de temporal y abran utilizado otra, habrá alguna manera de investigar cual posiblemente haya sido la más
> cercana a dar tal rendimiento? Si nos fijamos, en el régimen B, si destaca que muy probablemente hayan utilizado la
> técnica de temporal. Pero como podemos saber cual es la que más probablemente utilizaron para el régimen A?
>
> Otra cosa ya se realizó una segunda sesión de preguntas, podrás extraer la información importante para nuestra
> investigación? La que pueda realizar una modificación en nuestro proceso de investigación o modelado?

### 7. Capa de crédito (14 de octubre de 2026)

Resultado: la capa económica por parcela con AgroCostos, el INPC, el precio y el siniestro del SIAP, y el semáforo.

> Necesitamos resolver estos dos issues de github:
>
> [Datos] Precio, costos de AgroCostos, punto de equilibrio y siniestralidad por municipio
>
> [Modelo] Calibración del p10 y marca de confianza por parcela
>
> Como investigamos en los objetivos de FIRA con este hackaton, es para tener una mejor base para hacer préstamos y
> demás, ya que es una institución financiera enfocada al desarrollo rural, entonces, como investigamos, como tal no
> está mal el modelo, pero tenemos que guíarlo a una aplicación financiera, tomando en cuenta el objetivo principal de
> la institución, de ahí nacen ambos issues.
>
> Especificamente honestamente no estoy seguro que es lo que debemos de realizar, pero entiendo que está enfocado para
> que el equipo encargado del desarrollo del dashboard lo utilicen y llegue al analista correctamente. Asi que necesito
> que pienses en todas las consideraciones necearias antes de empezar a implementar nada, y si tienes gaps de
> información investiga al respecto antes.
>
> Puedes dividir el trabajo en agentes sonnet para que trabajen en paralelo, tu trabajo es de orquestrador.

### 8. Observaciones del asesor al reporte final (17 de octubre de 2026)

Resultado: aclaraciones del anexo técnico sobre la asignación del régimen, el rezago, los intervalos, la prueba de
permutación, el error esperado, el bootstrap, la fuga de información, el mapa municipal y la capa de crédito, y la
bibliografía en un archivo aparte.

> El asesor ya realizó las observaciones para el reporte final, dejo los comentarios como un sub apartado en el
> highlight que hizo. También llegaron nuevas indicaciones por parte de FIRA. Primero me gustaría atender las
> observaciones, y luego vemos si necesitamos realizar algo adicional con el correo de FIRA.
