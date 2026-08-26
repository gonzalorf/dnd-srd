"""Exporta el árbol a markdown, un fichero por capítulo.

No es un formato de consumo: es la salida legible que hace comparable una
versión del SRD con la siguiente. Un `git diff` entre dos ejecuciones dice qué
ha cambiado en el libro; un diff de `document.json` no dice nada.

Por eso lleva la página en cada título: el diff sigue siendo legible aunque la
paginación se mueva.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..textutil import slugify

HEADING = {"chapter": "#", "section": "##", "subsection": "###", "entry": "####"}


def _render(node: dict, out: list[str]) -> None:
    kind = node.get("type")
    page = node.get("source", {}).get("page")

    if kind in HEADING:
        out.append(f"\n{HEADING[kind]} {node['title']}  <!-- p{page} -->\n")
    elif kind == "subtitle":
        out.append(f"*{node['text']}*\n")
    elif kind in ("paragraph", "definition", "step"):
        out.append(node.get("md", "") + "\n")
    elif kind == "list-item":
        out.append(node.get("md", "") + "\n")
    elif kind == "property":
        out.append(f"- **{node.get('label','')}:** {node.get('value','')}")
    elif kind == "toc-entry":
        out.append(node.get("text", "") + "\n")
    elif kind == "table":
        out.append(_table(node, page))
    elif kind == "sidebar":
        out.append(f"\n> **{node['title']}**  <!-- p{page} -->\n>")
        for child in node.get("children", []):
            out.append("> " + child.get("md", "").replace("\n", "\n> ") + "\n>")
        out.append("")
        return
    elif kind == "statblock":
        out.append(_statblock(node, page))
        return

    for child in node.get("children", []):
        _render(child, out)


def _escape(cell: str) -> str:
    return cell.replace("|", "\\|").replace("\n", " ")


def _table(node: dict, page: int | None) -> str:
    caption = node.get("caption") or ""
    rows = node.get("rows", [])
    header = node.get("header") or []
    width = max([len(header)] + [len(r) for r in rows]) if rows or header else 0
    if not width:
        return ""
    if not header:
        header = [""] * width
    lines = [f"\n**{caption}**  <!-- p{page} -->\n" if caption else f"\n<!-- p{page} -->\n"]
    lines.append("| " + " | ".join(_escape(h) for h in header) + " |")
    lines.append("|" + "---|" * width)
    for row in rows:
        padded = list(row) + [""] * (width - len(row))
        lines.append("| " + " | ".join(_escape(c) for c in padded) + " |")
    return "\n".join(lines) + "\n"


def _statblock(node: dict, page: int | None) -> str:
    lines = [f"\n**{node['name']}**  <!-- p{page} -->\n"]
    for part in node.get("parts", []):
        if part["type"] == "section":
            lines.append(f"\n*{part['text']}*\n")
        else:
            lines.append(part.get("md", ""))
    return "\n".join(lines) + "\n"


def run(document: dict, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.md"):
        old.unlink()

    chapters = [c for c in document.get("children", []) if c.get("type") == "chapter"]
    for order, chapter in enumerate(chapters, start=1):
        out: list[str] = []
        _render(chapter, out)
        name = f"{order:02d}-{slugify(chapter['title'])}.md"
        text = "\n".join(out).replace("\n\n\n", "\n\n").strip() + "\n"
        # Saltos de línea LF siempre: el sentido de este export es comparar dos
        # versiones del SRD, y un CRLF de Windows ensucia el diff entero.
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
    return len(chapters)
