"""Fase 1: PDF -> data/raw/<lang>/pages.jsonl

Vuelca todos los spans y los rectángulos vectoriales relevantes de cada página,
sin interpretar nada. A partir de aquí el resto del pipeline no vuelve a abrir
el PDF, lo que permite depurar y comparar versiones sin coste.

Se emite también fingerprint.json con el SHA-256 del PDF y el inventario de
huellas tipográficas: es lo que permite detectar que una versión nueva del
documento fuente ha cambiado de maquetación ANTES de generar datos malos.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pymupdf

from .config import Language, Styles

# Los trazos finos y los rectángulos diminutos son decoración (filetes,
# separadores); no aportan nada a la estructura y multiplican el tamaño
# del volcado por diez.
MIN_RECT_W = 20.0
MIN_RECT_H = 4.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _spans_of(page: pymupdf.Page) -> list[dict]:
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if not span["text"].strip():
                    continue
                # `origin` es la línea base. Es el ÚNICO dato de posición
                # vertical fiable: los bbox de la fuente Cambria vienen con
                # las métricas infladas y llegan a solaparse e invertirse
                # entre líneas consecutivas.
                out.append(
                    {
                        "t": span["text"],
                        "f": span["font"],
                        "s": round(span["size"], 3),
                        "c": span["color"],
                        "fl": span["flags"],
                        "x": round(span["origin"][0], 2),
                        "y": round(span["origin"][1], 2),
                        "bbox": [round(v, 2) for v in span["bbox"]],
                    }
                )
    return out


def _rects_of(page: pymupdf.Page) -> list[dict]:
    out = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.width < MIN_RECT_W or rect.height < MIN_RECT_H:
            continue
        fill = drawing.get("fill")
        if fill is None:
            continue  # solo interesan los rellenos: delimitan tablas y cuadros
        out.append(
            {
                "kind": drawing["type"],
                "rect": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                "fill": [round(c, 3) for c in fill],
            }
        )
    return out


def run(lang: Language, styles: Styles, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(lang.source)

    inventory: Counter[tuple[str, float, int]] = Counter()
    unknown: Counter[tuple[str, float, int]] = Counter()
    pages_path = out_dir / "pages.jsonl"

    with pages_path.open("w", encoding="utf-8") as fh:
        for index in range(doc.page_count):
            page = doc[index]
            spans = _spans_of(page)
            for span in spans:
                key = (span["f"], span["s"], span["c"])
                inventory[key] += 1
                if styles.match(*key) is None:
                    unknown[key] += 1
            record = {
                "page": index + 1,
                "width": round(page.rect.width, 2),
                "height": round(page.rect.height, 2),
                "spans": spans,
                "rects": _rects_of(page),
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    fingerprint = {
        "source": str(lang.source.relative_to(lang.source.parents[1])),
        "sha256": sha256(lang.source),
        "pages": doc.page_count,
        "srd_version": lang.srd_version,
        "language": lang.code,
        "styles": sorted(
            ({"font": f, "size": s, "color": c, "spans": n} for (f, s, c), n in inventory.items()),
            key=lambda d: -d["spans"],
        ),
        "unknown_styles": sorted(
            ({"font": f, "size": s, "color": c, "spans": n} for (f, s, c), n in unknown.items()),
            key=lambda d: -d["spans"],
        ),
    }
    (out_dir / "fingerprint.json").write_text(
        json.dumps(fingerprint, ensure_ascii=False, indent=2), "utf-8"
    )
    doc.close()
    return fingerprint


def load_pages(raw_dir: Path):
    """Itera el volcado crudo página a página."""
    with (raw_dir / "pages.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)
