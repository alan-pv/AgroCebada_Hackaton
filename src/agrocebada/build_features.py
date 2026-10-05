"""Regenera la tabla de variables completa desde los datos crudos.

Orden: parcelas -> series -> variables satelitales -> clima y topografía -> unión.
La salida es `data/processed/features.parquet`, una fila por parcela (197), con
ID_POLIGONO, las columnas de `parcelas.parquet` sin el rendimiento y todas las variables.

Uso:
    uv run python -m agrocebada.build_features
"""
import time

import pandas as pd

from . import features_env, features_sat, parcelas, series
from .config import PROCESSED

N_PARCELAS = 197


def verificar(df):
    """Comprueba la forma de la tabla y reporta el porcentaje de nulos por columna."""
    assert len(df) == N_PARCELAS, f"se esperaban {N_PARCELAS} filas y hay {len(df)}"
    assert df["ID_POLIGONO"].is_unique, "ID_POLIGONO repetido"
    assert "rendimiento" not in df.columns, "la tabla no debe incluir el rendimiento"
    constantes = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
    assert not constantes, f"columnas constantes: {constantes}"
    nulos = (df.isna().mean() * 100).round(1)
    print("Columnas con nulos (%)")
    print(nulos[nulos > 0].sort_values(ascending=False).to_string())
    return nulos


def main():
    t0 = time.time()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    parcelas.main()
    series.main()
    sat = features_sat.construir()
    sat.to_parquet(PROCESSED / "features_sat.parquet", index=False)
    env = features_env.construir()
    env.to_parquet(PROCESSED / "features_env.parquet", index=False)

    base = pd.read_parquet(PROCESSED / "parcelas.parquet").drop(columns="rendimiento")
    df = (base.merge(sat, on="ID_POLIGONO", validate="one_to_one")
              .merge(env, on="ID_POLIGONO", validate="one_to_one"))
    verificar(df)
    df.to_parquet(PROCESSED / "features.parquet", index=False)

    prefijos = ("sat25_", "fen_", "hist_", "het_", "lab_", "tsup_", "clima_", "topo_")
    print("Columnas por bloque")
    for p in prefijos:
        print(f"  {p}: {sum(c.startswith(p) for c in df.columns)}")
    print(f"{df.shape[0]} filas, {df.shape[1]} columnas -> features.parquet en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
