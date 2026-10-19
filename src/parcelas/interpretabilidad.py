"""Importancia de variables por grupos: índices satelitales, variables climáticas y bloques.

Todas las medidas se calculan fuera de muestra, con las particiones del esquema A de `cv`.
Un grupo reúne todas las variables derivadas del mismo índice (sin importar el sensor ni
la métrica), o de la misma variable climática, o del mismo bloque del diccionario.

Los modelos de este módulo son modelos de análisis, no el candidato. Sirven para medir
cuánto aporta cada grupo y no para predecir las parcelas ocultas.

Dos escenarios
  Régimen presente. El modelo ve el régimen, el rezago espacial y el grupo de variables.
    Las permutaciones se hacen dentro de cada régimen, de modo que la importancia mide lo
    que el grupo aporta además del régimen.
  Régimen ausente. El modelo ve solo las variables. Las permutaciones se hacen entre todas
    las parcelas, de modo que el grupo puede aportar también como indicador del régimen.
"""
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.base import clone

from . import cv, modelos
from .config import SEED

REZAGO = {"k": 10, "radio_m": 400.0, "mismo_regimen": True, "solo_valor": True}

BLOQUES_ORDEN = ("sat25_fen", "hist", "het", "lab", "tsup", "clima", "topo")
PREFIJOS_BLOQUE = {"sat25_fen": ("sat25_", "fen_"), "hist": ("hist_",), "het": ("het_",),
                   "lab": ("lab_",), "tsup": ("tsup_",), "clima": ("clima_",), "topo": ("topo_",)}
PREFIJOS_SATELITE = ("sat25_", "fen_", "hist_", "het_", "lab_", "tsup_")

# Nombre del índice dentro del nombre de la variable. `fen_*` (fechas del ciclo, tomadas
# de la curva de NDVI de Planet) forma su propio grupo para no inflar el de NDVI.
INDICES = ("ndvi", "ndre", "evi", "msavi", "savi", "fapar", "ndwi", "dswi4", "dswi5", "nddi",
           "ndti", "crc", "mcrc", "ndsvi", "vi6t")
SENSORES = {"planet": "Planet", "s2": "Sentinel-2", "landsat": "Landsat"}

# Parejas de la Tabla IV (índice del conjunto Básico, índice equivalente). Las variables
# conservan una sola de cada pareja.
TABLA_IV = (("STI", "NDTI"), ("MSI", "NDWI"), ("EMSI", "ENDWI"), ("DSWI3", "NDSVI"),
            ("DSWI2", "MCRC"), ("LAI", "SAVI"))
ELIMINADOS_TABLA_IV = ("sti", "msi", "emsi", "dswi3", "dswi2", "lai")

CLIMA_GRUPOS = {
    "Lluvia": ("clima_prec_", "clima_anom_prec_"),
    "Tmax": ("clima_tmax_", "clima_anom_tmax_", "clima_meses_tmax_"),
    "Tmin": ("clima_tmin_", "clima_anom_tmin_"),
    "Amplitud térmica": ("clima_amplitud_",),
    "Grados-día": ("clima_gdd",),
}
# Cuánto llovió (total del ciclo) contra cuándo llovió (por bimestre).
LLUVIA_CUANDO = {
    "Lluvia total (cuánto)": ("clima_prec_total_may_oct", "clima_anom_prec_total_may_oct"),
    "Lluvia por bimestre (cuándo)": ("clima_prec_siembra", "clima_prec_crecimiento",
                                     "clima_prec_cosecha", "clima_anom_prec_siembra",
                                     "clima_anom_prec_crecimiento", "clima_anom_prec_cosecha"),
}


# ----------------------------------------------------------------------- grupos

def _partes(col):
    """Devuelve (índice, sensor) de una variable satelital, o None si no es de un índice."""
    p = col.split("_")
    if p[0] in ("sat25", "hist", "het", "lab", "tsup") and len(p) > 3:
        idx = next((x for x in p[2:] if x in INDICES), None)
        return (idx, p[1]) if idx else None
    return None


def columnas_satelitales(columnas):
    """Columnas derivadas de series satelitales (todo salvo clima y topografía)."""
    return [c for c in columnas if c.startswith(PREFIJOS_SATELITE)]


def grupos_indice(columnas, por_sensor=False):
    """Grupos de variables por índice. Cada columna satelital cae en exactamente un grupo.

    Con `por_sensor=False` el grupo se llama p. ej. "NDVI" y reúne Planet y Sentinel-2.
    Con `por_sensor=True` se llama "NDVI (Planet)". Las variables `fen_*` forman el grupo
    "Fenología (fechas)". Las de historia, heterogeneidad y labranza se asignan al índice
    del que se calculan (NDVI, NDTI, CRC...).
    """
    g = {}
    for c in columnas_satelitales(columnas):
        if c.startswith("fen_"):
            nombre = "Fenología (fechas)"
        else:
            idx, sensor = _partes(c)
            nombre = idx.upper()
            if por_sensor:
                nombre += f" ({SENSORES.get(sensor, sensor)})"
        g.setdefault(nombre, []).append(c)
    return g


