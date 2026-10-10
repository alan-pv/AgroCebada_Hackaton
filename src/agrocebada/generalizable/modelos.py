"""Tabla de modelado, bases y modelos del rendimiento municipal.

Cada modelo es una función `ajustar_predecir(tr, y_tr, te) -> pred`, donde `tr` y `te` son
partes de la tabla municipio-año. Todo lo que aprende de los datos (medias, escalas,
hiperparámetros, pesos) se calcula con `tr`, dentro del fold.

Familias, según la información que supone disponible.
  Sin el año en curso. Lugar nuevo y año sin cosechar. Solo usan la historia de otros
    municipios y el ambiente. Responden a la pregunta de FIRA.
  Con la cosecha del año. Lugar nuevo, pero ya se conoce la cosecha de ese año en los
    municipios de entrenamiento. Aquí van también las anomalías de clima del año cuando se
    evalúan en un esquema espacial, porque en ese esquema las anomalías sirven sobre todo para
    reconocer el año y copiar su cosecha (son casi iguales en toda la región). Si el clima
    del año ayuda a pronosticar se mide solo en el esquema por año.

Pesos. Los modelos de nivel se ajustan sobre las medias municipales y cada municipio pesa su
superficie sembrada media, igual que en la métrica principal (`validacion`).
"""
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.cluster import KMeans
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, Hyperparameter, Kernel, Matern, WhiteKernel
from sklearn.linear_model import LassoCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..config import SEED
from . import SALIDA, siap

FIJAS = ["elev_m", "pendiente", "frac_durica", "frac_litica", "textura_fina", "textura_gruesa",
         "suelo_ph", "suelo_lp", "suelo_vr", "suelo_an", "clim_prec_may_oct", "clim_tmax_jul_ago",
         "clim_tmin_may_oct", "clim_amplitud"]
ANUALES = ["anom_prec_may_jun", "anom_prec_jul_ago", "anom_prec_sep_oct", "anom_tmax_may_jun",
           "anom_tmax_jul_ago", "anom_tmax_sep_oct"]
ANUALES_EXT = ANUALES + ["anom_tmin_may_oct", "anom_gdd_may_oct"]
XY = ["x_m", "y_m"]

# Bloques para la importancia. Se eligen por su papel agronómico, dos o tres variables por
# bloque, sin mirar su relación con el rendimiento.
#   temperatura: calor en floración y llenado (Tmax jul-ago) y frío del ciclo (Tmin may-oct).
#   lluvia: agua del ciclo completo y de la siembra, que decide el establecimiento.
#   topografía: altitud y pendiente.
#   suelo: tepetate (dúrica), roca somera (lítica) y textura fina.
BLOQUES = {
    "temperatura": ["clim_tmax_jul_ago", "clim_tmin_may_oct"],
    "lluvia": ["clim_prec_may_oct", "clim_prec_may_jun"],
    "topografia": ["elev_m", "pendiente"],
    "suelo": ["frac_durica", "frac_litica", "textura_fina"],
}
VARIABLES_BLOQUES = [c for cols in BLOQUES.values() for c in cols]

# Modelos simples fijados antes de evaluar con pesos y zona de exclusión. La lista sale de lo
# que se sabe de la cebada de temporal en el Altiplano, no de las correlaciones de estos datos.
#   a. Tmax jul-ago. El calor en floración y llenado de grano acorta el ciclo y baja el peso
#      del grano. Es la restricción más citada para cebada maltera en el Altiplano.
#   b. Elevación. Resume temperatura y heladas en una variable que se mide en cualquier lugar.
#   c. Tmax jul-ago y lluvia may-oct. Calor y agua, los dos límites del temporal. Es el
#      contendiente principal, fijado de antemano para la regla de decisión.
#   d. (c) más la fracción dúrica. El tepetate limita la raíz y el agua disponible.
#   e. (c) con efecto fijo de estado. Separa el ambiente de diferencias de manejo, de
#      variedad y de forma de estimar de cada delegación del SIAP.
SIMPLES = {
    "simple_a_tmax": (["clim_tmax_jul_ago"], False),
    "simple_b_elev": (["elev_m"], False),
    "simple_c_tmax_prec": (["clim_tmax_jul_ago", "clim_prec_may_oct"], False),
    "simple_d_tmax_prec_durica": (["clim_tmax_jul_ago", "clim_prec_may_oct", "frac_durica"], False),
    "simple_e_tmax_prec_estado": (["clim_tmax_jul_ago", "clim_prec_may_oct"], True),
}
CONTENDIENTE = "simple_c_tmax_prec"
POTENCIA_IDW = 2.0
ALFAS = np.logspace(-3, 2, 11)
N_GRUPOS_CV = 8


