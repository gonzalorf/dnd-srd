"""CLI del extractor.

    python -m extractor extract    PDF  -> data/raw/<lang>/pages.jsonl
    python -m extractor blocks          -> data/interim/<lang>/blocks.json
    python -m extractor document        -> data/processed/<lang>/document.json
    python -m extractor collect         -> data/processed/<lang>/collections/
    python -m extractor export          -> schemas/, srd.sqlite, markdown/
    python -m extractor validate        -> reports/validation-<lang>.md
    python -m extractor build           -> todo lo anterior en orden
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .blocks import build_blocks, markdown
from .collect import run as run_collect
from .config import DATA_DIR, REPORTS_DIR, ROOT, load_language, load_styles
from .document import build_document, summarize
from .export import markdown as export_markdown
from .export import schemas as export_schemas
from .export import sqlite as export_sqlite
from .rawdump import run as run_extract
from .validate import validate


def _paths(code: str) -> dict[str, Path]:
    return {
        "raw": DATA_DIR / "raw" / code,
        "interim": DATA_DIR / "interim" / code,
        "processed": DATA_DIR / "processed" / code,
    }


def cmd_extract(args) -> int:
    lang = load_language(args.lang)
    styles = load_styles()
    if not lang.source.exists():
        print(f"ERROR: no encuentro {lang.source}", file=sys.stderr)
        return 1
    paths = _paths(lang.code)
    fingerprint = run_extract(lang, styles, paths["raw"])
    print(f"  paginas          : {fingerprint['pages']}")
    print(f"  sha256           : {fingerprint['sha256'][:16]}…")
    print(f"  huellas distintas: {len(fingerprint['styles'])}")
    unknown = fingerprint["unknown_styles"]
    if unknown:
        total = sum(u["spans"] for u in unknown)
        print(f"  AVISO: {len(unknown)} huellas sin clasificar ({total} spans)")
        for item in unknown[:8]:
            print(f"     {item['spans']:>6}  {item['font']} {item['size']} #{item['color']:06X}")
    else:
        print("  todas las huellas tipograficas estan clasificadas")
    print(f"  -> {paths['raw'] / 'pages.jsonl'}")
    return 0


def cmd_blocks(args) -> int:
    lang = load_language(args.lang)
    styles = load_styles()
    paths = _paths(lang.code)
    blocks = build_blocks(paths["raw"], styles, lang)
    paths["interim"].mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "type": b.type,
            "level": b.level,
            "page": b.page,
            "pages": b.pages,
            "column": b.column,
            "region": b.region,
            "bbox": b.bbox,
            "text": b.text,
            "md": markdown(b, styles),
            **({"table": b.table.to_dict()} if b.table else {}),
        }
        for b in blocks
    ]
    out = paths["interim"] / "blocks.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    counts: dict[str, int] = {}
    for b in blocks:
        counts[b.type] = counts.get(b.type, 0) + 1
    print(f"  bloques: {len(blocks)}")
    for key in sorted(counts, key=lambda k: -counts[k]):
        print(f"     {counts[key]:>6}  {key}")
    print(f"  -> {out}")
    return 0


def cmd_document(args) -> int:
    lang = load_language(args.lang)
    styles = load_styles()
    paths = _paths(lang.code)
    blocks = build_blocks(paths["raw"], styles, lang)
    document = build_document(blocks, styles, lang)
    paths["processed"].mkdir(parents=True, exist_ok=True)
    out = paths["processed"] / "document.json"
    out.write_text(json.dumps(document, ensure_ascii=False, indent=1), "utf-8")
    counts = summarize(document)
    for key in sorted(counts, key=lambda k: -counts[k]):
        print(f"     {counts[key]:>6}  {key}")
    print(f"  -> {out}  ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


def cmd_collect(args) -> int:
    lang = load_language(args.lang)
    paths = _paths(lang.code)
    document = json.loads((paths["processed"] / "document.json").read_text("utf-8"))
    summary = run_collect(document, lang, paths["processed"] / "collections")
    total = summary.pop("_ids")
    links = summary.pop("_links")
    lock = summary.pop("_lock")
    for key in sorted(summary, key=lambda k: -summary[k]):
        print(f"     {summary[key]:>6}  {key}")
    print(f"  {total} entidades con id estable")
    print(f"  {links} referencias cruzadas resueltas")
    if lock["added"] or lock["retired"]:
        print(f"  ids: +{len(lock['added'])} nuevos, -{len(lock['retired'])} retirados")
    else:
        print(f"  ids: {lock['total']} estables, sin cambios respecto al lock")
    print(f"  -> {paths['processed'] / 'collections'}")
    return 0


def cmd_export(args) -> int:
    lang = load_language(args.lang)
    paths = _paths(lang.code)
    processed = paths["processed"]
    collections = processed / "collections"
    indexes = processed / "indexes"

    written = export_schemas.run(collections, ROOT / "schemas" / lang.code)
    print(f"  esquemas JSON  : {len(written)} colecciones -> schemas/{lang.code}/")

    stats = export_sqlite.run(collections, indexes, processed / "srd.sqlite")
    print(f"  sqlite + FTS5  : {stats['entities']} entidades, {stats['links']} enlaces, "
          f"{stats['bytes'] / 1024 / 1024:.1f} MB")

    document = json.loads((processed / "document.json").read_text("utf-8"))
    chapters = export_markdown.run(document, processed / "markdown")
    print(f"  markdown       : {chapters} capítulos -> {processed / 'markdown'}")
    return 0


def cmd_validate(args) -> int:
    lang = load_language(args.lang)
    paths = _paths(lang.code)
    document = json.loads((paths["processed"] / "document.json").read_text("utf-8"))
    fingerprint = json.loads((paths["raw"] / "fingerprint.json").read_text("utf-8"))
    report, ok = validate(document, fingerprint, lang, paths["processed"] / "collections")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"validation-{lang.code}.md"
    out.write_text(report, "utf-8")
    print(report)
    print(f"  -> {out}")
    return 0 if ok else 1


def cmd_build(args) -> int:
    for step, fn in (
        ("extract", cmd_extract),
        ("blocks", cmd_blocks),
        ("document", cmd_document),
        ("collect", cmd_collect),
        ("export", cmd_export),
        ("validate", cmd_validate),
    ):
        print(f"\n=== {step} ===")
        code = fn(args)
        if code and step != "validate":
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="extractor", description="Extractor estructurado del SRD")
    parser.add_argument("--lang", default="es", help="código de idioma (config/lang/<code>.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn, help_text in (
        ("extract", cmd_extract, "PDF -> volcado crudo"),
        ("blocks", cmd_blocks, "volcado crudo -> bloques tipados"),
        ("document", cmd_document, "bloques -> árbol jerárquico"),
        ("collect", cmd_collect, "árbol -> colecciones de dominio"),
        ("export", cmd_export, "esquemas JSON, SQLite con FTS5 y markdown"),
        ("validate", cmd_validate, "comprobar invariantes"),
        ("build", cmd_build, "ejecutar todo el pipeline"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=fn)
    args = parser.parse_args(argv)
    return args.func(args)
