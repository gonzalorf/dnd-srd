"""Normalización de texto extraído del PDF.

El PDF de InDesign trae tres clases de caracteres que hay que tratar antes de
poder unir líneas en párrafos:

- 4344 guiones blandos (U+00AD) de partición silábica, tanto a final de línea
  ("ata­ques") como dentro de palabra ("­asegura").
- 10 125 espacios duros (U+00A0).
- Signo menos U+2212 y rayas U+2013/U+2014 en cifras y rangos.

Regla crítica: hay que comprobar si la línea TERMINA en guión blando ANTES de
eliminarlo, porque en ese caso las dos líneas se unen sin espacio.
"""

from __future__ import annotations

import re
import unicodedata

SOFT_HYPHEN = "­"
NBSP = " "
ZWSP = "​"
NB_HYPHEN = "‑"
MINUS = "−"


def clean(text: str) -> str:
    """Limpia el texto conservando la tipografía de presentación.

    Elimina los caracteres invisibles de maquetación pero mantiene comillas
    tipográficas, rayas y el signo menos: son correctos para mostrar y solo
    estorban al parsear cifras, donde se usa `numeric()`.
    """
    text = text.replace(SOFT_HYPHEN, "")
    text = text.replace(NBSP, " ")
    text = text.replace(ZWSP, "")
    text = text.replace(NB_HYPHEN, "-")
    return text


def numeric(text: str) -> str:
    """Normaliza a ASCII para poder parsear números y fórmulas de dados."""
    text = clean(text)
    text = text.replace(MINUS, "-").replace("–", "-").replace("—", "-")
    return text


def ends_hyphenated(raw: str) -> bool:
    """¿La línea termina partida por un guión blando?"""
    return raw.rstrip().endswith(SOFT_HYPHEN)


def join_lines(raw_lines: list[str]) -> str:
    """Une líneas de un párrafo respetando la partición silábica.

    Los fragmentos vacíos se saltan sin perder el estado de partición: dentro de
    una tabla, una celda recibe una cadena vacía por cada línea en la que la otra
    columna sí tiene texto, y esa cadena vacía se colaba entre las dos mitades de
    una palabra partida ("Intimida-" + "" + "ción").
    """
    out = ""
    previous: str | None = None
    for raw in raw_lines:
        piece = clean(raw).strip()
        if not piece:
            continue
        if not out:
            out = piece
        elif previous is not None and ends_hyphenated(previous):
            out += piece  # palabra partida: se pega sin espacio
        else:
            out += " " + piece
        previous = raw
    return re.sub(r"\s+", " ", out).strip()


def slugify(text: str) -> str:
    """Slug estable para identificadores.

    Quita acentos, pasa a minúsculas y deja solo [a-z0-9-]. Se usa para los
    ids del árbol, así que debe ser determinista entre ejecuciones.
    """
    text = clean(text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def sort_key(text: str) -> str:
    """Clave de ordenación alfabética sin acentos ni puntuación."""
    text = unicodedata.normalize("NFD", clean(text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", "", text).strip()
