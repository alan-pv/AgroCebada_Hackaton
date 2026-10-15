"""Cuenta las palabras de cada sección (separadas por espacios, como un procesador de texto) y escribe conteo_palabras.md."""
import glob, os
base = os.path.dirname(os.path.abspath(__file__))
limites = {
 '01_introduccion': ('Introducción', 400, 550), '02_justificacion': ('Justificación', 100, 200),
 '03_objetivos': ('Objetivos', None, 200), '04_metodologia': ('Metodología', 600, 700),
 '05_resultados': ('Resultados y discusión', None, 800),
 '06_ciencia_datos_inclusion_financiera': ('Uso de la ciencia de datos en la inclusión financiera del sector agro', None, 300),
 '07_conclusiones': ('Conclusiones', None, 400)}
filas = []; todo = True
for k, (nom, lo, hi) in limites.items():
    n = len(open(f'{base}/secciones/{k}.md', encoding='utf-8').read().split())
    ok = n <= hi and (lo is None or n >= lo)
    rango = f'{lo} a {hi}' if lo else f'máximo {hi}'
    uso = f'{100*n/hi:.0f} %'
    filas.append(f'| {nom} | {rango} | {n} | {uso} | {"Sí" if ok else "NO"} |'); todo &= ok
txt = '# Conteo de palabras por sección\n\nConteo con `contar.py`, palabras separadas por espacios.\n\n| Sección | Límite | Palabras | Uso del límite superior | Cumple |\n|---|---|---|---|---|\n' + '\n'.join(filas) + f'\n\nTodas cumplen: {"sí" if todo else "no"}.\n'
open(f'{base}/conteo_palabras.md', 'w', encoding='utf-8').write(txt); print(txt)
