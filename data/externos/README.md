# Datos externos

Datos públicos que se usaron en el análisis de los regímenes de etiquetas (`docs/reporte_regimenes`). El modelo de la entrega no los usa. Se consultaron el 9 de octubre de 2026.

## SIAP, cierre de la producción agrícola por municipio

- Fuente: Servicio de Información Agroalimentaria y Pesquera (SIAP), consulta de cierre agrícola, https://nube.agricultura.gob.mx/cierre_agricola/
- Filtros: reporte por ubicación geográfica, por municipio; ciclo primavera-verano; modalidad temporal; cultivo cebada grano; entidades Hidalgo, Puebla y Tlaxcala; años 2023, 2024 y 2025.
- Archivos: `siap/<estado>_<año>.xls`, uno por estado y año. Aunque la extensión es `.xls`, son tablas HTML tal como las exporta el portal. Columnas: municipio, superficie sembrada, cosechada y siniestrada (ha), producción (t), rendimiento (t/ha), precio medio rural y valor de la producción.
- El portal ofrece además los filtros de variedad y tipo de tecnología, pero para la cebada de temporal la variedad es "sin clasificar" y la tecnología distingue solo entre cielo abierto e invernadero, así que no aportan información.

## SIAP, asignación de municipios a Distritos de Desarrollo Rural

- Fuente: el mismo portal de cierre agrícola, reporte "Por Distrito - Municipio" (`opcionDDRMpio = 3`), con los filtros de cebada grano, temporal y primavera-verano.
- Periodo: 2003 a 2025, los cuatro estados, un reporte por estado y año.
- Archivo: `siap/ddr_municipio.csv`, columnas `anio`, `estado`, `ddr` y `municipio`. Solo trae los municipios que sembraron cebada ese año.
- Ningún municipio cambia de distrito entre años. Son 19 distritos (4 en Hidalgo, 6 en México, 6 en Puebla y 3 en Tlaxcala).
- Por qué: el SIAP estima muchas veces por distrito o por CADER y repite la cifra en municipios vecinos. El distrito sirve de grupo de validación para que esa repetición no favorezca al interpolador.
- Fecha de consulta: 9 de octubre de 2026. Se reproduce con `uv run --with requests python scripts/descargar_siap_ddr.py`.

## INEGI, conjunto de datos vectorial edafológico 1:250 000

- Fuente: Instituto Nacional de Estadística y Geografía (INEGI), https://www.inegi.org.mx/temas/edafologia/
- Hoja E14-2, Ciudad de México, que cubre las 197 parcelas.
- `inegi_edafologia/serie2/`: Serie II (clasificación WRB). Columnas principales: `CLAVE_WRB` (unidad de suelo), `GRUPO1` a `GRUPO3` (grupos de suelo en orden de dominancia), `CLASE_TEXT` (clase textural) y `FRUDICA` (fase física).
- `inegi_edafologia/serie1/`: Serie I (clasificación FAO). Columnas principales: `NOM_SUE1` (suelo dominante) y `FAS_FISCA` (fase física, por ejemplo dúrica, que corresponde al tepetate).
- Proyección: UTM zona 14 norte, datum ITRF92, según los archivos de metadatos `*_aux.txt`. Los `.shp` no traen `.prj`; se leen como EPSG:32614, que difiere de ITRF92 en menos de un metro.

## Copernicus DEM GLO-90, elevación y pendiente

