"""Modelo generalizable de rendimiento de cebada de temporal a nivel municipio y año.

Se entrena con el cierre agrícola municipal del SIAP y con variables que pueden calcularse
para cualquier lugar (clima, suelo y topografía). No usa las etiquetas del reto ni toca el
modelo de la entrega. Ver docs/MUNICIPAL.md.
"""
from pathlib import Path

from parcelas.config import RAIZ

EXTERNOS = RAIZ / "data" / "externos"
SALIDA = RAIZ / "data" / "processed" / "generalizable"
ESTADOS = ("Hidalgo", "México", "Puebla", "Tlaxcala")
