"""Particiones y métricas del modelo generalizable.

Esquemas, todos con particiones fijas y semilla 2026.

  Espacial con zona de exclusión (principal). Simula un lugar nuevo. Los municipios se agrupan
    en N_GRUPOS grupos espaciales con k-medias sobre los centroides y cada grupo es un fold
    (se deja fuera un grupo a la vez). Al predecir un grupo se quitan del entrenamiento los
    municipios a menos de B km de cualquier municipio del grupo. Con B = 0 queda la
    validación espacial de siempre. Con B grande se simula un lugar sin SIAP cerca. Las
    N_REP repeticiones usan k-medias con semillas distintas, así que cambian la forma de los
    grupos. Se usa un grupo por fold y no cinco folds de varios grupos porque con cinco folds
    una zona de 60 km deja menos de diez municipios para entrenar.
  Espacial de cinco folds (continuidad). El esquema anterior, con los 20 grupos repartidos en
    N_FOLDS folds y sin zona de exclusión. Se conserva para comparar con los resultados
    previos y para los modelos caros.
  Por DDR. Cada Distrito de Desarrollo Rural del SIAP es un fold. Como el SIAP copia cifras
    dentro de un distrito, este esquema evita que el interpolador gane por esa copia.
  Por año (pronóstico). Deja fuera un año completo, todos los municipios. Es la única prueba
    de si el clima del año ayuda a pronosticar un año nuevo, porque en los esquemas
    espaciales los municipios de entrenamiento ya traen la cosecha del mismo año.

Métrica principal (fijada antes de ver los resultados con pesos y con zona de exclusión).
  RMSE de nivel ponderado por superficie sembrada, en el esquema espacial con zona de
  exclusión. El error de nivel de un municipio es la media de sus predicciones menos la
  media de sus rendimientos observados, y cada municipio pesa su superficie sembrada media.
  Se evalúa en dos distancias fijadas de antemano, B = 0 km (lugar dentro de la región con
  SIAP cerca) y B = 50 km (lugar sin datos cerca). Se pondera porque la pregunta de FIRA es
  sobre dónde se siembra, y porque la media de un municipio chico depende de pocas parcelas y
  el SIAP la estima con poco cuidado. Sin ponderar, los municipios de 60 ha pesan lo mismo
  que los de 20 000 ha y la métrica la dominan los más ruidosos.
  Se reportan además, como secundarias, el RMSE por fila (municipio-año), el RMSE sin
  ponderar y el subconjunto de municipios con mediana de superficie sembrada de al menos
  UMBRAL_GRANDE_HA.

Regla de decisión, la del repositorio. Un modelo nuevo se acepta si tiene menor métrica que la
base en al menos 7 de las 10 repeticiones y además pasa la prueba de permutación con
p ≤ 0.05.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.cluster import KMeans

from ..config import SEED

N_GRUPOS = 20
N_FOLDS = 5
N_REP = 10
N_PERM = 99
N_JOBS = 6
UMBRAL_GRANDE_HA = 1000.0
BUFFERS_KM = (0, 20, 40, 60, 80)
BUFFERS_DECISION_KM = (0, 50)


# -------------------------------------------------------------- particiones

def grupos_espaciales(municipios, n_grupos=N_GRUPOS, semilla=SEED):
    """Serie clave -> grupo espacial, con k-medias sobre x_m, y_m (una fila por municipio)."""
    xy = municipios[["x_m", "y_m"]].to_numpy()
    km = KMeans(n_grupos, n_init=20, random_state=semilla).fit(xy)
    return pd.Series(km.labels_, index=municipios.clave.to_numpy(), name="grupo")


def _municipios(tabla, por="CVEGEO"):
    return tabla.drop_duplicates(por)[[por, "x_m", "y_m"]].rename(columns={por: "clave"})


def particiones_espaciales(claves, grupos, n_folds=N_FOLDS, n_rep=N_REP, semilla=SEED):
    """Lista de repeticiones. Cada una es un arreglo con el fold de cada fila de `claves`.

    `claves` es la columna clave de la tabla (una entrada por fila municipio-año) y `grupos`
    la salida de grupos_espaciales. Los grupos se reparten en folds de tamaño parecido en
    número de municipios.
    """
    claves = np.asarray(claves)
    rng = np.random.default_rng(semilla)
    ids = np.sort(grupos.unique())
    tam = grupos.value_counts()
    reps = []
    for _ in range(n_rep):
        orden = rng.permutation(ids)
        carga = np.zeros(n_folds)
        fold_de_grupo = {}
        # Reparto voraz: cada grupo va al fold con menos municipios hasta el momento.
        for g in orden:
            f = int(np.argmin(carga + rng.uniform(0, 1e-6, n_folds)))
            fold_de_grupo[g] = f
            carga[f] += tam[g]
        reps.append(np.array([fold_de_grupo[grupos[c]] for c in claves]))
    return reps


def particiones_grupo(tabla, n_grupos=N_GRUPOS, n_rep=N_REP, semilla=SEED, por="CVEGEO"):
    """Un fold por grupo espacial, con k-medias de semilla distinta en cada repetición."""
    mun = _municipios(tabla, por)
    claves = tabla[por].to_numpy()
    return [grupos_espaciales(mun, n_grupos, semilla + i).reindex(claves).to_numpy() for i in range(n_rep)]


def particiones_columna(tabla, columna):
    """Una repetición con un fold por valor de `columna` (por ejemplo ddr)."""
    _, inv = np.unique(tabla[columna].astype(str).to_numpy(), return_inverse=True)
    return [inv]


def particiones_anio(anios):
    """Una repetición con un fold por año."""
    anios = np.asarray(anios)
    _, inv = np.unique(anios, return_inverse=True)
    return [inv]


def mascara_entrenamiento(tabla, te, buffer_km=0.0, por="CVEGEO"):
    """Filas de entrenamiento al predecir las filas `te`.

    Son las que no están en `te` y cuyo municipio está a más de `buffer_km` de todos los
    municipios de prueba. Con buffer_km = 0 es simplemente ~te.
    """
    tr = ~te
    if buffer_km <= 0:
        return tr
    mun = _municipios(tabla, por).set_index("clave")
    xy = mun[["x_m", "y_m"]].to_numpy() / 1000.0
    prueba = np.isin(mun.index.to_numpy(), tabla.loc[te, por].unique())
    d = np.sqrt(((xy[:, None, :] - xy[None, prueba, :]) ** 2).sum(-1)).min(1)
    lejos = pd.Series(d > buffer_km, index=mun.index)
    return tr & tabla[por].map(lejos).to_numpy()


# ------------------------------------------------------------------ métricas

def metricas(y, pred, w=None):
    """RMSE, MAE, R² y sesgo, con pesos opcionales."""
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    w = np.ones(len(y)) if w is None else np.asarray(w, float)
    w = w / w.sum()
    e = pred - y
    ym = (w * y).sum()
    tot = (w * (y - ym) ** 2).sum()
    r2 = float(1 - (w * e ** 2).sum() / tot) if tot > 0 else float("nan")
    return {"rmse": float(np.sqrt((w * e ** 2).sum())), "mae": float((w * np.abs(e)).sum()),
            "r2": r2, "sesgo": float((w * e).sum())}


@dataclass
class Contexto:
    """Lo que hace falta para calcular las métricas de fila y de nivel con pesos y subconjuntos.

    claves: municipio de cada fila. w_fila: superficie sembrada de cada fila. w_mun: superficie
    sembrada media de cada municipio. subconjuntos: nombre -> claves que entran (None = todos).
    """
    claves: np.ndarray
    w_fila: np.ndarray
    w_mun: pd.Series
    subconjuntos: dict


def contexto(tabla, por="CVEGEO", umbral_grande=UMBRAL_GRANDE_HA):
    s = tabla.groupby(por).sembrada_ha
    grandes = s.median()
    return Contexto(claves=tabla[por].to_numpy(), w_fila=tabla.sembrada_ha.to_numpy(float), w_mun=s.mean(),
                    subconjuntos={"todos": None, "grandes": set(grandes[grandes >= umbral_grande].index)})


def metricas_rep(y, pred, ctx, unidad="nivel", ponderado=True, subconjunto="todos"):
    """Métricas de una repetición. unidad es "fila" (municipio-año) o "nivel" (media municipal)."""
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    sub = ctx.subconjuntos[subconjunto]
    if unidad == "fila":
        m = np.ones(len(y), bool) if sub is None else np.isin(ctx.claves, list(sub))
        return metricas(y[m], pred[m], ctx.w_fila[m] if ponderado else None)
    g = pd.DataFrame({"c": ctx.claves, "y": y, "p": pred}).groupby("c").mean()
    if sub is not None:
        g = g[g.index.isin(sub)]
    return metricas(g.y, g.p, ctx.w_mun.reindex(g.index).to_numpy() if ponderado else None)


def rmse_rep(res, ctx, unidad="nivel", ponderado=True, subconjunto="todos"):
    """RMSE por repetición. Por omisión es la métrica principal."""
    return np.array([metricas_rep(res.y, p, ctx, unidad, ponderado, subconjunto)["rmse"] for p in res.oof])


VARIANTES = [(u, p, s) for u in ("nivel", "fila") for p in (True, False) for s in ("todos", "grandes")]


def tabla_metricas(res, ctx):
    """Una fila por unidad, ponderación y subconjunto, con la media y la desviación entre repeticiones."""
    filas = []
    for u, p, s in VARIANTES:
        m = pd.DataFrame([metricas_rep(res.y, o, ctx, u, p, s) for o in res.oof])
        filas.append({"modelo": res.nombre, "unidad": u, "ponderado": p, "subconjunto": s, **m.mean().to_dict(),
                      "rmse_std": float(m.rmse.std(ddof=1)) if len(m) > 1 else 0.0, "n_rep": len(m)})
    return filas


# --------------------------------------------------------------- evaluación

@dataclass
class Resultado:
    """Predicciones fuera de fold de cada repetición."""
    nombre: str
    oof: list = field(default_factory=list)  # un arreglo de predicciones por repetición
    y: np.ndarray = None

    @property
    def rmse_rep(self):
        """RMSE por fila sin ponderar, por repetición (compatibilidad)."""
        return np.array([metricas(self.y, p)["rmse"] for p in self.oof])


def _una_rep(ajustar_predecir, tabla, y, folds, buffer_km):
    pred = np.full(len(y), np.nan)
    for f in np.unique(folds):
        te = folds == f
        tr = mascara_entrenamiento(tabla, te, buffer_km)
        pred[te] = ajustar_predecir(tabla[tr], y[tr], tabla[te])
    return pred


def evaluar(ajustar_predecir, tabla, y, reps, nombre, buffer_km=0.0, n_jobs=1):
    """Corre `ajustar_predecir(tabla_tr, y_tr, tabla_te) -> pred` en cada fold y repetición.

    Todo preprocesamiento debe ocurrir dentro de ajustar_predecir, con solo las filas de
    entrenamiento. Con buffer_km > 0 el entrenamiento excluye los municipios cercanos a los
    de prueba (`mascara_entrenamiento`).
    """
    y = np.asarray(y, float)
    if n_jobs == 1:
        oof = [_una_rep(ajustar_predecir, tabla, y, f, buffer_km) for f in reps]
    else:
        oof = Parallel(n_jobs=n_jobs)(delayed(_una_rep)(ajustar_predecir, tabla, y, f, buffer_km) for f in reps)
    return Resultado(nombre, oof=list(oof), y=y)


def comparacion_emparejada(nuevo, base, minimo=7):
    """Victorias del nuevo sobre la base. Acepta Resultado (RMSE por fila) o arreglos por repetición."""
    a = nuevo.rmse_rep if isinstance(nuevo, Resultado) else np.asarray(nuevo)
    b = base.rmse_rep if isinstance(base, Resultado) else np.asarray(base)
    victorias = int((a < b).sum())
    return {"victorias": victorias, "repeticiones": len(a), "metrica_nuevo": float(a.mean()),
            "metrica_base": float(b.mean()), "diferencia_media": float((a - b).mean()),
            "aceptada": victorias >= minimo}


def _permutar(tabla, columnas, rng, por):
    """Copia de la tabla con el bloque `columnas` revuelto entre municipios."""
    claves = tabla[por].unique()
    medias = tabla.groupby(por)[columnas].mean()
    por_anio = tabla.set_index([por, "anio"])[columnas]
    mapa = dict(zip(claves, rng.permutation(claves)))
    otro = tabla[por].map(mapa)
    idx = pd.MultiIndex.from_arrays([otro, tabla["anio"]])
    nuevos = por_anio.reindex(idx).to_numpy(dtype=float, copy=True)
    faltan = np.isnan(nuevos)
    if faltan.any():
        nuevos[faltan] = medias.loc[otro].to_numpy()[faltan]
    tp = tabla.copy()
    tp[columnas] = nuevos
    return tp


def prueba_permutacion(ajustar_predecir, tabla, y, columnas, reps, n=N_PERM, semilla=SEED, por="CVEGEO",
                       metrica=None, buffer_km=0.0, n_jobs=N_JOBS):
    """p-valor de revolver el bloque `columnas` entre municipios.

    Se revuelve por municipio (`por`), no por fila, para conservar la estructura de la tabla.
    A cada municipio le tocan los valores de otro municipio, en todos sus años a la vez si el
    bloque es fijo. Si el bloque cambia por año, a cada fila le toca la del otro municipio en
    el mismo año cuando existe y, si no, la de su media.

    `metrica(resultado) -> arreglo por repetición`, o un dict nombre -> función para sacar
    varias métricas de las mismas permutaciones. Por omisión es el RMSE por fila. El p-valor
    es (1 + #{perm ≤ real}) / (n + 1), así que con n = 99 el mínimo es 0.01.
    """
    unica = not isinstance(metrica, dict)
    metricas_ = {"m": metrica or (lambda r: r.rmse_rep)} if unica else metrica
    y = np.asarray(y, float)

    def valores(t):
        r = evaluar(ajustar_predecir, t, y, reps, "perm", buffer_km)
        return {k: float(np.mean(f(r))) for k, f in metricas_.items()}

    real = valores(tabla)
    rng = np.random.default_rng(semilla)
    tablas = [_permutar(tabla, columnas, rng, por) for _ in range(n)]
    perm = Parallel(n_jobs=n_jobs)(delayed(valores)(tp) for tp in tablas)
    out = {}
    for k in metricas_:
        v = np.array([p[k] for p in perm])
        out[k] = {"metrica_real": real[k], "metrica_perm_media": float(v.mean()), "n": n,
                  "p": float((1 + (v <= real[k]).sum()) / (n + 1))}
    return out["m"] if unica else out
