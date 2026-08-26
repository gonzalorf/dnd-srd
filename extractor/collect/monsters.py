"""Perfiles de criatura.

Un perfil llega del árbol como una lista de partes tipadas:

    meta     Aberración Grande, legal malvada
    header   CA: 17  Iniciativa: +7 (17)  PG: 150 (20d10 + 40)  Velocidad: 3 m…
    ability  Fue 21 +5 +5  Des 9 −1 +3  Con 15 +2 +6 …
    section  Atributos | Acciones | Acciones adicionales | Reacciones | Acciones legendarias
    body     ***Anfibio.*** El aboleth puede respirar…

Las etiquetas de cabecera pueden venir varias en la misma parte (van separadas
por tabulador en el PDF), así que se trocean por etiqueta conocida en lugar de
por línea.
"""

from __future__ import annotations

import re

from ..config import Language
from .common import make_id, number, source_of, split_runin, statblocks

ABILITY_RE = re.compile(
    r"\b(Fue|Des|Con|Int|Sab|Car)\s+(-?\d+)\s+([+-]?-?\d+)\s+([+-]?-?\d+)",
)
ABILITY_KEYS = {"Fue": "fue", "Des": "des", "Con": "con", "Int": "int", "Sab": "sab", "Car": "car"}

HP_RE = re.compile(r"^\s*(\d+)\s*(?:\((\d+d\d+(?:\s*[+-]\s*\d+)?)\))?")
INITIATIVE_RE = re.compile(r"([+-]?\d+)\s*(?:\((\d+)\))?")
CR_RE = re.compile(r"^\s*([\d/]+)\s*\(([\d\s]+)\s*PX[^;)]*(?:;\s*BC\s*([+-]?\d+))?")
SPEED_RE = re.compile(r"(?:^|,\s*)(?:([a-záéíóúñ ]+?)\s+)?([\d,]+)\s*m")

SECTION_KEYS = {
    "traits": "traits",
    "actions": "actions",
    "bonus_actions": "bonusActions",
    "reactions": "reactions",
    "legendary": "legendaryActions",
}


def _minus(text: str) -> str:
    return text.replace("−", "-")


# El tamaño viene en masculino o femenino según el tipo de criatura
# ("Monstruosidad Gargantuesca" / "Dragón Gargantuesco"). Se normaliza a una
# única forma canónica para que sea filtrable.
SIZES = {
    "diminuto": "Diminuto", "diminuta": "Diminuto",
    "pequeño": "Pequeño", "pequeña": "Pequeño",
    "mediano": "Mediano", "mediana": "Mediano",
    "grande": "Grande",
    "enorme": "Enorme",
    "gigantesco": "Gigantesco", "gigantesca": "Gigantesco",
    "gargantuesco": "Gargantuesco", "gargantuesca": "Gargantuesco",
}


def _parse_meta(text: str) -> dict:
    """'Aberración Grande, legal malvada' -> tipo, tamaño, alineamiento.

    El alineamiento va tras la ÚLTIMA coma, no tras la primera: hay perfiles con
    coma en el tipo ("Celestial, feérico o infernal Grande (a tu elección),
    neutral").
    """
    head, _, alignment = text.rpartition(",")
    if not head:
        head, alignment = text, ""
    words = head.strip().split()
    size = next((SIZES[w.lower()] for w in words if w.lower() in SIZES), None)
    kind = " ".join(w for w in words if w.lower() not in SIZES and w not in {"o", "más", "y"})
    out = {"metaRaw": text, "type": kind.strip(" ,"), "alignment": alignment.strip() or None}
    if size:
        out["size"] = size
    swarm = re.search(r"\(([^)]*)\)", head)
    if swarm:
        out["tags"] = [t.strip() for t in swarm.group(1).split(",")]
        out["type"] = re.sub(r"\s*\([^)]*\)", "", out["type"]).strip()
    return out


def _parse_speeds(raw: str) -> dict:
    speeds: dict[str, float] = {}
    for name, value in SPEED_RE.findall(raw):
        key = (name or "").strip().lower() or "caminando"
        speeds[key] = float(value.replace(",", "."))
    return speeds


