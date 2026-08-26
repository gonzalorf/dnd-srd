"""Carga de config/styles.yaml y config/lang/<code>.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


@dataclass(frozen=True)
class StyleRule:
    role: str
    font: str
    size: float
    color: int
    level: int | None = None
    discard: bool = False


@dataclass
class Styles:
    rules: list[StyleRule]
    tolerance: float
    fills: dict[str, list[float]]
    heading_roles: set[str]
    statblock_roles: set[str]
    inline_emphasis: dict[str, set[str]]

    def match(self, font: str, size: float, color: int) -> StyleRule | None:
        """Devuelve la primera regla cuya huella casa con el span."""
        for rule in self.rules:
            if (
                rule.font == font
                and abs(rule.size - size) <= self.tolerance
                and rule.color == color
            ):
                return rule
        return None

    def level_of(self, role: str) -> int | None:
        for rule in self.rules:
            if rule.role == role:
                return rule.level
        return None


@dataclass
class Language:
    code: str
    name: str
    source: Path
    srd_version: str
    book_title: str
    layout: dict[str, Any]
    chrome: dict[str, Any]
    statblock_labels: dict[str, str]
    abilities: list[str]
    statblock_sections: dict[str, str]
    spell_props: dict[str, str]
    sections: dict[str, str]
    list_markers: dict[str, str] = field(default_factory=dict)

    @property
    def column_split(self) -> float:
        return float(self.layout["column_split_x"])

    @property
    def full_width_min(self) -> float:
        return float(self.layout["full_width_min"])


def load_styles(path: Path | None = None) -> Styles:
    raw = yaml.safe_load((path or CONFIG_DIR / "styles.yaml").read_text("utf-8"))
    colors = raw["colors"]
    rules = [
        StyleRule(
            role=item["role"],
            font=item["font"],
            size=float(item["size"]),
            color=colors[item["color"]] if isinstance(item["color"], str) else int(item["color"]),
            level=item.get("level"),
            discard=bool(item.get("discard", False)),
        )
        for item in raw["styles"]
    ]
    return Styles(
        rules=rules,
        tolerance=float(raw["meta"]["size_tolerance"]),
        fills={
            k: [float(x) for x in (v if isinstance(v, list) else [v])]
            for k, v in raw["fills"].items()
        },
        heading_roles=set(raw["heading_roles"]),
        statblock_roles=set(raw["statblock_roles"]),
        inline_emphasis={k: set(v) for k, v in raw["inline_emphasis"].items()},
    )


def load_language(code: str = "es") -> Language:
    raw = yaml.safe_load((CONFIG_DIR / "lang" / f"{code}.yaml").read_text("utf-8"))
    return Language(
        code=raw["code"],
        name=raw["name"],
        source=ROOT / raw["source"],
        srd_version=raw["srd_version"],
        book_title=raw["book_title"],
        layout=raw["layout"],
        chrome=raw["chrome"],
        statblock_labels=raw["statblock_labels"],
        abilities=raw["abilities"],
        statblock_sections=raw["statblock_sections"],
        spell_props=raw["spell_props"],
        sections=raw["sections"],
        list_markers=raw.get("list_markers", {}),
    )