def cruzar(s, mun):
    """Une la tabla del SIAP con las variables municipales por estado y nombre normalizado.

    Se cruza por estado y clave porque hay homónimos entre estados (Tlaxco en Puebla y en
    Tlaxcala). Cada fila del SIAP debe encontrar a lo más un municipio.
    """
    return s.merge(mun, on=["estado", "clave"], how="inner", validate="many_to_one")


def tabla_modelado(objetivo="rend", sin_repetidos=False):
    """Tabla municipio-año del SIAP limpia, con las variables ambientales unidas.

    Con sin_repetidos=True se quitan las filas con marca_repetido (cifra copiada entre
    municipios del mismo estado y año) y los municipios que quedan con menos de MIN_ANIOS años.
    Agrega grupo_cv, un grupo espacial por municipio (k-medias sobre las coordenadas, sin la
    etiqueta) para la validación interna de los hiperparámetros.
    """
    d = siap.tabla(filtro="sembrada" if objetivo == "rend_sembrada" else "cosechada")
    if sin_repetidos:
        d = d[~d.marca_repetido]
        d = d[d.groupby(["estado", "clave"]).anio.transform("size") >= siap.MIN_ANIOS]
    mun = pd.read_parquet(SALIDA / "municipios.parquet")
    clima = pd.read_parquet(SALIDA / "clima_anual.parquet")
    d = cruzar(d, mun.drop(columns=["municipio"]))
    d = d.merge(clima, on=["CVEGEO", "anio"], how="left")
    d["y"] = d[objetivo]
    m = d.drop_duplicates("CVEGEO")
    km = KMeans(N_GRUPOS_CV, n_init=10, random_state=SEED).fit(m[XY].to_numpy())
    d["grupo_cv"] = d.CVEGEO.map(pd.Series(km.labels_, index=m.CVEGEO.to_numpy()))
    return d.reset_index(drop=True)


# ------------------------------------------------------------------- bases

def media_global(tr, y, te):
    return np.full(len(te), y.mean())


def media_estatal(tr, y, te):
    m = pd.Series(y, index=tr.index).groupby(tr.estado).mean()
    return te.estado.map(m).fillna(y.mean()).to_numpy()


def media_estatal_anio(tr, y, te):
    s = pd.Series(y, index=tr.index)
    m = s.groupby([tr.estado, tr.anio]).mean()
    idx = pd.MultiIndex.from_arrays([te.estado, te.anio])
    return pd.Series(m.reindex(idx).to_numpy()).fillna(pd.Series(media_estatal(tr, y, te))).to_numpy()


def _idw(xy_tr, v_tr, xy_te, potencia=POTENCIA_IDW):
    d = np.sqrt(((xy_te[:, None, :] - xy_tr[None, :, :]) ** 2).sum(-1)) / 1000.0
    w = 1.0 / np.maximum(d, 1.0) ** potencia
    return (w * v_tr[None, :]).sum(1) / w.sum(1)


def _medias_municipio(tr, y):
    """Media de y por municipio, con coordenadas, varianza de la media y superficie media."""
    g = pd.DataFrame({"clave": tr.CVEGEO.to_numpy(), "x": tr.x_m.to_numpy(), "y_m": tr.y_m.to_numpy(), "v": y})
    m = g.groupby("clave").agg(x=("x", "first"), y_m=("y_m", "first"), v=("v", "mean"), s2=("v", "var"),
                               n=("v", "size"))
    m["var_media"] = (m.s2 / m.n).fillna(m.s2.median() / m.n)
    return m


