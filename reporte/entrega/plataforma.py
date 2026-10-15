"""Prepara los textos de entrega a partir de las secciones LaTeX.

1. Escribe referencias.tex con las obras citadas, en estilo IEEE y en orden de primera cita. Toma cada \\bibitem de los
   reportes del repositorio o de bibitems_extra.tex.
2. Escribe plataforma/NN_seccion.txt, el texto plano de cada campo de la plataforma, con las citas como [n].
3. Escribe conteo_palabras.md y avisa si alguna sección no cumple su límite.

Uso, desde reporte/entrega:  python3 plataforma.py   (antes y después de compilar main.tex)
"""
import re
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
SECCIONES = [
    ("01_introduccion", "Introducción", 400, 550),
    ("02_justificacion", "Justificación", 100, 200),
    ("03_objetivos", "Objetivos", None, 200),
    ("04_metodologia", "Metodología", 600, 700),
    ("05_resultados", "Resultados y discusión", None, 800),
    ("06_inclusion_financiera", "Uso de la ciencia de datos en la inclusión financiera del sector agro", None, 300),
    ("07_conclusiones", "Conclusiones", None, 400),
]
FUENTES_BIB = [
    AQUI / "bibitems_extra.tex",
    RAIZ / "docs/reporte_modelo/secciones/referencias.tex",
    RAIZ / "docs/reporte_generalizable/secciones/referencias.tex",
    RAIZ / "docs/reporte_contexto/secciones/referencias.tex",
]


def bibitems():
    items = {}
    for f in FUENTES_BIB:
        texto = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem\{|\\end\{thebibliography\}|\Z)", texto, re.S):
            items.setdefault(m.group(1), m.group(2).strip())
    return items


def orden_citas():
    orden = []
    # Primero las secciones del reporte y después el anexo técnico, que comparte la numeración.
    archivos = [AQUI / "secciones" / f"{clave}.tex" for clave, *_ in SECCIONES] + [AQUI / "anexo_tecnico.tex"]
    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8")
        for grupo in re.findall(r"\\cite\{([^}]+)\}", texto):
            for c in grupo.split(","):
                c = c.strip()
                if c not in orden:
                    orden.append(c)
    return orden


def escribir_referencias(orden, items):
    faltan = [c for c in orden if c not in items]
    if faltan:
        raise SystemExit(f"Faltan bibitems: {faltan}")
    cuerpo = "\n\n".join(f"\\bibitem{{{c}}}\n{items[c]}" for c in orden)
    (AQUI / "referencias.tex").write_text(
        "% Generado por plataforma.py. Estilo IEEE, en orden de primera cita.\n"
        "\\begin{thebibliography}{99}\n\n" + cuerpo + "\n\n\\end{thebibliography}\n", encoding="utf-8")


def etiquetas_anexo():
    """Números de figuras, tablas y ecuaciones del anexo técnico, leídos de su .aux."""
    aux = AQUI / "anexo_tecnico.aux"
    if not aux.exists():
        raise SystemExit("Compila primero anexo_tecnico.tex")
    return dict(re.findall(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", aux.read_text(encoding="utf-8")))


def a_texto(tex, numero, anexo):
    t = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", "", tex, flags=re.S)
    t = re.sub(r"\\section\{[^}]*\}(\\label\{[^}]*\})?", "", t)
    t = re.sub(r"\\ref\{A-([^}]+)\}", lambda m: anexo[m.group(1)], t)
    t = re.sub(r"~?\\cite\{([^}]+)\}", lambda m: " [" + ", ".join(str(numero[c.strip()]) for c in m.group(1).split(",")) + "]", t)
    t = re.sub(r"\\(textbf|emph|url)\{([^}]*)\}", r"\2", t)
    t = t.replace("\\begin{enumerate}", "").replace("\\end{enumerate}", "")
    n = iter(range(1, 50))
    t = re.sub(r"\\item\s*", lambda m: f"\n{next(n)}. ", t)
    t = t.replace("$p\\le0.05$", "p ≤ 0.05").replace("$R^2$", "R²")
    t = re.sub(r"\$([^$]*)\$", lambda m: m.group(1).replace("-", "−").replace("=", " = "), t)
    t = t.replace("\\,", " ").replace("\\%", "%").replace("\\$", "$").replace("~", " ")
    parrafos = [" ".join(p.split()) for p in re.split(r"\n\s*\n", t)]
    return "\n\n".join(p for p in parrafos if p).replace("\n\n1.", "\n1.") + "\n"


def main():
    items = bibitems()
    orden = orden_citas()
    escribir_referencias(orden, items)
    numero = {c: i + 1 for i, c in enumerate(orden)}
    anexo = etiquetas_anexo()
    salida = AQUI / "plataforma"
    salida.mkdir(exist_ok=True)
    filas, todo = [], True
    for clave, nombre, lo, hi in SECCIONES:
        texto = a_texto((AQUI / "secciones" / f"{clave}.tex").read_text(encoding="utf-8"), numero, anexo)
        (salida / f"{clave}.txt").write_text(texto, encoding="utf-8")
        n = len(texto.split())
        ok = n <= hi and (lo is None or n >= lo)
        todo &= ok
        rango = f"{lo} a {hi}" if lo else f"máximo {hi}"
        filas.append(f"| {nombre} | {rango} | {n} | {'Sí' if ok else 'NO'} |")
    tabla = ("# Conteo de palabras por sección\n\nPalabras separadas por espacios en el texto de plataforma/, que es el "
             "que se pega en cada campo. Generado por plataforma.py.\n\n| Sección | Límite | Palabras | Cumple |\n"
             "|---|---|---|---|\n" + "\n".join(filas) + f"\n\nTodas cumplen: {'sí' if todo else 'no'}.\n")
    (AQUI / "conteo_palabras.md").write_text(tabla, encoding="utf-8")
    print(tabla)
    print(f"{len(orden)} referencias")


if __name__ == "__main__":
    main()
