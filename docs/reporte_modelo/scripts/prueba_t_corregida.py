"""Prueba t corregida de Nadeau y Bengio (2003) sobre los 50 pares (10 rep x 5 folds).

Usa el pipeline oficial (agrocebada.cv, esquema A, mismas particiones y semilla). Cada
sub-modelo se ajusta solo con el entrenamiento de cada fold, incluido el rezago espacial
(RezagoEspacial excluye a cada parcela de su propio rezago en el ajuste; en prueba solo
cuentan parcelas de entrenamiento).

Uso: uv run python docs/reporte_modelo/scripts/prueba_t_corregida.py
Salida: outputs/prueba_t_corregida.json
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy import stats

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts"))
warnings.filterwarnings("ignore")

from agrocebada import cv, modelos  # noqa: E402
from agrocebada.config import OUTPUTS  # noqa: E402
from agrocebada.transformers import MediaPorGrupo  # noqa: E402
from experimentos_v1 import cargar, spec, variante  # noqa: E402


def t_corregida(a, b, n_tr, n_te, usar_mse=False):
    """a, b: arreglos (rep x fold) de RMSE por fold. Diferencia a - b."""
    a, b = a.ravel(), b.ravel()
    if usar_mse:
        a, b = a ** 2, b ** 2
    d = a - b
    j = len(d)
    s2 = d.var(ddof=1)
    se = np.sqrt((1 / j + n_te / n_tr) * s2)
    t = d.mean() / se
    tc = stats.t.ppf(0.975, j - 1)
    se_nc = np.sqrt(s2 / j)
    return {"dif_media": float(d.mean()), "se": float(se), "t": float(t), "gl": j - 1,
            "ic95": [float(d.mean() - tc * se), float(d.mean() + tc * se)],
            "p_bilateral": float(2 * stats.t.sf(abs(t), j - 1)),
            "p_sin_corregir": float(2 * stats.t.sf(abs(d.mean() / se_nc), j - 1)),
            "pares_ganados_gp": int((d < 0).sum()), "pares": j}


def main():
    X, y, _ = cargar()
    base = spec("ridge", [], contexto=["regimen"], residuos=False,
                rezago={"k": 10, "radio_m": 400.0, "mismo_regimen": True, "solo_valor": True})
    s_gp = variante(base, modelo="gp")
    res = {
        "gp": cv.evaluate(modelos.desde_config(s_gp), X, y, "A"),
        "ridge": cv.evaluate(modelos.desde_config(base), X, y, "A"),
        "media_regimen": cv.evaluate(MediaPorGrupo("regimen"), X, y, "A"),
    }
    n = len(X)
    n_te = n / cv.N_FOLDS
    n_tr = n - n_te
    out = {"n": n, "n_train_aprox": n_tr, "n_test_aprox": n_te,
           "rmse_promedio_10rep": {k: v.rmse for k, v in res.items()}}
    f = {k: v.rmse_fold for k, v in res.items()}
    for nombre, otro in (("gp_vs_ridge_mismas_entradas", "ridge"), ("gp_vs_media_regimen", "media_regimen")):
        out[nombre] = t_corregida(f["gp"], f[otro], n_tr, n_te)
        out[nombre + "__variante_MSE"] = t_corregida(f["gp"], f[otro], n_tr, n_te, usar_mse=True)
        # variante con una diferencia por repeticion (RMSE sobre todas las parcelas), 10 pares
        d = res["gp"].rmse_rep - res[otro].rmse_rep
        se = np.sqrt((1 / len(d) + n_te / n_tr) * d.var(ddof=1))
        t = d.mean() / se
        out[nombre + "__variante_10_repeticiones"] = {
            "dif_media": float(d.mean()), "t": float(t),
            "p_bilateral": float(2 * stats.t.sf(abs(t), len(d) - 1)),
            "ic95": [float(d.mean() - stats.t.ppf(.975, len(d) - 1) * se),
                     float(d.mean() + stats.t.ppf(.975, len(d) - 1) * se)]}
    out["ridge_vs_media_regimen"] = t_corregida(f["ridge"], f["media_regimen"], n_tr, n_te)
    OUTPUTS.mkdir(exist_ok=True)
    (OUTPUTS / "prueba_t_corregida.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
