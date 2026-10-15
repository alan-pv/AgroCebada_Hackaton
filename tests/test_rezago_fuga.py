"""El rezago espacial y el modelo final no ven las etiquetas del fold de prueba."""
import numpy as np
from agrocebada import cv, modelos
from agrocebada.train_final import cargar_datos
from agrocebada.transformers import RezagoEspacial

X, y, X59 = cargar_datos()


def _fold(rep=0, f=0):
    p = cv.particiones_A(X)
    p = p[(p.repeticion == rep) & (p.fold == f)]
    te = X.index.get_indexer(p.ID_POLIGONO)
    tr = np.setdiff1d(np.arange(len(X)), te)
    return tr, te


def _manual(i, xtr, ytr, rtr, xq, rq, radio=400.0, k=10):
    d = np.hypot(*(xtr - xq).T)
    ok = (d <= radio) & (rtr == rq)
    idx = np.flatnonzero(ok)
    idx = idx[np.argsort(d[idx])][:k]
    if len(idx) == 0:
        return float(ytr[rtr == rq].mean()), 0
    w = 1 / np.maximum(d[idx], 1.0)
    return float((w * ytr[idx]).sum() / w.sum()), len(idx)


def test_rezago_ignora_etiquetas_del_fold_de_prueba():
    tr, te = _fold()
    rz = RezagoEspacial(k=10, radio_m=400.0, mismo_regimen=True)
    rz.fit_transform(X.iloc[tr], y.iloc[tr])
    a = rz.transform(X.iloc[te])[:, 0]
    # Cambiar las etiquetas del fold de prueba no debe mover el rezago de prueba
    y2 = y.copy(); y2.iloc[te] = 999.0
    rz2 = RezagoEspacial(k=10, radio_m=400.0, mismo_regimen=True)
    rz2.fit_transform(X.iloc[tr], y2.iloc[tr])
    b = rz2.transform(X.iloc[te])[:, 0]
    assert np.allclose(a, b)


def test_rezago_coincide_con_calculo_manual_y_relleno_es_media_del_entrenamiento():
    tr, te = _fold()
    rz = RezagoEspacial(k=10, radio_m=400.0, mismo_regimen=True).fit(X.iloc[tr], y.iloc[tr])
    out = rz.transform(X.iloc[te])
    xtr = X.iloc[tr][["x_m", "y_m"]].to_numpy(); ytr = y.iloc[tr].to_numpy(); rtr = X.iloc[tr].regimen.to_numpy()
    n_sin = 0
    for j, i in enumerate(te):
        esp, n = _manual(i, xtr, ytr, rtr, X.iloc[i][["x_m", "y_m"]].to_numpy(float), X.iloc[i].regimen)
        assert abs(out[j, 0] - esp) < 1e-9
        n_sin += n == 0
    assert n_sin > 0, "el fold debe tener al menos una parcela sin vecinos para probar el relleno"
    # la media de relleno sale solo del entrenamiento del fold
    for r in "AB":
        assert abs(rz.media_reg_[r] - ytr[rtr == r].mean()) < 1e-12


def test_fit_transform_excluye_la_propia_parcela_y_su_etiqueta_en_el_relleno():
    tr, _ = _fold()
    Xt, yt = X.iloc[tr], y.iloc[tr]
    base = RezagoEspacial(k=10, radio_m=400.0, mismo_regimen=True).fit_transform(Xt, yt)[:, 0]
    # Cambiar la etiqueta de UNA parcela no debe cambiar su propio rezago de entrenamiento
    for pos in (0, 5, 17, 40):
        y2 = yt.copy(); y2.iloc[pos] += 50
        nuevo = RezagoEspacial(k=10, radio_m=400.0, mismo_regimen=True).fit_transform(Xt, y2)[:, 0]
        assert abs(nuevo[pos] - base[pos]) < 1e-12


def test_pipeline_completo_no_ve_etiquetas_de_prueba():
    tr, te = _fold()
    m = modelos.candidato().fit(X.iloc[tr], y.iloc[tr])
    p1 = m.predict(X.iloc[te])
    y2 = y.copy(); y2.iloc[te] = -123.0
    m2 = modelos.candidato().fit(X.iloc[tr], y2.iloc[tr])
    assert np.allclose(p1, m2.predict(X.iloc[te]))
