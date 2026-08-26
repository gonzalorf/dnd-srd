"""Exporta las colecciones a SQLite con búsqueda de texto completo.

El objetivo es que una web estática pueda buscar en todo el SRD sin backend:
se sirve el fichero y se consulta con sql.js (SQLite compilado a WASM) desde el
navegador.

FTS5 no trae stemmer de español, pero sí `unicode61 remove_diacritics 2`, que
normaliza los acentos. Con eso «bola de fuego» y «Bola de Fuego» encuentran lo
mismo, que es el 90 % de lo que se necesita aquí.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode = OFF;

CREATE TABLE entity (
    id          TEXT PRIMARY KEY,
    collection  TEXT NOT NULL,
    name        TEXT NOT NULL,
    page        INTEGER,
    data        TEXT NOT NULL
);
CREATE INDEX entity_collection ON entity(collection);
CREATE INDEX entity_page       ON entity(page);

CREATE TABLE ref (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    PRIMARY KEY (source, target)
);
CREATE INDEX ref_target ON ref(target);

CREATE VIRTUAL TABLE search USING fts5(
    id UNINDEXED,
    collection UNINDEXED,
    name,
    body,
    tokenize = "unicode61 remove_diacritics 2"
);
"""


def _searchable(record: dict) -> str:
    parts = [record.get("text", "")]
    for section in ("traits", "actions", "bonusActions", "reactions"):
        parts += [entry.get("md", "") for entry in record.get(section, [])]
    legendary = record.get("legendary") or {}
    parts += [entry.get("md", "") for entry in legendary.get("actions", [])]
    for feature in record.get("features", []):
        parts.append(feature.get("text", ""))
    for subclass in record.get("subclasses", []):
        for feature in subclass.get("features", []):
            parts.append(feature.get("text", ""))
    for row in record.get("rows", []):
        parts.append(" ".join(row))
    return "\n".join(p for p in parts if p)


def run(collections_dir: Path, indexes_dir: Path, out_path: Path) -> dict:
    if out_path.exists():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(out_path)
    connection.executescript(SCHEMA)

    entities = 0
    for path in sorted(collections_dir.glob("*.json")):
        if path.name.endswith(".index.json"):
            continue
        collection = path.stem
        for record in json.loads(path.read_text("utf-8")):
            name = record.get("name") or record.get("caption") or record.get("title") or ""
            page = record.get("source", {}).get("page")
            connection.execute(
                "INSERT OR REPLACE INTO entity VALUES (?,?,?,?,?)",
                (record["id"], collection, name, page, json.dumps(record, ensure_ascii=False)),
            )
            connection.execute(
                "INSERT INTO search VALUES (?,?,?,?)",
                (record["id"], collection, name, _searchable(record)),
            )
            entities += 1

    links = 0
    crossrefs = indexes_dir / "crossrefs.json"
    if crossrefs.exists():
        graph = json.loads(crossrefs.read_text("utf-8"))
        for source, targets in graph.get("outgoing", {}).items():
            for target in targets:
                connection.execute("INSERT OR IGNORE INTO ref VALUES (?,?)", (source, target))
                links += 1

    connection.commit()
    connection.execute("VACUUM")
    connection.close()
    return {"entities": entities, "links": links, "bytes": out_path.stat().st_size}
