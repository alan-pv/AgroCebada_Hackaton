"""Construye la tabla económica por municipio del reto (issue #47).

Entradas (todas versionadas, no se descarga nada)
  data/externos/fira_agrocostos/cebada_agrocostos_crudo.csv   filas de cebada del CSV público de AgroCostos
  data/externos/inegi_inpc/inpc_mensual.csv                    INPC mensual de 2022 y 2025
  data/externos/siap/cebada_temporal_pv_municipal.csv          cierre agrícola municipal 2003 a 2025

Salidas
  data/externos/fira_agrocostos/zonas_usadas.csv   paquetes PV 2022 usados, con costo del crédito
  data/externos/inegi_inpc/factor_inpc.csv         factor de actualización 2022 a 2025
  data/externos/economia_municipal.csv             una fila por municipio del reto
  outputs/capa_economica.csv                       capa económica de las 197 parcelas

Costos. Se toma el paquete PV 2022 de temporal (tecnología TEMPORAL-MEJORADA-FERTILIZADA,
modalidad tradicional) de la zona que corresponde a cada municipio. Los campos de crédito del
paquete reconcilian así (probado abajo con `verificar_reconciliacion`)

    CostoTotal = TotalCredito + TotalAportacion + TotalIntereses + TotalNoFinanciable

TotalCredito es lo que presta el intermediario, TotalAportacion lo que pone el productor de lo
financiable, TotalIntereses el interés del avío sobre el crédito y TotalNoFinanciable lo que el
paquete no permite financiar. Hay una versión para acreditados menores a un monto en UDIS
(columnas MenorUDIS, tasa y aportación N1) y otra para mayores (MayorUDIS, N2). Se usa la de
menores porque el reto trata con productores chicos. El monto exacto de UDIS no viene en el
CSV, es lectura de los nombres de columna.

    costo_total_2022   = TotalMenorUDIS  (incluye el interés del avío)
    costo_credito_2022 = TotalCreditoMenorUDIS + TotalInteresesMenorUDIS  (capital más interés)

Actualización a 2025. Los dos se multiplican por el factor INPC general, promedio de 2025
entre promedio de 2022. Es una simplificación, pues el interés depende de la tasa y no del
INPC y la partición crédito y aportación se mantiene fija.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agrocebada.generalizable import siap as sp  # noqa: E402

EXT = RAIZ / "data" / "externos"
AGRO = EXT / "fira_agrocostos"
SALIDA = EXT / "economia_municipal.csv"
ANIO_COSTO, ANIO_PRECIO_INI, ANIO_PRECIO_FIN = 2022, 2023, 2025

# (CVEGEO, estado, nombre en el SIAP, nombre corto, régimen, zona AgroCostos, nota)
MUNICIPIOS = [
    ("13007", "Hidalgo", "Almoloya", "Almoloya", "A", "AGENCIAS HIDALGO"),
    ("13008", "Hidalgo", "Apan", "Apan", "B", "AGENCIAS HIDALGO"),
    ("13016", "Hidalgo", "Cuautepec de Hinojosa", "Cuautepec de Hinojosa", "A", "AGENCIAS HIDALGO"),
    ("13021", "Hidalgo", "Emiliano Zapata", "Emiliano Zapata", "B", "AGENCIAS HIDALGO"),
    ("13057", "Hidalgo", "Singuilucan", "Singuilucan", "B", "AGENCIAS HIDALGO"),
    ("13061", "Hidalgo", "Tepeapulco", "Tepeapulco", "A", "AGENCIAS HIDALGO"),
    ("21053", "Puebla", "Chignahuapan", "Chignahuapan", "A", "SIERRA NORTE PUEBLA"),
    ("29006", "Tlaxcala", "Calpulalpan", "Calpulalpan", "B", "AGENCIAS DE TLAXCALA"),
    ("29021", "Tlaxcala", "Nanacamilpa de Mariano Arista", "Nanacamilpa de Mariano Arista", "B",
     "AGENCIAS DE TLAXCALA"),
]
COLUMNAS_CRUDAS = [
    "Año", "Estado", "IdZona", "Zona", "Cultivo", "Tecnología", "Modalidad", "Estatus",
    "Rendimiento pesimista", "Rendimiento probable", "Rendimiento optimista", "Precio probable",
    "Ingreso probable", "TotalFinanciable", "TotalNoFinanciable", "AportacionN1", "AportacionN2",
    "TasaN1", "TasaN2", "TotalCreditoMenorUDIS", "TotalAportacionMenorUDIS",
    "TotalInteresesMenorUDIS", "TotalMenorUDIS", "TotalCreditoMayorUDIS",
    "TotalAportacionMayorUDIS", "TotalInteresesMayorUDIS", "TotalMayorUDIS", "CostoTotal",
    "UtilidadProbable", "CostoUnitario", "PuntoEquilibrio", "Inicio de siembra",
    "Fin de cosecha", "Fecha de termino del prestamo"]


def factor_inpc():
    """Promedio anual de 2025 entre promedio anual de 2022 (INPC mensual de INEGI)."""
    inpc = pd.read_csv(AGRO.parent / "inegi_inpc" / "inpc_mensual.csv")
    assert inpc.groupby("anio").size().eq(12).all()
    prom = inpc.groupby("anio").inpc_mensual.mean()
    f = pd.DataFrame({"inpc_promedio_2022": [prom[2022]], "inpc_promedio_2025": [prom[2025]],
                      "factor_inpc": [prom[2025] / prom[2022]]})
    return f


def zonas_usadas():
    raw = pd.read_csv(AGRO / "cebada_agrocostos_crudo.csv")
    z = raw[(raw["Año"] == ANIO_COSTO) & (raw["Ciclo corto"] == "PV")
            & raw["Tecnología"].eq("TEMPORAL-MEJORADA-FERTILIZADA")
            & raw["Modalidad"].eq("TRADICIONAL") & raw["Zona"].isin({m[5] for m in MUNICIPIOS})]
    z = z[COLUMNAS_CRUDAS].copy()
    assert len(z) == 3, z
    z["costo_total_2022"] = z.TotalMenorUDIS
    z["costo_credito_2022"] = z.TotalCreditoMenorUDIS + z.TotalInteresesMenorUDIS
    z["costo_credito_mayor_udis_2022"] = z.TotalCreditoMayorUDIS + z.TotalInteresesMayorUDIS
    verificar_reconciliacion(z)
    return z.rename(columns={"Zona": "zona_agrocostos"}).reset_index(drop=True)


def verificar_reconciliacion(z):
    for s in ("Menor", "Mayor"):
        suma = (z[f"TotalCredito{s}UDIS"] + z[f"TotalAportacion{s}UDIS"]
                + z[f"TotalIntereses{s}UDIS"] + z.TotalNoFinanciable)
        assert np.allclose(suma, z[f"Total{s}UDIS"], atol=1.0), (s, suma, z[f"Total{s}UDIS"])
    assert np.allclose(z.TotalMayorUDIS, z.CostoTotal, atol=0.01)
    # el crédito más la aportación cubren lo financiable
    assert np.allclose(z.TotalCreditoMenorUDIS + z.TotalAportacionMenorUDIS, z.TotalFinanciable,
                       atol=15)


def siap_municipal():
    raw = sp.leer()
    raw["rend_s"] = raw.produccion_t / raw.sembrada_ha
    raw["rep"] = sp.marca_repetido(raw, "rendimiento")
    filas = []
    for cve, est, nom, corto, reg, zona in MUNICIPIOS:
        g = raw[(raw.estado == est) & (raw.municipio == nom)].sort_values("anio")
        assert len(g) == 23 and g.anio.min() == 2003 and g.anio.max() == 2025, (nom, len(g))
        r = g[(g.anio >= ANIO_PRECIO_INI) & (g.anio <= ANIO_PRECIO_FIN)]
        frac = (g.siniestrada_ha / g.sembrada_ha).clip(0, 1)
        y = g.rend_s.to_numpy()
        g13 = g[g.anio >= 2013]
        filas.append({
            "CVEGEO": cve,
            "precio_2023_2025": float(np.average(r.precio_rural, weights=r.produccion_t)),
            "precio_min": float(r.precio_rural.min()), "precio_max": float(r.precio_rural.max()),
            "siniestralidad_2003_2025": float(g.siniestrada_ha.sum() / g.sembrada_ha.sum()),
            "siniestralidad_2013_2025": float(g13.siniestrada_ha.sum() / g13.sembrada_ha.sum()),
            "anios_perdida_20": int((frac > 0.2).sum()), "anios_perdida_50": int((frac > 0.5).sum()),
            "siap_rend_media": float(y.mean()), "siap_rend_sd": float(y.std(ddof=1)),
            "siap_rend_p10": float(np.percentile(y, 10)),
            "siap_frac_rend_repetido": float(g.rep.mean())})
    return pd.DataFrame(filas)


def construir():
    f = factor_inpc().iloc[0]
    z = zonas_usadas()
    m = pd.DataFrame(MUNICIPIOS, columns=["CVEGEO", "estado", "siap_nombre", "municipio",
                                          "regimen", "zona_agrocostos"]).drop(columns="siap_nombre")
    m = m.merge(z[["zona_agrocostos", "costo_total_2022", "costo_credito_2022",
                   "Rendimiento probable"]], on="zona_agrocostos", how="left")
    m = m.rename(columns={"Rendimiento probable": "rendimiento_paquete_probable"})
    m["factor_inpc"] = f.factor_inpc
    m["costo_total_2025"] = m.costo_total_2022 * f.factor_inpc
    m["costo_credito_2025"] = m.costo_credito_2022 * f.factor_inpc
    m = m.merge(siap_municipal(), on="CVEGEO")
    m["pe_total_t_ha"] = m.costo_total_2025 / m.precio_2023_2025
    m["pe_credito_t_ha"] = m.costo_credito_2025 / m.precio_2023_2025
    cols = ["CVEGEO", "estado", "municipio", "regimen", "zona_agrocostos", "costo_total_2022",
            "costo_credito_2022", "factor_inpc", "costo_total_2025", "costo_credito_2025",
            "precio_2023_2025", "precio_min", "precio_max", "pe_total_t_ha", "pe_credito_t_ha",
            "rendimiento_paquete_probable", "siniestralidad_2003_2025", "siniestralidad_2013_2025",
            "anios_perdida_20", "anios_perdida_50", "siap_rend_media", "siap_rend_sd",
            "siap_rend_p10", "siap_frac_rend_repetido"]
    return m[cols], z, factor_inpc()


def parcelas(tabla_municipal=None):
    """Capa económica de las 197 parcelas con outputs/predicciones.parquet."""
    from agrocebada.economia import capa_economica
    p = pd.read_parquet(RAIZ / "outputs" / "predicciones.parquet")
    e = capa_economica(p, tabla=tabla_municipal)
    cols = ["ID_POLIGONO", "conjunto", "estado", "municipio", "regimen", "area_ha", "pred", "p10"]
    return pd.concat([p[cols].reset_index(drop=True), e.drop(columns="ID_POLIGONO")], axis=1)


def main():
    m, z, f = construir()
    z.to_csv(AGRO / "zonas_usadas.csv", index=False)
    f.to_csv(AGRO.parent / "inegi_inpc" / "factor_inpc.csv", index=False)
    m.round(6).to_csv(SALIDA, index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(f.T)
    print(m.round(3).to_string())
    from agrocebada.economia import cargar_tabla
    c = parcelas(cargar_tabla(SALIDA))
    c.round(6).to_csv(RAIZ / "outputs" / "capa_economica.csv", index=False)
    p59 = c[c.conjunto == "PREDICCION"]
    for col in ("semaforo_credito", "semaforo_costos"):
        print(col, p59[col].value_counts().to_dict())


if __name__ == "__main__":
    main()
