"""Clases de personaje.

Una clase es una sección con esta forma:

    Bárbaro                                  (section)
      tabla "Atributos básicos de bárbaro"   clave/valor: dado de golpe, competencias…
      subsección "Convertirse en bárbaro"    requisitos de nivel 1 y de multiclase
      subsección "Rasgos de clase de bárbaro"
        entrada "Nivel 1: Furia"             un rasgo por entrada
      subsección "Subclase de bárbaro: …"
      tabla "Rasgos de bárbaro"              progresión de 20 niveles

La tabla de progresión no siempre cuelga del mismo nodo: al ir a ancho completo
puede caer al final de la página, después del primer rasgo. Se busca por título
dentro del subárbol de la clase, no por posición.
"""

from __future__ import annotations

import re

from ..config import Language
from .common import blocks_of, make_id, plain_text, source_of, walk

LEVEL_RE = re.compile(r"^\s*Nivel\s+(\d+)\s*:\s*(.+)$", re.I)
SPELL_LIST_RE = re.compile(r"conjuros de [\wáéíóúñ]+ de nivel (\d)|trucos", re.I)


def _find_table(node: dict, prefix: str) -> dict | None:
    for _, candidate in walk(node):
        if candidate.get("type") == "table" and (candidate.get("caption") or "").startswith(prefix):
            return candidate
    return None


def _core_traits(table: dict | None) -> dict:
    """La tabla 'Atributos básicos de X' es una lista clave/valor."""
    if not table:
        return {}
    return {row[0]: row[1] for row in table.get("rows", []) if len(row) >= 2 and row[0]}


def _features(node: dict, lang: Language) -> list[dict]:
    out = []
    for ancestors, entry in walk(node):
        if entry.get("type") != "entry":
            continue
        match = LEVEL_RE.match(entry.get("title", ""))
        if not match:
            continue
        body = blocks_of(entry.get("children", []))
        out.append(
            {
                "level": int(match.group(1)),
                "name": match.group(2).strip(),
                "title": entry["title"],
                "subclass": next((a for a in ancestors if a and a.startswith("Subclase")), None),
                "text": plain_text(body),
                "blocks": body,
                "page": entry["source"]["page"],
            }
        )
    return sorted(out, key=lambda f: (f["subclass"] is not None, f["level"]))


def _spell_lists(node: dict) -> list[dict]:
    """Listas de conjuros por nivel, si la clase las tiene."""
    out = []
    for _, table in walk(node):
        if table.get("type") != "table":
            continue
        caption = table.get("caption") or ""
        if not SPELL_LIST_RE.search(caption):
            continue
        level = re.search(r"nivel (\d)", caption, re.I)
        out.append(
            {
                "level": int(level.group(1)) if level else 0,
                "caption": caption,
                "header": table.get("header", []),
                "rows": table.get("rows", []),
                "page": table["source"]["page"],
            }
        )
    return sorted(out, key=lambda s: s["level"])


def collect(document: dict, lang: Language) -> list[dict]:
    chapter = lang.sections["classes"]
    taken: set[str] = set()
    classes: list[dict] = []

    for ancestors, node in walk(document):
        if node.get("type") != "section" or chapter not in ancestors:
            continue
        name = node["title"]
        core = _find_table(node, "Atributos básicos")
        progression = _find_table(node, f"Rasgos de {name.lower()}")
        features = _features(node, lang)
        subclasses = sorted(
            {f["subclass"] for f in features if f["subclass"]}
        )

        classes.append(
            {
                "id": make_id("class", name, taken),
                "name": name,
                "coreTraits": _core_traits(core),
                "progression": {
                    "caption": progression.get("caption") if progression else None,
                    "header": progression.get("header", []) if progression else [],
                    "rows": progression.get("rows", []) if progression else [],
                }
                if progression
                else None,
                "features": [f for f in features if not f["subclass"]],
                "subclasses": [
                    {
                        "name": subclass,
                        "features": [f for f in features if f["subclass"] == subclass],
                    }
                    for subclass in subclasses
                ],
                "spellLists": _spell_lists(node),
                "source": source_of(node, f"SRD {lang.srd_version} {lang.code}"),
            }
        )
    return classes


NAME = "classes"
INDEX_FIELDS = ["id", "name"]