def idw_nivel(tr, y, te):
    """Interpolación por inverso de la distancia del rendimiento medio de los municipios vecinos."""
    m = _medias_municipio(tr, y)
    return _idw(m[["x", "y_m"]].to_numpy(), m.v.to_numpy(), te[["x_m", "y_m"]].to_numpy())


def idw_anio(tr, y, te):
    """Interpolación por inverso de la distancia del rendimiento de los vecinos en el mismo año."""
    pred = np.empty(len(te))
    xy_te = te[["x_m", "y_m"]].to_numpy()
    for a in np.unique(te.anio):
        mt, me = (tr.anio == a).to_numpy(), (te.anio == a).to_numpy()
        if mt.sum() == 0:
            pred[me] = idw_nivel(tr, y, te[me])
            continue
        pred[me] = _idw(tr.loc[mt, ["x_m", "y_m"]].to_numpy(), y[mt], xy_te[me])
    return pred


def ruido_minimo(m):
    """Cota inferior del ruido blanco del GP, en las unidades normalizadas de normalize_y.

    La media de un municipio tiene un error propio (varianza entre años entre número de años).
    Un GP sin ruido interpola esas medias como si fueran exactas. La cota es la mitad de la
    mediana de esa varianza, relativa a la varianza entre municipios. Se calcula en el fold.
    """
    return float(max(0.5 * m.var_media.median() / max(m.v.var(), 1e-9), 1e-3))


def _gp_espacial(ruido_min=1e-4):
    k = ConstantKernel(0.2, (1e-3, 10)) * Matern(30.0, (2.0, 500.0), nu=1.5) \
        + WhiteKernel(max(0.05, 2 * ruido_min), (ruido_min, 2))
    return GaussianProcessRegressor(k, normalize_y=True, n_restarts_optimizer=2, random_state=SEED)


def _kriging_medias(m, te):
    gp = _gp_espacial(ruido_minimo(m)).fit(m[["x", "y_m"]].to_numpy() / 1000.0, m.v.to_numpy())
    return gp.predict(te[["x_m", "y_m"]].to_numpy() / 1000.0)


def kriging_nivel(tr, y, te):
    """Proceso gaussiano sobre las coordenadas (km) de las medias municipales."""
    return _kriging_medias(_medias_municipio(tr, y), te)


def media_propia(tr, y, te):
    """Media histórica del mismo municipio (solo tiene sentido en el esquema por año)."""
    m = pd.Series(y, index=tr.index).groupby(tr.CVEGEO).mean()
    return te.CVEGEO.map(m).fillna(y.mean()).to_numpy()


# ------------------------------------------------------- regresión de nivel

def _xy_nivel(tr, y, cols):
    """Medias municipales de y y de las columnas, con el peso (superficie sembrada media).

    Si la tabla no trae superficie, cada municipio pesa su número de años.
    """
    g = tr[["CVEGEO"] + list(cols)].assign(v=y).groupby("CVEGEO").mean()
    if "sembrada_ha" in tr:
        w = tr.groupby("CVEGEO").sembrada_ha.mean().reindex(g.index)
    else:
        w = tr.groupby("CVEGEO").size().reindex(g.index).astype(float)
    return g[list(cols)], g.v.to_numpy(), w.to_numpy()


