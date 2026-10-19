# Datos

Este documento describe los datos del proyecto, qué significa la etiqueta de rendimiento según las aclaraciones de FIRA y qué variables se construyeron. Las cifras del modelo están en `MODELO.md`.

## Datos del reto

Los archivos que entregó FIRA están en `data/reto/` sin cambios.

| Archivo | Contenido |
|---|---|
| `ID_area_rendimiento_70_30_Reto_AgroCebada.csv` | ID, área, rendimiento y conjunto de las 197 parcelas |
| `Parcelas_Reto_AGC_CONJUNTO_70_30.zip` | Polígonos de las parcelas (EPSG:4326) |
| `Conjunto_datos_BASICO_AgroCebada2026.csv` | Series de Sentinel-2 y Landsat de 2022 a 2025 |
| `Conjunto_datos_PRO_AgroCebada.csv` | Series de Planet de 2025 |
| `Reto_AgroCebada_CHIRPS_Precipitacion_2022_2025.zip` | Lluvia mensual CHIRPS, celdas de 0.05 grados |
| `Reto_AgroCebada_Temperatura_2022_2025_RECORTADA_CHIRPS.zip` | Temperatura máxima y mínima mensual CHIRTS-ERA5 |
| `Reto_AgroCebada_Topografia_INEGI_CEM4.zip` | Elevación de INEGI de 120 m (EPSG:6372) y pendiente |
| `.docx` y `.pdf` | Descripción de variables, diccionario y ecuaciones de los índices |

Son 197 parcelas de Puebla, Hidalgo y Tlaxcala. Las 138 de ENTRENAMIENTO traen el rendimiento de la temporada 2025 y las 59 de PREDICCION no lo traen. FIRA hizo la división 70/30 con muestreo aleatorio estratificado, así que las 59 están repartidas entre las mismas zonas que las 138.

## Qué es la etiqueta

FIRA aclaró lo siguiente en las dos sesiones de preguntas y por correo.

* El rendimiento es grano cosechado en toneladas por hectárea. Viene de pesaje en báscula e incluye todo lo que se recolectó en la parcela. No se ajustó por humedad, impurezas ni mermas.
* La mayoría de los valores los reportó la comercializadora que compró el grano y una parte menor el productor. FIRA no dirá qué parcela viene de cada fuente y pide tratar todos los registros como una misma variable objetivo.
* `AREA_HA` es la superficie del polígono, con el mismo criterio en las 197 parcelas.
* La evaluación usa sobre todo RMSE, MAE y R² sobre las 59 parcelas, sin ponderar por superficie, además de la robustez de la metodología. Valorarán que el error se explique en términos productivos.
* No hay fecha de corte obligatoria para los datos. Si una herramienta se propone para usarse antes de la cosecha, hay que decir en qué momento del ciclo predice y con qué información.
* No habrá parcelas de otras campañas en la evaluación oficial.
* No respondieron cuál es la variedad de cebada ni las fechas reales de siembra.

## Los dos regímenes de registro

Cada municipio registra el rendimiento de una sola forma. En el régimen A (Chignahuapan, Almoloya, Cuautepec de Hinojosa y Tepeapulco) los valores tienen dos decimales y promedian 4.49 t/ha. En el régimen B (Singuilucan, Emiliano Zapata, Apan, Calpulalpan y Nanacamilpa) están redondeados a 0.5 o a 0.1 y promedian 3.05 t/ha. En el entrenamiento hay 87 parcelas del A y 51 del B, y en las 59 hay 37 y 22. Singuilucan, del régimen B, queda a 9 km de parcelas del A, y ninguna variable de clima, altitud, suelo o calendario explica la diferencia. El SIAP no muestra la brecha entre esos municipios. La fuente mixta es una posible explicación que FIRA no confirma. El análisis completo está en `docs/reportes/REGIMENES.pdf`.

El régimen se asigna por municipio con una regla fija (`REGIMEN_POR_MUNICIPIO` en `src/parcelas/config.py`), así que se conoce para cualquier parcela de esos nueve municipios sin usar su rendimiento.