- Fuente: Copernicus DEM GLO-90 de la Agencia Espacial Europea, distribuido como teselas COG de 1° en el bucket público de AWS, https://copernicus-dem-90m.s3.amazonaws.com/ (por ejemplo `Copernicus_DSM_COG_30_N19_00_W099_00_DEM/Copernicus_DSM_COG_30_N19_00_W099_00_DEM.tif`). No pide autenticación.
- Versión: la publicada en el bucket a la fecha de consulta (GLO-90, 3 segundos de arco, alturas sobre el geoide EGM2008). Es un modelo de superficie, así que incluye edificios y vegetación.
- Fecha de consulta: 9 de octubre de 2026.
- Por qué: el CEM del INEGI que entregó el reto (120 m, EPSG:6372) no cubre el Estado de México al oeste de -99.95. Copernicus cubre los cuatro estados.
- Cobertura: ventana de longitud -100.75 a -96.60 y latitud 17.75 a 21.45 (Hidalgo, Estado de México, Puebla y Tlaxcala). Se usaron 24 teselas de N17 a N21 y de W101 a W097. La tesela N21 W097 no existe porque es mar, así que la esquina noreste queda sin dato (1.2 % de las celdas).
- Procesamiento: se arma el mosaico en EPSG:4326, se reproyecta a EPSG:6372 a 90 m con interpolación bilineal y ahí se calcula la pendiente en grados con el método de Horn (3 x 3), para que las distancias estén en metros. Después se agrega a una rejilla EPSG:4326 de 0.0025° (unos 275 m) alineada a múltiplos de 0.0025. La elevación es la media de los píxeles nativos de cada celda y la pendiente es la media de los píxeles de 90 m que caen en ella.
- Archivos: `topografia/elevacion_m.tif` (m) y `topografia/pendiente_grados.tif` (grados). Float32, compresión deflate, nodata -9999, 1480 filas por 1660 columnas.
- Comparación contra el CEM del reto (`topografia/comparacion_reto.csv`): ambos se agregan a la misma rejilla de 0.0025° en la ventana común (unas 820 mil celdas). La elevación tiene correlación de 0.9995 y Copernicus queda 2.9 m arriba en promedio (RMSE de 22.6 m). La pendiente tiene correlación de 0.958 y un sesgo de 0.1° (RMSE de 2.6°, media de 10.3° contra 10.2°). Si la pendiente de Copernicus se calcula a 120 m sobre la malla del reto, la correlación queda igual (0.958) y el sesgo pasa a -0.6°, así que la diferencia de resolución mueve un poco el nivel pero no el patrón.
- Se reproduce con `uv run python scripts/descargar_topografia.py --crudos <directorio>`. Las teselas crudas no se versionan.

## CHC, clima mensual CHIRPS v2.0 y CHIRTS-ERA5

