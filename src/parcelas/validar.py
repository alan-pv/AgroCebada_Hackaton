"""Validación de integridad del dataset crudo.

Uso:
    uv run python -m parcelas.validar

Las comprobaciones críticas se afirman con `assert`; los hallazgos que no deberían
ocultarse pero tampoco impiden trabajar se imprimen como ADVERTENCIA.
"""
import pandas as pd

from .io import leer_basico, leer_etiquetas, leer_parcelas, leer_pro

advertencias = []


def avisar(msg):
    advertencias.append(msg)
    print(f"ADVERTENCIA: {msg}")


def main():
    et = leer_etiquetas()
    parc = leer_parcelas()
    basico = leer_basico()
    pro = leer_pro()

    # --- Identificadores -----------------------------------------------------
    ids = set(et.ID_POLIGONO)
    assert len(et) == len(ids) == 197, f"Se esperaban 197 IDs únicos, hay {len(ids)}"
    conteo = et.CONJUNTO.value_counts()
    assert conteo.get("ENTRENAMIENTO") == 138 and conteo.get("PREDICCION") == 59, conteo.to_dict()
    assert set(parc.ID_POLIGONO) == ids, "Shapefile y etiquetas tienen IDs distintos"
    assert set(basico.ID_POLIGONO) == ids, "Básico y etiquetas tienen IDs distintos"
    assert set(pro.ID_POLIGONO) == ids, "PRO y etiquetas tienen IDs distintos"
    print(f"IDs: 197 | entrenamiento {conteo['ENTRENAMIENTO']} | predicción {conteo['PREDICCION']}")
    print("Mismos IDs en etiquetas, shapefile, Básico y PRO")

    # --- Duplicados ----------------------------------------------------------
    for nombre, df in (("Básico", basico), ("PRO", pro)):
        clave = ["ID_POLIGONO", "fecha_captura", "sensor"]
        dup = df.duplicated(clave, keep=False)
        if dup.any():
            avisar(f"{nombre}: {int(dup.sum())} filas con (ID, fecha, sensor) repetido "
                   f"({int(df.duplicated(clave).sum())} sobrantes)")
        else:
            print(f"{nombre}: sin duplicados (ID, fecha, sensor)")
        completas = df.duplicated(keep=False)
        if completas.any():
            avisar(f"{nombre}: {int(completas.sum())} filas completamente idénticas")

    # --- Rangos físicos ------------------------------------------------------
    for nombre, df in (("Básico", basico), ("PRO", pro)):
        ndvi = df.filter(regex=r"^ndvi_")
        assert ndvi.min().min() >= -1 and ndvi.max().max() <= 1, f"{nombre}: NDVI fuera de [-1, 1]"
        nub = df.porcentaje_nubosidad
        assert nub.min() >= 0 and nub.max() <= 100, f"{nombre}: nubosidad fuera de [0, 100]"
        print(f"{nombre}: NDVI en [{ndvi.min().min():.3f}, {ndvi.max().max():.3f}], "
              f"nubosidad en [{nub.min():g}, {nub.max():g}]")
    y = et.RENDIMIENTO_T_HA.dropna()
    assert len(y) == 138 and y.min() >= 0 and y.max() <= 10, "Rendimiento fuera de [0, 10]"
    assert et.loc[et.CONJUNTO == "PREDICCION", "RENDIMIENTO_T_HA"].isna().all(), \
        "Hay rendimiento en parcelas de PREDICCION"
    print(f"Rendimiento: {len(y)} valores en [{y.min():g}, {y.max():g}] t/ha; "
          "PREDICCION sin etiqueta")

    # --- Fechas (#25) --------------------------------------------------------
    print("\nRango de fechas por sensor y año (tras parsear DD/MM/AAAA)")
    for nombre, df in (("Básico", basico), ("PRO", pro)):
        r = (df.groupby(["sensor", df.fecha_captura.dt.year], observed=True).fecha_captura
             .agg(["min", "max", "nunique", "size"]))
        r.columns = ["min", "max", "fechas_distintas", "filas"]
        r["min"] = r["min"].dt.date
        r["max"] = r["max"].dt.date
        print(f"[{nombre}]\n{r.to_string()}")
    planet = pro[pro.sensor == "Planet"].fecha_captura
    assert planet.dt.year.eq(2025).all(), "Planet tiene fechas fuera de 2025"
    assert planet.min().month == 1 and planet.max().month == 12, \
        f"Planet no cubre enero a diciembre: {planet.min().date()} a {planet.max().date()}"
    print(f"Planet: {planet.min().date()} a {planet.max().date()}")

    print(f"\n{len(advertencias)} advertencia(s). Validación terminada.")


if __name__ == "__main__":
    main()
