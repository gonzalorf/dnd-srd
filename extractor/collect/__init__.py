"""Fase 4: árbol -> colecciones tipadas.

Cada colección se escribe en tres granularidades, porque cada una sirve a un
modo de consumo distinto:

    <nombre>.json          la colección entera, para empaquetar en build
    <nombre>.index.json    índice ligero, para listar, filtrar y buscar
    <nombre>/<slug>.json   una ficha por fichero, para carga bajo demanda

Y dos índices transversales: `by-page` (la trazabilidad al PDF) y `by-id`.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import CONFIG_DIR, Language
from . import classes, crossrefs, equipment, idlock, magic_items, monsters, simple, spells
from .common import walk


def _tables(document: dict, lang: Language) -> list[dict]:
    out = []
    for ancestors, node in walk(document):
        if node.get("type") != "table":
            continue
        out.append(
            {
                "id": node["id"],
                "caption": node.get("caption"),
                "header": node.get("header", []),
                "rows": node.get("rows", []),
                "fullWidth": node.get("layout", {}).get("fullWidth", False),
                "context": [a for a in ancestors if a][1:],
                "source": {"book": f"SRD {lang.srd_version} {lang.code}", "page": node["source"]["page"]},
            }
        )
    return out


def _sidebars(document: dict, lang: Language) -> list[dict]:
    out = []
    for ancestors, node in walk(document):
        if node.get("type") != "sidebar":
            continue
        out.append(
            {
                "id": node["id"],
                "title": node["title"],
                "blocks": [
                    {"type": c["type"], "md": c.get("md", ""), "text": c.get("text", "")}
                    for c in node.get("children", [])
                ],
                "context": [a for a in ancestors if a][1:],
                "source": {"book": f"SRD {lang.srd_version} {lang.code}", "page": node["source"]["page"]},
            }
        )
    return out


COLLECTIONS = [
    ("spells", spells.collect, spells.INDEX_FIELDS),
    ("monsters", monsters.collect, monsters.INDEX_FIELDS),
    ("magic-items", magic_items.collect, magic_items.INDEX_FIELDS),
    ("classes", classes.collect, classes.INDEX_FIELDS),
    ("equipment", equipment.collect, equipment.INDEX_FIELDS),
    ("rules-glossary", simple.collect_glossary, ["id", "name", "kind"]),
    ("feats", simple.collect_feats, ["id", "name", "category"]),
    ("backgrounds", simple.collect_backgrounds, ["id", "name"]),
    ("species", simple.collect_species, ["id", "name"]),
    ("tables", _tables, ["id", "caption", "context"]),
    ("sidebars", _sidebars, ["id", "title", "context"]),
]


def _index_entry(record: dict, fields: list[str]) -> dict:
    out = {f: record[f] for f in fields if f in record}
    out["page"] = record.get("source", {}).get("page")
    return out


def run(document: dict, lang: Language, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, int] = {}
    by_page: dict[str, list[str]] = {}
    by_id: dict[str, dict] = {}

    # Se recogen todas primero: las referencias cruzadas necesitan el índice
    # completo de nombres antes de poder resolver ninguna cursiva.
    gathered = {name: collector(document, lang) for name, collector, _ in COLLECTIONS}
    graph = crossrefs.annotate(gathered, lang)
    lock = idlock.apply(gathered, CONFIG_DIR / f"ids.{lang.code}.lock.json", lang.srd_version)

    for name, _, fields in COLLECTIONS:
        records = gathered[name]
        summary[name] = len(records)

        (out_dir / f"{name}.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=1), "utf-8"
        )
        (out_dir / f"{name}.index.json").write_text(
            json.dumps([_index_entry(r, fields) for r in records], ensure_ascii=False, indent=1),
            "utf-8",
        )

        per_entity = out_dir / name
        per_entity.mkdir(exist_ok=True)
        for old in per_entity.glob("*.json"):
            old.unlink()
        for record in records:
            slug = record["id"].split(".", 1)[1]
            (per_entity / f"{slug}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=1), "utf-8"
            )
            page = record.get("source", {}).get("page")
            if page:
                by_page.setdefault(str(page), []).append(record["id"])
            by_id[record["id"]] = {
                "collection": name,
                "name": record.get("name") or record.get("caption") or record.get("title"),
                "page": page,
                "path": f"{name}/{slug}.json",
            }

    indexes = out_dir.parent / "indexes"
    indexes.mkdir(parents=True, exist_ok=True)
    (indexes / "by-page.json").write_text(
        json.dumps({k: v for k, v in sorted(by_page.items(), key=lambda kv: int(kv[0]))},
                   ensure_ascii=False, indent=1),
        "utf-8",
    )
    (indexes / "by-id.json").write_text(json.dumps(by_id, ensure_ascii=False, indent=1), "utf-8")
    (indexes / "crossrefs.json").write_text(json.dumps(graph, ensure_ascii=False, indent=1), "utf-8")
    summary["_ids"] = len(by_id)
    summary["_links"] = graph["links"]
    summary["_lock"] = lock
    return summary
