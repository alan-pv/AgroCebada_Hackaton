# Datos externos

Datos públicos que se usaron en el análisis de los regímenes de etiquetas (`docs/reporte_regimenes`). El modelo de la entrega no los usa. Se consultaron el 9 de octubre de 2026.

## SIAP, cierre de la producción agrícola por municipio

- Fuente: Servicio de Información Agroalimentaria y Pesquera (SIAP), consulta de cierre agrícola, https://nube.agricultura.gob.mx/cierre_agricola/
- Filtros: reporte por ubicación geográfica, por municipio; ciclo primavera-verano; modalidad temporal; cultivo cebada grano; entidades Hidalgo, Puebla y Tlaxcala; años 2023, 2024 y 2025.
- Archivos: `siap/<estado>_<año>.xls`, uno por estado y año. Aunque la extensión es `.xls`, son tablas HTML tal como las exporta el portal. Columnas: municipio, superficie sembrada, cosechada y siniestrada (ha), producción (t), rendimiento (t/ha), precio medio rural y valor de la producción.
- El portal ofrece además los filtros de variedad y tipo de tecnología, pero para la cebada de temporal la variedad es "sin clasificar" y la tecnología distingue solo entre cielo abierto e invernadero, así que no aportan información.

## INEGI, conjunto de datos vectorial edafológico 1:250 000

- Fuente: Instituto Nacional de Estadística y Geografía (INEGI), https://www.inegi.org.mx/temas/edafologia/
- Hoja E14-2, Ciudad de México, que cubre las 197 parcelas.
- `inegi_edafologia/serie2/`: Serie II (clasificación WRB). Columnas principales: `CLAVE_WRB` (unidad de suelo), `GRUPO1` a `GRUPO3` (grupos de suelo en orden de dominancia), `CLASE_TEXT` (clase textural) y `FRUDICA` (fase física).
- `inegi_edafologia/serie1/`: Serie I (clasificación FAO). Columnas principales: `NOM_SUE1` (suelo dominante) y `FAS_FISCA` (fase física, por ejemplo dúrica, que corresponde al tepetate).
- Proyección: UTM zona 14 norte, datum ITRF92, según los archivos de metadatos `*_aux.txt`. Los `.shp` no traen `.prj`; se leen como EPSG:32614, que difiere de ITRF92 en menos de un metro.
