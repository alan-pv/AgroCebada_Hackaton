# Diccionario de variables

Esta tabla describe las variables de la tabla de entrenamiento y predicción. Hay una fila por parcela (197). Ninguna variable usa el rendimiento. Los valores que no se pudieron calcular quedan vacíos y el modelo los imputa dentro de cada partición.

Definiciones. El pico de verdor es el día del máximo del NDVI suavizado de Planet entre el 1 de junio y el 31 de octubre de 2025. Las ventanas "pico" se miden en días antes y después de ese día. La curva suavizada es la serie compuesta a pasos de 5 días y suavizada con el método de Whittaker. La amplitud es el máximo menos el mínimo de la temporada. NDRE es el índice de borde rojo que se recupera del LAI de Planet como (LAI + 0.114) / 5.405.

## Variables de identificación

Las columnas de la tabla de parcelas (estado, municipio, régimen, coordenadas, área y conjunto) acompañan a las variables. El rendimiento no se incluye.

## Variables derivadas

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