def _ridge_pesos(X, v, w, alfa):
    """Ridge con pesos, sobre variables estandarizadas con los pesos. Intercepto sin penalizar.

    Devuelve la función que predice. alfa = 0 es mínimos cuadrados ponderados. Los pesos se
    normalizan a suma 1, así que alfa se compara contra correlaciones (entre 0 y 1).
    """
    X, v = np.asarray(X, float), np.asarray(v, float)
    w = np.asarray(w, float) / np.sum(w)
    mu = w @ X
    sd = np.sqrt(w @ (X - mu) ** 2)
    sd = np.where(sd < 1e-9, 1.0, sd)
    Z = (X - mu) / sd
    vm = w @ v
    A = Z.T @ (w[:, None] * Z) + (alfa + 1e-10) * np.eye(X.shape[1])
    b = np.linalg.solve(A, Z.T @ (w * (v - vm)))
    return lambda Xn: vm + ((np.asarray(Xn, float) - mu) / sd) @ b


def _alfa_agrupado(X, v, w, grupos, alfas=ALFAS):
    """Alfa con menor error ponderado al dejar fuera grupos espaciales completos."""
    X, v, w, grupos = (np.asarray(a) for a in (X, v, w, grupos))
    ids = np.unique(grupos)
    if len(ids) < 3:
        return float(alfas[len(alfas) // 2])
    err = []
    for a in alfas:
        e = 0.0
        for g in ids:
            te = grupos == g
            f = _ridge_pesos(X[~te], v[~te], w[~te], a)
            e += (w[te] * (f(X[te]) - v[te]) ** 2).sum()
        err.append(e)
    return float(alfas[int(np.argmin(err))])


def _efecto_estado(tr, y, te, cols, alfa=0.0):
    """Regresión con efecto fijo de estado (estimador dentro de estado, con pesos).

    Se quitan las medias ponderadas de cada estado a y y a las variables, se ajusta la
    pendiente sobre esas diferencias y se predice con la media del estado más la pendiente por
    la diferencia del lugar contra su estado. Si el estado no está en el entrenamiento se usan
    las medias globales.
    """
    X, v, w = _xy_nivel(tr, y, cols)
    est = tr.groupby("CVEGEO").estado.first().reindex(X.index).to_numpy()
    df = X.assign(_v=v, _w=w, _e=est)

    def medias(g):
        return pd.Series(np.average(g[list(cols) + ["_v"]], axis=0, weights=g._w), index=list(cols) + ["_v"])

    me = df.groupby("_e")[list(cols) + ["_v", "_w"]].apply(medias)
    glob = medias(df)
    Xd = X.to_numpy() - me.loc[est, cols].to_numpy()
    vd = v - me.loc[est, "_v"].to_numpy()
    f = _ridge_pesos(Xd, vd, w, alfa)
    base = np.array(me.reindex(te.estado.to_numpy())[list(cols) + ["_v"]], dtype=float)
    faltan = np.isnan(base[:, -1])
    base[faltan] = glob[list(cols) + ["_v"]].to_numpy()
    return base[:, -1] + f(te[cols].to_numpy() - base[:, :-1])


def nivel_lineal(cols, estado=False, alfas=None):
    """Regresión de nivel sobre las medias municipales, ponderada por superficie.

    alfas=None es mínimos cuadrados ponderados (modelos simples). Con una lista de alfas es
    ridge y el alfa se elige con validación interna por grupos espaciales (grupo_cv).
    estado=True agrega efecto fijo de estado.
    """
    cols = list(cols)

    def f(tr, y, te):
        if estado:
            return _efecto_estado(tr, y, te, cols)
        X, v, w = _xy_nivel(tr, y, cols)
        alfa = 0.0
        if alfas is not None:
            g = tr.groupby("CVEGEO").grupo_cv.first().reindex(X.index).to_numpy()
            alfa = _alfa_agrupado(X.to_numpy(), v, w, g, alfas)
        return _ridge_pesos(X.to_numpy(), v, w, alfa)(te[cols].to_numpy())
    return f


def ridge(cols):
    """Ridge de nivel con alfa por validación interna agrupada espacialmente."""
    return nivel_lineal(cols, alfas=ALFAS)


def lasso(cols):
    """Lasso de nivel con pesos y validación interna por grupos espaciales. Selecciona variables en el fold."""
    cols = list(cols)

    def f(tr, y, te):
        X, v, w = _xy_nivel(tr, y, cols)
        g = tr.groupby("CVEGEO").grupo_cv.first().reindex(X.index).to_numpy()
        k = min(5, len(np.unique(g)))
        cv = list(GroupKFold(k).split(X, v, g)) if k >= 2 else 3
        m = make_pipeline(StandardScaler(), LassoCV(cv=cv, max_iter=20000))
        m.fit(X, v, lassocv__sample_weight=w / w.mean())
        return m.predict(te[cols])
    return f


# ----------------------------------------------------------------- modelos

def lgbm(cols, anuales=()):
    """LightGBM poco profundo sobre filas municipio-año."""
    todas = list(cols) + list(anuales)

    def f(tr, y, te):
        m = LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=7, max_depth=3, min_child_samples=40,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0,
                          random_state=SEED, verbose=-1).fit(tr[todas], y)
        return m.predict(te[todas])
    return f


def lgbm_indicadoras_anio(cols):
    """LightGBM con indicadoras de año en lugar de anomalías de clima.

    Sirve de control. Si da lo mismo que las anomalías, lo que ayudaba era reconocer el año
    (y su cosecha en los municipios de entrenamiento), no el clima.
    """
    cols = list(cols)

    def f(tr, y, te):
        anios = np.sort(tr.anio.unique())
        ind = lambda t: pd.DataFrame({f"a{a}": (t.anio.to_numpy() == a).astype(float) for a in anios}, index=t.index)
        X, Xt = pd.concat([tr[cols], ind(tr)], axis=1), pd.concat([te[cols], ind(te)], axis=1)
        m = LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=7, max_depth=3, min_child_samples=40,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0,
                          random_state=SEED, verbose=-1).fit(X, y)
        return m.predict(Xt)
    return f


