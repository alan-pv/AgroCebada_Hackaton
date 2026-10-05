"""Limpieza de series satelitales: nubes, despiking, composición a 5 días y suavizado.

Cada sensor se procesa por separado y nunca se mezclan índices homónimos entre sensores.
Salida en formato largo, una tabla por sensor (`data/processed/series_{s2,landsat,planet}.parquet`),
con las columnas `ID_POLIGONO, fecha, indice, valor_crudo, valor_suave, flag`.

Cada observación original cae en una de estas categorías.
  - "valida": pasó el filtro de nubes y el despiking. Se reporta una fila por cada paso de
    5 días de la malla regular que contiene al menos una observación válida, con
    `valor_crudo` igual al promedio de esas observaciones y `valor_suave` suavizado.
  - "interpolada": paso de la malla sin observaciones válidas. `valor_crudo` es NaN y
    `valor_suave` sale del suavizado.
  - "nube": observación descartada por nubosidad (o sin valor). Una fila por observación,
    con la fecha original y `valor_suave` NaN.
  - "pico": observación descartada por el despiking. Una fila por observación, con su
    valor crudo y `valor_suave` NaN.
El suavizado queda en NaN antes de la primera y después de la última observación válida.

Uso:
    uv run python -m agrocebada.series
"""
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import spsolve

from .config import PROCESSED, REPORTE
from .io import leer_basico, leer_pro

# Umbral principal de nubosidad (%). Se conservan las observaciones con nubosidad <= umbral.
UMBRAL_NUBES = 20
UMBRALES_SENSIBILIDAD = (10, 20, 50)

PASO_DIAS = 5

# Parámetro lambda de Whittaker (mayor valor, curva más suave) con diferencias de orden 2
LAMBDA = {"s2": 10.0, "landsat": 10.0, "planet": 10.0}

# Ventana temporal del despiking (días a cada lado) y umbral en desviaciones robustas
VENTANA_PICO = {"s2": 15, "landsat": 30, "planet": 10}
K_PICO = 4.0
MIN_VECINOS = 4

# Índices de cada sensor. Sentinel-2 omite LAI, STI, MSI, EMSI, DSWI2 y DSWI3, que son
# transformaciones de otro índice (SAVI, NDTI, NDWI, ENDWI, MCRC y NDSVI).
INDICES_S2 = ["ndvi", "evi", "savi", "crc", "mcrc", "ndsvi", "srndi", "mra", "fapar", "ndti",
              "ndwi", "endwi", "dswi4", "dswi5", "nddi", "enddi"]
INDICES_LANDSAT = ["vi6t"]
INDICES_PLANET = ["ndvi", "evi", "msavi", "ndre"]
INDICES = {"s2": INDICES_S2, "landsat": INDICES_LANDSAT, "planet": INDICES_PLANET}
ANIOS = {"s2": (2022, 2025), "landsat": (2022, 2025), "planet": (2025, 2025)}
INDICE_CALIDAD = {"s2": "ndvi", "landsat": "vi6t", "planet": "ndvi"}
NOMBRE_SENSOR = {"s2": "Sentinel-2", "landsat": "Landsat", "planet": "Planet"}


# ---------------------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------------------
def leer_sensor(sensor):
    """Observaciones de un sensor con una columna por índice (promedio de la parcela).

    Devuelve un DataFrame con ID_POLIGONO, fecha_captura, porcentaje_nubosidad, las columnas
    `{indice}_promedio` y `{indice}_std`. Para Planet se agrega el NDRE derivado del LAI
    como (LAI + 0.114) / 5.405, porque el LAI de Planet es 5.405 * NDRE - 0.114.
    """
    if sensor == "planet":
        df = leer_pro()
        df["ndre_promedio"] = (df["lai_promedio"] + 0.114) / 5.405
        df["ndre_std"] = df["lai_std"] / 5.405
    else:
        df = leer_basico()
        df = df[df["sensor"] == NOMBRE_SENSOR[sensor]]
    desde, hasta = ANIOS[sensor]
    anio = df["fecha_captura"].dt.year
    df = df[(anio >= desde) & (anio <= hasta)]
    cols = ["ID_POLIGONO", "fecha_captura", "porcentaje_nubosidad"]
    for i in INDICES[sensor]:
        cols += [f"{i}_promedio"] + ([f"{i}_std"] if f"{i}_std" in df.columns else [])
    return df[cols].reset_index(drop=True)


