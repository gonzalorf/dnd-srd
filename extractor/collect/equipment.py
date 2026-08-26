"""Equipo: armas, armaduras, herramientas, equipo de aventureros y monturas.

A diferencia de conjuros y perfiles, aquí los datos técnicos viven en TABLAS y
las descripciones en entradas sueltas. Se cruzan las dos cosas: cada fila de la
tabla se convierte en una ficha, y si existe una entrada con ese nombre se le
adjunta la descripción.

Las tablas traen filas de encabezado de grupo («Armas cuerpo a cuerpo
sencillas») con una sola celda rellena: no son objetos, son subtítulos, y se
usan para etiquetar las filas que las siguen.
"""

from __future__ import annotations

import re

from ..config import Language
from .common import blocks_of, make_id, plain_text, source_of, walk
from ..textutil import slugify

PRICE_RE = re.compile(r"^\s*([\d.,]+)\s*(pc|pp|pe|po|ppt)\s*$", re.I)
WEIGHT_RE = re.compile(r"^\s*([\d.,]+)\s*kg\s*$", re.I)
COIN_VALUE = {"pc": 0.01, "pp": 0.1, "pe": 0.5, "po": 1.0, "ppt": 10.0}

TABLES = {
    "Armas": "weapon",
    "Armaduras": "armor",
    "Equipo de aventureros": "gear",
    "Herramientas": "tool",
    "Monturas y otros animales": "mount",
    "Arreos": "tack",
    "Vehículos terrestres": "vehicle",
    "Vehículos acuáticos y aéreos": "vehicle",
    "Canalizadores arcanos": "focus",
    "Munición": "ammunition",
}


def _number(text: str) -> float | None:
    if not text:
        return None
    value = text.replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def _price(text: str) -> dict | None:
    match = PRICE_RE.match(text)
    if not match:
        return None
    amount = _number(match.group(1))
    coin = match.group(2).lower()
    out = {"raw": text, "amount": amount, "coin": coin}
    if amount is not None and coin in COIN_VALUE:
        out["gp"] = round(amount * COIN_VALUE[coin], 4)
    return out


def _weight(text: str) -> dict | None:
    match = WEIGHT_RE.match(text)
    if not match:
        return None
    return {"raw": text, "kg": _number(match.group(1))}


def _is_group_row(row: list[str]) -> bool:
    """Fila de subtítulo: una sola celda con contenido."""
    filled = [c for c in row if c.strip()]
    return len(filled) == 1 and len(row) > 1


def _descriptions(document: dict, lang: Language) -> dict[str, dict]:
    """Entradas del capítulo Equipo indexadas por slug del nombre.

    Los títulos llevan el precio detrás («Abrojos (1 po)»), así que se indexa
    también la versión sin él para poder cruzarlos con las filas de tabla.
    """
    out: dict[str, dict] = {}
    chapter = lang.sections["equipment"]
    for ancestors, node in walk(document):
        if node.get("type") != "entry" or chapter not in ancestors:
            continue
        title = node["title"]
        body = blocks_of(node.get("children", []))
        record = {
            "title": title,
            "text": plain_text(body),
            "blocks": body,
            "page": node["source"]["page"],
        }
        out.setdefault(slugify(title), record)
        bare = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
        out.setdefault(slugify(bare), record)
    return out


def collect(document: dict, lang: Language) -> list[dict]:
    chapter = lang.sections["equipment"]
    descriptions = _descriptions(document, lang)
    taken: set[str] = set()
    items: list[dict] = []

    for ancestors, table in walk(document):
        if table.get("type") != "table" or chapter not in ancestors:
            continue
        caption = table.get("caption") or ""
        kind = next((v for k, v in TABLES.items() if caption.startswith(k)), None)
        if kind is None:
            continue

        header = [h.strip() for h in table.get("header", [])]
        group: str | None = None
        for row in table.get("rows", []):
            if not row or not any(c.strip() for c in row):
                continue
            if _is_group_row(row):
                group = next(c for c in row if c.strip())
                continue

            name = row[0].strip()
            if not name:
                continue
            fields = {header[i] if i < len(header) else f"col{i}": row[i] for i in range(len(row))}

            item: dict = {
                "id": make_id(kind, name, taken),
                "name": name,
                "kind": kind,
                "group": group,
                "table": caption,
                "fields": {k: v for k, v in fields.items() if v.strip()},
                "source": {"book": f"SRD {lang.srd_version} {lang.code}", "page": table["source"]["page"]},
            }
            for label, value in fields.items():
                if label.lower().startswith("precio"):
                    price = _price(value)
                    if price:
                        item["price"] = price
                elif label.lower().startswith("peso"):
                    weight = _weight(value)
                    if weight:
                        item["weight"] = weight

            description = descriptions.get(slugify(name))
            if description:
                item["text"] = description["text"]
                item["blocks"] = description["blocks"]
                item["descriptionPage"] = description["page"]

            items.append(item)

    items += _from_entries(document, lang, taken, {i["id"] for i in items})
    return items


# Las herramientas y las monturas no tienen tabla propia en el SRD: son entradas
# con el precio metido en el título ("Herramientas de albañil (10 po)").
ENTRY_SECTIONS = {
    "Herramientas de artesano": "tool",
    "Otras herramientas": "tool",
    "Monturas y cargamento": "mount",
    "Barda": "tack",
    "Sillas": "tack",
    "Vehículos grandes": "vehicle",
}
TITLE_PRICE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<price>[\d.,]+\s*(?:pc|pp|pe|po|ppt))\)\s*$", re.I)


def _from_entries(document: dict, lang: Language, taken: set[str], seen: set[str]) -> list[dict]:
    out = []
    for ancestors, node in walk(document):
        if node.get("type") != "entry":
            continue
        kind = next((v for a in ancestors if a for k, v in ENTRY_SECTIONS.items() if a.startswith(k)), None)
        if kind is None:
            continue
        title = node["title"]
        match = TITLE_PRICE_RE.match(title)
        name = match.group("name").strip() if match else title
        body = blocks_of(node.get("children", []))
        item: dict = {
            "id": make_id(kind, name, taken),
            "name": name,
            "kind": kind,
            "group": ancestors[-1] if ancestors else None,
            "text": plain_text(body),
            "blocks": body,
            "source": source_of(node, f"SRD {lang.srd_version} {lang.code}"),
        }
        if match:
            price = _price(match.group("price"))
            if price:
                item["price"] = price
        out.append(item)
    return out


NAME = "equipment"
INDEX_FIELDS = ["id", "name", "kind", "group", "price", "weight"]
