"""Utilidades compartidas por los parsers de dominio.

La fase `collect` consume `document.json` y no vuelve a mirar el PDF. El árbol
es fiel al documento; aquí es donde se normaliza y se interpreta.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterator

from ..textutil import slugify

RUNIN_RE = re.compile(r"^(\*{2,3})(?P<name>[^*]+?)\.?\1\s*(?P<rest>.*)$", re.S)
DICE_RE = re.compile(r"\b(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?\b")


def walk(node: dict, ancestors: tuple = ()) -> Iterator[tuple[tuple, dict]]:
    yield ancestors, node
    label = node.get("title") or node.get("name") or node.get("type")
    for child in node.get("children", []):
        yield from walk(child, ancestors + (label,))


def entries_under(document: dict, section: str, level: str = "entry") -> list[dict]:
    """Entradas que cuelgan de una sección concreta, por título."""
    return [n for anc, n in walk(document) if section in anc and n.get("type") == level]


def statblocks(document: dict) -> list[tuple[tuple, dict]]:
    return [(anc, n) for anc, n in walk(document) if n.get("type") == "statblock"]


def source_of(node: dict, book: str) -> dict:
    src = node.get("source", {})
    out = {"book": book, "page": src.get("page")}
    if src.get("pages"):
        out["pages"] = src["pages"]
    return out


def split_runin(md: str) -> tuple[str | None, str]:
    """Separa la entradilla en negrita del resto: '***Anfibio.*** El aboleth…'."""
    match = RUNIN_RE.match(md.strip())
    if not match:
        return None, md.strip()
    return match.group("name").strip(), match.group("rest").strip()


def blocks_of(children: list[dict], skip: set[str] = frozenset()) -> list[dict]:
    """Normaliza los hijos de una entrada a bloques de contenido."""
    out = []
    for child in children:
        kind = child.get("type")
        if kind in skip:
            continue
        block = {"type": kind, "page": child.get("source", {}).get("page")}
        if kind == "table":
            block["caption"] = child.get("caption")
            block["header"] = child.get("header")
            block["rows"] = child.get("rows")
        elif kind == "statblock":
            block["name"] = child.get("name")
            block["ref"] = child.get("id")
        else:
            block["md"] = child.get("md", "")
            block["text"] = child.get("text", "")
        out.append(block)
    return out


def plain_text(blocks: list[dict]) -> str:
    return "\n\n".join(b["text"] for b in blocks if b.get("text"))


def markdown_text(blocks: list[dict]) -> str:
    return "\n\n".join(b["md"] for b in blocks if b.get("md"))


def deaccent(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def number(text: str) -> float | int | None:
    """Primer número del texto, admitiendo coma decimal y fracciones ('1/4')."""
    text = text.replace("−", "-")
    fraction = re.search(r"\b(\d+)\s*/\s*(\d+)\b", text)
    if fraction:
        return int(fraction.group(1)) / int(fraction.group(2))
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    value = float(match.group(0).replace(",", "."))
    return int(value) if value.is_integer() else value


def label_value(text: str) -> tuple[str, str]:
    label, _, value = text.partition(":")
    return label.strip(), value.strip()


def make_id(prefix: str, name: str, taken: set[str]) -> str:
    base = f"{prefix}.{slugify(name)}"
    candidate, n = base, 1
    while candidate in taken:
        n += 1
        candidate = f"{base}-{n}"
    taken.add(candidate)
    return candidate
