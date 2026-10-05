"""Baselines de validación y regla de decisión de H1 (régimen como variable base).

Uso:
    uv run python scripts/baselines.py
"""
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from agrocebada import cv
from agrocebada.config import EXPERIMENTOS, PROCESSED
from agrocebada.registro import ARCHIVO_REGISTRO, registrar
from agrocebada.transformers import MediaPorGrupo, SeleccionColumnas


def modelos():
    ridge = Pipeline([
        ("pre", ColumnTransformer([
            ("estado", OneHotEncoder(handle_unknown="ignore"), ["estado"]),
            ("num", StandardScaler(), ["lon", "lat", "area_ha"])])),
        ("ridge", Ridge(alpha=1.0))])
    m = {
        "media_global": (MediaPorGrupo(None), ["(ninguna)"]),
        "media_estado": (MediaPorGrupo("estado"), ["estado"]),
        "media_municipio": (MediaPorGrupo("municipio"), ["municipio"]),
        "media_regimen": (MediaPorGrupo("regimen"), ["regimen"]),
    }
    for k in (3, 5, 10):
        m[f"knn_espacial_k{k}"] = (make_pipeline(
            SeleccionColumnas(["x_m", "y_m"]),
            KNeighborsRegressor(k, weights="distance")), ["x_m", "y_m"])
    m["ridge_estado_lonlat_area"] = (ridge, ["estado", "lon", "lat", "area_ha"])
    return m


def main():
    df = pd.read_parquet(PROCESSED / "parcelas.parquet")
    df = df[df["conjunto"] == "ENTRENAMIENTO"].set_index("ID_POLIGONO").sort_index()
    y = df["rendimiento"]
    X = df.drop(columns="rendimiento")
    cv.guardar_particiones(df.reset_index())
    cl = cv.clusters_espaciales(X)
    print(f"Clusters espaciales (enlace simple, {cv.UMBRAL_CLUSTER_M:.0f} m): {cl.nunique()}, "
          f"tamaños {sorted(cl.value_counts().tolist(), reverse=True)}")

    if ARCHIVO_REGISTRO.exists():
        ARCHIVO_REGISTRO.unlink()
    mods = modelos()
    res = {}
    for nombre, (mod, feats) in mods.items():
        res[nombre] = cv.evaluate(mod, X, y, "AB")
        registrar(res[nombre], nombre, "baseline", feats, type(mod).__name__)

    # H1: régimen contra estado y contra municipio. La permutación revuelve la columna
    # régimen entre todas las parcelas, porque revolverla dentro del régimen no cambia nada.
    mod_reg = mods["media_regimen"][0]
    for base in ("media_estado", "media_municipio"):
        dec = cv.regla_decision(res["media_regimen"]["A"], res[base]["A"], mod_reg, X, y,
                                ["regimen"], n=200, repeticiones=10, dentro_de=None)
        print(f"H1 regimen vs {base}: {dec['comparacion']} p={dec['p_permutacion']:.4f} "
              f"aceptada={dec['aceptada']}")
        registrar(res["media_regimen"], f"H1_regimen_vs_{base}", "H1", ["regimen"],
                  "MediaPorGrupo", decision=dec,
                  notas=f"base={base}; permutacion global n=200 con 10 repeticiones")

    filas = []
    for n, r in res.items():
        a, b = r["A"], r["B"]
        filas.append({"modelo": n, "RMSE_A": a.rmse, "sd_A": a.rmse_std, "MAE_A": a.mae,
                      "R2_A": a.r2, "A_reg_A": a.por_regimen["A"]["rmse"],
                      "A_reg_B": a.por_regimen["B"]["rmse"], "RMSE_B": b.rmse,
                      "MAE_B": b.mae, "R2_B": b.r2, "B_reg_A": b.por_regimen["A"]["rmse"],
                      "B_reg_B": b.por_regimen["B"]["rmse"]})
    tabla = pd.DataFrame(filas).round(3)
    print(tabla.to_string(index=False))
    tabla.to_csv(EXPERIMENTOS / "baselines_tabla.csv", index=False)


if __name__ == "__main__":
    main()
