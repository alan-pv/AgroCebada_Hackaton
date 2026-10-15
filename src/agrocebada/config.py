"""Rutas, constantes y mapeos compartidos por todo el proyecto."""
from pathlib import Path

# Raíz del repo: src/agrocebada/config.py -> subir tres niveles
RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "DATASET_RETO_AGRO_2026"
INTERIM = RAIZ / "data" / "interim"
PROCESSED = RAIZ / "data" / "processed"
OUTPUTS = RAIZ / "outputs"
MODELS = RAIZ / "models"
EXPERIMENTOS = RAIZ / "experimentos"
REPORTE = RAIZ / "reporte"

SEED = 2026

# Nombre del equipo registrado en la plataforma del reto, en minúsculas y con guiones bajos.
NOMBRE_EQUIPO = "los_bien_dotados"

CRS_GEO = "EPSG:4326"
CRS_METRICO = "EPSG:6372"  # México ITRF2008 / LCC, el mismo de la topografía

# Régimen de etiquetas por municipio (ver ROADMAP.md, sección 2.1). Las claves son los
# nombres exactos del campo Municipio del shapefile.
REGIMEN_POR_MUNICIPIO = {
    # A: rendimientos con dos decimales
    "Chignahuapan": "A",
    "Almoloya": "A",
    "Cuautepec de Hinojosa": "A",
    "Tepeapulco": "A",
    # B: rendimientos redondeados a 0.5 o 0.1
    "Singuilucan": "B",
    "Emiliano Zapata": "B",
    "Apan": "B",
    "Calpulalpan": "B",
    "Nanacamilpa de Mariano Arista": "B",
}
