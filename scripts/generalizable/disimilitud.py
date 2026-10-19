"""Revisa si los municipios del mapa sin datos del SIAP se parecen a los 100 con SIAP en conjunto, no solo variable por
variable (observación del asesor al anexo técnico).

La regla de caja del mapa pide que la Tmax, la lluvia, la elevación y el suelo caigan dentro del mínimo y el máximo
de los 100 municipios con SIAP. Aquí se mide, para los municipios del mapa sin SIAP, la distancia al municipio con
SIAP más parecido en Tmax de julio y agosto, lluvia de mayo a octubre y elevación, con las variables estandarizadas.
Es una versión simple del índice de disimilitud de Meyer y Pebesma (2021): la distancia se divide entre la distancia
media entre municipios con SIAP, y el límite es el bigote superior (Q3 + 1.5 IQR) de esa misma medida entre los
municipios con SIAP, cada uno contra los demás. También se reporta la distancia de Mahalanobis al centro de los 100, y
cuántos municipios con SIAP tienen otro con SIAP a 25 km o menos, que justifica el corte de la confianza media.

Uso: uv run python scripts/generalizable/disimilitud.py
Salida: analisis/generalizable/disimilitud.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

RAIZ = Path(__file__).resolve().parents[2]
VARIABLES = ["clim_tmax_jul_ago", "clim_prec_may_oct", "elev_m"]
ESTADOS_RETO = ["Hidalgo", "Puebla", "Tlaxcala"]

mapa = pd.read_parquet(RAIZ / "outputs/generalizable/capa_municipal.parquet")
amb = pd.read_parquet(RAIZ / "data/processed/generalizable/municipios.parquet")
# La capa ya trae elev_m; el resto de las variables sale de la tabla ambiental
d = mapa.merge(amb[["CVEGEO"] + [v for v in VARIABLES if v not in mapa]], on="CVEGEO")

con = d[d["con_siap"]]
sin = d[d["dentro_rango_ambiental"] & ~d["con_siap"]]
X = con[VARIABLES].to_numpy(float)
Q = sin[VARIABLES].to_numpy(float)
media, desv = X.mean(0), X.std(0)
Xs, Qs = (X - media) / desv, (Q - media) / desv

# Índice de disimilitud: distancia al vecino con SIAP más cercano entre la distancia media entre municipios con SIAP
dd = cdist(Xs, Xs)
media_pares = dd[np.triu_indices(len(Xs), 1)].mean()
np.fill_diagonal(dd, np.inf)
di_con = dd.min(1) / media_pares
q1, q3 = np.quantile(di_con, [0.25, 0.75])
limite = q3 + 1.5 * (q3 - q1)
di_sin = cdist(Qs, Xs).min(1) / media_pares
lejos = sin.assign(di=di_sin)[di_sin > limite]

# Mahalanobis al centro de los 100 con SIAP
inv = np.linalg.inv(np.cov(X.T))
maha = lambda Z: np.sqrt(np.einsum("ij,jk,ik->i", Z - media, inv, Z - media))
m_con, m_sin = maha(X), maha(Q)

# Justificación de los 25 km de la confianza media: cuántos municipios con SIAP tienen otro con SIAP a esa distancia
xy = con.merge(amb[["CVEGEO", "x_m", "y_m"]], on="CVEGEO")[["x_m", "y_m"]].to_numpy(float)
dxy = cdist(xy, xy)
np.fill_diagonal(dxy, np.inf)
vecino_km = dxy.min(1) / 1000

salida = {
    "variables": VARIABLES,
    "municipios_con_siap": int(len(con)),
    "municipios_mapa_sin_siap": int(len(sin)),
    "limite_disimilitud": round(float(limite), 4),
    "lejos_de_todos": int(len(lejos)),
    "lejos_por_confianza": {k: int(v) for k, v in lejos["confianza"].value_counts().items()},
    "lejos_municipios": sorted(f"{e}, {m}" for e, m in zip(lejos["estado"], lejos["municipio"])),
    "mahalanobis_max_con_siap": round(float(m_con.max()), 3),
    "mahalanobis_sobre_max": int((m_sin > m_con.max()).sum()),
    "con_siap_con_vecino_siap_a_25km": int((vecino_km <= 25).sum()),
    "distancia_vecino_siap_mediana_km": round(float(np.median(vecino_km)), 1),
}

# El mapa del anexo solo dibuja los estados del reto y da valor a todo municipio con la Tmax dentro del rango de los
# 100 con SIAP (el modelo solo usa la Tmax; ver mapas_separados.py). El entrenamiento sigue usando los cuatro estados.
tmax_lo, tmax_hi = con["clim_tmax_jul_ago"].min(), con["clim_tmax_jul_ago"].max()
reto = d[d["estado"].isin(ESTADOS_RETO)]
mapa_reto = reto[reto["clim_tmax_jul_ago"] <= tmax_hi]
sin_reto = mapa_reto[~mapa_reto["con_siap"]]
di_reto = cdist((sin_reto[VARIABLES].to_numpy(float) - media) / desv, Xs).min(1) / media_pares
salida["tres_estados"] = {
    "municipios": int(len(reto)),
    "con_valor_en_mapa": int(len(mapa_reto)),
    "mas_calidos": int((reto["clim_tmax_jul_ago"] > tmax_hi).sum()),
    "con_siap": int(reto["con_siap"].sum()),
    "con_valor_sin_siap": int(len(sin_reto)),
    "lejos_de_todos": int((di_reto > limite).sum()),
    # Por qué unos municipios son más frescos que otros: la Tmax baja con la altitud
    "corr_tmax_elevacion": round(float(np.corrcoef(reto["clim_tmax_jul_ago"], reto["elev_m"])[0, 1]), 3),
    "elevacion_media_con_valor_m": round(float(mapa_reto["elev_m"].mean())),
    "elevacion_media_mas_calidos_m": round(float(reto.loc[reto["clim_tmax_jul_ago"] > tmax_hi, "elev_m"].mean())),
}
ruta = RAIZ / "analisis/generalizable/disimilitud.json"
ruta.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(salida, indent=1, ensure_ascii=False))