def gp_ambiente(cols, espacial=True):
    """Proceso gaussiano sobre las medias municipales con variables ambientales estandarizadas.

    Con espacial=True agrega un kernel sobre las coordenadas, de modo que el GP combina el
    ambiente con la interpolación de vecinos (kriging con covariables). El ruido blanco tiene
    la cota inferior de `ruido_minimo`, para que no interpole las medias como si fueran exactas.
    """
    def f(tr, y, te):
        X, v, _ = _xy_nivel(tr, y, cols + ["x_m", "y_m"])
        rmin = ruido_minimo(_medias_municipio(tr, y))
        blanco = WhiteKernel(max(0.05, 2 * rmin), (rmin, 2))
        esc = StandardScaler().fit(X[cols])
        Z = esc.transform(X[cols])
        Zt = esc.transform(te[cols])
        A, At = Z, Zt
        if espacial:
            # Coordenadas en unidades de 100 km.
            A = np.hstack([Z, X[["x_m", "y_m"]].to_numpy() / 1e5])
            At = np.hstack([Zt, te[["x_m", "y_m"]].to_numpy() / 1e5])
            k = _kernel_mixto(len(cols)) + blanco
        else:
            k = ConstantKernel(0.2, (1e-3, 10)) * RBF(np.full(len(cols), 3.0), (0.3, 100.0)) + blanco
        gp = GaussianProcessRegressor(k, normalize_y=True, n_restarts_optimizer=1, random_state=SEED)
        gp.fit(A, v)
        return gp.predict(At)
    return f


def _kernel_mixto(p):
    """Suma de un RBF sobre las p variables ambientales y un Matern sobre las 2 coordenadas."""
    amb = ConstantKernel(0.2, (1e-3, 10)) * _Sub(RBF(np.full(p, 3.0), (0.3, 100.0)), slice(0, p))
    esp = ConstantKernel(0.2, (1e-3, 10)) * _Sub(Matern(0.3, (0.02, 5.0), nu=1.5), slice(p, p + 2))
    return amb + esp


