"""Paso final: estructurar el índice general y el índice de perfiles.

Las páginas 2–4 del PDF son índices a TRES columnas, con la página unida al
título por una fila de puntos:

    Berserker......................................................288

Eso da dos problemas que solo afectan a estas páginas:

1. El resto del libro va a dos columnas y el extractor parte por x=302, así que
   las entradas de las columnas 1 y 2 caen en el mismo grupo y se funden en una
   línea: «Druida……52 Elaborar pergaminos de conjuro…… 112 Lista de…».
2. Los puntos de relleno son maquetación de papel. En pantalla no se dibujan
   con puntos: se dibujan con una regla o con una rejilla.

Este módulo deshace las dos cosas. No toca nada más del documento y **no pierde
información**: el texto original se conserva íntegro en `text`, junto a las
entradas ya separadas en título, página y nivel.

La estructura del PDF ayuda: cada entrada del índice es UN span completo, con
sus puntos y su número, y el peso de la fuente marca el nivel (Cambria-Bold
para los capítulos, Cambria para las secciones).
"""

from __future__ import annotations

import re

from .textutil import clean

# Título, relleno de puntos y número de página. El relleno puede ser puntos
# normales o puntos suspensivos, y a veces hay un espacio antes del número.
ENTRADA_RE = re.compile(r"^(?P<titulo>.*?)\s*[.…]{2,}\s*(?P<pagina>\d+)\s*$")

# Separación mínima entre dos columnas del índice. Las columnas empiezan en
# x≈63, 229 y 398, así que cualquier umbral entre 20 y 150 vale; 40 deja
# margen de sobra sin arriesgarse a partir una entrada por dentro.
HUECO_COLUMNA = 40.0


def _columna(x: float, inicios: list[float]) -> int:
    """Índice de la columna a la que pertenece una x."""
    for i, inicio in enumerate(inicios):
        if x < inicio - HUECO_COLUMNA:
            return max(0, i - 1)
    return len(inicios) - 1


def _inicios_de_columna(xs: list[float]) -> list[float]:
    """Agrupa las x de inicio en las bandas que forman las columnas."""
    bandas: list[float] = []
    for x in sorted(xs):
        if not bandas or x - bandas[-1] > HUECO_COLUMNA:
            bandas.append(x)
    return bandas


def parse_blocks(blocks) -> list[dict]:
    """Convierte los bloques de índice de UNA página en su lista de entradas.

    Hay que darle la página entera, no bloque a bloque: el orden de lectura de
    un índice a tres columnas es columna a columna de arriba abajo, y los
    bloques llegan troceados por los saltos verticales, así que por separado
    saldrían intercalados («Druida 52, Lista de conjuros de druida 55, Elaborar
    pergaminos de conjuro 112», que son tres columnas de la misma fila).
    """
    spans = [
        (line.y, s, role)
        for block in blocks
        for line in block.lines
        for s, role in zip(line.spans, line.roles)
    ]
    if not spans:
        return []

    inicios = _inicios_de_columna([s["x"] for _, s, _ in spans])
    spans.sort(key=lambda t: (_columna(t[1]["x"], inicios), t[0], t[1]["x"]))

    entradas: list[dict] = []
    # Un título largo se parte en dos líneas: la primera no lleva puntos ni
    # número («Subclase de druida:») y el resto va en la siguiente entrada de
    # su misma columna. Se arrastra hacia delante.
    arrastre = ""
    columna_arrastre = -1

    for y, span, role in spans:
        # Misma normalización que el resto del libro: fuera guiones blandos
        # y espacios duros («Dominio de la vida»).
        texto = clean(span["t"]).strip()
        if not texto:
            continue
        columna = _columna(span["x"], inicios)
        if arrastre and columna != columna_arrastre:
            entradas.append({"title": arrastre, "page": None, "level": 2})
            arrastre = ""

        match = ENTRADA_RE.match(texto)
        if not match:
            arrastre = f"{arrastre} {texto}".strip()
            columna_arrastre = columna
            continue

        titulo = f"{arrastre} {match.group('titulo')}".strip()
        arrastre = ""
        entradas.append(
            {
                "title": titulo,
                "page": int(match.group("pagina")),
                # El peso de la fuente distingue capítulo de sección.
                "level": 1 if "Bold" in span["f"] else 2,
            }
        )

    if arrastre:
        entradas.append({"title": arrastre, "page": None, "level": 2})
    return entradas


def summarize(document: dict) -> dict:
    """Recuento para el informe de validación."""
    total = resueltas = 0

    def recorrer(node: dict) -> None:
        nonlocal total, resueltas
        if node.get("type") == "toc":
            for entrada in node.get("entries", []):
                total += 1
                if entrada.get("page"):
                    resueltas += 1
        for child in node.get("children", []):
            recorrer(child)

    recorrer(document)
    return {"entries": total, "withPage": resueltas}
