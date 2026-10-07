import numpy as np
import pandas as pd

from agrocebada import config
from agrocebada.series import despike, whittaker


def _senal():
    x = np.arange(0, 73)
    return 0.2 + 0.6 * np.exp(-((x - 36) / 12.0) ** 2)


def test_whittaker_reproduce_senal_suave():
    senal = _senal()
    rng = np.random.default_rng(config.SEED)
    z = whittaker(senal + rng.normal(0, 0.01, len(senal)), lam=10.0)
    assert np.abs(z - senal).max() < 0.03


def test_whittaker_llena_huecos():
    senal = _senal()
    w = np.ones(len(senal))
    w[30:40] = 0
    y = senal.copy()
    y[30:40] = np.nan
    z = whittaker(y, w, lam=10.0)
    assert not np.isnan(z).any()
    assert np.abs(z - senal).max() < 0.06


def test_despike_quita_pico_sintetico():
    dias = np.arange(0, 120, 5)
    y = 0.3 + 0.004 * dias
    y[10] += 0.5
    pico = despike(dias, y, ventana=15)
    assert pico[10]
    assert pico.sum() == 1


def test_despike_no_marca_serie_suave():
    dias = np.arange(0, 120, 5)
    y = 0.3 + 0.5 * np.sin(dias / 40.0)
    assert not despike(dias, y, ventana=15).any()


def test_features_parquet():
    df = pd.read_parquet(config.PROCESSED / "features.parquet")
    assert len(df) == 197
    assert df["ID_POLIGONO"].is_unique
    assert "rendimiento" not in df.columns