def sensibilidad_nubes(umbrales=UMBRALES_SENSIBILIDAD):
    """Cuántas observaciones quedan con cada umbral de nubosidad, por sensor.

    Una observación queda si su nubosidad es menor o igual al umbral y su índice principal
    tiene valor. Devuelve una fila por sensor y umbral con el total, las que quedan y la
    mediana por parcela de observaciones válidas de junio a septiembre de 2025.
    """
    filas = []
    for sensor in INDICES:
        df = leer_sensor(sensor)
        col = f"{INDICE_CALIDAD[sensor]}_promedio"
        jjas = df["fecha_captura"].between("2025-06-01", "2025-09-30")
        for u in umbrales:
            ok = (df["porcentaje_nubosidad"] <= u) & df[col].notna()
            por_parcela = ok[jjas].groupby(df.loc[jjas, "ID_POLIGONO"]).sum()
            filas.append({"sensor": sensor, "umbral": u, "total": len(df), "quedan": int(ok.sum()),
                          "fraccion": round(ok.mean(), 3),
                          "mediana_jjas_2025": float(por_parcela.median())})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------------------
# Despiking y suavizado
# ---------------------------------------------------------------------------------------
def despike(dias, y, ventana=10, k=K_PICO, min_vecinos=MIN_VECINOS):
    """Marca observaciones aisladas que se alejan de la mediana móvil.

    `dias` son días enteros (ordenados) y `y` los valores. Para cada punto se toma la mediana
    y el MAD de los valores a +-`ventana` días. Un punto es pico si su distancia a la mediana
    supera `k` veces la desviación robusta (1.4826 * MAD), con un piso igual al 5 % del
    rango entre percentiles 5 y 95 para no marcar series casi constantes. Con menos de
    `min_vecinos` valores en la ventana no se marca nada. Devuelve un arreglo booleano.
    """
    dias = np.asarray(dias, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < min_vecinos:
        return np.zeros(n, dtype=bool)
    cerca = np.abs(dias[:, None] - dias[None, :]) <= ventana
    m = np.where(cerca, y[None, :], np.nan)
    med = np.nanmedian(m, axis=1)
    mad = np.nanmedian(np.abs(m - med[:, None]), axis=1)
    piso = 0.05 * (np.nanpercentile(y, 95) - np.nanpercentile(y, 5))
    sigma = np.maximum(1.4826 * mad, piso)
    pico = np.abs(y - med) > k * np.maximum(sigma, 1e-9)
    return pico & (cerca.sum(axis=1) >= min_vecinos)


def whittaker(y, w=None, lam=LAMBDA["s2"], orden=2):
    """Suavizado de Whittaker-Eilers sobre una malla regular.

    Resuelve (W + lam * D'D) z = W y con D la matriz de diferencias de orden `orden`
    (dispersa). Los pesos `w` valen 1 donde hay observación y 0 en los huecos, que se
    llenan con la tendencia de la curva. Sin pesos, todos valen 1.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    w = np.ones(n) if w is None else np.asarray(w, dtype=float)
    y0 = np.where(w > 0, np.nan_to_num(y), 0.0)
    D = sparse.identity(n, format="csc")
    for _ in range(orden):
        m = D.shape[0]
        D = sparse.diags([-1.0, 1.0], [0, 1], shape=(m - 1, m), format="csc") @ D
    A = sparse.diags(w, 0, format="csc") + lam * (D.T @ D)
    return spsolve(A.tocsc(), w * y0)


def suavizado_savgol(y, w=None, ventana=7, grado=2):
    """Alternativa a Whittaker: interpola los huecos y aplica Savitzky-Golay.

    Los huecos (peso 0) se llenan por interpolación lineal antes del filtro. `ventana` es
    el número de pasos de la malla (impar).
    """
    from scipy.signal import savgol_filter

    y = np.asarray(y, dtype=float)
    ok = np.ones(len(y), bool) if w is None else np.asarray(w) > 0
    ok &= ~np.isnan(y)
    if ok.sum() < ventana:
        return np.full(len(y), np.nan)
    x = np.arange(len(y))
    lleno = np.interp(x, x[ok], y[ok])
    return savgol_filter(lleno, ventana, grado)


# ---------------------------------------------------------------------------------------
# Procesamiento por sensor
# ---------------------------------------------------------------------------------------
def _hueco_maximo(dias, ini, fin):
    """Hueco máximo en días entre observaciones, contando los extremos de la ventana."""
    pts = np.sort(np.concatenate([[ini], np.asarray(dias, float)[(dias >= ini) & (dias <= fin)], [fin]]))
    return float(np.diff(pts).max())


def procesar_sensor(sensor, umbral=UMBRAL_NUBES, lam=None, metodo="whittaker"):
    """Devuelve (serie larga, calidad por parcela) de un sensor.

    `metodo` puede ser "whittaker" (por defecto) o "savgol".
    """
    lam = LAMBDA[sensor] if lam is None else lam
    df = leer_sensor(sensor)
    inicio = pd.Timestamp(f"{ANIOS[sensor][0]}-01-01")
    fin = pd.Timestamp(f"{ANIOS[sensor][1]}-12-31")
    n_bins = (fin - inicio).days // PASO_DIAS + 1
    centros = inicio + pd.to_timedelta(np.arange(n_bins) * PASO_DIAS + PASO_DIAS // 2, unit="D")
    dia_abs = (df["fecha_captura"] - inicio).dt.days.to_numpy()
    j0 = (pd.Timestamp("2025-06-01") - inicio).days
    j1 = (pd.Timestamp("2025-09-30") - inicio).days
    cal_idx = INDICE_CALIDAD[sensor]

    partes, calidad = [], []
    for pid, g in df.groupby("ID_POLIGONO", sort=True):
        idx = g.index.to_numpy()
        dias = dia_abs[idx]
        orden = np.argsort(dias)
        idx, dias = idx[orden], dias[orden]
        fechas = df["fecha_captura"].to_numpy()[idx]
        nubosidad = df["porcentaje_nubosidad"].to_numpy()[idx]
        for ind in INDICES[sensor]:
            y = df[f"{ind}_promedio"].to_numpy()[idx]
            sin_nube = (nubosidad <= umbral) & ~np.isnan(y)
            pico = np.zeros(len(y), bool)
            if sin_nube.any():
                pico[sin_nube] = despike(dias[sin_nube], y[sin_nube], VENTANA_PICO[sensor])
            valida = sin_nube & ~pico

            # Composición a 5 días: promedio de las observaciones válidas de cada paso
            b = dias[valida] // PASO_DIAS
            suma = np.bincount(b, weights=y[valida], minlength=n_bins)
            cuenta = np.bincount(b, minlength=n_bins)
            comp = np.where(cuenta > 0, suma / np.maximum(cuenta, 1), np.nan)
            w = (cuenta > 0).astype(float)
            if w.sum() >= 3:
                z = (whittaker(comp, w, lam) if metodo == "whittaker" else suavizado_savgol(comp, w))
                con_dato = np.flatnonzero(w)
                z[: con_dato[0]] = np.nan
                z[con_dato[-1] + 1:] = np.nan
            else:
                z = np.full(n_bins, np.nan)
            malla = pd.DataFrame({
                "fecha": centros, "valor_crudo": comp, "valor_suave": z,
                "flag": np.where(w > 0, "valida", "interpolada")})
            malla = malla[~np.isnan(malla["valor_suave"]) | (w > 0)]
            malla["ID_POLIGONO"], malla["indice"] = pid, ind
            partes.append(malla)

            rech = ~valida
            if rech.any():
                partes.append(pd.DataFrame({
                    "ID_POLIGONO": pid, "fecha": fechas[rech], "indice": ind,
                    "valor_crudo": y[rech], "valor_suave": np.nan,
                    "flag": np.where(pico[rech], "pico", "nube")}))

            if ind == cal_idx:
                dv = dias[valida]
                en_jjas = dv[(dv >= j0) & (dv <= j1)]
                calidad.append({
                    "ID_POLIGONO": pid, "sensor": sensor,
                    "n_validas_jjas_2025": int(len(en_jjas)),
                    "n_nube_jjas_2025": int((~sin_nube & (dias >= j0) & (dias <= j1)).sum()),
                    "n_pico_jjas_2025": int((pico & (dias >= j0) & (dias <= j1)).sum()),
                    "hueco_max_jjas_2025": _hueco_maximo(dv, j0, j1)})

    largo = pd.concat(partes, ignore_index=True)
    largo["fecha"] = pd.to_datetime(largo["fecha"])
    largo = largo[["ID_POLIGONO", "fecha", "indice", "valor_crudo", "valor_suave", "flag"]]
    largo["flag"] = largo["flag"].astype("category")
    largo["indice"] = largo["indice"].astype("category")
    return largo.sort_values(["ID_POLIGONO", "indice", "fecha"]).reset_index(drop=True), pd.DataFrame(calidad)


def leer_serie(sensor):
    """Lee `data/processed/series_{sensor}.parquet`."""
    return pd.read_parquet(PROCESSED / f"series_{sensor}.parquet")


def matriz_suave(serie, indice, anio=None):
    """Pivota el valor suavizado de un índice a una matriz fecha x parcela."""
    s = serie[serie["indice"] == indice]
    if anio is not None:
        s = s[s["fecha"].dt.year == anio]
    s = s[s["flag"].isin(["valida", "interpolada"])]
    return s.pivot(index="fecha", columns="ID_POLIGONO", values="valor_suave")


# ---------------------------------------------------------------------------------------
# Figura
# ---------------------------------------------------------------------------------------
def figura_ejemplo(series, ruta=None):
    """NDVI crudo y suavizado de 6 parcelas con rendimiento alto, medio y bajo.

    El rendimiento solo se usa aquí para elegir los ejemplos, no para construir variables.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ruta = ruta or REPORTE / "figuras" / "series_ejemplo.png"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    par = pd.read_parquet(PROCESSED / "parcelas.parquet")
    ent = par[par["conjunto"] == "ENTRENAMIENTO"]
    casos = [("alto", "Puebla", 0.9), ("alto", "Tlaxcala", 0.9), ("medio", "Hidalgo", 0.5),
             ("medio", "Puebla", 0.5), ("bajo", "Tlaxcala", 0.1), ("bajo", "Hidalgo", 0.1)]
    elegidas, usadas = [], set()
    for nivel, estado, q in casos:
        e = ent[(ent["estado"] == estado) & ~ent["ID_POLIGONO"].isin(usadas)]
        meta = e["rendimiento"].quantile(q)
        fila = e.iloc[(e["rendimiento"] - meta).abs().argsort().iloc[0]]
        usadas.add(fila["ID_POLIGONO"])
        elegidas.append((nivel, fila))

    fig, ejes = plt.subplots(2, 3, figsize=(13, 6.5), sharex=True, sharey=True)
    azul, naranja = "#1b6ca8", "#d9822b"
    for ax, (nivel, fila) in zip(ejes.ravel(), elegidas):
        pid = fila["ID_POLIGONO"]
        for sensor, color, nombre in (("planet", azul, "Planet"), ("s2", naranja, "Sentinel-2")):
            s = series[sensor]
            s = s[(s["ID_POLIGONO"] == pid) & (s["indice"] == "ndvi") & (s["fecha"].dt.year == 2025)]
            v = s[s["flag"] == "valida"]
            ax.scatter(v["fecha"], v["valor_crudo"], s=6, color=color, alpha=0.35, linewidths=0)
            p = s[s["flag"] == "pico"]
            ax.scatter(p["fecha"], p["valor_crudo"], s=22, marker="x", color=color, linewidths=1)
            m = s[s["flag"].isin(["valida", "interpolada"])]
            ax.plot(m["fecha"], m["valor_suave"], color=color, lw=1.8, label=f"{nombre} suavizado")
        ax.set_title(f"{pid}, {fila['estado']}, {nivel} ({fila['rendimiento']:.2f} t/ha)", fontsize=10)
        ax.set_xlim(pd.Timestamp("2025-03-01"), pd.Timestamp("2025-12-31"))
        ax.grid(alpha=0.25)
        ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    for ax in ejes[:, 0]:
        ax.set_ylabel("NDVI")
    ejes[0, 0].legend(loc="upper left", fontsize=8, frameon=False)
    fig.suptitle("NDVI de 2025 por parcela. Puntos: observaciones válidas. Cruces: picos descartados",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    print("Sensibilidad al umbral de nubosidad")
    print(sensibilidad_nubes().to_string(index=False))
    series, calidad = {}, []
    for sensor in INDICES:
        largo, cal = procesar_sensor(sensor)
        largo.to_parquet(PROCESSED / f"series_{sensor}.parquet", index=False)
        series[sensor] = largo
        calidad.append(cal)
        f = largo["flag"].value_counts()
        print(f"{sensor}: {len(largo)} filas, {largo['ID_POLIGONO'].nunique()} parcelas, "
              f"picos {int(f.get('pico', 0))}, nubes {int(f.get('nube', 0))}")
    calidad = pd.concat(calidad, ignore_index=True)
    calidad.to_parquet(PROCESSED / "calidad_series.parquet", index=False)
    print(calidad.groupby("sensor")[["n_validas_jjas_2025", "hueco_max_jjas_2025"]].describe().T.to_string())
    print(f"Figura: {figura_ejemplo(series)}")


if __name__ == "__main__":
    main()