## Tablas procesadas

| Archivo en `data/processed/` | Contenido |
|---|---|
| `parcelas.parquet` y `parcelas.gpkg` | Una fila por parcela con estado, municipio, régimen, centroide en metros, área, conjunto y rendimiento |
| `features.parquet` | Tabla de variables de las 197 parcelas. Es la unión de `features_sat.parquet` y `features_env.parquet` |
| `calidad_series.parquet` | Observaciones válidas por parcela y sensor |
| `serie_ficha.parquet` | Serie suavizada de NDVI y NDDI de Sentinel-2 que muestra la ficha de la app |
| `generalizable/` | Tablas del modelo municipal (municipios, clima anual y zonas agrícolas) |

Las series suavizadas completas (`series_*.parquet`) y los rásteres descomprimidos de `data/interim/` no se versionan. Se regeneran con `uv run python -m parcelas.build_features`.

## Datos públicos externos

Están en `data/externos/`. Los usa el modelo municipal, el análisis de regímenes y la capa de crédito. El modelo de parcelas no los usa. Se consultaron entre el 9 y el 15 de octubre de 2026.

| Carpeta | Fuente | Script |
|---|---|---|
| `siap/` | SIAP, cierre de la producción agrícola por municipio, cebada grano de temporal, primavera-verano, 2003 a 2025, y asignación de municipios a Distritos de Desarrollo Rural. https://nube.agricultura.gob.mx/cierre_agricola/ | `siap.py` y `ddr.py` |
| `clima/` | Climate Hazards Center, lluvia CHIRPS v2.0 y temperatura CHIRTS-ERA5 mensuales. https://data.chc.ucsb.edu/ | `clima.py` |
| `topografia/` | Copernicus DEM GLO-90, elevación y pendiente. https://copernicus-dem-90m.s3.amazonaws.com/ | `topografia.py` |
| `inegi_marcogeo/` | INEGI, Marco Geoestadístico 2025, municipios de Hidalgo, México, Puebla y Tlaxcala | `inegi.py` |
| `inegi_edafologia/` | INEGI, edafología 1:250 000, Series I y II por hoja | `inegi.py` |
| `inegi_usv/` | INEGI, uso de suelo y vegetación Serie VII, polígonos agrícolas | `inegi.py` |
| `fira_agrocostos/` | FIRA AgroCostos, paquete de cebada de temporal, ciclo primavera-verano 2022, el más reciente público. https://www.fira.gob.mx/Nd/Agrocostos.jsp | `credito.py` |
| `inegi_inpc/` | INEGI, INPC general para llevar los costos a pesos de 2025 (factor 1.147) | `credito.py` |
| `economia_municipal.csv` | Tabla económica por municipio del reto (precio, costos, puntos de equilibrio, siniestralidad) | `credito.py` |

Los scripts de descarga están en `scripts/descargas/` y los de la capa de crédito en `scripts/parcelas/`. Las descargas crudas del INEGI se guardan fuera del repositorio con `uv run python scripts/descargas/inegi.py --descargas <directorio>`.

Datos que no existen para estas parcelas y que limitan cualquier modelo son la variedad, la fecha real de siembra, la rotación, la dosis de siembra y los siniestros de 2025. La siembra típica en la zona va del 1 al 15 de mayo al 15 de junio.

## Diccionario de variables

La tabla `features.parquet` tiene una fila por parcela. Ninguna variable usa el rendimiento. Los valores que no se pudieron calcular quedan vacíos y el modelo los imputa dentro de cada partición.

El pico de verdor es el día del máximo del NDVI suavizado de Planet entre el 1 de junio y el 31 de octubre de 2025. Las ventanas "pico" se miden en días antes y después de ese día. La curva suavizada es la serie compuesta a pasos de 5 días y suavizada con el método de Whittaker. La amplitud es el máximo menos el mínimo de la temporada. NDRE es el índice de borde rojo que se recupera del LAI de Planet como (LAI + 0.114) / 5.405. El modelo final no usa ninguna de estas variables (ver `MODELO.md`).

