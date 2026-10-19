"""Variables satelitales por parcela (no usan el rendimiento).

Se calculan para las 197 parcelas por igual, con las series suavizadas de `series.py`.
Los valores que no se pueden calcular quedan en NaN. Nombres de columnas.
  - sat25_{sensor}_{indice}_{metrica}: fenología de 2025 por sensor e índice.
  - fen_{metrica}: pico de verdor y fecha de siembra aproximada.
  - hist_s2_{indice}_{metrica}: historia de 2022 a 2024 con Sentinel-2 y anomalía de 2025.
  - het_{sensor}_{indice}_{metrica}: heterogeneidad dentro de la parcela.
  - lab_s2_{indice}_{metrica}: labranza y residuos antes de la siembra.
  - tsup_landsat_vi6t_{metrica}: temperatura de superficie (VI6T de Landsat).

Uso:
    uv run python -m parcelas.features_sat
"""
import numpy as np
import pandas as pd

from .config import PROCESSED
from .series import UMBRAL_NUBES, leer_sensor, leer_serie, matriz_suave

ANIO = 2025
T0 = pd.Timestamp(f"{ANIO}-01-01")

# Ventanas de 2025 (fecha inicial, fecha final)
VENTANA_PICO = ("2025-06-01", "2025-10-31")  # donde se busca el máximo de verdor
VENTANA_TEMPORADA = ("2025-05-01", "2025-11-30")  # AUC total
VENTANA_BASE = ("2025-04-01", "2025-11-30")  # base, amplitud, SOS y EOS
VENTANA_LABRANZA = ("2025-04-01", "2025-05-31")
FRAC_SOS, FRAC_EOS = 0.2, 0.5  # fracción de la amplitud para SOS y EOS

# Ventanas en días relativos al pico de verdor
REL_PRE, REL_PICO, REL_POST = (-30, -10), (-10, 10), (10, 40)

# Índices por sensor. "completo" calcula todas las métricas, "basico" solo tres.
PLANET_COMPLETO = ["ndvi", "ndre"]
PLANET_BASICO = ["evi", "msavi"]
S2_BASICO = ["ndvi", "evi", "savi", "fapar", "ndwi", "dswi4", "dswi5", "nddi"]
LABRANZA = ["ndti", "crc", "mcrc", "ndsvi"]
METRICAS_BASICAS = ["max", "auc_pico", "pend_senesc"]


def _doy(fecha):
    return float((pd.Timestamp(fecha) - T0).days + 1)


def _auc(t, v, a, b):
    """Integral trapezoidal diaria de v(t) entre los días a y b (unidad índice x día)."""
    ok = ~np.isnan(v)
    if ok.sum() < 3 or a < t[ok].min() or b > t[ok].max():
        return np.nan
    d = np.arange(np.ceil(a), np.floor(b) + 1)
    if len(d) < 2:
        return np.nan
    return float(np.trapezoid(np.interp(d, t[ok], v[ok]), d))


def _cruce(t, v, nivel, desde, hasta, subiendo):
    """Primer día entre `desde` y `hasta` en que v cruza `nivel` (interpolación lineal)."""
    m = (t >= desde) & (t <= hasta) & ~np.isnan(v)
    tt, vv = t[m], v[m]
    for i in range(len(tt) - 1):
        a, b = vv[i], vv[i + 1]
        if (subiendo and a < nivel <= b) or (not subiendo and a >= nivel > b):
            return float(tt[i] + (nivel - a) / (b - a) * (tt[i + 1] - tt[i]))
    return np.nan