def grupos_clima(columnas):
    """Grupos por variable climática (lluvia, Tmax, Tmin, amplitud, grados-día)."""
    cols = [c for c in columnas if c.startswith("clima_")]
    g = {}
    for nombre, pref in CLIMA_GRUPOS.items():
        sel = [c for c in cols if c.startswith(pref)]
        if sel:
            g[nombre] = sel
    return g


def grupos_lluvia_cuando(columnas):
    """Lluvia total (cuánto llovió) contra lluvia por bimestre (cuándo llovió)."""
    out = {}
    for n, cs in LLUVIA_CUANDO.items():
        sel = [c for c in cs if c in columnas]
        if sel:
            out[n] = sel
    return out


def grupos_bloque(columnas):
    """Grupos por bloque del diccionario (sat25_fen, hist, het, lab, tsup, clima, topo)."""
    return {b: [c for c in columnas if c.startswith(p)] for b, p in PREFIJOS_BLOQUE.items()
            if any(c.startswith(p) for c in columnas)}


def verificar_sin_duplicados(columnas):
    """Variables cuyo índice es de los eliminados de la Tabla IV (debe devolver una lista vacía)."""
    return [c for c in columnas
            if any(e in c.split("_")[2:] for e in ELIMINADOS_TABLA_IV)]


# ---------------------------------------------------------------------- modelos

def modelo_analisis(algoritmo, columnas, regimen=True, seleccion_k=None, **params):
    """Modelo de análisis. Con `regimen=True` agrega el régimen y el rezago espacial.

    Sin régimen el modelo ve solo las columnas, y la selección de variables dentro del fold
    usa la correlación con y (no con el residuo de la media por régimen).
    """
    if algoritmo == "rf":
        params.setdefault("n_estimators", 150)
    if regimen:
        return modelos.construir_modelo(algoritmo, columnas, contexto=("regimen",),
                                        rezago=REZAGO, seleccion_k=seleccion_k, **params)
    return modelos.construir_modelo(algoritmo, columnas, contexto=(), rezago=None,
                                    seleccion_k=seleccion_k, criterio="y", **params)


# ------------------------------------------------------------ permutación

def _rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def _revolver(Xte, cols, rng, dentro_de):
    """Revuelve juntas las columnas `cols` en el fold de prueba (opcionalmente por régimen)."""
    X2 = Xte.copy()
    n = len(Xte)
    if dentro_de is None:
        orden = rng.permutation(n)
    else:
        orden = np.arange(n)
        v = Xte[dentro_de].to_numpy()
        for g in np.unique(v):
            idx = np.flatnonzero(v == g)
            orden[idx] = idx[rng.permutation(len(idx))]
    X2[cols] = Xte[cols].to_numpy()[orden]
    return X2


def _una_repeticion(modelo, X, y, parts_r, grupos, n_perm, dentro_de, mascaras, semilla):
    pos = pd.Series(np.arange(len(X)), index=X.index)
    n = len(X)
    base = np.full(n, np.nan)
    perm = {g: np.full((n_perm, n), np.nan) for g in grupos}
    rng = np.random.default_rng(semilla)
    for f in sorted(parts_r["fold"].unique()):
        te = pos[parts_r.loc[parts_r["fold"] == f, "ID_POLIGONO"]].to_numpy()
        tr = np.setdiff1d(np.arange(n), te)
        m = clone(modelo).fit(X.iloc[tr], y.iloc[tr])
        Xte = X.iloc[te]
        base[te] = m.predict(Xte)
        for g, cols in grupos.items():
            for s in range(n_perm):
                perm[g][s, te] = m.predict(_revolver(Xte, cols, rng, dentro_de))
    yv = y.to_numpy()
    cubierto = ~np.isnan(base)
    sal = {}
    for nom, mk in mascaras.items():
        mk = mk & cubierto
        rb = _rmse(base[mk] - yv[mk])
        sal[nom] = {"base": rb, **{g: float(np.mean([_rmse(perm[g][s, mk] - yv[mk])
                                                     for s in range(n_perm)]) - rb)
                                   for g in grupos}}
    return sal


