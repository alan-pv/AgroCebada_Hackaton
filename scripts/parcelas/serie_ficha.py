"""Serie suavizada de NDVI y NDDI de Sentinel-2 para la ficha de parcela (issue #12).

Toma la serie que construye `parcelas.series.procesar_sensor("s2")` en memoria, sin escribir
los `series_*.parquet` ni `calidad_series.parquet`, y guarda solo los índices NDVI y NDDI de
2022 a 2025 en `data/processed/serie_ficha.parquet`, en formato largo:

    ID_POLIGONO  texto, identificador de la parcela
    indice       "ndvi" o "nddi"
    anio         int16, de 2022 a 2025
    dia_anio     int16, día del año del paso de 5 días de la malla del suavizado
    valor        float32, valor suavizado (`valor_suave`), sin filas nulas

Entran los pasos "valida" e "interpolada", igual que en `series.matriz_suave`.

Uso (desde la raíz del repo; tarda alrededor de un minuto):
    .venv/bin/python scripts/parcelas/serie_ficha.py
"""
import pandas as pd

from parcelas.config import PROCESSED
from parcelas.series import procesar_sensor

INDICES = ("ndvi", "nddi")
ANIOS = (2022, 2025)
FLAGS = ["valida", "interpolada"]
SALIDA = PROCESSED / "serie_ficha.parquet"


def build_series():
    # La serie se construye en memoria; procesar_sensor no escribe archivos
    largo, _ = procesar_sensor("s2")
    s = largo[largo["indice"].isin(INDICES) & largo["flag"].isin(FLAGS)]
    s = s[s["valor_suave"].notna()]
    fecha = s["fecha"]
    out = pd.DataFrame({
        "ID_POLIGONO": s["ID_POLIGONO"].astype(str),
        "indice": s["indice"].astype(str),
        "anio": fecha.dt.year.astype("int16"),
        "dia_anio": fecha.dt.dayofyear.astype("int16"),
        "valor": s["valor_suave"].astype("float32"),
    })
    # La malla del suavizado sigue de largo más allá de 2025; esos pasos no entran
    out = out[out["anio"].between(*ANIOS)]
    return out.sort_values(["ID_POLIGONO", "indice", "anio", "dia_anio"]).reset_index(drop=True)


def main():
    print("Construyendo la serie de Sentinel-2 en memoria...", flush=True)
    serie = build_series()
    serie.to_parquet(SALIDA, index=False, compression="zstd")
    print(f"{len(serie)} filas, {SALIDA.stat().st_size / 1024:.0f} KB -> {SALIDA}")
    print(f"{serie['ID_POLIGONO'].nunique()} parcelas")
    print("años:", sorted(serie["anio"].unique().tolist()),
          "| índices:", sorted(serie["indice"].unique().tolist()))


if __name__ == "__main__":
    main()
