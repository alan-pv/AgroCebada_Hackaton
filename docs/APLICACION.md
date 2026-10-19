# Aplicación web

La aplicación está publicada en https://agrocebada.alan-pv.com y no hace falta instalarla para revisarla. Solo lee archivos ya generados y nunca reentrena el modelo. El código está en `app/`, con un módulo por sección en `app/modules/`, y sus pruebas en `tests/test_app*.py`.

| Ruta | Qué muestra |
|---|---|
| `/` | Mapa con dos modelos. El de parcelas (datos de FIRA) colorea las 197 parcelas por conjunto, régimen, rendimiento, predicción o riesgo de no pagar el crédito, con la lista de las 59 ordenada por riesgo. El municipal (SIAP y clima) colorea los 361 municipios de Hidalgo, Puebla y Tlaxcala por rendimiento esperado, confianza, temperatura o elevación, con su propia lista y un resumen por municipio que separa de dónde sale cada estimación |
| `/parcela/<id>` | Ficha de la parcela con su intervalo, confianza, economía, desglose del modelo y serie de NDVI |
| `/ejecutar` | Corre el modelo en vivo sobre parcelas del conjunto o parcelas nuevas por coordenadas o CSV |
| `/metodologia` | Validación, cobertura, confianza, margen de azar e importancia de las variables |
| `/api/parcels`, `/api/predictions`, `/api/economics`, `/api/methodology`, `/api/municipal` | Los mismos datos en JSON, y en CSV con `format=csv` donde aplica |
| `POST /api/predict` y `POST /api/predict/new` | Predicción en vivo de parcelas del conjunto o nuevas |