def importancia_permutacion(modelo, X, y, grupos, repeticiones=5, n_perm=5, dentro_de="regimen",
                            mascaras=None, n_jobs=1, semilla=SEED):
    """Importancia por permutación agrupada, fuera de fold.

    En cada fold del esquema A se entrena el modelo con el entrenamiento y se mide el RMSE
    en el fold de prueba. Luego se revuelven juntas las columnas de un grupo en el fold de
    prueba y se mide de nuevo. La importancia es el aumento del RMSE. Se calcula con las
    predicciones de todos los folds de una repetición (RMSE agrupado) y se promedia sobre
    `n_perm` revueltas. El resultado reporta la media sobre repeticiones y los percentiles
    5 y 95 entre repeticiones.

    X: parcelas con las columnas del modelo. Si es un subconjunto de las de entrenamiento
    (p. ej. un solo régimen), las particiones del esquema A se calculan sobre ese
    subconjunto. grupos: {nombre: [columnas]}. dentro_de: columna dentro de la cual se
    revuelve (None para revolver entre todas). mascaras: {nombre: arreglo booleano} para
    calcular el RMSE sobre subconjuntos (p. ej. un régimen), alineado con el orden de X.
    Devuelve {máscara: DataFrame con grupo, importancia_media, p05, p95, n_rep, rmse_base}.
    """
    X = X.sort_index()
    y = y.loc[X.index]
    grupos = {g: [c for c in cs if c in X.columns] for g, cs in grupos.items()}
    grupos = {g: cs for g, cs in grupos.items() if cs}
    if mascaras is None:
        mascaras = {"todas": np.ones(len(X), dtype=bool)}
    partes = particiones(X, repeticiones)
    out = Parallel(n_jobs=n_jobs)(
        delayed(_una_repeticion)(modelo, X, y, partes[partes["repeticion"] == r], grupos, n_perm,
                                 dentro_de, mascaras, semilla + r) for r in range(repeticiones))
    res = {}
    for nom in mascaras:
        filas = []
        for g in grupos:
            v = np.array([o[nom][g] for o in out])
            filas.append({"grupo": g, "importancia_media": v.mean(), "p05": np.percentile(v, 5),
                          "p95": np.percentile(v, 95), "n_rep": len(v),
                          "rmse_base": float(np.mean([o[nom]["base"] for o in out]))})
        res[nom] = pd.DataFrame(filas).sort_values("importancia_media", ascending=False)
    return res


def particiones(X, repeticiones):
    """Particiones del esquema A para las parcelas de X (estratos por municipio)."""
    p = cv.particiones_A(X.assign(conjunto="ENTRENAMIENTO"), n_rep=repeticiones)
    return p[p["ID_POLIGONO"].isin(X.index)]


# --------------------------------------------------------------- ablación

def ablacion_grupos(fabrica, columnas, X, y, grupos, repeticiones=10, n_jobs=1):
    """Ablación quitando un grupo a la vez (leave-one-group-out), en el esquema A.

    fabrica: función que recibe la lista de columnas y devuelve el modelo.
    El efecto es RMSE sin el grupo menos RMSE completo (positivo = el grupo ayuda). Los
    percentiles salen de las diferencias emparejadas por repetición.
    """
    X = X.sort_index()
    y = y.loc[X.index]
    completo = cv.evaluate(fabrica(columnas), X, y, "A", repeticiones=repeticiones)
    grupos = {g: cs for g, cs in grupos.items() if any(c in columnas for c in cs)}

    def una(g, cs):
        resto = [c for c in columnas if c not in set(cs)]
        r = cv.evaluate(fabrica(resto), X, y, "A", repeticiones=repeticiones)
        d = r.rmse_rep - completo.rmse_rep
        return {"grupo": g, "importancia_media": float(d.mean()), "p05": float(np.percentile(d, 5)),
                "p95": float(np.percentile(d, 95)), "rmse_sin_grupo": r.rmse,
                "victorias_con_grupo": int((d > 0).sum()), "n_rep": len(d)}

    filas = Parallel(n_jobs=n_jobs)(delayed(una)(g, cs) for g, cs in grupos.items())
    t = pd.DataFrame(filas).sort_values("importancia_media", ascending=False)
    t.attrs["rmse_completo"] = completo.rmse
    return t


# ------------------------------------------------- selección hacia adelante

def modelo_bloques(algoritmo, columnas, rezago):
    """Modelo con régimen, rezago opcional y las columnas. Ridge selecciona 15 en el fold."""
    k = 15 if algoritmo == "ridge" and len(columnas) > 20 else None
    params = {"n_estimators": 150} if algoritmo == "rf" else {}
    return modelos.construir_modelo(algoritmo, list(columnas), contexto=("regimen",),
                                    rezago=REZAGO if rezago else None, seleccion_k=k, **params)


