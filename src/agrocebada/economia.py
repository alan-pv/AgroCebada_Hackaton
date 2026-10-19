"""Capa económica: de toneladas por hectárea a pesos y riesgo de crédito.

    from agrocebada.economia import capa_economica
    tabla = capa_economica(pred_df)   # pred_df: salida de predict() más CVEGEO, regimen y area_ha

No es una variable del modelo. Toma la predicción (pred, p10), el municipio y el área de cada
parcela y los datos de `data/externos/economia_municipal.csv` (se construye con
`scripts/credito.py`) y devuelve por parcela

  precio, costo_total, costo_credito         $/t y $/ha usados (2025)
  pe_total, pe_credito                       puntos de equilibrio en t/ha
  ingreso_esperado_ha, ingreso_conservador_ha, ingreso_esperado_parcela
  margen_esperado_ha                         ingreso esperado menos costo total, $/ha
  prob_perdida                               q, fracción siniestrada histórica del municipio
  prob_no_pagar_credito, prob_no_cubrir_costos
  semaforo_credito, semaforo_costos          "verde", "amarillo" o "rojo"

Puntos de equilibrio. pe_total = costo_total / precio. pe_credito = costo_credito / precio,
donde costo_credito es lo que se debe pagar de lo financiado (capital más interés del avío).

Probabilidades. Se combinan dos fuentes de riesgo

    P = q + (1 - q) * P(y < PE | cosecha)

q es la siniestralidad municipal (fracción de superficie sembrada que no se cosecha, del SIAP,
periodo elegible con `siniestro`). Con pérdida se supone ingreso cero. P(y < PE | cosecha) sale de
la distribución calibrada de residuos del modelo (`CalibradorIntervalo.prob_bajo`), que es la
incertidumbre de la predicción para una parcela en un año como 2025. No incluye la variación de
un año a otro (sequía, helada, precio), que el SIAP solo muestra como contexto en las columnas
`siap_*` de la tabla municipal. Por eso la probabilidad se lee como riesgo en un año parecido al
de la predicción más la pérdida histórica, no como una probabilidad de incumplimiento.

Semáforo. verde si P < 0.10, amarillo si 0.10 <= P < 0.30, rojo si P >= 0.30. Los cortes son
argumentos (`cortes`).

Sustituir valores. `precio`, `costo_total` y `costo_credito` aceptan un número (todas las
parcelas), un arreglo con un valor por parcela o un diccionario {CVEGEO: valor} que solo cambia esos municipios. Los puntos de
equilibrio se recalculan con ellos. `siniestro` puede ser "2003_2025", "2013_2025", un número o
un diccionario por CVEGEO.
"""
import numpy as np
import pandas as pd

from .config import RAIZ

RUTA_TABLA = RAIZ / "data" / "externos" / "economia_municipal.csv"
CORTES = (0.10, 0.30)
SINIESTROS = {"2003_2025": "siniestralidad_2003_2025", "2013_2025": "siniestralidad_2013_2025"}


def cargar_tabla(ruta=None):
    """Tabla municipal indexada por CVEGEO (texto de 5 dígitos)."""
    t = pd.read_csv(ruta or RUTA_TABLA, dtype={"CVEGEO": str})
    return t.set_index("CVEGEO", drop=False)


def _valor(arg, cve, base, nombre):
    """Serie por parcela: `base` (de la tabla) salvo que `arg` la sustituya."""
    if arg is None:
        return base
    if isinstance(arg, dict):
        r = {str(k): float(v) for k, v in arg.items()}
        return cve.map(r).astype(float).fillna(base)
    if np.ndim(arg) == 0:
        return pd.Series(float(arg), index=cve.index)
    a = np.asarray(arg, dtype=float)
    if a.ndim == 1 and len(a) == len(cve):
        return pd.Series(a, index=cve.index)
    raise ValueError(f"{nombre} debe ser un número, un diccionario {{CVEGEO: valor}} o un "
                     "arreglo con un valor por parcela")


def _semaforo(p, cortes):
    verde, rojo = cortes
    return pd.Series(np.select([p < verde, p < rojo], ["verde", "amarillo"], "rojo"),
                     index=p.index)


def _prob_bajo_pe(calibrador, pred, regimen, area, pe):
    """P(y < pe | cosecha) con un umbral distinto por parcela (el calibrador acepta un escalar)."""
    out = np.empty(len(pred))
    for u in np.unique(pe):
        m = pe == u
        out[m] = calibrador.prob_bajo(pred[m], regimen[m], area[m], float(u))
    return out


