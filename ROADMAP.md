# ROADMAP · Reto AgroCebada FIRA 2026

**Meta:** entregar la Etapa 1 completa el **sábado 18 de octubre de 2026**, un día antes del límite oficial (19 de octubre, 23:59).

**Hoy:** 23 de septiembre de 2026. Quedan 26 días.

Este documento resume qué hay que entregar, qué aprendimos del diagnóstico del dataset, la estrategia técnica, quién hace qué y en qué orden. El detalle de cada tarea vive en los [issues](https://github.com/alan-pv/AgroCebada_Hackaton/issues). **El documento de contexto del equipo es [AgroCebada_contexto.pdf](AgroCebada_contexto.pdf)**: reúne el reto, el cultivo, los datos, el tipo de problema, las observaciones preliminares, las hipótesis y la regla de decisión. Donde haya conflicto, manda ese documento.

---

## 1. Qué hay que entregar (según las bases oficiales)

### Entregables de la Etapa 1

| Entregable | Detalle | Issue |
|---|---|---|
| Predicciones | Rendimiento (t/ha) de las 59 parcelas de PREDICCION. **El formato no está en las bases: confirmarlo en la plataforma.** | [#14](https://github.com/alan-pv/AgroCebada_Hackaton/issues/14) |
| Reporte técnico | Estructura y extensión fijas (tabla abajo), en PDF | [#15](https://github.com/alan-pv/AgroCebada_Hackaton/issues/15) |
| App funcional | Web, dashboard u otra interfaz que **ejecute el modelo** y permita consultar resultados de forma interactiva, con link para el jurado | [#3](https://github.com/alan-pv/AgroCebada_Hackaton/issues/3), [#12](https://github.com/alan-pv/AgroCebada_Hackaton/issues/12) |
| Código fuente | App y modelo, con documentación para ejecutarlos | [#13](https://github.com/alan-pv/AgroCebada_Hackaton/issues/13), [#14](https://github.com/alan-pv/AgroCebada_Hackaton/issues/14) |
| Video | Máximo 5 minutos: funcionamiento del modelo y de la solución | [#16](https://github.com/alan-pv/AgroCebada_Hackaton/issues/16) |
| Uso de IA | Indicar dónde se usó y **anexar los prompts** | [#4](https://github.com/alan-pv/AgroCebada_Hackaton/issues/4) |

### Estructura del reporte técnico

| Sección | Palabras |
|---|---|
| Introducción | 400–550 |
| Justificación | 100–200 |
| Objetivos | 200 |
| Metodología | 600–700 |
| Resultados y discusión | 800 |
| Uso de la ciencia de datos en la inclusión financiera del sector agro | 300 |
| Conclusiones | 400 |
| Bibliografía | — |
| Anexos: actividades y aportaciones de cada integrante | máx. 2 cuartillas |

### Cómo se evalúa

| Etapa | Criterio | Peso |
|---|---|---|
| 1 | Desempeño predictivo (RMSE, MAE, r² u otras) y justificación técnica | 70 % |
| 1 | Aplicación o interfaz web | 30 % |
| 1 | Bonus: responder con justificación las 3 preguntas guía | extra |
| 2 | Presentación de 15 min: dominio, interpretación, relación con inclusión financiera, viabilidad | desempate y lugares |

Las preguntas guía son: ¿qué índice es más importante?, ¿qué variable climática tiene mayor peso? y ¿qué combinación de variables funciona mejor? Se atienden en [#11](https://github.com/alan-pv/AgroCebada_Hackaton/issues/11).

### Calendario oficial

| Fecha | Hito |
|---|---|
| 19 oct 2026, 23:59 | **Fecha límite de entrega** |
| 3 nov 2026 | Notificación de los 3 finalistas |
| 10 nov 2026 | Presentación en línea ante el jurado |
| 20 nov 2026 | III Congreso Nacional de Ciencia de Datos y premiación |

---

## 2. Hallazgos del diagnóstico inicial

Todas las cifras se reproducen con:

```bash
pip install pandas numpy pyshp rasterio
python scripts/diagnostico_inicial.py
```

Varios hallazgos **corrigen supuestos de la investigación previa**. Donde haya conflicto, manda esta sección.

> **Actualización 4 oct.** La primera revisión de los datos ([AgroCebada_contexto.pdf](AgroCebada_contexto.pdf), Sección VI) agrega observaciones preliminares que deben comprobarse de forma independiente (Tabla VII) antes de apoyar decisiones. Las cifras de modelo de esta sección se recalcularán con el esquema de validación oficial ([#2](https://github.com/alan-pv/AgroCebada_Hackaton/issues/2)).

### 2.1 Etiquetas

- **El rendimiento es más alto de lo esperado.** Media 3.96 t/ha, desviación 0.85, rango 2.0–5.6. La investigación previa suponía 1.5–3.5 t/ha con base en promedios estatales del SIAP.
- **El estado explica mucho.** Puebla promedia 4.48 t/ha (71 parcelas), Hidalgo 3.76 (36) y Tlaxcala 2.98 (31).
- **Las etiquetas parecen venir de dos regímenes de medición, separados por municipio y no por estado** (observación preliminar). Régimen A (Chignahuapan, Almoloya, Cuautepec de Hinojosa, Tepeapulco): rendimientos con dos decimales, media 4.49 t/ha. Régimen B (Singuilucan, Emiliano Zapata, Apan, Calpulalpan, Nanacamilpa): redondeados a 0.5 o 0.1, media 3.05 t/ha. Hidalgo tiene municipios de los dos tipos. Solo el redondeo impone ~0.14 t/ha de error irreducible en el régimen B. Ver hipótesis H1 y H2 del documento de contexto, [#19](https://github.com/alan-pv/AgroCebada_Hackaton/issues/19) y [#21](https://github.com/alan-pv/AgroCebada_Hackaton/issues/21).
- **Las parcelas pequeñas tienen los rendimientos más extremos** (observación preliminar): cuatro de los cinco valores de 5.4 t/ha o más son parcelas de menos de 1.5 ha. Ver H2 y H4, [#20](https://github.com/alan-pv/AgroCebada_Hackaton/issues/20).
- El campo `Cultivo` del shapefile dice "Cebada" en Tlaxcala y "CEBADA" en los demás, lo que refuerza la hipótesis de fuentes distintas.

### 2.2 La partición es aleatoria, no espacial

- La distancia mediana al vecino de entrenamiento más cercano es **0.38 km** para entrenamiento y **0.36 km** para predicción. Las 59 parcelas a predecir están intercaladas con las de entrenamiento.
- Todo cae en **9 municipios** de un área de ~42 × 50 km. Chignahuapan concentra 100 parcelas.
- **Consecuencia:** el rendimiento de los vecinos es un predictor legítimo y fuerte, siempre que se calcule dentro de cada fold. La validación cruzada aleatoria imita bien la partición oficial. La espacial sirve para medir cuánto depende el modelo de los vecinos.

### 2.3 El piso real a superar

Baselines con leave-one-out sobre las 138 parcelas de entrenamiento:

| Baseline | RMSE (t/ha) |
|---|---|
| Media global | 0.85 |
| Media por estado | 0.61 |
| Media por municipio | 0.51 |
| Promedio de los 3 vecinos más cercanos | 0.51 |
| Promedio de los 10 vecinos más cercanos | 0.50 |

**Un modelo que no baje de ~0.50 no aporta nada sobre la geografía.** Nuestra meta interna es **RMSE < 0.45** en validación aleatoria repetida.

### 2.4 Satélite

- **Nubosidad casi binaria.** El 86 % (Básico) y el 89 % (PRO) de los registros tienen nubosidad de exactamente 0 o 100. Con 100, los índices vienen nulos.
- **Cobertura suficiente.** Sentinel-2 deja una mediana de 25 observaciones útiles por parcela entre mayo y octubre de 2025, con huecos máximos de 20–28 días entre junio y septiembre. Planet aporta ~243 fechas por parcela en 2025.
- **Hay picos espurios** que desplazan el "máximo" de NDVI a inicios de mayo en varias parcelas de Tlaxcala. Hace falta despiking.
- **El PRO sí trae señal red-edge.** El LAI de Planet es `5.405·NDRE − 0.114`, calculado con la banda b7 red-edge. Se puede recuperar el NDRE exacto. La investigación previa decía lo contrario.
- **El PRO cubre todo 2025** (311 fechas, de enero a diciembre). Si el rango de fechas se calcula comparando el texto `DD/MM/AAAA`, sale por error el 31/08/2025 como máximo.
- **El LAI de Sentinel-2 es redundante:** es una función de SAVI.
- Planet mide NDVI sistemáticamente más alto que Sentinel-2. No se deben mezclar sin armonizar.
- El NDVI máximo de 2025 casi no correlaciona con el rendimiento dentro de cada estado. La señal está en la fenología alineada, la heterogeneidad y la historia de la parcela, no en el verdor bruto.

### 2.5 Clima y topografía

- Las 197 parcelas caen en **26 píxeles CHIRPS**. El clima funciona casi como identificador de zona.
- **Localmente, 2024 fue tan lluvioso como 2025.** La investigación previa suponía 2024 seco a partir de datos nacionales.

| Año | Precipitación junio–octubre (mm, media sobre parcelas) |
|---|---|
| 2022 | 477 |
| 2023 | 410 |
| 2024 | 876 |
| 2025 | 813 |

- **En 2025 lo distintivo fue cuándo llovió:** mayo–junio y septiembre–octubre muy lluviosos, julio–agosto normales y Tmax más fresca que en 2023–2024 (documento de contexto, Tabla VI).
- **El clima entregado es mensual.** Las ventanas relativas a la floración requieren datos diarios.
- **La topografía entregada es de 120 m**, no de 15 m. Una parcela mediana de 5 ha cubre ~3 píxeles. El CEM de 15 m de INEGI es candidato a dato externo.
- CRS: parcelas y clima en EPSG:4326, topografía en EPSG:6372.

---

## 3. Estrategia técnica

```
datos crudos ─► limpieza de series (nubes, despiking, suavizado) ─► tabla de features (197 filas)
                                                                          │
      contexto espacial (estado, municipio, vecinos; dentro del fold) ────┤
                                                                          ▼
                 validación cruzada A (aleatoria) y B (espacial) ─► modelos ─► ensemble + intervalos
                                                                          │
                                   predicciones de 59 parcelas ◄──────────┤
                                   app (mapa, ficha, riesgo)   ◄──────────┤
                                   interpretabilidad y bonus   ◄──────────┘
```

Decisiones clave:

1. **Validación antes que modelos.** Dos esquemas con particiones fijas para todos. El A (aleatorio repetido 5×10) elige modelo. El B (grupos espaciales) se reporta al lado. Todo preprocesamiento va dentro del fold. Una mejora se acepta solo con la regla de decisión del documento de contexto (Sección X): gana en al menos 7 de cada 10 particiones y pasa la prueba de permutación.
2. **Features por bloques**, para poder responder las preguntas guía con ablaciones:
   - contexto espacial: estado, municipio y rezago kNN del rendimiento;
   - fenología 2025 por sensor, alineada al pico de verdor de cada parcela;
   - historia 2022–2024 de la parcela;
   - heterogeneidad intra-parcela;
   - labranza y residuos antes de la siembra;
   - clima en ventanas fenológicas;
   - topografía.
3. **Pocas features y modelos regularizados.** Con 138 filas: Ridge/ElasticNet, PLS, RandomForest, LightGBM poco profundo, Gaussian Process y TabPFN. Nada de deep learning.
4. **Ensemble por promedio** de 3–4 modelos diversos, con intervalos conformal p10–p90. La incertidumbre es lo que le sirve a FIRA para decidir crédito.
5. **La app cuenta una historia de crédito:** probabilidad de rendimiento bajo un umbral e ingreso esperado por parcela. Así se conecta con el criterio de inclusión financiera.

---

## 4. Equipo y responsabilidades

| Integrante | Rol | Es dueño de |
|---|---|---|
| @lm-vicente-j | Datos y features | Carga de datos, limpieza de series, features, datos externos, pipeline reproducible. Redacta la parte de datos de la Metodología. |
| @alan-pv | Modelado y validación | Esquema de validación, baselines, modelos, ensemble, interpretabilidad, predicciones finales. Redacta Resultados y la parte de modelado de la Metodología. |
| @EmmanuelRamiro23 | App y comunicación | App y despliegue, registro de IA, integración del reporte, video y carga de la entrega. Redacta Introducción, Justificación, Objetivos e Inclusión financiera. |

La asignación inicial de roles es una propuesta. Si alguien prefiere otro rol, basta con reasignar los issues.

### Contratos entre roles

Para trabajar en paralelo sin bloquearse, acordamos estos archivos desde el día 1:

| Archivo | Lo produce | Lo consume |
|---|---|---|
| `data/processed/parcelas.parquet` (ID, estado, municipio, lon, lat, área, conjunto, rendimiento) | Datos, en [#1](https://github.com/alan-pv/AgroCebada_Hackaton/issues/1) | Modelo y app |
| `data/processed/series_{sensor}.parquet` | Datos, en [#5](https://github.com/alan-pv/AgroCebada_Hackaton/issues/5) | Features y app |
| `data/processed/features.parquet` (197 filas) | Datos, en [#13](https://github.com/alan-pv/AgroCebada_Hackaton/issues/13) | Modelo |
| `predict(features_df) -> DataFrame[ID_POLIGONO, pred, p10, p90]` | Modelo, en [#14](https://github.com/alan-pv/AgroCebada_Hackaton/issues/14) | App |
| `outputs/predicciones.parquet`, `outputs/importancias.parquet`, `outputs/shap_values.parquet` | Modelo, en [#10](https://github.com/alan-pv/AgroCebada_Hackaton/issues/10) y [#11](https://github.com/alan-pv/AgroCebada_Hackaton/issues/11) | App y reporte |

---

## 5. Plan por fases

### Fase 0 · Setup y diagnóstico (23–26 sep)

| Issue | Tarea | Responsable |
|---|---|---|
| [#1](https://github.com/alan-pv/AgroCebada_Hackaton/issues/1) | Estructura del repo, entorno reproducible y carga de datos | @lm-vicente-j |
| [#2](https://github.com/alan-pv/AgroCebada_Hackaton/issues/2) | Esquema de validación, baselines y registro de experimentos | @alan-pv |
| [#4](https://github.com/alan-pv/AgroCebada_Hackaton/issues/4) | Registro de uso de IA y plantilla del reporte | @EmmanuelRamiro23 |

**Sale cuando:** los tres pueden instalar el entorno, `parcelas.parquet` existe y los baselines están en el registro.

### Fase 1 · Features v1 y primer modelo (27 sep – 3 oct)

| Issue | Tarea | Responsable |
|---|---|---|
| [#5](https://github.com/alan-pv/AgroCebada_Hackaton/issues/5) | Limpieza de nubes y reconstrucción de series | @lm-vicente-j |
| [#6](https://github.com/alan-pv/AgroCebada_Hackaton/issues/6) | Features satelitales | @lm-vicente-j |
| [#7](https://github.com/alan-pv/AgroCebada_Hackaton/issues/7) | Features de clima y topografía | @lm-vicente-j |
| [#8](https://github.com/alan-pv/AgroCebada_Hackaton/issues/8) | Modelos v1 con contexto espacial y ablaciones | @alan-pv |
| [#3](https://github.com/alan-pv/AgroCebada_Hackaton/issues/3) | Esqueleto de la app desplegado con link público | @EmmanuelRamiro23 |

**Sale cuando:** hay un modelo evaluado con la tabla de features v1 y la app está en línea con predicción provisional.

### Fase 2 · Features v2 y modelo candidato (4–10 oct)

| Issue | Tarea | Responsable |
|---|---|---|
| [#9](https://github.com/alan-pv/AgroCebada_Hackaton/issues/9) | Datos públicos externos (máximo 3 días) | @lm-vicente-j |
| [#13](https://github.com/alan-pv/AgroCebada_Hackaton/issues/13) | Pipeline reproducible y **congelamiento de features el 10 de octubre** | @lm-vicente-j |
| [#10](https://github.com/alan-pv/AgroCebada_Hackaton/issues/10) | Ensemble e intervalos de predicción | @alan-pv |
| [#12](https://github.com/alan-pv/AgroCebada_Hackaton/issues/12) | Funcionalidades completas de la app (inicia) | @EmmanuelRamiro23 |

**Sale cuando:** etiqueta `features-v1.0` creada y un modelo candidato con RMSE < 0.45 en el esquema A, o la mejor cifra alcanzada documentada.

### Fase 3 · Integración y congelamiento (11–15 oct)

| Issue | Tarea | Responsable |
|---|---|---|
| [#11](https://github.com/alan-pv/AgroCebada_Hackaton/issues/11) | Interpretabilidad y preguntas guía (bonus) | @alan-pv |
| [#14](https://github.com/alan-pv/AgroCebada_Hackaton/issues/14) | Modelo final y predicciones, **congelado el 14 de octubre** | @alan-pv |
| [#12](https://github.com/alan-pv/AgroCebada_Hackaton/issues/12) | App con el modelo final, **congelada el 15 de octubre** | @EmmanuelRamiro23 |
| [#15](https://github.com/alan-pv/AgroCebada_Hackaton/issues/15) | Borrador completo del reporte el 13 de octubre | los tres |

**Sale cuando:** predicciones finales, app con el modelo final y borrador completo del reporte.

### Fase 4 · Entrega (16–19 oct)

| Issue | Tarea | Responsable |
|---|---|---|
| [#15](https://github.com/alan-pv/AgroCebada_Hackaton/issues/15) | Reporte técnico final en PDF (17 de octubre) | @EmmanuelRamiro23 integra |
| [#16](https://github.com/alan-pv/AgroCebada_Hackaton/issues/16) | Video y **carga a la plataforma el 18 de octubre** | @EmmanuelRamiro23 |

### Etapa 2 · Solo si quedamos finalistas (3–20 nov)

| Issue | Tarea | Responsable |
|---|---|---|
| [#17](https://github.com/alan-pv/AgroCebada_Hackaton/issues/17) | Presentación de 15 min, ensayos y documentación del incentivo | los tres |

### Carga por persona y fase

| Fase | @lm-vicente-j | @alan-pv | @EmmanuelRamiro23 |
|---|---|---|---|
| 0 | Repo, entorno y carga de datos | Validación y baselines | Registro de IA y plantilla del reporte |
| 1 | Series limpias y features | Modelos v1 | App desplegada |
| 2 | Datos externos y pipeline | Ensemble e intervalos | Funcionalidades de la app |
| 3 | Metodología de datos y apoyo a QA | Interpretabilidad, modelo final, Resultados | App final e integración del reporte |
| 4 | Revisión cruzada | Revisión cruzada | Reporte final, video y carga |

---

## 6. Cómo trabajamos

- **Ramas:** `feat/<area>-<descripcion>`, por ejemplo `feat/datos-series`. Nada directo a `main`.
- **Pull requests:** una revisión de otro integrante antes de fusionar. En la descripción del PR, `Closes #n` para cerrar el issue.
- **Estructura:**
  - `src/agrocebada/` para código reutilizable;
  - `notebooks/` para exploración (numerados: `01_...`);
  - `data/processed/` para tablas generadas;
  - `models/` y `outputs/` para artefactos del modelo;
  - `app/` para la aplicación;
  - `docs/` y `reporte/` para documentación.
- **Experimentos:** cada corrida de modelo se anota en `experimentos/registro.csv` con las mismas particiones de validación. Semillas fijas.
- **Uso de IA:** cada prompt relevante se registra el mismo día en `docs/uso_ia.md`. Es obligatorio por las bases.
- **Datos externos:** cada fuente se documenta con URL, fecha de consulta, resolución, procesamiento y cita.
- **Seguimiento:** revisión corta de avance al cierre de cada fase: 26 sep, 3 oct, 10 oct y 15 oct.

---

## 7. Checklist de entrega final

Validación y modelo:

- [ ] El modelo final supera a los baselines espaciales en los esquemas A y B, y se reportan ambos.
- [ ] Todo el preprocesamiento, incluidas las features de vecinos, se ajustó dentro de cada fold.
- [ ] No se mezclaron sensores sin armonizar.
- [ ] Las predicciones son 59, sin nulos, con IDs correctos y dentro del rango plausible (2.0–5.6 t/ha).
- [ ] La distribución de predicciones es comparable con la de entrenamiento y el mapa es espacialmente coherente.
- [ ] Hay intervalos de predicción con cobertura verificada.

Documentación:

- [ ] Las 3 preguntas guía están respondidas con evidencia.
- [ ] El reporte respeta los límites de palabras por sección.
- [ ] Los anexos incluyen las contribuciones de cada integrante y el uso de IA con prompts.
- [ ] Los datos externos están documentados.
- [ ] El código se ejecuta desde cero siguiendo el README.

App y entrega:

- [ ] La app abre desde el link público en una ventana de incógnito y ejecuta el modelo.
- [ ] El video dura menos de 5 minutos.
- [ ] Todo está cargado en la plataforma el 18 de octubre, con captura de la confirmación.

---

## 8. Riesgos y preguntas abiertas

| Riesgo o pregunta | Mitigación | Dueño |
|---|---|---|
| Las bases no especifican el formato de las predicciones | Revisar la plataforma y, si no aparece, escribir al comité esta semana | @alan-pv |
| La sesión de dudas del 18 de septiembre ya pasó | Buscar en la plataforma si publicaron minuta o preguntas frecuentes | @alan-pv |
| Los anexos tienen máximo 2 cuartillas pero deben incluir los prompts | Resumen en el anexo y registro completo enlazado al repo | @EmmanuelRamiro23 |
| El repo es privado y el jurado necesita el link de la app | Verificar el hosting en la primera semana | @EmmanuelRamiro23 |
| Las etiquetas parecen venir de dos regímenes de medición y tienen ruido | Comprobar H1 y H2 ([#19](https://github.com/alan-pv/AgroCebada_Hackaton/issues/19)) y reportar el error por régimen | @alan-pv |
| No se sabe cómo se midió el rendimiento en cada municipio | Consultar al comité ([#21](https://github.com/alan-pv/AgroCebada_Hackaton/issues/21)) | @alan-pv |
| Las observaciones preliminares no están verificadas | Verificación independiente de la Tabla VII del documento de contexto | @lm-vicente-j |
| Con 138 parcelas, las mejoras pequeñas pueden ser azar | Regla de decisión fija antes de probar | @alan-pv |
| Sobreajuste con 138 filas | Límite de ~15–30 features, regularización y validación con particiones fijas | @alan-pv |
| Los datos externos consumen demasiado tiempo | Máximo 3 días. Se integran solo si mejoran la validación | @lm-vicente-j |
| Retraso en features bloquea el modelo | `parcelas.parquet` el día 1 para que el modelo arranque con baselines | @lm-vicente-j |
