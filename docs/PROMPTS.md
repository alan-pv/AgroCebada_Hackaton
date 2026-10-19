# Prompts principales

Las bases del Reto AgroCebada FIRA 2026 permiten usar inteligencia artificial siempre que se indique dónde se usó y se
anexen los prompts. Este archivo reúne los prompts más útiles del proyecto, no todos. El anexo técnico lo cita en su
sección de aportaciones y uso de inteligencia artificial, y resume los prompts en su Tabla IV.

Usamos Claude Code, de Anthropic, para programar, auditar y redactar. Ningún resultado se usó sin revisarlo. Las
cifras de los reportes salen del código del repositorio, no del texto que generó la herramienta.

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

> _Pegar aquí el prompt._

### 3. Plan de validación y regla de decisión (5 de octubre de 2026)

Resultado: validación cruzada repetida, esquema por zonas y la regla de 7 de 10 repeticiones con prueba de
permutación (`src/parcelas/cv.py`).

> _Pegar aquí el prompt._

### 4. Auditoría del código del modelo (7 de octubre de 2026)

Resultado: el relleno del rezago espacial usaba la propia etiqueta. Se corrigió y se repitieron todos los
experimentos.

> _Pegar aquí el prompt._

### 5. Auditoría independiente y modelo municipal (9 de octubre de 2026)

Resultado: el modelo municipal con datos públicos del SIAP de 2003 a 2025.

> _Pegar aquí el prompt._

### 6. Qué explica los regímenes (9 de octubre de 2026)

Resultado: el reporte de los regímenes, que descarta causas ambientales y plantea la hipótesis de fuente mixta.

> _Pegar aquí el prompt._

### 7. Capa de crédito (14 de octubre de 2026)

Resultado: la capa económica por parcela con AgroCostos, el INPC, el precio y el siniestro del SIAP, y el semáforo.

> _Pegar aquí el prompt._

### 8. Observaciones del asesor al reporte final (17 de octubre de 2026)

Resultado: aclaraciones del anexo técnico sobre la asignación del régimen, el rezago, los intervalos, la prueba de
permutación, el error esperado, el bootstrap, la fuga de información, el mapa municipal y la capa de crédito, y la
bibliografía en un archivo aparte.

> El asesor ya realizó las observaciones para el reporte final, dejo los comentarios como un sub apartado en el
> highlight que hizo. También llegaron nuevas indicaciones por parte de FIRA. Primero me gustaría atender las
> observaciones, y luego vemos si necesitamos realizar algo adicional con el correo de FIRA.
