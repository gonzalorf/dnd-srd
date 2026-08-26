"""Referencias cruzadas: las cursivas del texto resueltas a su ficha.

El SRD pone en cursiva el nombre de un conjuro o de un objeto mágico cada vez
que lo menciona («el efecto del conjuro *libertad de movimiento*»). Eso es
justo lo que hace falta para convertir el libro en hipertexto: cada cursiva que
coincida con una ficha conocida se resuelve a su identificador.

Dos cuidados para no inventar enlaces:

- Se resuelve por nombre normalizado (sin acentos, sin puntuación) y solo si
  coincide **entero**, no como fragmento. «Bola de fuego» no debe enlazar desde
  «bola de fuego retardada».
- Una cursiva que apunta a la propia ficha que la contiene no es una referencia:
  es la costumbre del libro de repetir el nombre del objeto en su descripción.
"""

from __future__ import annotations

import re

from ..config import Language
from ..textutil import slugify

# Tramos en cursiva del markdown: *así*, pero no **negrita** ni ***ambas***.
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)")

# Colecciones donde buscar destino, por orden de prioridad ante un empate.
TARGETS = ("spells", "magic-items", "rules-glossary", "feats", "equipment")


# Los perfiles ponen en cursiva los términos mecánicos ("*Acierto:*", "*Tirada
# de ataque cuerpo a cuerpo:*"). No son referencias, son etiquetas, y llevan los
# dos puntos DENTRO de la cursiva: eso basta para distinguirlos.
STOPWORDS = {"consulta también", "véase", "ver"}


def _is_label(italic: str) -> bool:
    text = italic.strip()
    return text.endswith(":") or text.lower().strip(" .") in STOPWORDS


def _key(name: str) -> str:
    return slugify(name)


def build_index(collections: dict[str, list[dict]]) -> dict[str, str]:
    """Nombre normalizado -> id. La primera colección de TARGETS gana."""
    index: dict[str, str] = {}
    for name in TARGETS:
        for record in collections.get(name, []):
            key = _key(record.get("name", ""))
            if key and key not in index:
                index[key] = record["id"]
    return index


def _blocks_of(record: dict):
    yield from record.get("blocks", [])
    for section in ("traits", "actions", "bonusActions", "reactions"):
        yield from record.get(section, [])
    legendary = record.get("legendary") or {}
    yield from legendary.get("actions", [])
    for subclass in record.get("subclasses", []):
        for feature in subclass.get("features", []):
            yield from feature.get("blocks", [])
    for feature in record.get("features", []):
        yield from feature.get("blocks", [])


def annotate(collections: dict[str, list[dict]], lang: Language) -> dict:
    """Añade `refs` a cada ficha y devuelve el grafo completo."""
    index = build_index(collections)
    graph: dict[str, list[str]] = {}
    unresolved: dict[str, int] = {}
    total = 0

    for name, records in collections.items():
        for record in records:
            found: dict[str, None] = {}
            for block in _blocks_of(record):
                for italic in ITALIC_RE.findall(block.get("md", "")):
                    if _is_label(italic):
                        continue
                    key = _key(italic.strip(" .,;:"))
                    if not key:
                        continue
                    target = index.get(key)
                    if target is None:
                        unresolved[key] = unresolved.get(key, 0) + 1
                    elif target != record["id"]:  # no enlazar la ficha consigo misma
                        found[target] = None
            if found:
                record["refs"] = list(found)
                graph[record["id"]] = list(found)
                total += len(found)

    incoming: dict[str, list[str]] = {}
    for source, targets in graph.items():
        for target in targets:
            incoming.setdefault(target, []).append(source)

    return {
        "links": total,
        "outgoing": graph,
        "incoming": {k: sorted(v) for k, v in sorted(incoming.items())},
        "unresolved": dict(sorted(unresolved.items(), key=lambda kv: -kv[1])[:200]),
    }
