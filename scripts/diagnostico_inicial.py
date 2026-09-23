"""Diagnóstico inicial del dataset del Reto AgroCebada 2026.

Reproduce las cifras de la sección "Hallazgos del diagnóstico inicial" de ROADMAP.md.

Uso (desde la raíz del repo):
    pip install pandas numpy pyshp rasterio
    python scripts/diagnostico_inicial.py

No escribe nada en el repo: descomprime los ZIP en un directorio temporal.
"""
from pathlib import Path
import tempfile
import zipfile

import numpy as np
import pandas as pd
import rasterio
import shapefile

RAW = Path(__file__).resolve().parents[1] / "DATASET_RETO_AGRO_2026"


def dist_km(a, b):
    """Distancia aproximada en km entre centroides lon/lat (válida a ~20° N)."""
    dx = (a[:, None, 0] - b[None, :, 0]) * 104.6
    dy = (a[:, None, 1] - b[None, :, 1]) * 110.8
    return np.sqrt(dx**2 + dy**2)


def rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="agrocebada_"))
    for z in RAW.glob("*.zip"):
        zipfile.ZipFile(z).extractall(tmp)

    # --- Etiquetas -----------------------------------------------------------
    y = pd.read_csv(RAW / "ID_area_rendimiento_70_30_Reto_AgroCebada.csv", encoding="utf-8-sig").iloc[:, :4]
    shp = shapefile.Reader(str(next(tmp.rglob("Parcelas_Reto_AGC_CONJUNTO.shp"))))
    rows = []
    for sr in shp.shapeRecords():
        rec = sr.record.as_dict()
        pts = np.array(sr.shape.points)
        rows.append({"ID_POLIGONO": rec["ID_POLIGON"], "cultivo": rec["Cultivo"], "municipio": rec["Municipio"],
                     "estado": rec["Estado"], "lon": pts[:, 0].mean(), "lat": pts[:, 1].mean()})
    parc = pd.DataFrame(rows).merge(y, on="ID_POLIGONO")
    tr = parc[parc.CONJUNTO == "ENTRENAMIENTO"].reset_index(drop=True)
    pr = parc[parc.CONJUNTO == "PREDICCION"].reset_index(drop=True)

    print("== Rendimiento (t/ha), entrenamiento")
    print(tr.RENDIMIENTO_T_HA.describe().round(2).to_string())
    print("\n== Por estado")
    print(tr.groupby("estado").RENDIMIENTO_T_HA.agg(["count", "mean", "std"]).round(2).to_string())
    tr["multiplo_05"] = np.isclose(tr.RENDIMIENTO_T_HA * 2, np.round(tr.RENDIMIENTO_T_HA * 2))
    print("\n== Fracción de etiquetas múltiplo de 0.5 por estado")
    print(tr.groupby("estado").multiplo_05.mean().round(2).to_string())
    print("\n== Campo 'Cultivo' por estado")
    print(pd.crosstab(parc.cultivo, parc.estado).to_string())
    print("\n== Parcelas por municipio y conjunto")
    print(parc.groupby(["municipio", "CONJUNTO"]).size().unstack(fill_value=0).to_string())

    # --- Partición espacial --------------------------------------------------
    T, P = tr[["lon", "lat"]].values, pr[["lon", "lat"]].values
    dtt = dist_km(T, T)
    np.fill_diagonal(dtt, np.inf)
    print("\n== Distancia al vecino de ENTRENAMIENTO más cercano (mediana, km)")
    print(f"entrenamiento: {np.median(dtt.min(1)):.2f}  |  predicción: {np.median(dist_km(P, T).min(1)):.2f}")

    # --- Baselines (leave-one-out) ------------------------------------------
    yv = tr.RENDIMIENTO_T_HA.values
    n = len(yv)
    loo_global = (yv.sum() - yv) / (n - 1)

    def loo_group(col):
        out = np.empty(n)
        for i in range(n):
            mask = (tr[col] == tr.loc[i, col]).to_numpy(copy=True)
            mask[i] = False
            out[i] = yv[mask].mean() if mask.any() else loo_global[i]
        return out

    order = np.argsort(dtt, 1)
    print("\n== Baselines LOO (RMSE t/ha)")
    print(f"media global        {rmse(yv, loo_global):.3f}")
    print(f"media por estado    {rmse(yv, loo_group('estado')):.3f}")
    print(f"media por municipio {rmse(yv, loo_group('municipio')):.3f}")
    for k in (1, 3, 5, 10):
        print(f"kNN espacial k={k:<3} {rmse(yv, yv[order[:, :k]].mean(1)):.3f}")

    # --- Clima ---------------------------------------------------------------
    prec_dir = next(tmp.rglob("Precipitacion_mensual"))
    with rasterio.open(prec_dir / "2025" / "PREC_2025_07.tif") as ds:
        idx = [ds.index(lo, la) for lo, la in parc[["lon", "lat"]].values]
    print(f"\n== Píxeles CHIRPS únicos que cubren las 197 parcelas: {len(set(idx))}")
    print("== Precipitación acumulada junio-octubre, media sobre parcelas (mm)")
    for yr in range(2022, 2026):
        tot = np.zeros(len(parc))
        for m in range(6, 11):
            with rasterio.open(prec_dir / str(yr) / f"PREC_{yr}_{m:02d}.tif") as ds:
                a = ds.read(1)
            tot += np.array([a[i, j] for i, j in idx])
        print(f"{yr}: {tot.mean():.0f}")

    # --- Satélite ------------------------------------------------------------
    b = pd.read_csv(RAW / "Conjunto_datos_BASICO_AgroCebada2026.csv", encoding="utf-8-sig")
    b["fecha"] = pd.to_datetime(b.fecha_captura, dayfirst=True)
    p = pd.read_csv(RAW / "Conjunto_datos_PRO_AgroCebada.csv", encoding="utf-8-sig")
    p["fecha"] = pd.to_datetime(p.fecha_captura, dayfirst=True)
    print("\n== Observaciones Básico por año y sensor")
    print(b.groupby([b.fecha.dt.year, "sensor"]).size().unstack().to_string())
    print(f"\nNubosidad exactamente 0 o 100: Básico {b.porcentaje_nubosidad.isin([0, 100]).mean():.0%}, "
          f"PRO {p.porcentaje_nubosidad.isin([0, 100]).mean():.0%}")
    s2 = b[b.sensor == "Sentinel-2"]
    print("Nubosidad media cuando los índices S2 son nulos:",
          s2.loc[s2.ndvi_promedio.isna(), "porcentaje_nubosidad"].mean())
    s25 = s2[(s2.fecha.dt.year == 2025) & s2.fecha.dt.month.between(5, 10)]
    for th in (100, 20, 0):
        k = s25[s25.porcentaje_nubosidad <= th].groupby("ID_POLIGONO").size()
        print(f"S2 may-oct 2025, nubosidad <= {th:>3}%: mediana {k.median():.0f} obs/parcela, mínimo {k.min()}")
    print("\n== NDVI S2 (nubosidad <= 10%), mediana mensual por año")
    s2c = s2[s2.porcentaje_nubosidad <= 10]
    print(s2c.groupby([s2c.fecha.dt.year, s2c.fecha.dt.month]).ndvi_promedio.median().unstack().round(2).to_string())
    print("\n== NDVI Planet (nubosidad <= 10%), mediana mensual 2025")
    pc = p[p.porcentaje_nubosidad <= 10]
    print(pc.groupby(pc.fecha.dt.month).ndvi_promedio.median().round(2).to_string())
    print(f"\nPRO: {p.groupby('ID_POLIGONO').size().median():.0f} obs/parcela en 2025; "
          f"{p.ndvi_promedio.isna().mean():.0%} con índices nulos")


if __name__ == "__main__":
    main()