def seleccion_adelante(X, y, bloques, algoritmo="rf", repeticiones=10, n_perm=50,
                       rep_perm=3, n_jobs=1):
    """Selección hacia adelante por bloques, partiendo del régimen.

    En cada paso se prueba agregar cada bloque que falta (o el rezago espacial) al modelo
    actual, y se toma el de menor RMSE en el esquema A. Ese paso se somete a la regla de
    decisión de `cv.regla_decision` contra el modelo del paso anterior: al menos 7 de 10
    victorias y prueba de permutación del bloque con p <= 0.05. La prueba de permutación
    solo se corre si hay 7 victorias o más. Tras el primer paso rechazado la regla ya no se
    evalúa (la tabla sigue agregando bloques solo para mostrar la curva).
    bloques: {nombre: [columnas]}. Devuelve un DataFrame con una fila por candidato.
    """
    X = X.sort_index()
    y = y.loc[X.index]
    pendientes = ["rezago"] + list(bloques)
    cols, con_rezago = [], False
    actual = cv.evaluate(modelo_bloques(algoritmo, cols, False), X, y, "A", repeticiones=repeticiones)
    filas = [{"modelo": algoritmo, "paso": 0, "candidato": "contexto (régimen)", "rmse_A": actual.rmse,
              "victorias": np.nan, "dif_media": 0.0, "p": np.nan, "elegido": True,
              "aceptado": True, "regla_vigente": True, "n_vars": 0}]
    activa = True
    paso = 0
    while pendientes:
        paso += 1

        def evaluar(b):
            c = cols + (bloques[b] if b != "rezago" else [])
            r = cv.evaluate(modelo_bloques(algoritmo, c, con_rezago or b == "rezago"), X, y, "A",
                            repeticiones=repeticiones)
            return b, r

        res = dict(Parallel(n_jobs=n_jobs)(delayed(evaluar)(b) for b in pendientes))
        mejor = min(res, key=lambda b: res[b].rmse)
        paso_filas = []
        for b in pendientes:
            comp = cv.comparacion_emparejada(res[b], actual)
            paso_filas.append({"modelo": algoritmo, "paso": paso, "candidato": b,
                               "rmse_A": res[b].rmse, "victorias": comp["victorias"],
                               "dif_media": comp["diferencia_media"], "p": np.nan,
                               "elegido": b == mejor, "aceptado": False, "regla_vigente": activa,
                               "n_vars": len(cols) + (len(bloques[b]) if b != "rezago" else 0)})
        fila = next(f for f in paso_filas if f["elegido"])
        if activa and fila["victorias"] >= 7:
            c = cols + (bloques[mejor] if mejor != "rezago" else [])
            perm_cols = ["x_m", "y_m"] if mejor == "rezago" else bloques[mejor]
            dec = cv.regla_decision(res[mejor], actual,
                                    modelo_bloques(algoritmo, c, con_rezago or mejor == "rezago"),
                                    X, y, perm_cols, n=n_perm, repeticiones=rep_perm)
            fila["p"] = dec["p_permutacion"]
            fila["aceptado"] = dec["aceptada"]
        filas += paso_filas
        activa = activa and fila["aceptado"]
        if mejor == "rezago":
            con_rezago = True
        else:
            cols = cols + bloques[mejor]
        actual = res[mejor]
        pendientes.remove(mejor)
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------- SHAP

def nombres_variables(modelo, columnas):
    """Nombres de las columnas que recibe el regresor final de `modelo_analisis`."""
    pre = modelo.named_steps["pre"]
    nombres = []
    for nombre, trans, _ in pre.transformers_:
        if nombre == "ctx_regimen":
            nombres += [f"regimen_{c}" for c in trans.categories_[0]]
        elif nombre == "rezago":
            nombres += ["rezago_y"]
        elif nombre == "vars":
            nombres += list(columnas)
    return nombres


def matriz_explicable(modelo, X, y, ids_entrenamiento):
    """Matriz transformada de todas las parcelas, con el rezago de leave-one-out en las de entrenamiento.

    `modelo` ya ajustado con las parcelas de entrenamiento. Las de entrenamiento se
    transforman con `fit_transform` de un clon del preprocesador (el rezago excluye a la
    propia parcela, igual que durante el ajuste). Las demás usan `transform`.
    """
    pre = modelo.named_steps["pre"]
    ent = X.index.isin(ids_entrenamiento)
    Z = np.full((len(X), pre.transform(X.iloc[:1]).shape[1]), np.nan)
    Z[ent] = clone(pre).fit_transform(X[ent], y.loc[X.index[ent]])
    if (~ent).any():
        Z[~ent] = pre.transform(X[~ent])
    return Z
