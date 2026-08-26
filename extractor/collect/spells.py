"""Conjuros.

El subtítulo en cursiva lleva escuela, nivel y clases:

    Abjuración de nivel 1 (explorador, mago)
    Truco de nigromancia (brujo, hechicero, mago)

Y las cuatro propiedades van en un bloque propio. Con una excepción real: la
ficha de “Toque helado” (p. 189) está maquetada con Cambria en vez de GillSans,
así que sus propiedades llegan al árbol como ítems de definición. El árbol es
fiel al PDF; normalizar esa irregularidad es trabajo de aquí, y por eso las
propiedades se buscan por etiqueta y no por tipo de bloque.
"""

from __future__ import annotations

import re

from ..config import Language
from .common import blocks_of, entries_under, label_value, make_id, number, plain_text, source_of

SUBTITLE_RE = re.compile(
    r"^\s*(?:"
    r"(?P<school_lv>[A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+nivel\s+(?P<level>\d)"
    r"|Truco\s+de\s+(?P<school_c>[A-Za-zÁÉÍÓÚÑáéíóúñ]+)"
    r")\s*(?:\((?P<classes>[^)]*)\))?",
    re.I,
)

# Etiquetas de propiedad, sin acentos ni mayúsculas, para tolerar variaciones.
PROP_KEYS = {
    "tiempo de lanzamiento": "castingTime",
    "alcance": "range",
    "componentes": "components",
    "duracion": "duration",
}


def _norm(text: str) -> str:
    return (
        text.lower()
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
        .strip()
    )


def _parse_range(raw: str) -> dict:
    out: dict = {"raw": raw}
    low = _norm(raw)
    if low.startswith("lanzador"):
        out["kind"] = "self"
    elif low.startswith("toque"):
        out["kind"] = "touch"
    elif low.startswith("vista") or low.startswith("a la vista"):
        out["kind"] = "sight"
    elif low.startswith("ilimitado"):
        out["kind"] = "unlimited"
    elif re.search(r"\d", raw):
        out["kind"] = "ranged"
        value = number(raw)
        if value is not None:
            out["meters"] = value
            if "km" in low:
                out["meters"] = value * 1000
    else:
        out["kind"] = "special"
    shape = re.search(r"\(([^)]*)\)", raw)
    if shape:
        out["shape"] = shape.group(1)
    return out


def _parse_components(raw: str) -> dict:
    head = raw.split("(", 1)[0]
    letters = set(re.findall(r"\b([VSM])\b", head))
    out = {"raw": raw, "v": "V" in letters, "s": "S" in letters, "m": "M" in letters}
    material = re.search(r"\(([^)]*(?:\([^)]*\))?[^)]*)\)", raw)
    if out["m"] and material:
        out["material"] = material.group(1)
        out["consumed"] = bool(re.search(r"consume", material.group(1), re.I))
    return out


def _parse_duration(raw: str) -> dict:
    low = _norm(raw)
    out: dict = {"raw": raw, "concentration": low.startswith("concentracion")}
    if "instantaneo" in low:
        out["kind"] = "instantaneous"
    elif "hasta que se disipe" in low or "disipado" in low:
        out["kind"] = "until-dispelled"
    elif "especial" in low:
        out["kind"] = "special"
    else:
        out["kind"] = "timed"
    unit = re.search(r"(asalto|minuto|hora|d[íi]a|a[ñn]o)s?", low)
    value = number(raw)
    if out["kind"] == "timed" and unit and value is not None:
        out["value"] = value
        out["unit"] = unit.group(1).replace("i", "í") if unit.group(1) == "dia" else unit.group(1)
    return out


def _parse_casting_time(raw: str) -> dict:
    low = _norm(raw)
    out: dict = {"raw": raw, "ritual": "ritual" in low}
    if low.startswith("accion adicional"):
        out["kind"] = "bonus-action"
    elif low.startswith("accion"):
        out["kind"] = "action"
    elif low.startswith("reaccion"):
        out["kind"] = "reaction"
        trigger = re.search(r",\s*(?:que\s+)?(.*)$", raw)
        if trigger:
            out["trigger"] = trigger.group(1)
    else:
        out["kind"] = "time"
        out["value"] = number(raw)
        unit = re.search(r"(minuto|hora|d[íi]a)s?", low)
        if unit:
            out["unit"] = unit.group(1)
    return out


def collect(document: dict, lang: Language) -> list[dict]:
    section = lang.sections["spells"]
    taken: set[str] = set()
    spells: list[dict] = []

    for node in entries_under(document, section):
        children = node.get("children", [])
        if not children:
            continue

        subtitle = children[0]["text"] if children[0]["type"] == "subtitle" else ""
        match = SUBTITLE_RE.match(subtitle)
        if not match:
            continue  # no es una ficha de conjuro (subsección suelta del capítulo)

        raw_props: dict[str, str] = {}
        consumed = 0
        for child in children[1:]:
            if child["type"] not in ("property", "definition"):
                break
            label, value = label_value(child.get("text", ""))
            key = PROP_KEYS.get(_norm(label))
            if key is None:
                break
            raw_props[key] = value
            consumed += 1
        if len(raw_props) < 4:
            continue

        level = int(match.group("level")) if match.group("level") else 0
        school = (match.group("school_lv") or match.group("school_c") or "").capitalize()
        classes = [c.strip() for c in (match.group("classes") or "").split(",") if c.strip()]

        body = blocks_of(children[1 + consumed :])
        casting = _parse_casting_time(raw_props["castingTime"])
        duration = _parse_duration(raw_props["duration"])

        spells.append(
            {
                "id": make_id("spell", node["title"], taken),
                "name": node["title"],
                "level": level,
                "cantrip": level == 0,
                "school": school,
                "classes": classes,
                "ritual": casting["ritual"],
                "concentration": duration["concentration"],
                "castingTime": casting,
                "range": _parse_range(raw_props["range"]),
                "components": _parse_components(raw_props["components"]),
                "duration": duration,
                "text": plain_text(body),
                "blocks": body,
                "source": source_of(node, f"SRD {lang.srd_version} {lang.code}"),
            }
        )
    return spells


NAME = "spells"
INDEX_FIELDS = ["id", "name", "level", "school", "classes", "ritual", "concentration"]
