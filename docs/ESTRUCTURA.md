# Estructura del repositorio

Qué hay en cada carpeta.

```
app/               aplicación web (Flask)
data/reto/         datos entregados por FIRA, sin cambios
data/externos/     datos públicos (SIAP, INEGI, CHC, Copernicus, FIRA AgroCostos)
data/processed/    tablas generadas (parcelas, variables, modelo municipal)
docs/              documentación técnica
docs/reportes/     reportes en PDF y texto de la plataforma
experimentos/      particiones, registro de experimentos y calibración
models/            modelo final entrenado
outputs/           predicciones y resultados de los análisis
scripts/           scripts de experimentos, descargas y capas
scripts/analisis/  auditoría independiente, prueba t corregida y disimilitud
src/parcelas/      código del modelo de parcelas (datos del reto)
src/generalizable/ código del modelo municipal (SIAP y clima)
tests/             pruebas
```

Los dos modelos comparten `src/parcelas/config.py`, con las rutas del proyecto y la semilla, y `src/parcelas/intervalos.py`, con el cálculo del intervalo p10 a p90. El modelo municipal los importa de ahí.
