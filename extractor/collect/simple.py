"""Colecciones cuya ficha es «título + cuerpo», sin campos técnicos propios.

Glosario de reglas, dotes, trasfondos y especies comparten forma: lo único que
cambia es de qué sección cuelgan y qué se deduce del título o del padre.
"""

from __future__ import annotations

import re

from ..config import Language
from .common import blocks_of, entries_under, make_id, plain_text, source_of, walk

# El glosario marca el tipo de término entre corchetes: "Agarrado [estado]".
KIND_RE = re.compile(r"^(?P<name>.+?)\s*\[(?P<kind>[^\]]+)\]\s*$")


def _entry(node: dict, prefix: str, taken: set[str], lang: Language, extra: dict | None = None) -> dict:
    title = node["title"]
    kind = None
    match = KIND_RE.match(title)
    if match:
        title, kind = match.group("name"), match.group("kind")
    body = blocks_of(node.get("children", []))
    out = {
        "id": make_id(prefix, title, taken),
        "name": title,
        "text": plain_text(body),
        "blocks": body,
        "source": source_of(node, f"SRD {lang.srd_version} {lang.code}"),
    }
    if kind:
        out["kind"] = kind
    if extra:
        out.update(extra)
    return out


def _parent_of(document: dict, node: dict) -> str | None:
    """Título de la subsección que contiene la entrada (su categoría)."""
    for ancestors, candidate in walk(document):
        if candidate is node:
            return ancestors[-1] if ancestors else None
    return None


def collect_glossary(document: dict, lang: Language) -> list[dict]:
    taken: set[str] = set()
    return [
        _entry(node, "rule", taken, lang)
        for node in entries_under(document, lang.sections["glossary"])
    ]


def collect_feats(document: dict, lang: Language) -> list[dict]:
    taken: set[str] = set()
    out = []
    for ancestors, node in walk(document):
        if node.get("type") != "entry" or lang.sections["feats"] not in ancestors:
            continue
        category = ancestors[-1] if ancestors else None
        out.append(_entry(node, "feat", taken, lang, {"category": category}))
    return out


def collect_backgrounds(document: dict, lang: Language) -> list[dict]:
    taken: set[str] = set()
    return [
        _entry(node, "background", taken, lang)
        for node in entries_under(document, lang.sections["backgrounds"])
    ]


def collect_species(document: dict, lang: Language) -> list[dict]:
    taken: set[str] = set()
    return [
        _entry(node, "species", taken, lang)
        for node in entries_under(document, lang.sections["species"])
    ]
