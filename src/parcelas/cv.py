"""Validación cruzada del proyecto y regla de decisión para aceptar ideas.

Esquema A: 5 folds x 10 repeticiones al azar, estratificado por municipio como la
partición oficial 70/30. Es el esquema principal.
Esquema B: 5 folds agrupados por clusters espaciales de centroides. Mide cuánto depende un
modelo de tener vecinos cercanos en el entrenamiento.

Los estratos del esquema A salen de `estratos()`. Los municipios con menos de
`MIN_ESTRATO` parcelas de entrenamiento no alcanzan para repartirse en 5 folds, así que se
juntan en un estrato "otros" por régimen. Si ese estrato sigue por debajo del mínimo
(ocurre con el régimen A, donde solo queda Tepeapulco), se une al municipio más grande del
mismo régimen.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.base import clone
from sklearn.model_selection import StratifiedKFold

from .config import ANALISIS_PARCELAS, PROCESSED, SEED

N_FOLDS = 5
N_REP = 10
MIN_ESTRATO = 5
UMBRAL_CLUSTER_M = 2000.0
ARCHIVO_PARTICIONES = ANALISIS_PARCELAS / "particiones.parquet"


# ---------------------------------------------------------------- particiones

def _entrenamiento(df):
    """Filas de entrenamiento ordenadas por ID (el orden fija el resultado)."""
    if "conjunto" in df.columns:
        df = df[df["conjunto"] == "ENTRENAMIENTO"]
    if "ID_POLIGONO" in df.columns:
        df = df.set_index("ID_POLIGONO")
    return df.sort_index()


def estratos(df):
    """Serie con el estrato de cada parcela (municipio, con los pequeños fusionados)."""
    df = _entrenamiento(df)
    est = df["municipio"].astype(str).copy()
    cuenta = est.value_counts()
    for reg, sub in df.groupby("regimen"):
        munis = sub["municipio"].unique()
        peq = [m for m in munis if cuenta[m] < MIN_ESTRATO]
        if not peq:
            continue
        est[df["municipio"].isin(peq) & (df["regimen"] == reg)] = f"otros_{reg}"
        if (est == f"otros_{reg}").sum() < MIN_ESTRATO:
            grandes = cuenta[[m for m in munis if cuenta[m] >= MIN_ESTRATO]]
            est[est == f"otros_{reg}"] = grandes.idxmax()
    return est


def particiones_A(df, n_folds=N_FOLDS, n_rep=N_REP, semilla=SEED):
    """DataFrame (ID_POLIGONO, repeticion, fold) del esquema A. Determinista."""
    est = estratos(df)
    ids = est.index.to_numpy()
    filas = []
    for r in range(n_rep):
        skf = StratifiedKFold(n_folds, shuffle=True, random_state=semilla + r)
        for f, (_, test) in enumerate(skf.split(ids, est.to_numpy())):
            filas.append(pd.DataFrame({"ID_POLIGONO": ids[test], "repeticion": r, "fold": f}))
    return pd.concat(filas, ignore_index=True)


def clusters_espaciales(df, umbral_m=UMBRAL_CLUSTER_M):
    """Serie con el cluster de cada parcela (enlace simple sobre x_m, y_m, umbral en metros)."""
    df = _entrenamiento(df)
    z = linkage(df[["x_m", "y_m"]].to_numpy(dtype=float), method="single")
    return pd.Series(fcluster(z, t=umbral_m, criterion="distance"), index=df.index, name="cluster")


def particiones_B(df, n_folds=N_FOLDS, n_rep=N_REP, semilla=SEED, umbral_m=UMBRAL_CLUSTER_M):
    """Esquema B. Cada cluster completo cae en un solo fold.

    En cada repetición se baraja el orden de los clusters y se asigna cada uno, del más
    grande al más pequeño, al fold con menos parcelas. Así las repeticiones difieren y los
    folds quedan parejos aun si hay un cluster dominante.
    """
    cl = clusters_espaciales(df, umbral_m)
    tam = cl.value_counts()
    filas = []
    for r in range(n_rep):
        rng = np.random.default_rng(semilla + 1000 + r)
        orden = rng.permutation(tam.index.to_numpy())
        orden = sorted(orden, key=lambda c: -tam[c])  # estable: el desempate es aleatorio
        carga = np.zeros(n_folds)
        fold_de = {}
        for c in orden:
            f = int(np.argmin(carga))
            fold_de[c] = f
            carga[f] += tam[c]
        filas.append(pd.DataFrame({"ID_POLIGONO": cl.index, "repeticion": r,
                                   "fold": cl.map(fold_de).to_numpy()}))
    return pd.concat(filas, ignore_index=True)


def guardar_particiones(df=None, ruta=ARCHIVO_PARTICIONES):
    """Escribe las particiones A y B para que todo el equipo use las mismas."""
    if df is None:
        df = pd.read_parquet(PROCESSED / "parcelas.parquet")
    a = particiones_A(df).assign(esquema="A")
    b = particiones_B(df).assign(esquema="B")
    out = pd.concat([a, b], ignore_index=True)[["esquema", "ID_POLIGONO", "repeticion", "fold"]]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(ruta, index=False)
    return out


# ----------------------------------------------------------------- evaluación

_CACHE = {}


def _particiones_cache(base, esquema):
    """Particiones del esquema, memorizadas por contenido (la permutación las pide muchas veces)."""
    t = _entrenamiento(base)
    cols = ["municipio", "regimen"] if esquema == "A" else ["x_m", "y_m"]
    clave = (esquema, int(pd.util.hash_pandas_object(t[cols], index=True).sum()))
    if clave not in _CACHE:
        _CACHE[clave] = particiones_A(base) if esquema == "A" else particiones_B(base)
    return _CACHE[clave]


def _rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def _std(v):
    return float(np.std(v, ddof=1)) if len(v) > 1 else 0.0


@dataclass
class Resultado:
    """Resultado de evaluar un modelo con un esquema."""
    esquema: str
    oof: pd.DataFrame          # filas = parcelas, columnas = repeticiones
    y: pd.Series
    meta: pd.DataFrame         # regimen y estado de cada parcela
    rmse_rep: np.ndarray       # una por repetición
    mae_rep: np.ndarray
    r2_rep: np.ndarray
    rmse_fold: np.ndarray      # repeticiones x folds
    por_regimen: dict = field(default_factory=dict)  # {grupo: {"rmse", "mae", "n"}}
    por_estado: dict = field(default_factory=dict)

    @property
    def rmse(self):
        return float(self.rmse_rep.mean())

    @property
    def rmse_std(self):
        return _std(self.rmse_rep)

    @property
    def mae(self):
        return float(self.mae_rep.mean())

    @property
    def r2(self):
        return float(self.r2_rep.mean())

    def resumen(self):
        return {"esquema": self.esquema, "rmse": self.rmse, "rmse_std": self.rmse_std,
                "mae": self.mae, "mae_std": _std(self.mae_rep),
                "r2": self.r2, "r2_std": _std(self.r2_rep)}


def _agrupar(oof, y, grupos):
    """RMSE y MAE por grupo, calculados por repetición y promediados."""
    out = {}
    for g in sorted(grupos.unique()):
        m = (grupos == g).to_numpy()
        e = oof.loc[m].sub(y[m], axis=0)
        out[g] = {"rmse": float(np.mean([_rmse(e[c]) for c in e.columns])),
                  "mae": float(e.abs().mean().mean()), "n": int(m.sum())}
    return out


def _ajustar(modelo, X, y, tr, te, sample_weight):
    m = clone(modelo)
    kw = {}
    if sample_weight is not None:
        paso = m.steps[-1][0] if hasattr(m, "steps") else None
        kw[f"{paso}__sample_weight" if paso else "sample_weight"] = sample_weight.iloc[tr].to_numpy()
    m.fit(X.iloc[tr], y.iloc[tr], **kw)
    return np.asarray(m.predict(X.iloc[te]), dtype=float)


def _evaluar_esquema(modelo, X, y, esquema, repeticiones, sample_weight, ref=None):
    X = X.sort_index()
    y = y.loc[X.index]
    if sample_weight is not None:
        sample_weight = sample_weight.loc[X.index]
    base = X if ref is None else ref.sort_index()
    base = base if "conjunto" in base.columns else base.assign(conjunto="ENTRENAMIENTO")
    parts = _particiones_cache(base, esquema)
    pos = pd.Series(np.arange(len(X)), index=X.index)
    reps = list(range(N_REP if repeticiones is None else repeticiones))
    oof = pd.DataFrame(np.nan, index=X.index, columns=reps)
    rmse_fold = np.full((len(reps), N_FOLDS), np.nan)
    for r in reps:
        pr = parts[parts["repeticion"] == r]
        for f in range(N_FOLDS):
            te = pos[pr.loc[pr["fold"] == f, "ID_POLIGONO"]].to_numpy()
            if len(te) == 0:
                continue
            tr = np.setdiff1d(np.arange(len(X)), te)
            pred = _ajustar(modelo, X, y, tr, te, sample_weight)
            oof.iloc[te, r] = pred
            rmse_fold[r, f] = _rmse(pred - y.iloc[te].to_numpy())
    err = oof.sub(y, axis=0)
    rmse_rep = np.array([_rmse(err[c]) for c in reps])
    mae_rep = np.array([err[c].abs().mean() for c in reps])
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2_rep = np.array([1 - (err[c] ** 2).sum() / ss_tot for c in reps])
    meta = (X if ref is None else ref.loc[X.index])[["regimen", "estado"]]
    return Resultado(esquema, oof, y, meta, rmse_rep, mae_rep, r2_rep, rmse_fold,
                     _agrupar(oof, y, meta["regimen"]), _agrupar(oof, y, meta["estado"]))


def evaluate(modelo, X, y, esquema="A", repeticiones=None, sample_weight=None, ref=None):
    """Evalúa un estimador sklearn con validación cruzada.

    X: DataFrame indexado por ID_POLIGONO solo con parcelas de entrenamiento, con las
      columnas de parcelas.parquet (municipio, estado, regimen, x_m, y_m...) más las
      numéricas que quiera usar el modelo. y: Serie con el rendimiento, mismo índice.
    esquema: "A", "B" o "AB". Con "AB" devuelve {"A": Resultado, "B": Resultado}.
    repeticiones: número de repeticiones a usar (por defecto las 10).
    sample_weight: Serie opcional con pesos, se pasa al último paso del pipeline.
    ref: DataFrame con el que se arman las particiones y los grupos (por defecto X). La
      prueba de permutación lo usa para que revolver el régimen no cambie las particiones.
    El modelo se clona en cada fold, así que todo lo que use y debe ir dentro del pipeline.
    """
    if esquema == "AB":
        return {e: _evaluar_esquema(modelo, X, y, e, repeticiones, sample_weight, ref) for e in "AB"}
    if esquema not in ("A", "B"):
        raise ValueError("esquema debe ser 'A', 'B' o 'AB'")
    return _evaluar_esquema(modelo, X, y, esquema, repeticiones, sample_weight, ref)


# ------------------------------------------------------------ regla de decisión

def comparacion_emparejada(res_nuevo, res_base, minimo=7):
    """Cuenta en cuántas repeticiones el modelo nuevo tiene menor RMSE que el base.

    Se acepta con `minimo` victorias o más (7 de 10). Ambos resultados deben venir del
    mismo esquema y de las mismas particiones.
    """
    a, b = np.asarray(res_nuevo.rmse_rep), np.asarray(res_base.rmse_rep)
    if a.shape != b.shape:
        raise ValueError("Los resultados deben tener el mismo número de repeticiones")
    victorias = int((a < b).sum())
    return {"victorias": victorias, "repeticiones": len(a),
            "diferencia_media": float((a - b).mean()),  # negativa = el nuevo es mejor
            "aceptada": victorias >= minimo}


def _permutar_bloque(X, columnas, rng, dentro_de="regimen"):
    """Revuelve el bloque de columnas conjuntamente (mismo orden de filas para todas)."""
    columnas = list(columnas)
    grupos = [np.arange(len(X))] if dentro_de is None else [
        np.flatnonzero((X[dentro_de] == g).to_numpy()) for g in X[dentro_de].unique()]
    bloque = X[columnas].to_numpy()
    nuevo = bloque.copy()
    for idx in grupos:
        nuevo[idx] = bloque[rng.permutation(idx)]
    Xp = X.copy()
    Xp[columnas] = pd.DataFrame(nuevo, index=X.index, columns=columnas).astype(X[columnas].dtypes.to_dict())
    return Xp


def prueba_permutacion(modelo, X, y, columnas, n=50, repeticiones=3, dentro_de="regimen",
                       semilla=SEED):
    """Prueba de permutación del bloque `columnas`.

    Revuelve el bloque de forma conjunta dentro de cada régimen (dentro_de="regimen". Con
    None lo revuelve entre todas las parcelas, necesario si el bloque es el propio régimen),
    reevalúa con el esquema A y compara con el RMSE real. Para acotar el costo se usan solo
    las primeras `repeticiones` del esquema A (por defecto 3 de 10, o sea 15 ajustes por
    permutación). El RMSE real se calcula con esas mismas repeticiones.
    p = (1 + #{RMSE_perm <= RMSE_real}) / (n + 1).
    """
    X = X.sort_index()
    y = y.loc[X.index]
    real = evaluate(modelo, X, y, "A", repeticiones=repeticiones).rmse
    rng = np.random.default_rng(semilla)
    perm = np.array([evaluate(modelo, _permutar_bloque(X, columnas, rng, dentro_de), y, "A",
                              repeticiones=repeticiones, ref=X).rmse for _ in range(n)])
    p = (1 + int((perm <= real).sum())) / (n + 1)
    return {"rmse_real": float(real), "rmse_perm_media": float(perm.mean()),
            "rmse_perm_min": float(perm.min()), "n": n, "repeticiones": repeticiones, "p": float(p)}


def regla_decision(res_nuevo, res_base, modelo=None, X=None, y=None, columnas=None, n=50,
                   repeticiones=3, dentro_de="regimen", minimo=7, alfa=0.05):
    """Combina la comparación emparejada y la prueba de permutación.

    Se acepta solo si hay al menos `minimo` victorias de 10 y el p-valor de la permutación
    es menor o igual a `alfa`. Sin `columnas` no hay permutación y no puede aceptarse.
    """
    comp = comparacion_emparejada(res_nuevo, res_base, minimo)
    perm = None
    if modelo is not None and columnas is not None:
        perm = prueba_permutacion(modelo, X, y, columnas, n, repeticiones, dentro_de)
    ok_perm = perm is not None and perm["p"] <= alfa
    return {"aceptada": bool(comp["aceptada"] and ok_perm), "victorias": comp["victorias"],
            "diferencia_media": comp["diferencia_media"],
            "p_permutacion": None if perm is None else perm["p"],
            "comparacion": comp, "permutacion": perm}