def _split_header(text: str, labels: dict[str, str]) -> dict[str, str]:
    """Trocea 'CA: 17 Iniciativa: +7 (17) PG: 150 (…)' por etiqueta conocida."""
    names = sorted(labels.values(), key=len, reverse=True)
    pattern = re.compile(r"(" + "|".join(re.escape(n) for n in names) + r"):")
    parts: dict[str, str] = {}
    matches = list(pattern.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts[match.group(1)] = text[match.end() : end].strip()
    return parts


def _parse_abilities(text: str) -> dict:
    out: dict[str, dict] = {}
    for abbr, score, mod, save in ABILITY_RE.findall(_minus(text)):
        out[ABILITY_KEYS[abbr]] = {
            "score": int(score),
            "mod": int(mod),
            "save": int(save),
        }
    return out


def _parse_cr(raw: str) -> dict:
    out: dict = {"raw": raw}
    match = CR_RE.match(_minus(raw))
    if not match:
        return out
    cr = match.group(1)
    out["cr"] = number(cr) if "/" in cr else int(cr)
    out["xp"] = int(match.group(2).replace(" ", ""))
    if match.group(3):
        out["proficiencyBonus"] = int(match.group(3))
    lair = re.search(r"o\s+([\d\s]+)\s+en la guarida", raw)
    if lair:
        out["xpInLair"] = int(lair.group(1).replace(" ", ""))
    return out


def _entries(parts: list[dict], start: int, end: int) -> list[dict]:
    out = []
    for part in parts[start:end]:
        if part["type"] != "body":
            continue
        name, rest = split_runin(part["md"])
        entry = {"name": name, "md": part["md"], "page": part["source"]["page"]}
        if name:
            entry["description"] = rest
            uses = re.search(r"\(([^)]*(?:/d[íi]a|recarga|guarida)[^)]*)\)", name, re.I)
            if uses:
                entry["uses"] = uses.group(1)
                entry["name"] = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
        out.append(entry)
    return out


def collect(document: dict, lang: Language) -> list[dict]:
    labels = lang.statblock_labels
    sections = {v: k for k, v in lang.statblock_sections.items()}
    taken: set[str] = set()
    monsters: list[dict] = []

    for ancestors, node in statblocks(document):
        parts = node["parts"]
        header_text = " ".join(p["text"] for p in parts if p["type"] == "header")
        fields = _split_header(header_text, labels)

        monster: dict = {
            "id": make_id("monster", node["name"], taken),
            "name": node["name"],
            "source": source_of(node, f"SRD {lang.srd_version} {lang.code}"),
            "context": [a for a in ancestors if a][-1:],
        }

        meta = next((p["text"] for p in parts if p["type"] == "meta"), "")
        if meta:
            monster.update(_parse_meta(meta))

        # Todos los campos conservan su `raw`: hay perfiles con valores no
        # numéricos legítimos ("PG: la mitad de los pg máximos de su invocador",
        # "VD: ninguno"), y perderlos sería peor que no parsearlos.
        if labels["ac"] in fields:
            monster["ac"] = number(fields[labels["ac"]])
            monster["acRaw"] = fields[labels["ac"]]
        if labels["initiative"] in fields:
            match = INITIATIVE_RE.search(_minus(fields[labels["initiative"]]))
            if match:
                monster["initiative"] = {"mod": int(match.group(1))}
                if match.group(2):
                    monster["initiative"]["score"] = int(match.group(2))
        if labels["hp"] in fields:
            raw = fields[labels["hp"]]
            monster["hp"] = {"raw": raw}
            match = HP_RE.match(raw)
            if match:
                monster["hp"]["average"] = int(match.group(1))
                if match.group(2):
                    monster["hp"]["formula"] = re.sub(r"\s+", " ", match.group(2))
        if labels["speed"] in fields:
            monster["speeds"] = _parse_speeds(fields[labels["speed"]])

        for key in ("skills", "senses", "languages", "immunities", "resistances", "vulnerabilities", "gear"):
            raw = fields.get(labels[key])
            if not raw:
                continue
            if key == "skills":
                monster["skills"] = {
                    name.strip(): int(_minus(bonus))
                    for name, bonus in re.findall(r"([A-Za-zÁÉÍÓÚáéíóúñ ]+?)\s*([+-]?−?\d+)", _minus(raw))
                }
            elif key == "senses":
                passive = re.search(r"pasiva\s+(\d+)", raw, re.I)
                monster["senses"] = {"raw": raw}
                if passive:
                    monster["senses"]["passivePerception"] = int(passive.group(1))
            elif key == "languages":
                monster["languages"] = [l.strip() for l in re.split(r"[;,]", raw) if l.strip()]
            else:
                monster[key] = [t.strip() for t in re.split(r"[;,]", raw) if t.strip()]

        if labels["cr"] in fields:
            monster["challenge"] = _parse_cr(fields[labels["cr"]])

        ability = next((p["text"] for p in parts if p["type"] == "ability"), "")
        if ability:
            monster["abilities"] = _parse_abilities(ability)

        # las secciones parten la lista de partes en tramos
        marks = [(i, p["text"]) for i, p in enumerate(parts) if p["type"] == "section"]
        for order, (index, title) in enumerate(marks):
            end = marks[order + 1][0] if order + 1 < len(marks) else len(parts)
            key = SECTION_KEYS.get(sections.get(title, ""), None)
            entries = _entries(parts, index + 1, end)
            if key is None:
                monster.setdefault("otherSections", []).append({"title": title, "entries": entries})
                continue
            if key == "legendaryActions":
                intro = next(
                    (p["text"] for p in parts[index + 1 : end] if p["type"] == "meta"), None
                )
                block: dict = {"actions": entries}
                if intro:
                    block["intro"] = intro
                    uses = re.search(r":\s*(\d+)", intro)
                    if uses:
                        block["uses"] = int(uses.group(1))
                    lair = re.search(r"\((\d+)\s+en la guarida\)", intro)
                    if lair:
                        block["usesInLair"] = int(lair.group(1))
                monster["legendary"] = block
            else:
                monster[key] = entries

        monsters.append(monster)
    return monsters


NAME = "monsters"
INDEX_FIELDS = ["id", "name", "size", "type", "alignment", "ac", "challenge"]