class _Sub(Kernel):
    """Aplica un kernel a un subconjunto de columnas."""

    def __init__(self, base, cols):
        self.base = base
        self.cols = cols

    @property
    def hyperparameters(self):
        return [Hyperparameter("base__" + h.name, h.value_type, h.bounds, h.n_elements)
                for h in self.base.hyperparameters]

    @property
    def theta(self):
        return self.base.theta

    @theta.setter
    def theta(self, t):
        self.base.theta = t

    @property
    def bounds(self):
        return self.base.bounds

    def get_params(self, deep=True):
        p = {"base": self.base, "cols": self.cols}
        if deep:
            p.update({"base__" + k: v for k, v in self.base.get_params().items()})
        return p

    def __call__(self, X, Y=None, eval_gradient=False):
        Y = None if Y is None else Y[:, self.cols]
        return self.base(X[:, self.cols], Y, eval_gradient=eval_gradient)

    def diag(self, X):
        return self.base.diag(X[:, self.cols])

    def is_stationary(self):
        return self.base.is_stationary()

    def clone_with_theta(self, theta):
        k = _Sub(self.base.clone_with_theta(theta), self.cols)
        return k


def anomalia(tr, y, te, anuales=ANUALES, tipo="ridge"):
    """Desviación del año respecto de la media del municipio, explicada por el clima del año.

    Se ajusta con y menos la media del municipio en el entrenamiento. No usa el nivel.
    """
    from sklearn.linear_model import RidgeCV
    a = y - pd.Series(y, index=tr.index).groupby(tr.CVEGEO).transform("mean").to_numpy()
    cols = list(anuales)
    if tipo == "ridge":
        m = make_pipeline(StandardScaler(), RidgeCV(np.logspace(-2, 4, 30))).fit(tr[cols], a)
    else:
        m = LGBMRegressor(n_estimators=200, learning_rate=0.03, num_leaves=5, max_depth=2, min_child_samples=60,
                          subsample=0.8, subsample_freq=1, reg_lambda=5.0, random_state=SEED,
                          verbose=-1).fit(tr[cols], a)
    return m.predict(te[cols])


def nivel_mas_anomalia(nivel, anuales=ANUALES, tipo="ridge"):
    """Nivel del lugar (cualquier función de nivel) más la anomalía del clima del año."""
    def f(tr, y, te):
        return nivel(tr, y, te) + anomalia(tr, y, te, anuales, tipo)
    return f


def efecto_estado_anio(tr, y, te):
    """Anomalía media de los municipios de entrenamiento del mismo estado y año (cero si no hay)."""
    a = y - pd.Series(y, index=tr.index).groupby(tr.CVEGEO).transform("mean").to_numpy()
    m = pd.Series(a, index=tr.index).groupby([tr.estado, tr.anio]).mean()
    return m.reindex(pd.MultiIndex.from_arrays([te.estado, te.anio])).fillna(0).to_numpy()


def kriging_mas_efecto_estado_anio(tr, y, te):
    return kriging_nivel(tr, y, te) + efecto_estado_anio(tr, y, te)


def kriging_residual(nivel_amb):
    """Nivel ambiental más kriging de sus residuos municipales (kriging con deriva).

    Cerca de municipios con SIAP corrige el modelo ambiental con lo observado. Lejos, el
    kriging de residuos regresa a la media de los residuos y queda el modelo ambiental.
    """
    def f(tr, y, te):
        base_tr = nivel_amb(tr, y, tr)
        return nivel_amb(tr, y, te) + _kriging_medias(_medias_municipio(tr, y - base_tr), te)
    return f


ANIO_REFERENCIA = 2025


def pendiente_comun(tr, y):
    """Tendencia anual común (t/ha por año), estimada dentro de cada municipio y promediada.

    Es la pendiente de la regresión de y contra el año después de quitar la media de cada
    municipio a las dos variables, así que no la confunde el nivel de los municipios.
    """
    g = tr.CVEGEO.to_numpy()
    a = tr.anio.to_numpy(float)
    ya = y - pd.Series(y).groupby(g).transform("mean").to_numpy()
    aa = a - pd.Series(a).groupby(g).transform("mean").to_numpy()
    return float((ya * aa).sum() / (aa * aa).sum())


