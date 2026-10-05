"""Registro de experimentos en experimentos/registro.csv (una fila por experimento)."""
import csv
from datetime import datetime

from .config import EXPERIMENTOS

ARCHIVO_REGISTRO = EXPERIMENTOS / "registro.csv"
ENCABEZADO = [
    "fecha", "autor", "experimento", "bloque", "n_features", "features", "modelo",
    "rmse_A", "mae_A", "r2_A", "rmse_A_std", "rmse_B", "mae_B", "r2_B",
    "rmse_regimen_A", "rmse_regimen_B", "rmse_estado_A",
    "victorias", "p_permutacion", "aceptada", "notas",
]


def _grupos(d):
    return " ".join(f"{k}={v['rmse']:.3f}" for k, v in d.items())


def _abreviar(features, maximo=8):
    f = list(features)
    return ",".join(f[:maximo]) + (f",...(+{len(f) - maximo})" if len(f) > maximo else "")


def registrar(resultado, nombre, bloque, features, modelo, autor="alan-pv", decision=None,
              notas="", ruta=ARCHIVO_REGISTRO):
    """Añade una fila al registro.

    resultado: salida de `evaluate` con esquema "AB" (dict) o un Resultado suelto de A o B.
    decision: dict de `regla_decision`, o None si no aplica.
    """
    res = resultado if isinstance(resultado, dict) else {resultado.esquema: resultado}
    a, b = res.get("A"), res.get("B")
    dec = decision or {}
    features = list(features)
    fila = {
        "fecha": datetime.now().isoformat(timespec="seconds"), "autor": autor,
        "experimento": nombre, "bloque": bloque, "n_features": len(features),
        "features": _abreviar(features), "modelo": modelo,
        "rmse_A": f"{a.rmse:.4f}" if a else "", "mae_A": f"{a.mae:.4f}" if a else "",
        "r2_A": f"{a.r2:.4f}" if a else "", "rmse_A_std": f"{a.rmse_std:.4f}" if a else "",
        "rmse_B": f"{b.rmse:.4f}" if b else "", "mae_B": f"{b.mae:.4f}" if b else "",
        "r2_B": f"{b.r2:.4f}" if b else "",
        "rmse_regimen_A": _grupos(a.por_regimen) if a else "",
        "rmse_regimen_B": _grupos(b.por_regimen) if b else "",
        "rmse_estado_A": _grupos(a.por_estado) if a else "",
        "victorias": dec.get("victorias", ""),
        "p_permutacion": "" if dec.get("p_permutacion") is None else f"{dec['p_permutacion']:.4f}",
        "aceptada": dec.get("aceptada", ""), "notas": notas,
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists()
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ENCABEZADO)
        if nuevo:
            w.writeheader()
        w.writerow(fila)
