"""Objetos mágicos.

El subtítulo en cursiva concentra toda la ficha técnica:

    Objeto maravilloso, común
    Arma (garrote grande), muy rara (requiere sintonización)
    Bastón, muy raro (requiere sintonización por parte de un druida o un mago)

La categoría es lo que va antes de la primera coma (con la variante entre
paréntesis, si la hay), la rareza es lo siguiente, y la sintonización va al
final entre paréntesis, a veces con restricción de clase.
"""

from __future__ import annotations

import re

from ..config import Language
from .common import blocks_of, deaccent, entries_under, make_id, plain_text, source_of

# La rareza aparece en masculino o femenino según la categoría del objeto.
RARITIES = {
    "comun": "común",
    "infrecuente": "infrecuente",
    "raro": "raro",
    "rara": "raro",
    "muy raro": "muy raro",
    "muy rara": "muy raro",
    "legendario": "legendario",
    "legendaria": "legendario",
    "artefacto": "artefacto",
    "varia": "varía",
    "varias": "varía",
    "rareza variable": "varía",
}


def _parse_subtitle(raw: str) -> dict:
    out: dict = {"raw": raw}

    attunement = re.search(r"\(requiere sintonizaci[óo]n([^)]*)\)", raw, re.I)
    out["attunement"] = bool(attunement)
    if attunement:
        restriction = attunement.group(1).strip()
        if restriction:
            out["attunementRequires"] = re.sub(r"^por parte de\s*", "", restriction).strip()
        raw = raw[: attunement.start()].strip().rstrip(",")

    # la variante de la categoría va entre paréntesis: "Arma (garrote grande)"
    variant = re.match(r"^([^(,]+)\s*\(([^)]*)\)", raw)
    if variant:
        out["category"] = variant.group(1).strip()
        out["variant"] = variant.group(2).strip()
        rest = raw[variant.end() :]
    else:
        category, _, rest = raw.partition(",")
        out["category"] = category.strip()

    tail = deaccent(rest.strip(" ,"))
    for key in sorted(RARITIES, key=len, reverse=True):
        if tail.startswith(key):
            out["rarity"] = RARITIES[key]
            break
    else:
        if tail:
            out["rarity"] = rest.strip(" ,")
    return out


def collect(document: dict, lang: Language) -> list[dict]:
    section = lang.sections["magic_items"]
    taken: set[str] = set()
    items: list[dict] = []

    for node in entries_under(document, section):
        children = node.get("children", [])
        if not children or children[0]["type"] != "subtitle":
            continue
        info = _parse_subtitle(children[0]["text"])
        body = blocks_of(children[1:])
        items.append(
            {
                "id": make_id("item", node["title"], taken),
                "name": node["title"],
                "category": info.get("category"),
                "variant": info.get("variant"),
                "rarity": info.get("rarity"),
                "attunement": info.get("attunement", False),
                "attunementRequires": info.get("attunementRequires"),
                "subtitle": info["raw"],
                "text": plain_text(body),
                "blocks": body,
                "source": source_of(node, f"SRD {lang.srd_version} {lang.code}"),
            }
        )
    return items


NAME = "magic-items"
INDEX_FIELDS = ["id", "name", "category", "variant", "rarity", "attunement"]
