# Reproducir la entrega

Para regenerar solo las predicciones bastan los dos últimos pasos, porque el modelo y los archivos de `analisis/parcelas/` están versionados. Qué escribe cada paso está en [ESTRUCTURA.md](ESTRUCTURA.md).

```bash
uv run python -m parcelas.parcelas                    # data/processed/parcelas.parquet y .gpkg
uv run python -m parcelas.build_features              # data/processed/features.parquet (unos 2 min)
uv run python scripts/parcelas/lineas_base.py         # modelos de referencia y regla de decisión del régimen
uv run python scripts/parcelas/seleccion_modelo.py    # selección del modelo y registro (unos 35 min)
uv run python scripts/parcelas/intervalos.py          # promedios de modelos e intervalos p10 a p90 (unos 10 min)
uv run python scripts/parcelas/calibracion.py         # calibración del p10 y marca de confianza
uv run python scripts/parcelas/interpretabilidad.py   # preguntas guía, importancias y SHAP
uv run python scripts/parcelas/serie_ficha.py         # serie de NDVI de la ficha de cada parcela
uv run python scripts/parcelas/credito.py             # capa de crédito
uv run python -m parcelas.train_final                 # models/modelo_final.joblib
uv run python -m parcelas.predict                     # archivos de entrega y controles
uv run pytest                                         # pruebas
```

Los experimentos son deterministas (semilla 2026). `train_final` se detiene si la calibración guardada no coincide con el modelo, es decir, si se cambió el modelo sin recalibrar. Las figuras de diagnóstico se escriben en `outputs/figuras/`, que no se versiona. Los pasos del modelo municipal están en [MUNICIPAL.md](MUNICIPAL.md).

Comprobaciones independientes

```bash
uv run python scripts/auditoria/auditoria.py . analisis/parcelas/auditoria          # reimplementa el modelo sin el paquete
uv run python scripts/auditoria/auditoria_regimen.py . analisis/parcelas/auditoria  # sensibilidad al régimen y cobertura
uv run python scripts/parcelas/prueba_t.py                                          # prueba t corregida de Nadeau y Bengio
uv run python scripts/generalizable/disimilitud.py                                  # municipios sin SIAP contra los que sí tienen
```

Uso desde Python

```python
from parcelas.predict import predict
tabla = predict(features_df)   # ID_POLIGONO, pred, p10, p90, prob_bajo_umbral y confianza
```

`features_df` tiene el formato de `features.parquet`. Para parcelas del entrenamiento devuelve la predicción fuera de fold, porque el modelo final las vería como vecinas de sí mismas.