def metricas_fenologia(t, v, doy_pico, completo=True):
    """Métricas de la curva suavizada `v` (días del año `t`) de una parcela.

    `doy_pico` es el día del pico de verdor de la parcela, común a todos los índices.
    Devuelve un dict con max, doy_max, auc_temp, auc_pre, auc_pico, auc_post, pend_verdeo,
    pend_senesc, sos, eos, duracion y amplitud (todas NaN si falta la curva).
    """
    nombres = ["max", "doy_max", "auc_temp", "auc_pre", "auc_pico", "auc_post", "pend_verdeo",
               "pend_senesc", "sos", "eos", "duracion", "amplitud"]
    out = dict.fromkeys(nombres, np.nan)
    if np.isnan(v).all():
        return out
    d = lambda ini, fin: (_doy(ini), _doy(fin))
    p0, p1 = d(*VENTANA_PICO)
    en_pico = (t >= p0) & (t <= p1) & ~np.isnan(v)
    if not en_pico.any():
        return out
    k = np.flatnonzero(en_pico)[np.nanargmax(v[en_pico])]
    out["max"], out["doy_max"] = float(v[k]), float(t[k])
    out["auc_pico"] = _auc(t, v, doy_pico + REL_PICO[0], doy_pico + REL_PICO[1])
    out["auc_pre"] = _auc(t, v, doy_pico + REL_PRE[0], doy_pico + REL_PRE[1])
    out["auc_post"] = _auc(t, v, doy_pico + REL_POST[0], doy_pico + REL_POST[1])
    b0, b1 = d(*VENTANA_BASE)
    en_base = (t >= b0) & (t <= b1) & ~np.isnan(v)
    base = np.nanmin(v[en_base])
    amp = out["max"] - base
    out["amplitud"] = float(amp)
    out["sos"] = _cruce(t, v, base + FRAC_SOS * amp, b0, out["doy_max"], True)
    out["eos"] = _cruce(t, v, base + FRAC_EOS * amp, out["doy_max"], b1, False)
    if not np.isnan(out["sos"]):
        vs = base + FRAC_SOS * amp
        out["pend_verdeo"] = float((out["max"] - vs) / max(out["doy_max"] - out["sos"], 1.0))
    if not np.isnan(out["eos"]):
        ve = base + FRAC_EOS * amp
        out["pend_senesc"] = float((ve - out["max"]) / max(out["eos"] - out["doy_max"], 1.0))
    if not (np.isnan(out["sos"]) or np.isnan(out["eos"])):
        out["duracion"] = out["eos"] - out["sos"]
    t0, t1 = d(*VENTANA_TEMPORADA)
    out["auc_temp"] = _auc(t, v, t0, t1)
    return out


def _curvas(serie, indice, anio=ANIO):
    """Matriz (días del año, parcelas) del valor suavizado de un índice en un año."""
    m = matriz_suave(serie, indice, anio)
    t = ((m.index - pd.Timestamp(f"{anio}-01-01")).days + 1).to_numpy(float)
    return t, m


def _pico(planet, s2):
    """Día del pico de verdor por parcela (Planet, con respaldo de Sentinel-2) y su fuente."""
    res = {}
    for nombre, serie in (("planet", planet), ("s2", s2)):
        t, m = _curvas(serie, "ndvi")
        sel = (t >= _doy(VENTANA_PICO[0])) & (t <= _doy(VENTANA_PICO[1]))
        sub = m.iloc[np.flatnonzero(sel)]
        ok = sub.notna().any()
        res[nombre] = pd.Series(t[sel][np.nanargmax(sub.fillna(-np.inf).to_numpy(), axis=0)],
                                index=sub.columns).where(ok)
    doy = res["planet"].copy()
    falta = doy.isna()
    doy[falta] = res["s2"][falta]
    return doy, falta


def _media_ventana(t, m, a, b):
    """Media por parcela de una matriz (t, parcelas) entre los días a y b."""
    sel = (t >= a) & (t <= b)
    return m.iloc[np.flatnonzero(sel)].mean()


def _heterogeneidad(sensor, doy_pico, ndvi_flags):
    """Media de ndvi_std y del coeficiente de variación (std/promedio) en [-10, +10] del pico."""
    df = leer_sensor(sensor)
    df = df[(df["porcentaje_nubosidad"] <= UMBRAL_NUBES) & df["ndvi_promedio"].notna()]
    df = df[df["fecha_captura"].dt.year == ANIO]
    df = df.merge(ndvi_flags, left_on=["ID_POLIGONO", "fecha_captura"], right_on=["ID_POLIGONO", "fecha"],
                  how="left")
    df = df[df["flag"] != "pico"]
    df["doy"] = (df["fecha_captura"] - T0).dt.days + 1
    df["pico"] = df["ID_POLIGONO"].map(doy_pico)
    df = df[(df["doy"] - df["pico"]).between(REL_PICO[0], REL_PICO[1])]
    df["cv"] = df["ndvi_std"] / df["ndvi_promedio"].where(df["ndvi_promedio"] > 0.05)
    g = df.groupby("ID_POLIGONO")
    pref = f"het_{'planet' if sensor == 'planet' else 's2'}_ndvi"
    return pd.DataFrame({f"{pref}_std_media": g["ndvi_std"].mean(), f"{pref}_cv": g["cv"].mean()})


