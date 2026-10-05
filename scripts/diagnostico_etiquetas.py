"""Diagnóstico de etiquetas, ruido y señal del dataset del Reto AgroCebada 2026.

Reproduce las cifras de docs/problema_del_dataset.md.

Uso (desde la raíz del repo):
    pip install pandas numpy pyshp rasterio scipy scikit-learn
    python scripts/diagnostico_etiquetas.py              # todo, ~5 min
    python scripts/diagnostico_etiquetas.py --rapido     # sin la prueba de permutación

No escribe nada en el repo: descomprime los ZIP en un directorio temporal.
"""
from pathlib import Path
import argparse
import tempfile
import warnings
import zipfile

import numpy as np
import pandas as pd
import rasterio
import shapefile
from scipy.signal import savgol_filter
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import RepeatedKFold
from sklearn.pipeline import make_pipeline

warnings.filterwarnings("ignore")
RAW = Path(__file__).resolve().parents[1] / "DATASET_RETO_AGRO_2026"

# Municipios cuyas etiquetas traen decimales continuos (régimen A).
# El resto viene redondeado a múltiplos de 0.5 o 0.1 (régimen B).
REGIMEN_A = {"Chignahuapan", "Almoloya", "Cuautepec de Hinojosa", "Tepeapulco"}


def dist_km(a, b):
    """Distancia aproximada en km entre centroides lon/lat (válida a ~20° N)."""
    dx = (a[:, None, 0] - b[None, :, 0]) * 104.6
    dy = (a[:, None, 1] - b[None, :, 1]) * 110.8
    return np.sqrt(dx**2 + dy**2)


def rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def cargar_parcelas(tmp):
    y = pd.read_csv(RAW / "ID_area_rendimiento_70_30_Reto_AgroCebada.csv", encoding="utf-8-sig").iloc[:, :4]
    shp = shapefile.Reader(str(next(tmp.rglob("Parcelas_Reto_AGC_CONJUNTO.shp"))))
    rows = []
    for sr in shp.shapeRecords():
        rec = sr.record.as_dict()
        pts = np.array(sr.shape.points)
        rows.append({"ID_POLIGONO": rec["ID_POLIGON"], "municipio": rec["Municipio"], "estado": rec["Estado"],
                     "lon": pts[:, 0].mean(), "lat": pts[:, 1].mean()})
    parc = pd.DataFrame(rows).merge(y, on="ID_POLIGONO")
    parc["regimen"] = np.where(parc.municipio.isin(REGIMEN_A), "A", "B")
    return parc.set_index("ID_POLIGONO")


def serie_suave(df, col, year, umbral=20):
    """Serie por parcela: filtro de nubes, despiking, interpolación a 5 días y Savitzky-Golay."""
    d = df[(df.porcentaje_nubosidad <= umbral) & df[col].notna() & (df.fecha.dt.year == year)]
    d = d.groupby(["ID_POLIGONO", "fecha"])[col].mean().reset_index()
    grid = pd.date_range(f"{year}-03-01", f"{year}-12-15", freq="5D")
    xi = (grid - grid[0]).days.values
    out = {}
    for pid, g in d.groupby("ID_POLIGONO"):
        s = g.set_index("fecha")[col]
        s = s[(s - s.rolling(5, center=True, min_periods=1).median()).abs() < 0.15]
        v = np.interp(xi, (s.index - grid[0]).days.values, s.values)
        out[pid] = pd.Series(savgol_filter(v, 7, 2), index=grid)
    return pd.DataFrame(out).T


