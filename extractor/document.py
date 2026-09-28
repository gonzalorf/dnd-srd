"""Fase 3: bloques -> árbol jerárquico (document.json).

El árbol es fiel al documento y agnóstico de dominio: no sabe qué es un conjuro
ni un monstruo. Esa interpretación llega en la fase `collect`, que consume este
árbol. Aquí solo se resuelve la jerarquía, se agrupan los cuadros destacados y
los perfiles de criatura, y se anota la procedencia de cada nodo.

Invariante que sostiene todo lo demás: **todos los nodos llevan página**.
"""

from __future__ import annotations

from collections import Counter

from .blocks import Block, markdown
from .config import Language, Styles
from .textutil import slugify
from .toc import parse_blocks as parse_toc

CONTENT_TYPES = {
    "paragraph": "paragraph",
    "list.bullet": "list-item",
    "list.step": "step",
    "list.definition": "definition",
    "property": "property",
    "table": "table",
    "toc": "toc-entry",
    "table.caption": "paragraph",
    "subtitle": "subtitle",
    # Fuera de un cuadro destacado, la tipografía sans marca los recuadros de
    # fórmula del texto corrido ("CA base = 10 + el modificador por Destreza").
    # Sin esta entrada el árbol los descartaba en silencio: 47 bloques perdidos.
    "sidebar.body": "callout",
    "sidebar.title": "callout",
}

STATBLOCK_TYPES = {
    "statblock.name",
    "statblock.meta",
    "statblock.header",
    "statblock.ability",
    "statblock.section",
    "statblock.body",
    "statblock.ability",
}


class IdFactory:
    def __init__(self) -> None:
        self.seen: Counter[str] = Counter()

    def make(self, prefix: str, title: str) -> str:
        base = f"{prefix}.{slugify(title) or 'sin-titulo'}"
        self.seen[base] += 1
        n = self.seen[base]
        return base if n == 1 else f"{base}-{n}"


def _source(block: Block) -> dict:
    pages = block.pages
    src = {"page": pages[0], "column": block.column, "bbox": block.bbox}
    if len(pages) > 1:
        src["pages"] = pages
    return src


def _toc_node(group: list[Block], styles: Styles) -> dict | None:
    """Índice general e índice de perfiles, ya separados en entradas.

    Es el único sitio del libro con tres columnas y con puntos de relleno entre
    el título y la página. Ver `extractor/toc.py`: el texto original se conserva
    íntegro en `text`, no se pierde nada.
    """
    entries = parse_toc(group)
    if not entries:
        return None
    node = {
        "type": "toc",
        "source": _source(group[0]),
        "entries": entries,
        "text": " ".join(b.text for b in group),
    }
    pages = sorted({p for b in group for p in b.pages})
    if len(pages) > 1:
        node["source"]["pages"] = pages
    return node


def _content_node(block: Block, styles: Styles, ids: IdFactory) -> dict | None:
    if block.type == "table":
        node = block.table.to_dict()
        node["id"] = ids.make("table", block.table.caption or f"p{block.page}")
        node["source"] = _source(block)
        return node

    kind = CONTENT_TYPES.get(block.type)
    if kind is None:
        return None
    text = block.text
    if not text:
        return None
    node = {
        "type": kind,
        "source": _source(block),
        "text": text,
        "md": markdown(block, styles),
    }
    if kind == "property":
        label, _, value = text.partition(":")
        node["label"] = label.strip()
        node["value"] = value.strip()
    return node


def _statblock_node(group: list[Block], styles: Styles, ids: IdFactory) -> dict:
    name = next((b.text for b in group if b.type == "statblock.name"), "")
    node = {
        "id": ids.make("statblock", name),
        "type": "statblock",
        "name": name,
        "source": _source(group[0]),
        "parts": [],
    }
    pages = sorted({p for b in group for p in b.pages})
    if len(pages) > 1:
        node["source"]["pages"] = pages
    for block in group:
        if block.type == "statblock.name":
            continue
        part = {
            "type": block.type.split(".", 1)[1],
            "text": block.text,
            "md": markdown(block, styles),
            "source": _source(block),
        }
        if block.table is not None:
            part["grid"] = {"header": block.table.header, "rows": block.table.rows}
        node["parts"].append(part)
    return node


def _sidebar_node(group: list[Block], styles: Styles, ids: IdFactory) -> dict:
    title_blocks = [b for b in group if b.type == "sidebar.title"]
    title = " ".join(b.text for b in title_blocks).strip()
    node = {
        "id": ids.make("sidebar", title),
        "type": "sidebar",
        "title": title,
        "source": _source(group[0]),
        "children": [],
    }
    for block in group:
        if block.type == "sidebar.title":
            continue
        if block.type == "table":
            child = _content_node(block, styles, ids)
        else:
            child = {
                "type": "paragraph",
                "source": _source(block),
                "text": block.text,
                "md": markdown(block, styles),
            }
        if child:
            node["children"].append(child)
    return node


def build_document(blocks: list[Block], styles: Styles, lang: Language) -> dict:
    ids = IdFactory()
    dropped: Counter[str] = Counter()
    root = {
        "type": "document",
        "language": lang.code,
        "srdVersion": lang.srd_version,
        "title": lang.book_title,
        "children": [],
    }
    stack: list[tuple[int, dict]] = [(0, root)]

    def container() -> dict:
        return stack[-1][1]

    index = 0
    while index < len(blocks):
        block = blocks[index]

        # --- perfil de criatura: absorbe todo hasta el siguiente perfil o título
        if block.type == "statblock.name":
            group = [block]
            index += 1
            while index < len(blocks) and blocks[index].type in STATBLOCK_TYPES:
                if blocks[index].type == "statblock.name":
                    break
                group.append(blocks[index])
                index += 1
            container().setdefault("children", []).append(_statblock_node(group, styles, ids))
            continue

        # --- índice: se agrupa la página entera para respetar el orden
        # de lectura por columnas
        if block.type == "toc":
            page = block.page
            group = []
            while index < len(blocks) and blocks[index].type == "toc" and blocks[index].page == page:
                group.append(blocks[index])
                index += 1
            node = _toc_node(group, styles)
            if node:
                container().setdefault("children", []).append(node)
            continue

        # --- cuadro destacado: agrupa por región
        if block.region and block.region.startswith("sidebar"):
            region, page = block.region, block.page
            group = []
            while (
                index < len(blocks)
                and blocks[index].region == region
                and blocks[index].page == page
            ):
                group.append(blocks[index])
                index += 1
            container().setdefault("children", []).append(_sidebar_node(group, styles, ids))
            continue

        # --- título: abre un nivel del árbol
        if block.type == "heading" and block.level:
            level = block.level
            while stack and stack[-1][0] >= level:
                stack.pop()
            prefix = {1: "chapter", 2: "section", 3: "subsection", 4: "entry"}[level]
            node = {
                "id": ids.make(prefix, block.text),
                "type": prefix,
                "level": level,
                "title": block.text,
                "source": _source(block),
                "children": [],
            }
            stack[-1][1].setdefault("children", []).append(node)
            stack.append((level, node))
            index += 1
            continue

        node = _content_node(block, styles, ids)
        if node:
            container().setdefault("children", []).append(node)
        elif block.text.strip():
            dropped[block.type] += 1
        index += 1

    root["dropped"] = dict(dropped)
    return root


def summarize(document: dict) -> dict:
    counts: Counter[str] = Counter()

    def walk(node: dict) -> None:
        counts[node.get("type", "?")] += 1
        for child in node.get("children", []):
            walk(child)

    walk(document)
    return dict(counts)
