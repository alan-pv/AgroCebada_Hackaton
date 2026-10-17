"""Escribe tabla_predicciones.tex, la tabla obligatoria del anexo con las 59 parcelas de predicción.

Cabe en una columna con dos bloques lado a lado (30 y 29 filas). Lee outputs/predicciones_finales.csv y el régimen de
data/processed/parcelas.parquet.

Uso, desde reporte/entrega:  python3 tabla_predicciones.py
"""
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]


def main():
    pred = pd.read_csv(RAIZ / "outputs/predicciones_finales.csv")
    reg = pd.read_parquet(RAIZ / "data/processed/parcelas.parquet")[["ID_POLIGONO", "regimen"]]
    t = pred.merge(reg, on="ID_POLIGONO").sort_values("ID_POLIGONO").reset_index(drop=True)
    if len(t) != 59:
        raise SystemExit(f"Se esperaban 59 parcelas, hay {len(t)}")
    celdas = [f"{r.ID_POLIGONO.replace('_', chr(92) + '_')} & {r.regimen} & {r.RENDIMIENTO_T_HA:.2f} & {r.p10:.2f} & "
              f"{r.p90:.2f}" for r in t.itertuples()]
    mitad = (len(celdas) + 1) // 2
    izq, der = celdas[:mitad], celdas[mitad:] + [" & & & & "]
    filas = "\n".join(f"{a} & {b} \\\\" for a, b in zip(izq, der))
    (AQUI / "tabla_predicciones.tex").write_text(
        "% Tabla obligatoria del anexo técnico. ID de la parcela y rendimiento predicho (t/ha), de\n"
        "% outputs/predicciones_finales.csv. La genera tabla_predicciones.py.\n"
        "\\begin{table}[!t]\n\\centering\n"
        "\\caption{ID de la parcela, régimen (R), rendimiento predicho (Pred.) e intervalo p10 a p90, en t/ha, de las 59\n"
        "parcelas, generados con el código del repositorio~\\cite{repo}.}\n"
        "\\label{tab:predicciones}\n\\fontsize{6.5}{7.6}\\selectfont\n\\setlength{\\tabcolsep}{2.2pt}\n"
        "\\begin{tabular}{@{}lcrrr@{\\hspace{1.2em}}lcrrr@{}}\n\\toprule\n"
        "ID & R & Pred. & p10 & p90 & ID & R & Pred. & p10 & p90 \\\\\n\\midrule\n"
        f"{filas}\n\\bottomrule\n\\end{{tabular}}\n\\end{{table}}\n", encoding="utf-8")
    print(f"tabla_predicciones.tex: {len(t)} parcelas en {mitad} filas")


if __name__ == "__main__":
    main()