| Nombre | Bloque | Sensor o fuente | Descripción | Unidades | Ventana temporal |
|---|---|---|---|---|---|
| sat25_planet_ndvi_max | Fenología 2025 | Planet | Máximo de la curva suavizada de NDVI | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_planet_ndvi_auc_temp | Fenología 2025 | Planet | Área bajo la curva de toda la temporada de NDVI | índice por día | 1 de mayo a 30 de noviembre de 2025 |
| sat25_planet_ndvi_auc_pre | Fenología 2025 | Planet | Área bajo la curva de 30 a 10 días antes del pico de verdor de NDVI | índice por día | pico -30 a -10 días |
| sat25_planet_ndvi_auc_pico | Fenología 2025 | Planet | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de NDVI | índice por día | pico -10 a +10 días |
| sat25_planet_ndvi_auc_post | Fenología 2025 | Planet | Área bajo la curva de 10 a 40 días después del pico de verdor de NDVI | índice por día | pico +10 a +40 días |
| sat25_planet_ndvi_pend_verdeo | Fenología 2025 | Planet | Pendiente media entre el inicio de temporada y el máximo de NDVI | índice por día | inicio de temporada al máximo |
| sat25_planet_ndvi_pend_senesc | Fenología 2025 | Planet | Pendiente media entre el máximo y el fin de temporada (negativa) de NDVI | índice por día | máximo al fin de temporada |
| sat25_planet_ndvi_eos | Fenología 2025 | Planet | Fin de temporada, cruce del 50 % de la amplitud tras el máximo de NDVI | día del año | 1 de abril a 30 de noviembre de 2025 |
| sat25_planet_ndvi_duracion | Fenología 2025 | Planet | Días entre el inicio y el fin de temporada de NDVI | días | 1 de abril a 30 de noviembre de 2025 |
| sat25_planet_ndvi_amplitud | Fenología 2025 | Planet | Máximo menos el mínimo de la temporada de NDVI | unidad del índice | 1 de abril a 30 de noviembre de 2025 |
| sat25_planet_ndre_max | Fenología 2025 | Planet | Máximo de la curva suavizada de NDRE | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_planet_ndre_doy_max | Fenología 2025 | Planet | Día del año del máximo de NDRE | día del año | 1 de junio a 31 de octubre de 2025 |
| sat25_planet_ndre_auc_temp | Fenología 2025 | Planet | Área bajo la curva de toda la temporada de NDRE | índice por día | 1 de mayo a 30 de noviembre de 2025 |
| sat25_planet_ndre_auc_pre | Fenología 2025 | Planet | Área bajo la curva de 30 a 10 días antes del pico de verdor de NDRE | índice por día | pico -30 a -10 días |
| sat25_planet_ndre_auc_pico | Fenología 2025 | Planet | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de NDRE | índice por día | pico -10 a +10 días |
| sat25_planet_ndre_auc_post | Fenología 2025 | Planet | Área bajo la curva de 10 a 40 días después del pico de verdor de NDRE | índice por día | pico +10 a +40 días |
| sat25_planet_ndre_pend_verdeo | Fenología 2025 | Planet | Pendiente media entre el inicio de temporada y el máximo de NDRE | índice por día | inicio de temporada al máximo |
| sat25_planet_ndre_pend_senesc | Fenología 2025 | Planet | Pendiente media entre el máximo y el fin de temporada (negativa) de NDRE | índice por día | máximo al fin de temporada |
| sat25_planet_ndre_sos | Fenología 2025 | Planet | Inicio de temporada, cruce del 20 % de la amplitud de NDRE | día del año | 1 de abril a 30 de noviembre de 2025 |
| sat25_planet_ndre_eos | Fenología 2025 | Planet | Fin de temporada, cruce del 50 % de la amplitud tras el máximo de NDRE | día del año | 1 de abril a 30 de noviembre de 2025 |
| sat25_planet_ndre_duracion | Fenología 2025 | Planet | Días entre el inicio y el fin de temporada de NDRE | días | 1 de abril a 30 de noviembre de 2025 |
| sat25_planet_ndre_amplitud | Fenología 2025 | Planet | Máximo menos el mínimo de la temporada de NDRE | unidad del índice | 1 de abril a 30 de noviembre de 2025 |
| sat25_planet_evi_max | Fenología 2025 | Planet | Máximo de la curva suavizada de EVI | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_planet_evi_auc_pico | Fenología 2025 | Planet | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de EVI | índice por día | pico -10 a +10 días |
| sat25_planet_evi_pend_senesc | Fenología 2025 | Planet | Pendiente media entre el máximo y el fin de temporada (negativa) de EVI | índice por día | máximo al fin de temporada |
| sat25_planet_msavi_max | Fenología 2025 | Planet | Máximo de la curva suavizada de MSAVI | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_planet_msavi_auc_pico | Fenología 2025 | Planet | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de MSAVI | índice por día | pico -10 a +10 días |
| sat25_planet_msavi_pend_senesc | Fenología 2025 | Planet | Pendiente media entre el máximo y el fin de temporada (negativa) de MSAVI | índice por día | máximo al fin de temporada |
| sat25_s2_ndvi_max | Fenología 2025 | Sentinel-2 | Máximo de la curva suavizada de NDVI | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_s2_ndvi_auc_pico | Fenología 2025 | Sentinel-2 | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de NDVI | índice por día | pico -10 a +10 días |
| sat25_s2_ndvi_pend_senesc | Fenología 2025 | Sentinel-2 | Pendiente media entre el máximo y el fin de temporada (negativa) de NDVI | índice por día | máximo al fin de temporada |
| sat25_s2_evi_max | Fenología 2025 | Sentinel-2 | Máximo de la curva suavizada de EVI | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_s2_evi_auc_pico | Fenología 2025 | Sentinel-2 | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de EVI | índice por día | pico -10 a +10 días |
| sat25_s2_evi_pend_senesc | Fenología 2025 | Sentinel-2 | Pendiente media entre el máximo y el fin de temporada (negativa) de EVI | índice por día | máximo al fin de temporada |
| sat25_s2_savi_max | Fenología 2025 | Sentinel-2 | Máximo de la curva suavizada de SAVI | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_s2_savi_auc_pico | Fenología 2025 | Sentinel-2 | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de SAVI | índice por día | pico -10 a +10 días |
| sat25_s2_savi_pend_senesc | Fenología 2025 | Sentinel-2 | Pendiente media entre el máximo y el fin de temporada (negativa) de SAVI | índice por día | máximo al fin de temporada |
| sat25_s2_fapar_max | Fenología 2025 | Sentinel-2 | Máximo de la curva suavizada de FAPAR | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_s2_fapar_auc_pico | Fenología 2025 | Sentinel-2 | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de FAPAR | índice por día | pico -10 a +10 días |
| sat25_s2_fapar_pend_senesc | Fenología 2025 | Sentinel-2 | Pendiente media entre el máximo y el fin de temporada (negativa) de FAPAR | índice por día | máximo al fin de temporada |
| sat25_s2_ndwi_max | Fenología 2025 | Sentinel-2 | Máximo de la curva suavizada de NDWI | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_s2_ndwi_auc_pico | Fenología 2025 | Sentinel-2 | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de NDWI | índice por día | pico -10 a +10 días |
| sat25_s2_ndwi_pend_senesc | Fenología 2025 | Sentinel-2 | Pendiente media entre el máximo y el fin de temporada (negativa) de NDWI | índice por día | máximo al fin de temporada |
| sat25_s2_dswi4_max | Fenología 2025 | Sentinel-2 | Máximo de la curva suavizada de DSWI4 | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_s2_dswi4_auc_pico | Fenología 2025 | Sentinel-2 | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de DSWI4 | índice por día | pico -10 a +10 días |
| sat25_s2_dswi4_pend_senesc | Fenología 2025 | Sentinel-2 | Pendiente media entre el máximo y el fin de temporada (negativa) de DSWI4 | índice por día | máximo al fin de temporada |
| sat25_s2_dswi5_max | Fenología 2025 | Sentinel-2 | Máximo de la curva suavizada de DSWI5 | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_s2_dswi5_auc_pico | Fenología 2025 | Sentinel-2 | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de DSWI5 | índice por día | pico -10 a +10 días |
| sat25_s2_dswi5_pend_senesc | Fenología 2025 | Sentinel-2 | Pendiente media entre el máximo y el fin de temporada (negativa) de DSWI5 | índice por día | máximo al fin de temporada |
| sat25_s2_nddi_max | Fenología 2025 | Sentinel-2 | Máximo de la curva suavizada de NDDI | unidad del índice | 1 de junio a 31 de octubre de 2025 |
| sat25_s2_nddi_auc_pico | Fenología 2025 | Sentinel-2 | Área bajo la curva de 10 días antes a 10 días después del pico de verdor de NDDI | índice por día | pico -10 a +10 días |
| sat25_s2_nddi_pend_senesc | Fenología 2025 | Sentinel-2 | Pendiente media entre el máximo y el fin de temporada (negativa) de NDDI | índice por día | máximo al fin de temporada |
| fen_pico_doy | Fenología | Planet | Día del año del pico de verdor (máximo del NDVI suavizado de Planet) | día del año | 1 de junio a 31 de octubre de 2025 |
| fen_sos_doy | Fenología | Planet | Día del año del inicio de temporada del NDVI de Planet, usado como siembra aproximada | día del año | 1 de abril a 30 de noviembre de 2025 |
| fen_dias_sos_pico | Fenología | Planet | Días del inicio de temporada al pico de verdor | días | 2025 |
| hist_s2_ndvi_max_media | Historia | Sentinel-2 | Media del máximo anual de NDVI | NDVI | 2022 a 2024, 1 de junio a 31 de octubre |
| hist_s2_ndvi_max_std | Historia | Sentinel-2 | Desviación estándar entre años del máximo anual de NDVI | NDVI | 2022 a 2024 |
| hist_s2_ndvi_auc_media | Historia | Sentinel-2 | Media del área bajo la curva de NDVI de mayo a noviembre | NDVI por día | 2022 a 2024 |
| hist_s2_ndvi_anom_max | Historia | Sentinel-2 | Máximo de NDVI de 2025 menos su media de 2022 a 2024 | NDVI | 2025 contra 2022 a 2024 |
| hist_s2_ndvi_anom_auc | Historia | Sentinel-2 | Área de NDVI de 2025 menos su media de 2022 a 2024 | NDVI por día | 2025 contra 2022 a 2024 |
| het_planet_ndvi_std_media | Heterogeneidad | Planet | Media de la desviación estándar de NDVI dentro de la parcela | NDVI | pico -10 a +10 días |
| het_planet_ndvi_cv | Heterogeneidad | Planet | Media del coeficiente de variación (desviación estándar entre promedio) de NDVI dentro de la parcela | adimensional | pico -10 a +10 días |
| het_s2_ndvi_std_media | Heterogeneidad | Sentinel-2 | Media de la desviación estándar de NDVI dentro de la parcela | NDVI | pico -10 a +10 días |
| het_s2_ndvi_cv | Heterogeneidad | Sentinel-2 | Media del coeficiente de variación (desviación estándar entre promedio) de NDVI dentro de la parcela | adimensional | pico -10 a +10 días |
| lab_s2_ndti_media | Labranza y residuos | Sentinel-2 | Media de NDTI suavizado antes de la siembra | unidad del índice | 1 de abril a 31 de mayo de 2025 |
| lab_s2_crc_media | Labranza y residuos | Sentinel-2 | Media de CRC suavizado antes de la siembra | unidad del índice | 1 de abril a 31 de mayo de 2025 |
| lab_s2_mcrc_media | Labranza y residuos | Sentinel-2 | Media de MCRC suavizado antes de la siembra | unidad del índice | 1 de abril a 31 de mayo de 2025 |
| lab_s2_ndsvi_media | Labranza y residuos | Sentinel-2 | Media de NDSVI suavizado antes de la siembra | unidad del índice | 1 de abril a 31 de mayo de 2025 |
| tsup_landsat_vi6t_pico | Temperatura de superficie | Landsat | Media del VI6T suavizado, tratado como temperatura de superficie | adimensional, más negativo es más cálido | pico -10 a +10 días |
| tsup_landsat_vi6t_temporada | Temperatura de superficie | Landsat | Media del VI6T suavizado, tratado como temperatura de superficie | adimensional, más negativo es más cálido | 1 de junio a 31 de octubre de 2025 |
| clima_prec_total_may_oct | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia total | mm | mayo a octubre de 2025 |
| clima_prec_siembra | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia del bimestre de siembra | mm | mayo y junio de 2025 |
| clima_prec_crecimiento | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia del bimestre de crecimiento | mm | julio y agosto de 2025 |
| clima_prec_cosecha | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia del bimestre de cosecha | mm | septiembre y octubre de 2025 |
| clima_tmax_media_may_sep | Clima | CHIRPS y CHIRTS-ERA5 | Media de la temperatura máxima mensual | °C | mayo a septiembre de 2025 |
| clima_tmin_media_may_sep | Clima | CHIRPS y CHIRTS-ERA5 | Media de la temperatura mínima mensual | °C | mayo a septiembre de 2025 |
| clima_amplitud_termica | Clima | CHIRPS y CHIRTS-ERA5 | Temperatura máxima media menos mínima media | °C | mayo a septiembre de 2025 |
| clima_gdd0_may_sep | Clima | CHIRPS y CHIRTS-ERA5 | Grados-día con base 0 °C, aproximados con la temperatura media mensual por los días del mes | °C por día | mayo a septiembre de 2025 |
| clima_meses_tmax_sobre_umbral | Clima | CHIRPS y CHIRTS-ERA5 | Número de meses con temperatura máxima media sobre 23 °C | meses | mayo a septiembre de 2025 |
| clima_anom_prec_total_may_oct | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia total de 2025 menos su media de 2022 a 2024 | mm | mayo a octubre |
| clima_anom_prec_siembra | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia de siembra de 2025 menos su media de 2022 a 2024 | mm | mayo y junio |
| clima_anom_prec_crecimiento | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia de crecimiento de 2025 menos su media de 2022 a 2024 | mm | julio y agosto |
| clima_anom_prec_cosecha | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia de cosecha de 2025 menos su media de 2022 a 2024 | mm | septiembre y octubre |
| clima_anom_tmax_media_may_sep | Clima | CHIRPS y CHIRTS-ERA5 | Temperatura máxima media de 2025 menos su media de 2022 a 2024 | °C | mayo a septiembre |
| clima_anom_tmin_media_may_sep | Clima | CHIRPS y CHIRTS-ERA5 | Temperatura mínima media de 2025 menos su media de 2022 a 2024 | °C | mayo a septiembre |
| clima_prec_mes_pico | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia del mes que contiene al pico de verdor de la parcela | mm | mes del pico en 2025 |
| clima_prec_mes_previo | Clima | CHIRPS y CHIRTS-ERA5 | Lluvia del mes anterior al del pico de verdor | mm | mes previo al pico en 2025 |
| topo_elevacion | Topografía | INEGI CEM | Elevación media de la parcela | m sobre el nivel del mar | estática |
| topo_pendiente | Topografía | INEGI CEM | Pendiente media de la parcela | grados | estática |
| topo_aspecto_seno | Topografía | INEGI CEM | Seno del aspecto, dirección de la bajada medida desde el norte hacia el este | adimensional | estática |
| topo_aspecto_coseno | Topografía | INEGI CEM | Coseno del aspecto, componente norte de la bajada | adimensional | estática |
| topo_tpi | Topografía | INEGI CEM | Elevación de la parcela menos la media de un anillo de 500 a 1000 m alrededor | m | estática |
