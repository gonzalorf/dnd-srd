"""Genera un JSON Schema por colección a partir de los datos.

Los esquemas se infieren en vez de escribirse a mano, por el mismo motivo que
las cifras de `validate.py` no se escriben a ojo: así no se desincronizan del
pipeline. Lo que aportan es un contrato publicable y comprobable —y del que se
pueden generar tipos de TypeScript— no una verdad independiente.

Un campo se marca `required` cuando aparece en TODOS los registros, y se le pone
`enum` cuando es una cadena con pocos valores distintos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ENUM_MAX = 12  # valores distintos como máximo para publicar un enum
SAMPLE_KEYS = 60  # claves distintas como máximo antes de tratarlo como mapa libre


def _type_of(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _merge(schema: dict | None, value: Any) -> dict:
    kind = _type_of(value)
    if schema is None:
        schema = {"_types": set(), "_values": set(), "_count": 0}
    schema["_types"].add(kind)
    schema["_count"] += 1

    if kind == "string" and len(schema["_values"]) <= ENUM_MAX:
        schema["_values"].add(value)
    elif kind == "object":
        props = schema.setdefault("_props", {})
        counts = schema.setdefault("_propcount", {})
        for key, item in value.items():
            props[key] = _merge(props.get(key), item)
            counts[key] = counts.get(key, 0) + 1
    elif kind == "array":
        for item in value:
            schema["_items"] = _merge(schema.get("_items"), item)
    return schema


def _finish(schema: dict, total: int) -> dict:
    types = sorted(schema["_types"] - {"null"})
    nullable = "null" in schema["_types"]
    if "integer" in types and "number" in types:
        types = [t for t in types if t != "integer"]

    out: dict = {"type": (types + ["null"]) if nullable else (types[0] if len(types) == 1 else types)}
    if isinstance(out["type"], list) and len(out["type"]) == 1:
        out["type"] = out["type"][0]

    values = schema.get("_values", set())
    if types == ["string"] and values and len(values) <= ENUM_MAX:
        out["enum"] = sorted(v for v in values if v is not None)
        if nullable:
            out["enum"].append(None)

    if "_props" in schema:
        count = schema["_propcount"]
        own = schema["_count"]
        out["properties"] = {
            key: _finish(sub, count[key]) for key, sub in sorted(schema["_props"].items())
        }
        required = sorted(k for k, n in count.items() if n == own)
        if required and len(out["properties"]) <= SAMPLE_KEYS:
            out["required"] = required
    if "_items" in schema:
        out["items"] = _finish(schema["_items"], total)
    return out


def infer(records: list[dict], title: str) -> dict:
    root: dict | None = None
    for record in records:
        root = _merge(root, record)
    schema = _finish(root, len(records)) if root else {"type": "object"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "description": f"Inferido de {len(records)} fichas de la colección «{title}».",
        "type": "array",
        "items": schema,
    }


def run(collections_dir: Path, out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    for path in sorted(collections_dir.glob("*.json")):
        if path.name.endswith(".index.json"):
            continue
        records = json.loads(path.read_text("utf-8"))
        if not isinstance(records, list) or not records:
            continue
        name = path.stem
        schema = infer(records, name)
        (out_dir / f"{name}.schema.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=1), "utf-8"
        )
        written[name] = len(records)
    return written
