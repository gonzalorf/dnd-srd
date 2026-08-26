"""Identificadores estables entre versiones del SRD.

Los ids se derivan del nombre (`spell.bola-de-fuego`), así que una errata o un
cambio de terminología en una versión futura los rompería —y con ellos las URLs
publicadas y los personajes que el usuario tenga guardados—.

`config/ids.lock.json` fija la correspondencia. En cada ejecución:

- un id ya presente en el lock se conserva tal cual;
- uno nuevo se añade;
- uno que desaparece NO se borra: se marca como retirado, para poder redirigir
  en lugar de devolver un 404.

El lock se versiona con el repositorio. Es un dato del proyecto, no un artefacto
generado: por eso vive en `config/` y no en `data/`.
"""

from __future__ import annotations

import json
from pathlib import Path

LOCK_VERSION = 1


def _load(path: Path) -> dict:
    if not path.exists():
        return {"version": LOCK_VERSION, "ids": {}, "retired": {}}
    data = json.loads(path.read_text("utf-8"))
    data.setdefault("ids", {})
    data.setdefault("retired", {})
    return data


def apply(collections: dict[str, list[dict]], path: Path, srd_version: str) -> dict:
    """Fija los ids contra el lock y devuelve el resumen de cambios."""
    lock = _load(path)
    known: dict[str, dict] = lock["ids"]
    seen: set[str] = set()
    added: list[str] = []

    for name, records in collections.items():
        for record in records:
            entry = known.get(record["id"])
            if entry is None:
                known[record["id"]] = {"collection": name, "since": srd_version}
                added.append(record["id"])
            elif entry.get("collection") != name:
                # El mismo nombre ha cambiado de colección: se anota, no se pisa.
                entry.setdefault("movedFrom", entry.get("collection"))
                entry["collection"] = name
            seen.add(record["id"])

    retired = []
    for identifier in list(known):
        if identifier in seen:
            known[identifier].pop("retiredIn", None)
            continue
        known[identifier]["retiredIn"] = srd_version
        lock["retired"][identifier] = known[identifier]
        retired.append(identifier)

    lock["version"] = LOCK_VERSION
    lock["ids"] = dict(sorted(known.items()))
    lock["retired"] = dict(sorted(lock["retired"].items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, ensure_ascii=False, indent=1), "utf-8")

    return {"total": len(seen), "added": added, "retired": retired}
