"""Verificación independiente contra el PDF.

Estas pruebas NO usan el extractor. Abren el PDF con PyMuPDF y comprueban, con
una implementación mínima y separada, que lo generado se corresponde con el
documento fuente.

Existen porque las cifras de `validate.py` y las pruebas doradas se midieron
sobre la salida del propio extractor: sirven para detectar regresiones, pero no
demuestran por sí solas que la salida sea correcta. Esto sí: si el extractor
malinterpretara la estructura, los nombres y los valores no aparecerían en la
página que la ficha declara.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf")

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "source-docs" / "SP_SRD_CC_v5.2.1.pdf"
COLLECTIONS = ROOT / "data" / "processed" / "es" / "collections"

MAROON = 9183776


@pytest.fixture(scope="module")
def pdf():
    if not PDF.exists():
        pytest.skip("falta el PDF de origen")
    doc = pymupdf.open(PDF)
    yield doc
    doc.close()


@pytest.fixture(scope="module")
def pages(pdf) -> dict[int, str]:
    """Texto plano de cada página, normalizado igual que el extractor."""
    out = {}
    for index in range(pdf.page_count):
        text = pdf[index].get_text()
        # El guion blando (U+00AD) parte la palabra al final de linea: hay que
        # quitarlo JUNTO con el salto que le sigue. Si no, al colapsar los
        # espacios queda "murcie lago" y la comparacion falla por un motivo falso.
        text = re.sub(r"­\s*", "", text).replace(" ", " ")
        out[index + 1] = re.sub(r"\s+", " ", text)
    return out


def load(name: str) -> list[dict]:
    path = COLLECTIONS / f"{name}.json"
    if not path.exists():
        pytest.skip("ejecuta antes: python -m extractor build")
    return json.loads(path.read_text("utf-8"))


def count_fingerprint(pdf, size: float, font: str, color: int = MAROON) -> int:
    """Cuenta líneas base distintas con una huella tipográfica, por columna."""
    total = 0
    for index in range(pdf.page_count):
        seen = set()
        for block in pdf[index].get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    if (
                        abs(span["size"] - size) < 0.1
                        and span["color"] == color
                        and span["font"] == font
                        and span["text"].strip()
                    ):
                        column = 0 if span["origin"][0] < 302 else 1
                        seen.add((column, round(span["origin"][1], 1)))
        total += len(seen)
    return total


# --- recuentos contados directamente sobre el PDF ----------------------------


def test_numero_de_paginas(pdf):
    assert pdf.page_count == 398


def test_perfiles_contados_en_el_pdf(pdf):
    """336 líneas con la huella del nombre de perfil (GillSans-SemiBold 14.8)."""
    assert count_fingerprint(pdf, 14.8, "GillSans-SemiBold") == len(load("monsters")) == 336


def test_cuadros_destacados_contados_en_el_pdf(pdf):
    """Un cuadro destacado es un rectángulo oscuro de más de 50 pt de ancho."""
    total = 0
    for index in range(pdf.page_count):
        for drawing in pdf[index].get_drawings():
            fill = drawing.get("fill")
            if (
                drawing["type"] == "f"
                and fill
                and abs(fill[0] - 0.137) < 0.01
                and drawing["rect"].width > 50
            ):
                total += 1
    assert total == len(load("sidebars")) == 18


# --- cada ficha existe en la página que declara ------------------------------


def _missing(records: list[dict], pages: dict[int, str]) -> list[str]:
    out = []
    for record in records:
        name = record["name"]
        page = record["source"]["page"]
        if name not in pages.get(page, ""):
            out.append(f"{name} (p{page})")
    return out


def test_cada_conjuro_esta_en_su_pagina(pages):
    missing = _missing(load("spells"), pages)
    assert not missing, missing[:10]


def test_cada_perfil_esta_en_su_pagina(pages):
    missing = _missing(load("monsters"), pages)
    assert not missing, missing[:10]


def test_cada_objeto_magico_esta_en_su_pagina(pages):
    missing = _missing(load("magic-items"), pages)
    assert not missing, missing[:10]


def test_cada_regla_del_glosario_esta_en_su_pagina(pages):
    missing = _missing(load("rules-glossary"), pages)
    assert not missing, missing[:10]


# --- los valores parseados aparecen literalmente en la página ----------------


def test_valores_de_perfil_presentes_en_la_pagina(pages):
    """CA, PG y las 6 puntuaciones tienen que estar en el texto de la página."""
    problems = []
    for monster in load("monsters"):
        page = pages.get(monster["source"]["page"], "")
        if monster.get("acRaw") and f"CA: {monster['acRaw']}" not in page:
            problems.append(f"{monster['name']}: CA {monster['acRaw']}")
        if "raw" in monster.get("hp", {}) and monster["hp"]["raw"] not in page:
            problems.append(f"{monster['name']}: PG {monster['hp']['raw']}")
    assert not problems, problems[:10]


def test_propiedades_de_conjuro_presentes_en_la_pagina(pages):
    problems = []
    for spell in load("spells"):
        page = pages.get(spell["source"]["page"], "")
        for field, label in (
            ("range", "Alcance"),
            ("components", "Componentes"),
            ("duration", "Duración"),
        ):
            raw = spell[field]["raw"]
            # el valor puede continuar en la página siguiente
            following = pages.get(spell["source"]["page"] + 1, "")
            if raw not in page and raw not in following:
                problems.append(f"{spell['name']}: {label} = {raw!r}")
    assert not problems, problems[:10]


def test_ningun_texto_inventado(pages):
    """Una frase de cada ficha tiene que existir literalmente en su página."""
    problems = []
    for name in ("spells", "monsters", "magic-items"):
        for record in load(name):
            text = record.get("text") or ""
            fragment = " ".join(text.split()[:8])
            if len(fragment) < 20:
                continue
            page = record["source"]["page"]
            haystack = pages.get(page, "") + " " + pages.get(page + 1, "")
            if fragment not in haystack:
                problems.append(f"{name}/{record['name']} (p{page}): {fragment!r}")
    assert not problems, problems[:10]