def capa_economica(pred_df, modelo=None, precio=None, costo_total=None, costo_credito=None,
                   siniestro="2003_2025", tabla=None, cortes=CORTES):
    """Pesos y riesgo por parcela. Ver el docstring del módulo.

    pred_df: DataFrame con pred, p10, regimen, area_ha y la clave del municipio en CVEGEO
      (o bien estado y municipio, que se cruzan con la tabla). Puede traer ID_POLIGONO.
    modelo: ModeloFinal de `cargar_modelo()`. Si es None se carga el del repo.
    tabla: tabla municipal de `cargar_tabla()`; por defecto la del repo.
    """
    t = cargar_tabla() if tabla is None else tabla
    d = pred_df.reset_index(drop=True).copy()
    falta = [c for c in ("pred", "p10", "regimen", "area_ha") if c not in d.columns]
    if falta:
        raise ValueError(f"Faltan columnas en pred_df: {falta}")
    if "CVEGEO" not in d.columns:
        if not {"estado", "municipio"} <= set(d.columns):
            raise ValueError("pred_df necesita CVEGEO, o estado y municipio")
        llave = t.set_index(["estado", "municipio"]).CVEGEO
        d["CVEGEO"] = [llave.get((e, m)) for e, m in zip(d.estado, d.municipio)]
    d["CVEGEO"] = d["CVEGEO"].astype("string").str.zfill(5)
    desconocidos = sorted(set(d.CVEGEO.dropna()) - set(t.index))
    if d.CVEGEO.isna().any() or desconocidos:
        raise ValueError(f"Municipios fuera de la tabla económica: {desconocidos or 'sin CVEGEO'}")
    cve = d.CVEGEO.astype(str)
    fila = t.loc[cve]

    def base(col):
        return pd.Series(fila[col].to_numpy(dtype=float), index=d.index)

    pr = _valor(precio, cve, base("precio_2023_2025"), "precio")
    ct = _valor(costo_total, cve, base("costo_total_2025"), "costo_total")
    cc = _valor(costo_credito, cve, base("costo_credito_2025"), "costo_credito")
    if isinstance(siniestro, str):
        if siniestro not in SINIESTROS:
            raise ValueError(f"siniestro debe ser uno de {list(SINIESTROS)}, un número o un diccionario")
        q = base(SINIESTROS[siniestro])
    else:
        q = _valor(siniestro, cve, base(SINIESTROS["2003_2025"]), "siniestro")
    if (pr <= 0).any():
        raise ValueError("El precio debe ser positivo")
    if not q.between(0, 1).all():
        raise ValueError("La siniestralidad debe estar entre 0 y 1")

    pe_t, pe_c = ct / pr, cc / pr
    if modelo is None:
        from .predict import cargar_modelo
        modelo = cargar_modelo()
    cal = modelo.prediccion.calibrador
    pred = d["pred"].to_numpy(dtype=float)
    reg = d["regimen"].astype(str).to_numpy()
    area = d["area_ha"].to_numpy(dtype=float)
    p_t = _prob_bajo_pe(cal, pred, reg, area, pe_t.round(9).to_numpy())
    p_c = _prob_bajo_pe(cal, pred, reg, area, pe_c.round(9).to_numpy())
    q_ = q.to_numpy()
    no_cubre = pd.Series(q_ + (1 - q_) * p_t, index=d.index)
    no_paga = pd.Series(q_ + (1 - q_) * p_c, index=d.index)

    out = pd.DataFrame({
        "precio": pr, "costo_total": ct, "costo_credito": cc, "pe_total": pe_t,
        "pe_credito": pe_c,
        "ingreso_esperado_ha": d["pred"] * pr, "ingreso_conservador_ha": d["p10"] * pr,
        "ingreso_esperado_parcela": d["pred"] * pr * d["area_ha"],
        "margen_esperado_ha": d["pred"] * pr - ct, "prob_perdida": q,
        "prob_no_pagar_credito": no_paga, "prob_no_cubrir_costos": no_cubre,
        "semaforo_credito": _semaforo(no_paga, cortes),
        "semaforo_costos": _semaforo(no_cubre, cortes)})
    cabecera = [c for c in ("ID_POLIGONO",) if c in d.columns]
    return pd.concat([d[cabecera], pd.DataFrame({"CVEGEO": cve}), out], axis=1)