- Fuente: Climate Hazards Center (CHC) de la Universidad de California en Santa Bárbara. Lluvia de CHIRPS v2.0 mensual global, https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/cogs/ . Temperatura de CHIRTS-ERA5 mensual global, https://data.chc.ucsb.edu/experimental/CHIRTS-ERA5/tmax/tifs/monthly/ y https://data.chc.ucsb.edu/experimental/CHIRTS-ERA5/tmin/tifs/monthly/ . Son las mismas fuentes de los rásteres de clima del reto.
- Periodo: enero de 2003 a diciembre de 2025, los 12 meses de cada año. CHIRPS v2.0 y CHIRTS-ERA5 cubren de 1981 y 1980 a la fecha, así que no hay huecos.
- Ventana: longitud -100.75 a -96.60 y latitud 17.75 a 21.45, 83 columnas por 74 filas de 0.05°. Es la rejilla nativa de ambas fuentes y la misma de los rásteres del reto, que caen dentro con un desfase de 16 columnas y 1 fila. Se amplió hacia el oeste para cubrir el Estado de México.
- Archivos: `clima/prec/PREC_AAAA.tif` (lluvia acumulada en mm/mes), `clima/tmax/TMAX_AAAA.tif` y `clima/tmin/TMIN_AAAA.tif` (promedio mensual de la temperatura máxima y mínima diaria en °C). Un archivo por año con 12 bandas de enero a diciembre, y la descripción de cada banda es el nombre del mes. EPSG:4326, float32, nodata -9999, compresión deflate. La esquina noreste es mar y queda sin dato (unas 270 de 6142 celdas).
- Cálculo de los mensuales: no se calculó nada. Se usaron los productos mensuales que publica el CHC tal cual. El mensual de CHIRPS v2.0 equivale a la suma de los diarios y el de CHIRTS-ERA5 es el promedio de los valores diarios del mes. Los archivos globales no se bajan completos. Se lee por HTTP solo la ventana de interés y se copia sin remuestreo.
- Versión de CHIRPS: también existe CHIRPS v3.0 (https://data.chc.ucsb.edu/products/CHIRPS/v3.0/), pero no coincide con el reto, así que se usó la v2.0.
- Comparación contra los rásteres del reto (`clima/comparacion_reto.csv`): celda por celda en la ventana común, de 2022 a 2025, por variable y mes. Tmax y Tmin de CHIRTS-ERA5 son idénticas al reto en los 48 meses (correlación de 1 y diferencia máxima de 0). La lluvia de CHIRPS v2.0 coincide en 45 de los 48 meses. En ellos la correlación mínima es 0.978 y la diferencia máxima por celda es de 5 mm, siempre con el mensual del CHC un poco arriba de la suma de diarios del reto (sesgo medio de 0.2 mm). Los otros tres meses difieren mucho: octubre de 2022 (correlación de 0.68, el reto tiene 27.5 mm más en promedio), abril de 2023 (0.81, el reto tiene 11.2 mm menos) y mayo de 2023 (0.66, el reto tiene 13.5 mm más). Se revisó sumando los diarios de CHIRPS v2.0 que hoy publica el CHC y esa suma coincide con el mensual, no con el reto. Así que la diferencia viene de los diarios que usó el reto y no de la forma de agregar. CHIRPS v3.0 queda mucho más lejos en todos los meses (correlación de 0.50 a 0.93, error absoluto medio de 21.7 mm).
- Fecha de consulta: 9 de octubre de 2026.
- Se reproduce con `uv run python scripts/descargar_clima.py --descargas <directorio>`. Los recortes por mes se guardan en ese directorio y no se versionan.

## INEGI, Marco Geoestadístico 2025, municipios

- Fuente: INEGI, Marco Geoestadístico 2025 (UPC 794551163061), ficha en https://www.inegi.org.mx/app/biblioteca/ficha.html?upc=794551163061
- Descarga: https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/794551163061/mg_2025_integrado.zip (Marco Geoestadístico Integrado 2025, 245 MB). Es la versión más reciente publicada. Su corte es la actualización cartográfica de julio de 2025.
- Fecha de consulta: 9 de octubre de 2026.
- Capa usada: `conjunto_de_datos/00mun.shp` (áreas geoestadísticas municipales, codificación ISO 8859-1).
- Filtro: claves de entidad 13 (Hidalgo), 15 (México), 21 (Puebla) y 29 (Tlaxcala). Quedan 84, 125, 217 y 60 municipios, 486 en total.
- Archivo: `inegi_marcogeo/municipios_13_15_21_29.gpkg`, capa `municipios`. Columnas `CVEGEO` (clave de 5 dígitos), `CVE_ENT`, `CVE_MUN`, `NOMGEO` (nombre del municipio en UTF-8) y `estado`.
- Proyección: EPSG:6372, la misma del original (Cónica Conforme de Lambert, ITRF2008). Pesa 12.8 MB, así que no se simplificó.

## INEGI, edafología 1:250 000 de los cuatro estados

- Fuente: INEGI. Serie II, "Conjunto de Datos Vectorial Edafológico. Escala 1:250 000 Serie II Continuo Nacional", publicada por hoja (2007, clasificación WRB). Serie I, "Conjunto de datos vectoriales de la carta Edafológica escala 1:250 000 serie I", también por hoja (clasificación FAO). El INEGI no publica la Serie II como un solo archivo nacional, solo hoja por hoja.
- Hojas: las que cruzan la unión de los cuatro estados, que son E14-1 Morelia, E14-2 Ciudad de México, E14-3 Veracruz, E14-4 Ciudad Altamirano, E14-5 Cuernavaca, E14-6 Orizaba, E14-8 Chilpancingo, E14-9 Oaxaca, F14-8 Ciudad Valles, F14-10 Querétaro, F14-11 Pachuca y F14-12 Poza Rica.
- Descarga Serie II: https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/tematicas/Edafologia_hist/1_250_000/<UPC>_s.zip con los UPC 702825235185 (E14-1), 702825235222 (E14-2), 702825235239 (E14-3), 702825235246 (E14-4), 702825235253 (E14-5), 702825235260 (E14-6), 702825235284 (E14-8), 702825235291 (E14-9), 702825235710 (F14-8), 702825235628 (F14-10), 702825235635 (F14-11) y 702825235642 (F14-12).
- Descarga Serie I: la misma ruta con la carpeta `serie%20I/`, es decir .../Edafologia_hist/1_250_000/serie%20I/<UPC>_s.zip, con los UPC 702825677558 (E14-1), 702825677565 (E14-2), 702825677572 (E14-3), 702825677589 (E14-4), 702825677596 (E14-5), 702825677602 (E14-6), 702825234386 (E14-8), 702825234393 (E14-9), 702825677787 (F14-8), 702825234591 (F14-10), 702825677732 (F14-11) y 702825677749 (F14-12).
- Fecha de consulta: 9 de octubre de 2026.
- Por qué también la Serie I: la Serie II no tiene fase dúrica. Su campo `FRUDICA` solo marca piedras o gravas en la superficie. El tepetate aparece en la Serie II como grupo Durisol (`DU`) o como calificador petrodúrico o dúrico (`pdp`, `pdn`, `pd`, `dup`). La fase dúrica y dúrica profunda solo está en `FAS_FISCA` de la Serie I.
- Procesamiento: se leen las hojas, se proyectan a EPSG:6372, se unen y se recortan a la unión de los municipios de los cuatro estados. Los polígonos de la unión quedan sin huecos. Cada municipio queda cubierto al 100 % por las dos series, contando los polígonos de cuerpo de agua y zona urbana.
- Proyección de origen: los `.shp` no traen `.prj`. Según los `*_aux.txt`, la Serie II está en UTM 14 norte ITRF92 y se lee como EPSG:32614. La Serie I está en UTM 14 norte NAD27 y se lee como EPSG:26714. Se comprobó con los datos: con NAD27 los límites de la Serie I quedan a 3 o 4 m (mediana) de los de la Serie II y los polígonos de cuerpo de agua y zona urbana coinciden en 98 a 99 %. Leída como EPSG:32614 queda corrida unos 130 m al sur. Esto también aplica a la hoja `inegi_edafologia/serie1/e1402e.shp` de arriba, que es NAD27 y no ITRF92.
- `inegi_edafologia/serie2_4estados.gpkg`, capa `serie2`, 4349 polígonos. Columnas `CLAVE_WRB`, `GRUPO1` a `GRUPO3`, calificadores `CALIFS_G1` a `CALIFS_G3` y `CALIFP_G1` a `CALIFP_G3`, `CLASE_TEXT`, `FRUDICA`, `HOJA` (hoja de origen) y `UPC`.
- `inegi_edafologia/serie1_4estados.gpkg`, capa `serie1`, 3978 polígonos. Columnas `CLAVE`, `NOM_SUE1` a `NOM_SUE3` (suelos), `NOM_SUB1` a `NOM_SUB3` (subunidades), `CLA_TEX`, `FAS_FISCA`, `FAS_QUIMI`, `HOJA` y `UPC`.
- `inegi_edafologia/diccionario_serie2.csv`: significado de los códigos de `CLASE_TEXT`, `FRUDICA`, los grupos WRB y los calificadores petrodúricos de la Serie II, y de `CLA_TEX` y `FAS_FISCA` de la Serie I. Columnas `serie`, `campo`, `codigo`, `significado` y `fuente`. Fuentes: Diccionario de datos edafológicos 1:250 000 Serie II (INEGI 2009, UPC 702825224578), Guía para la interpretación de cartografía Edafología Serie II (INEGI 2011, UPC 702825231606) y Guía para la interpretación de cartografía Edafología (INEGI 2004, UPC 702825231736). Los calificadores `pd` y `dup` no vienen en esas guías y se tomaron de los códigos de la WRB 2006. Los valores `NA`, `N/A`, `H2O` y `ZU` no vienen en los diccionarios y se dedujeron de los datos (cuerpo de agua y zona urbana).

## INEGI, uso de suelo y vegetación Serie VII, polígonos agrícolas

- Fuente: INEGI, "Conjunto de datos vectoriales de uso del suelo y vegetación. Escala 1:250 000. Serie VII. Conjunto Nacional" (UPC 889463842781, año base 2018, publicado en 2021). Es la serie más reciente. No se encontró una Serie VIII.
- Descarga: https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/tematicas/uso_suelo/1_250_000/serie_VII/889463842781_s.zip (294 MB). Capa `conjunto_de_datos/cdv_usuev250sVII_cnal.shp`.
- Fecha de consulta: 9 de octubre de 2026.
- Filtro: polígonos cuyo campo `DESCRIPCIO` empieza con "AGRICULTURA" (temporal, riego y humedad, en sus variantes anual, semipermanente y permanente). Se recortan a la unión de los cuatro estados. No se disolvió por clase porque el archivo es chico.
- Proyección: el original está en Albers (GRS80, sin datum con nombre). Se declara sobre ITRF2008 y se pasa a EPSG:6372.
- Archivo: `inegi_usv/agricultura_temporal_4estados.gpkg`, capa `agricultura`, 3118 polígonos. Columnas `CLAVE` (clave de la clase, por ejemplo `TA`) y `DESCRIPCIO` (clase original, por ejemplo AGRICULTURA DE TEMPORAL ANUAL).
- La agricultura de temporal suma 0.66 millones de ha en Hidalgo, 0.69 en México, 1.18 en Puebla y 0.26 en Tlaxcala. Hay 18 municipios sin agricultura de temporal, casi todos urbanos del Estado de México (Nezahualcóyotl, Tlalnepantla, Coacalco y otros).

## Reproducción de los datos del INEGI

- `uv run python scripts/descargar_inegi.py --descargas <directorio fuera del repo>` descarga y prepara todo lo anterior. Con `--solo municipios suelos usv` se elige qué productos procesar. Los archivos crudos se guardan en ese directorio y no se versionan. Si ya están descargados no se vuelven a bajar.

## FIRA AgroCostos, paquete de cebada de temporal

- Fuente: sistema AgroCostos de FIRA, https://www.fira.gob.mx/Nd/Agrocostos.jsp . La aplicación (https://www.fira.gob.mx/agrocostosApp/AgroApp.jsp) carga un CSV público desde https://www.fira.gob.mx/Nd/agrocosto_data_completa.csv (el script que lo llama es https://www.fira.gob.mx/agrocostosApp/js/script.js). El encabezado `Last-Modified` del CSV es del 10 de junio de 2022 y el último ciclo que trae es primavera-verano 2022.
- Fecha de consulta: 14 de octubre de 2026. No encontramos paquetes de cebada de 2023 en adelante en una fuente pública.
- Archivo: `fira_agrocostos/cebada_agrocostos_crudo.csv`, las 54 filas de cebada del CSV (ciclos 2016 a 2022, todas las zonas). Es una copia sin cambios de las columnas originales.
- Paquete usado: ciclo PV 2022, tecnología TEMPORAL-MEJORADA-FERTILIZADA, modalidad TRADICIONAL, estatus Autorizado. Por estado hay estas zonas.

| Municipios | Zona AgroCostos | Cultivo del paquete | Rend. probable (t/ha) | Costo total 2022 ($/ha) |
|---|---|---|---|---|
| Almoloya, Apan, Cuautepec de Hinojosa, Emiliano Zapata, Singuilucan, Tepeapulco | AGENCIAS HIDALGO | Cebada alta productividad | 3.5 | 24,736 |
| Calpulalpan, Nanacamilpa | AGENCIAS DE TLAXCALA | Cebada | 4.0 | 21,594 |
| Chignahuapan | SIERRA NORTE PUEBLA | Cebada alta productividad | 5.5 | 31,128 |

- Hidalgo tiene una sola zona de cebada de temporal en 2022 (Agencias Hidalgo). En ciclos anteriores se llamó Altiplano de Hidalgo. Puebla tiene dos en 2022, Sierra Norte Puebla y Agencia Teziutlán. Asignamos Chignahuapan a Sierra Norte por ser la región geográfica en que está el municipio. Es un supuesto nuestro, el CSV y el catálogo de zonas no dicen qué municipios cubre cada zona.
- Campos usados. `Rendimiento probable`, `Precio probable`, `CostoTotal`, `TotalFinanciable`, `TotalNoFinanciable`, `AportacionN1/N2`, `TasaN1/N2`, `TotalCredito*UDIS`, `TotalAportacion*UDIS`, `TotalIntereses*UDIS`, `Total*UDIS`. Los campos `AvioInteres` y `CostoDirecto` no son pesos (son proporciones o factores) y no los usamos.
- Lectura de los campos de crédito (comprobada con los datos). Para cada paquete se cumple

  `Total*UDIS = TotalCredito + TotalAportacion + TotalIntereses + TotalNoFinanciable`

  El crédito y la aportación suman lo financiable. El interés se calcula sobre el crédito a la tasa `TasaN` por el plazo de siembra a vencimiento. Hay una versión para acreditados menores a cierto monto en UDIS (`MenorUDIS`, con `AportacionN1` y `TasaN1`) y otra para mayores (`MayorUDIS`, con `N2`). El monto en UDIS no viene en el CSV, la relación entre N1 y menores es lectura de los datos. Usamos la versión de menores. En Hidalgo y Puebla las dos versiones casi no cambian. En Tlaxcala el crédito de menores es de 5,240 y el de mayores de 6,550.
- Fórmulas.
  - `costo_total_2022 = TotalMenorUDIS` (incluye el interés del avío).
  - `costo_credito_2022 = TotalCreditoMenorUDIS + TotalInteresesMenorUDIS` (lo que se debe pagar de lo financiado, capital más interés).
  - `pe_total_t_ha = costo_total_2025 / precio` y `pe_credito_t_ha = costo_credito_2025 / precio`, con el precio en $/t.
- Cobertura del crédito. Por la parte no financiable y la aportación del productor, el crédito es 53 % del costo en Hidalgo, 27 % en Tlaxcala y 62 % en Puebla.
- Tabla de las zonas usadas, con los campos originales y el costo del crédito: `fira_agrocostos/zonas_usadas.csv`.

## INEGI, INPC para actualizar los costos a 2025

- Fuente: Índice Nacional de Precios al Consumidor (INPC) general, base segunda quincena de julio de 2018 = 100, tomado de los boletines mensuales de INEGI (ver la columna `boletin_url`). Página del programa, https://www.inegi.org.mx/temas/inpc/ . Fecha de consulta, 14 de octubre de 2026.
- Archivo: `inegi_inpc/inpc_mensual.csv`, los 12 meses de 2022 y de 2025 con los niveles de las dos quincenas.
- El boletín de 2025 publica el nivel mensual. Los boletines de 2022 publican solo los niveles de las dos quincenas, y el mensual lo calculamos como su promedio. Con los datos de 2025 comprobamos que el promedio de las quincenas reproduce el mensual publicado con una diferencia máxima de 0.001.
- Periodo: promedio de 2022 contra promedio de 2025. Son los años del paquete y de la predicción.

| | INPC |
|---|---|
| Promedio 2022 | 122.5075 |
| Promedio 2025 | 140.5422 |
| Factor | 1.147213 |

- Resultado en `inegi_inpc/factor_inpc.csv`. Para comparar, de mayo de 2022 (inicio de siembra del paquete, nivel 121.022) a diciembre de 2025 (143.042) el factor sería 1.182, 3 % más alto.
- Limitación. El INPC general no es un índice de insumos agrícolas. El fertilizante y las labores pueden haber subido distinto. Es una aproximación y el costo debe poderse editar.

## Tabla económica por municipio

- Archivo: `economia_municipal.csv`, una fila por municipio del reto (CVEGEO de 5 dígitos). Se construye con `uv run python scripts/capa_economica.py`, que además escribe `outputs/capa_economica.csv` (capa de las 197 parcelas).
- Precio. Del SIAP (`siap/cebada_temporal_pv_municipal.csv`), precio medio rural 2023 a 2025 ponderado por la producción de cada año (`precio_2023_2025`), con el mínimo y el máximo anuales de esos tres años. El cruce es por estado y nombre exacto del SIAP y después por CVEGEO. Emiliano Zapata existe en Hidalgo (13021) y en Tlaxcala (29046). El precio 2025 del de Hidalgo es 6,282 $/t. El 5,370 que se mencionaba en el issue era el promedio de ambos.
- Siniestralidad. Superficie siniestrada entre sembrada, acumulada de 2003 a 2025 y de 2013 a 2025. `anios_perdida_20` y `anios_perdida_50` cuentan los años de los 23 con más de 20 % y de 50 % de la superficie sembrada siniestrada. La pérdida se concentra en 2008 a 2011 y es casi nula desde 2013.
- Rendimiento SIAP. Media, desviación estándar (n − 1) y percentil 10 de producción entre superficie sembrada (incluye pérdidas), 2003 a 2025. `siap_frac_rend_repetido` es la fracción de años en que el mismo rendimiento, a dos decimales, aparece en otro municipio del estado y año. El SIAP copia cifras entre municipios de un mismo distrito, así que esos años no son mediciones independientes.
- Diccionario de columnas en `docs/capa_economica.md`.
