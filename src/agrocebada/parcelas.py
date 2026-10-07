"""Construye la tabla de parcelas (contrato `data/processed/parcelas.parquet`).

Uso:
    uv run python -m agrocebada.parcelas
"""
import geopandas as gpd
import numpy as np

from .config import CRS_GEO, CRS_METRICO, PROCESSED, REGIMEN_POR_MUNICIPIO
from .io import leer_etiquetas, leer_parcelas


def construir():
    """Devuelve (GeoDataFrame con geometrías en EPSG:4326, DataFrame plano)."""
    gdf = leer_parcelas()
    faltan = sorted(set(gdf.Municipio) - set(REGIMEN_POR_MUNICIPIO))
    sobran = sorted(set(REGIMEN_POR_MUNICIPIO) - set(gdf.Municipio))
    if faltan or sobran:
        raise ValueError(f"REGIMEN_POR_MUNICIPIO no coincide con el shapefile. "
                         f"Sin régimen: {faltan}. Sin parcelas: {sobran}")

    # Centroide y medidas en el CRS métrico; lon/lat se obtienen reproyectando el centroide
    m = gdf.to_crs(CRS_METRICO)
    cent = m.geometry.centroid
    cent_geo = cent.to_crs(CRS_GEO)
    area_m2 = m.geometry.area
    perim = m.geometry.length

    df = gdf.drop(columns="geometry").rename(
        columns={"Estado": "estado", "Municipio": "municipio", "Cultivo": "cultivo_texto"})
    df["regimen"] = df["municipio"].map(REGIMEN_POR_MUNICIPIO)
    df["lon"] = cent_geo.x.values
    df["lat"] = cent_geo.y.values
    df["x_m"] = cent.x.values
    df["y_m"] = cent.y.values
    df["area_geom_ha"] = (area_m2 / 1e4).values
    df["perimetro_m"] = perim.values
    df["compacidad"] = (4 * np.pi * area_m2 / perim**2).values

    et = leer_etiquetas().rename(columns={"AREA_HA": "area_ha", "RENDIMIENTO_T_HA": "rendimiento",
                                          "CONJUNTO": "conjunto"})
    df = df.merge(et, on="ID_POLIGONO", how="outer", validate="one_to_one", indicator=True)
    if (df["_merge"] != "both").any():
        raise ValueError("Los IDs de etiquetas y shapefile no coinciden")
    df = df.drop(columns="_merge")

    cols = ["ID_POLIGONO", "estado", "municipio", "regimen", "lon", "lat", "x_m", "y_m", "area_ha",
            "area_geom_ha", "perimetro_m", "compacidad", "conjunto", "rendimiento", "cultivo_texto"]
    df = df[cols].sort_values("ID_POLIGONO").reset_index(drop=True)
    geo = gdf[["ID_POLIGONO", "geometry"]].merge(df.drop(columns=["lon", "lat"]), on="ID_POLIGONO")
    geo = geo.sort_values("ID_POLIGONO").reset_index(drop=True)
    return geo, df


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    geo, df = construir()
    df.to_parquet(PROCESSED / "parcelas.parquet", index=False)
    # El GPKG cambia de bytes en cada escritura; solo se reescribe si cambió el contenido
    ruta_gpkg = PROCESSED / "parcelas.gpkg"
    if not ruta_gpkg.exists() or not gpd.read_file(ruta_gpkg)[geo.columns].equals(geo):
        geo.to_file(ruta_gpkg, driver="GPKG")
    print(f"{len(df)} parcelas -> {PROCESSED / 'parcelas.parquet'} y parcelas.gpkg")


if __name__ == "__main__":
    main()