def construir():
    """Devuelve el DataFrame de variables satelitales (una fila por parcela)."""
    planet, s2, landsat = leer_serie("planet"), leer_serie("s2"), leer_serie("landsat")
    ids = sorted(planet["ID_POLIGONO"].unique())
    doy_pico, usa_respaldo = _pico(planet, s2)
    doy_pico = doy_pico.reindex(ids)
    cols = {}

    # Fenología de 2025 por sensor e índice
    def bloque(sensor, serie, indices, completo):
        for ind in indices:
            t, m = _curvas(serie, ind)
            filas = {pid: metricas_fenologia(t, m[pid].to_numpy(float), doy_pico[pid], completo)
                     for pid in ids if pid in m.columns}
            tab = pd.DataFrame.from_dict(filas, orient="index")
            if completo:
                metricas = list(tab.columns)
                if sensor == "planet" and ind == "ndvi":
                    # El pico y la siembra de Planet NDVI se reportan en el bloque fen_
                    metricas = [x for x in metricas if x not in ("doy_max", "sos")]
            else:
                metricas = METRICAS_BASICAS
            for mt in metricas:
                cols[f"sat25_{sensor}_{ind}_{mt}"] = tab[mt]

    bloque("planet", planet, PLANET_COMPLETO, True)
    bloque("planet", planet, PLANET_BASICO, False)
    bloque("s2", s2, S2_BASICO, False)

    # Pico de verdor y siembra aproximada (SOS de Planet NDVI)
    t, m = _curvas(planet, "ndvi")
    sos = pd.Series({pid: metricas_fenologia(t, m[pid].to_numpy(float), doy_pico[pid])["sos"]
                     for pid in ids if pid in m.columns})
    cols["fen_pico_doy"] = doy_pico
    cols["fen_sos_doy"] = sos
    cols["fen_dias_sos_pico"] = doy_pico - sos

    # Historia 2022 a 2024 y anomalía de 2025 (Sentinel-2, NDVI)
    maximos, aucs = [], []
    for anio in (2022, 2023, 2024, 2025):
        t, m = _curvas(s2, "ndvi", anio)
        a, b = (pd.Timestamp(x.replace("2025", str(anio))) for x in VENTANA_PICO)
        sel = (t >= (a - pd.Timestamp(f"{anio}-01-01")).days + 1) & (t <= (b - pd.Timestamp(f"{anio}-01-01")).days + 1)
        mx = m.iloc[np.flatnonzero(sel)].max()
        t0 = (pd.Timestamp(f"{anio}-05-01") - pd.Timestamp(f"{anio}-01-01")).days + 1
        t1 = (pd.Timestamp(f"{anio}-11-30") - pd.Timestamp(f"{anio}-01-01")).days + 1
        au = pd.Series({pid: _auc(t, m[pid].to_numpy(float), t0, t1) for pid in m.columns})
        maximos.append(mx)
        aucs.append(au)
    maximos, aucs = pd.concat(maximos, axis=1), pd.concat(aucs, axis=1)
    cols["hist_s2_ndvi_max_media"] = maximos.iloc[:, :3].mean(axis=1)
    cols["hist_s2_ndvi_max_std"] = maximos.iloc[:, :3].std(axis=1)
    cols["hist_s2_ndvi_auc_media"] = aucs.iloc[:, :3].mean(axis=1)
    cols["hist_s2_ndvi_anom_max"] = maximos.iloc[:, 3] - cols["hist_s2_ndvi_max_media"]
    cols["hist_s2_ndvi_anom_auc"] = aucs.iloc[:, 3] - cols["hist_s2_ndvi_auc_media"]

    # Heterogeneidad dentro de la parcela, sin las observaciones marcadas como pico
    for sensor, serie in (("planet", planet), ("s2", s2)):
        fl = serie[(serie["indice"] == "ndvi") & (serie["flag"] == "pico")][["ID_POLIGONO", "fecha", "flag"]]
        h = _heterogeneidad(sensor, doy_pico, fl)
        for c in h.columns:
            cols[c] = h[c]

    # Labranza y residuos antes de la siembra
    a, b = _doy(VENTANA_LABRANZA[0]), _doy(VENTANA_LABRANZA[1])
    for ind in LABRANZA:
        t, m = _curvas(s2, ind)
        cols[f"lab_s2_{ind}_media"] = _media_ventana(t, m, a, b)

    # Temperatura de superficie (VI6T de Landsat) en el pico y en la temporada
    t, m = _curvas(landsat, "vi6t")
    cols["tsup_landsat_vi6t_pico"] = pd.Series(
        {pid: _media_ventana(t, m[[pid]], doy_pico[pid] + REL_PICO[0], doy_pico[pid] + REL_PICO[1])[pid]
         for pid in ids if pid in m.columns})
    cols["tsup_landsat_vi6t_temporada"] = _media_ventana(t, m, _doy(VENTANA_PICO[0]), _doy(VENTANA_PICO[1]))

    out = pd.DataFrame({k: pd.Series(v).reindex(ids) for k, v in cols.items()})
    out.index.name = "ID_POLIGONO"
    print(f"Parcelas con pico de respaldo (Sentinel-2): {int(usa_respaldo.reindex(ids).sum())}")
    return out.reset_index()


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df = construir()
    df.to_parquet(PROCESSED / "features_sat.parquet", index=False)
    print(f"{df.shape[0]} filas, {df.shape[1] - 1} columnas -> features_sat.parquet")
    print(df.isna().mean().sort_values(ascending=False).head(10).round(3).to_string())


if __name__ == "__main__":
    main()