def fenologia(M, pref):
    """Métricas fenológicas simples: máximo, día del máximo, amplitud, área, inicio, fin y duración."""
    doy = np.array([t.dayofyear for t in M.columns])
    V = M.values
    base = np.nanmedian(V[:, (doy >= 90) & (doy <= 130)], axis=1)
    f = pd.DataFrame(index=M.index)
    f[pref + "max"] = V.max(1)
    f[pref + "doymax"] = doy[V.argmax(1)]
    f[pref + "amp"] = V.max(1) - base
    f[pref + "auc"] = (V[:, (doy >= 150) & (doy <= 300)] - base[:, None]).clip(0).sum(1) * 5
    thr = base + 0.5 * (V.max(1) - base)
    sos, eos, pre, post = [], [], [], []
    for i in range(len(V)):
        im = V[i].argmax()
        up = np.where(V[i, :im] < thr[i])[0]
        dn = np.where(V[i, im:] < thr[i])[0]
        sos.append(doy[up[-1]] if len(up) else np.nan)
        eos.append(doy[im + dn[0]] if len(dn) else np.nan)
        pre.append(V[i, max(0, im - 6):max(1, im - 2)].mean())
        post.append(V[i, min(len(doy) - 1, im + 2):im + 8].mean())
    f[pref + "sos"], f[pref + "eos"] = sos, eos
    f[pref + "dur"] = f[pref + "eos"] - f[pref + "sos"]
    f[pref + "pre"], f[pref + "post"] = pre, post
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="omite la prueba de permutación")
    ap.add_argument("--permutaciones", type=int, default=60)
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="agrocebada_"))
    for z in RAW.glob("*.zip"):
        zipfile.ZipFile(z).extractall(tmp)
    parc = cargar_parcelas(tmp)
    tr = parc[parc.CONJUNTO == "ENTRENAMIENTO"].copy()
    y = tr.RENDIMIENTO_T_HA.to_numpy(float)
    reg = (tr.regimen == "A").to_numpy()

    # --- 1. Regímenes de medición --------------------------------------------
    print("== Rendimiento por régimen (entrenamiento)")
    print(tr.groupby(["regimen", "municipio"]).RENDIMIENTO_T_HA.agg(["count", "mean"]).round(2).to_string())
    tr["dos_decimales"] = np.round(tr.RENDIMIENTO_T_HA * 100) % 10 != 0
    print("\nFracción con segundo decimal distinto de 0, por régimen:")
    print(tr.groupby("regimen").dos_decimales.mean().round(2).to_string())
    print("\nParcelas por régimen y conjunto:")
    print(parc.groupby(["regimen", "CONJUNTO"]).size().unstack().to_string())

    def r2(col):
        m = tr.groupby(col).RENDIMIENTO_T_HA.transform("mean")
        return 1 - ((y - m) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"\nVarianza explicada: estado {r2('estado'):.3f} | régimen {r2('regimen'):.3f} | municipio {r2('municipio'):.3f}")

    # --- 2. Baselines con validación cruzada repetida 5x10 --------------------
    XY = tr[["lon", "lat"]].to_numpy()
    rk = list(RepeatedKFold(n_splits=5, n_repeats=10, random_state=0).split(tr))

    def cv(fn):
        return rmse(np.concatenate([fn(a, t) - y[t] for a, t in rk]))

    def media_grupo(col):
        g = tr[col].to_numpy()
        return lambda a, t: pd.Series(y[a], index=g[a]).groupby(level=0).mean().reindex(g[t]).to_numpy()

    def knn(a, t, k=10):
        d = dist_km(XY[t], XY[a])
        o = np.argsort(d, 1)[:, :k]
        w = 1 / (np.take_along_axis(d, o, 1) + 0.2)
        return (w * y[a][o]).sum(1) / w.sum(1)

    print("\n== RMSE con validación cruzada 5x10 (t/ha)")
    print(f"media global       {cv(lambda a, t: np.full(len(t), y[a].mean())):.3f}")
    print(f"media por estado   {cv(media_grupo('estado')):.3f}")
    print(f"vecinos k=10       {cv(knn):.3f}")
    print(f"media por régimen  {cv(media_grupo('regimen')):.3f}")

    # --- 3. Ruido: atípicos, tamaño de parcela y pares vecinos -----------------
    res = y - tr.groupby("regimen").RENDIMIENTO_T_HA.transform("mean").to_numpy()
    e2 = np.sort(res**2)[::-1]
    print(f"\n== Las 5 parcelas más atípicas concentran {e2[:5].sum() / e2.sum():.0%} del error cuadrático")
    for r in ("A", "B"):
        m = tr.regimen == r
        print(f"régimen {r}: correlación rendimiento vs log(área) = "
              f"{np.corrcoef(y[m], np.log(tr.AREA_HA[m]))[0, 1]:.2f}")
    print("Rendimientos >= 5.4 t/ha y su área:",
          tr.loc[tr.RENDIMIENTO_T_HA >= 5.4, "AREA_HA"].round(2).tolist())
    d = dist_km(XY, XY)
    iu = np.triu_indices(len(tr), 1)
    dy = (y[:, None] - y[None, :])[iu]
    mismo = (reg[:, None] == reg[None, :])[iu]
    cerca = mismo & (d[iu] < 0.3) & ~np.isclose(dy, 0)
    print(f"Pares < 300 m, mismo régimen, rendimiento distinto: {cerca.sum()} pares, "
          f"error típico equivalente {np.sqrt(0.5 * np.mean(dy[cerca] ** 2)):.2f} t/ha")

    # --- 4. Cuánta suerte lleva una calificación sobre 59 parcelas ------------
    rng = np.random.default_rng(0)
    s59 = [rmse(rng.choice(res, 59, replace=False)) for _ in range(5000)]
    print("\n== RMSE del mismo modelo (media por régimen) en 5000 sorteos de 59 parcelas")
    print("percentiles 5 / 50 / 95:", np.round(np.percentile(s59, [5, 50, 95]), 3))

    # --- 5. Cobertura temporal real del PRO ------------------------------------
    pro = pd.read_csv(RAW / "Conjunto_datos_PRO_AgroCebada.csv", encoding="utf-8-sig")
    pro["fecha"] = pd.to_datetime(pro.fecha_captura, dayfirst=True)
    print(f"\n== PRO (Planet): {pro.fecha.min().date()} a {pro.fecha.max().date()}, "
          f"{pro.fecha.nunique()} fechas. Máximo como texto DD/MM/AAAA: {pro.fecha_captura.max()}")

    # --- 6. Clima 2025 por régimen ---------------------------------------------
    rows = []
    for var, carpeta, pref in (("P", "Precipitacion_mensual", "PREC"), ("Tmax", "Tmax", "Tmax"), ("Tmin", "Tmin", "Tmin")):
        base = next(tmp.rglob(carpeta))
        for yr in range(2022, 2026):
            for m in range(1, 13):
                f = base / str(yr) / f"{pref}_{yr}_{m:02d}.tif"
                with rasterio.open(f) as ds:
                    v = [s[0] for s in ds.sample(list(zip(parc.lon, parc.lat)))]
                rows += [(i, var, yr, m, float(x)) for i, x in zip(parc.index, v)]
    C = pd.DataFrame(rows, columns=["id", "var", "anio", "mes", "v"]).merge(
        parc[["regimen"]], left_on="id", right_index=True)
    print("\n== Precipitación mensual media sobre las 197 parcelas (mm), abril-noviembre")
    print(C[C["var"] == "P"].groupby(["anio", "mes"]).v.mean().unstack()[list(range(4, 12))].round(0).to_string())
    print("\nPrecipitación junio-octubre por régimen (mm):")
    print(C[(C["var"] == "P") & C.mes.between(6, 10)].groupby(["regimen", "anio", "id"]).v.sum()
          .groupby(["regimen", "anio"]).mean().unstack().round(0).to_string())
    print("\nTmax media mayo-septiembre (°C):")
    print(C[(C["var"] == "Tmax") & C.mes.between(5, 9)].groupby(["regimen", "anio"]).v.mean().unstack().round(2).to_string())

    # --- 7. Fenología por régimen y prueba de permutación ----------------------
    bas = pd.read_csv(RAW / "Conjunto_datos_BASICO_AgroCebada2026.csv", encoding="utf-8-sig")
    bas["fecha"] = pd.to_datetime(bas.fecha_captura, dayfirst=True)
    s2 = bas[bas.sensor == "Sentinel-2"]
    pro["ndre"] = (pro.lai_promedio + 0.114) / 5.405
    bloques = [fenologia(serie_suave(pro, "ndvi_promedio", 2025), "pl_ndvi_"),
               fenologia(serie_suave(pro, "ndre", 2025), "pl_ndre_"),
               fenologia(serie_suave(s2, "ndvi_promedio", 2025), "s2_ndvi_"),
               fenologia(serie_suave(s2, "ndwi_promedio", 2025), "s2_ndwi_")]
    for yr in (2022, 2023, 2024):
        bloques.append(fenologia(serie_suave(s2, "ndvi_promedio", yr), f"h{yr}_")[[f"h{yr}_max", f"h{yr}_auc", f"h{yr}_doymax"]])
    X = pd.concat(bloques, axis=1)
    X["hist_max_media"] = X[["h2022_max", "h2023_max", "h2024_max"]].mean(axis=1)
    X["hist_auc_media"] = X[["h2022_auc", "h2023_auc", "h2024_auc"]].mean(axis=1)
    print("\n== Fenología Planet NDVI 2025 por régimen (197 parcelas)")
    print(parc.join(X).groupby("regimen")[["pl_ndvi_max", "pl_ndvi_sos", "pl_ndvi_eos", "pl_ndvi_dur"]].mean().round(2).to_string())

    if args.rapido:
        return
    Xt = X.loc[tr.index].to_numpy(float)
    sp = list(RepeatedKFold(n_splits=5, n_repeats=4, random_state=1).split(tr))

    def cv_sat(Xm):
        se = []
        for a, t in sp:
            mu = {r: y[a][reg[a] == r].mean() for r in (True, False)}
            ba, bt = np.array([mu[r] for r in reg[a]]), np.array([mu[r] for r in reg[t]])
            m = make_pipeline(SimpleImputer(strategy="median"),
                              ExtraTreesRegressor(200, min_samples_leaf=5, max_features=0.5, random_state=0, n_jobs=-1))
            m.fit(np.c_[Xm[a], reg[a]], y[a] - ba)
            se.append(bt + m.predict(np.c_[Xm[t], reg[t]]) - y[t])
        return rmse(np.concatenate(se))

    real = cv_sat(Xt)
    nulo = []
    for _ in range(args.permutaciones):
        Xp = Xt.copy()
        for r in (True, False):
            idx = np.where(reg == r)[0]
            Xp[idx] = Xt[rng.permutation(idx)]
        nulo.append(cv_sat(Xp))
    nulo = np.array(nulo)
    print(f"\n== Prueba de permutación ({args.permutaciones} barajadas dentro de cada régimen)")
    print(f"satélite real {real:.3f} | barajado: media {nulo.mean():.3f}, mínimo {nulo.min():.3f} | "
          f"p = {(1 + (nulo <= real).sum()) / (1 + len(nulo)):.3f}")


if __name__ == "__main__":
    main()