def con_tendencia(f, referencia=ANIO_REFERENCIA):
    """Quita la tendencia común antes de ajustar `f` y la devuelve al predecir.

    El modelo interno ve rendimientos llevados al año de referencia. La predicción de un año
    dado es la de referencia más la pendiente por la diferencia de años.
    """
    def g(tr, y, te):
        b = pendiente_comun(tr, y)
        ajust = y - b * (tr.anio.to_numpy() - referencia)
        return f(tr, ajust, te) + b * (te.anio.to_numpy() - referencia)
    return g


# ---------------------------------------------------------------- catálogo

T = con_tendencia


def simples():
    """Los cinco modelos simples y el kriging de los residuos de cada uno."""
    out = {}
    for nombre, (cols, estado) in SIMPLES.items():
        out[nombre] = ("ambiente simple", T(nivel_lineal(cols, estado)))
    for nombre, (cols, estado) in SIMPLES.items():
        out[f"kriging_residuos_{nombre}"] = ("ambiente+ubicacion", T(kriging_residual(nivel_lineal(cols, estado))))
    return out


def catalogo_buffer():
    """Modelos de la curva con zona de exclusión (esquema principal). Nombre -> (familia, función)."""
    return {
        "media_global": ("base", T(media_global)),
        "media_estatal": ("base", T(media_estatal)),
        "idw_vecinos": ("base", T(idw_nivel)),
        "kriging_vecinos": ("base", T(kriging_nivel)),
        **simples(),
        "ridge_ambiente": ("ambiente", T(ridge(FIJAS))),
        "lasso_ambiente": ("ambiente", T(lasso(FIJAS))),
    }


def catalogo_espacial():
    """Modelos del esquema espacial de cinco folds, sin zona de exclusión."""
    return {
        **catalogo_buffer(),
        "gp_ambiente": ("ambiente", T(gp_ambiente(FIJAS, espacial=False))),
        "lgbm_ambiente": ("ambiente", T(lgbm(FIJAS))),
        "gp_ambiente_espacial": ("ambiente+ubicacion", T(gp_ambiente(FIJAS, espacial=True))),
        "lgbm_ubicacion": ("ubicacion", T(lgbm(XY))),
        "lgbm_ubicacion_ambiente": ("ambiente+ubicacion", T(lgbm(XY + FIJAS))),
        # Usan la cosecha del año de los municipios de entrenamiento, directa o a través de
        # las anomalías de clima, que en este esquema reconocen el año.
        "lgbm_ubicacion_anomalias": ("con cosecha del año", T(lgbm(XY, ANUALES_EXT))),
        "lgbm_ubicacion_indicadoras_anio": ("con cosecha del año", T(lgbm_indicadoras_anio(XY))),
        "kriging_mas_anomalia": ("con cosecha del año", T(nivel_mas_anomalia(kriging_nivel, ANUALES_EXT, "lgbm"))),
        "kriging_mas_efecto_estado_anio": ("con cosecha del año", T(kriging_mas_efecto_estado_anio)),
        "media_estatal_anio": ("con cosecha del año", media_estatal_anio),
        "idw_vecinos_anio": ("con cosecha del año", idw_anio),
    }


def catalogo_anio():
    """Esquema por año: la prueba de pronóstico de un año nuevo con el clima del año."""
    return {
        "media_global": ("base", media_global),
        "media_propia": ("base", media_propia),
        "media_propia_tendencia": ("base", T(media_propia)),
        "propia_mas_anomalia_ridge": ("clima del año", T(nivel_mas_anomalia(media_propia, ANUALES_EXT))),
        "propia_mas_anomalia_lgbm": ("clima del año", T(nivel_mas_anomalia(media_propia, ANUALES_EXT, "lgbm"))),
    }


def modelo(nombre):
    """Función de un modelo por nombre, buscando en los catálogos espacial y por año."""
    return {**catalogo_anio(), **catalogo_espacial()}[nombre][1]
