"""Controles de la entrega. Los de tipo "falla" detienen la generación si no se cumplen.

Reciben la tabla de las 59 predicciones tal como se entrega (ID_POLIGONO,
RENDIMIENTO_T_HA, p10, p90 más el régimen de cada parcela) y la información del
entrenamiento. Devuelven una tabla con una fila por control (control, tipo, estado,
valor, detalle). Los de tipo "reporte" describen la distribución y la coherencia espacial
y nunca fallan.
"""
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

N_ESPERADO = 59
RANGO_PLAUSIBLE = (2.0, 5.6)
TOLERANCIA_MEDIA = 0.25
RADIO_VECINOS_M = 400.0


class ControlesFallidos(RuntimeError):
    """Se lanza cuando algún control de tipo "falla" no se cumple."""


def _fila(control, tipo, ok, valor, detalle):
    estado = "informativo" if tipo == "reporte" else ("ok" if ok else "FALLA")
    return {"control": control, "tipo": tipo, "estado": estado, "valor": valor,
            "detalle": detalle}


def ejecutar(entrega, ids_esperados, regimen_ent, y_ent, xy_ent=None, xy_pred=None):
    """Corre todos los controles y devuelve la tabla de resultados.

    entrega: DataFrame con ID_POLIGONO, RENDIMIENTO_T_HA, p10, p90 y regimen.
    ids_esperados: IDs de las parcelas de PREDICCION.
    regimen_ent, y_ent: régimen y rendimiento de las parcelas de entrenamiento (Series).
    xy_ent, xy_pred: coordenadas en metros (DataFrame con x_m, y_m) para el reporte espacial.
    """
    f = []
    pred = entrega["RENDIMIENTO_T_HA"]
    f.append(_fila("n_filas", "falla", len(entrega) == N_ESPERADO, len(entrega),
                   f"se esperan {N_ESPERADO}"))
    ids = entrega["ID_POLIGONO"]
    faltan = sorted(set(ids_esperados) - set(ids))
    sobran = sorted(set(ids) - set(ids_esperados))
    f.append(_fila("ids_de_prediccion", "falla", not faltan and not sobran,
                   len(faltan) + len(sobran), f"faltan {faltan[:5]}, sobran {sobran[:5]}"))
    nulos = int(entrega[["ID_POLIGONO", "RENDIMIENTO_T_HA", "p10", "p90"]].isna().sum().sum())
    f.append(_fila("sin_nulos", "falla", nulos == 0, nulos, "celdas vacías en la entrega"))
    dup = int(ids.duplicated().sum())
    f.append(_fila("sin_duplicados", "falla", dup == 0, dup, "IDs repetidos"))

    lo, hi = RANGO_PLAUSIBLE
    fuera = int(((pred < lo) | (pred > hi)).sum())
    f.append(_fila("rango_plausible", "falla", fuera == 0, fuera,
                   f"predicciones fuera de {lo} a {hi} t/ha"))

    for r in sorted(regimen_ent.unique()):
        yr = y_ent[regimen_ent == r]
        pr = pred[entrega["regimen"] == r]
        n_fuera = int(((pr < yr.min()) | (pr > yr.max())).sum())
        f.append(_fila(f"rango_regimen_{r}", "falla", n_fuera == 0, n_fuera,
                       f"fuera de {yr.min():.2f} a {yr.max():.2f} t/ha observado en entrenamiento"))
        dif = float(pr.mean() - yr.mean())
        f.append(_fila(f"media_regimen_{r}", "falla", abs(dif) < TOLERANCIA_MEDIA, round(dif, 4),
                       f"media predicha {pr.mean():.3f} contra {yr.mean():.3f} de entrenamiento "
                       f"(tolerancia {TOLERANCIA_MEDIA})"))

    mal = int(((entrega["p10"] > pred) | (pred > entrega["p90"])).sum())
    f.append(_fila("p10_pred_p90", "falla", mal == 0, mal, "filas con p10 <= pred <= p90 violado"))

    # Reporte, sin fallar
    for r in [*sorted(regimen_ent.unique()), "todas"]:
        m_e = np.ones(len(y_ent), bool) if r == "todas" else (regimen_ent == r).to_numpy()
        m_p = np.ones(len(entrega), bool) if r == "todas" else (entrega["regimen"] == r).to_numpy()
        ds_e, ds_p = float(y_ent[m_e].std()), float(pred[m_p].std())
        f.append(_fila(f"razon_desviaciones_{r}", "reporte", True, round(ds_p / ds_e, 3),
                       f"desviación predicha {ds_p:.3f} entre observada {ds_e:.3f}"))
        ks = ks_2samp(pred[m_p], y_ent[m_e])
        f.append(_fila(f"distribucion_{r}", "reporte", True, round(float(ks.statistic), 3),
                       "estadístico KS contra el entrenamiento, cuantiles 10/50/90 predichos "
                       + "/".join(f"{q:.2f}" for q in np.quantile(pred[m_p], [.1, .5, .9]))
                       + " contra " + "/".join(f"{q:.2f}" for q in np.quantile(y_ent[m_e], [.1, .5, .9]))))
    if xy_ent is not None and xy_pred is not None:
        f.append(_coherencia(entrega, regimen_ent, y_ent, xy_ent, xy_pred))
    return pd.DataFrame(f)


def _coherencia(entrega, regimen_ent, y_ent, xy_ent, xy_pred):
    """Correlación entre la predicción y el rendimiento medio de los vecinos observados."""
    q = xy_pred[["x_m", "y_m"]].to_numpy(float)
    e = xy_ent[["x_m", "y_m"]].to_numpy(float)
    d = np.sqrt(((q[:, None, :] - e[None, :, :]) ** 2).sum(-1))
    mismo = entrega["regimen"].to_numpy()[:, None] == regimen_ent.to_numpy()[None, :]
    cerca = (d <= RADIO_VECINOS_M) & mismo
    tiene = cerca.any(1)
    yv = y_ent.to_numpy(float)
    media_vec = np.array([yv[c].mean() if c.any() else np.nan for c in cerca])
    r = (np.corrcoef(entrega["RENDIMIENTO_T_HA"].to_numpy()[tiene], media_vec[tiene])[0, 1]
         if tiene.sum() > 2 else np.nan)
    return _fila("coherencia_espacial", "reporte", True, round(float(r), 3),
                 f"correlación con la media de vecinos del mismo régimen a {RADIO_VECINOS_M:.0f} m "
                 f"(hay vecinos en {int(tiene.sum())} de {len(entrega)} parcelas)")


def verificar(tabla):
    """Lanza ControlesFallidos si algún control de tipo "falla" no se cumple."""
    malos = tabla[tabla["estado"] == "FALLA"]
    if len(malos):
        resumen = "; ".join(f"{r.control} ({r.detalle})" for r in malos.itertuples())
        raise ControlesFallidos(f"Fallaron {len(malos)} controles de la entrega: {resumen}")
    return tabla
