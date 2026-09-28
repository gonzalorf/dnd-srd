"""Comprobación de invariantes sobre el árbol generado.

La gracia no es que pase, sino que cuando una versión futura del PDF cambie algo
el pipeline lo diga en vez de producir datos malos en silencio. Las cifras
esperadas están medidas sobre SP_SRD_CC_v5.2.1.pdf.
"""

from __future__ import annotations

from collections import Counter

from .config import Language

# Cifras verificadas contra el PDF, no estimadas. Si una versión futura del
# documento cambia alguna, `validate` falla y hay que revisar qué ha pasado
# antes de dar los datos por buenos.
EXPECTED = {
    "es": {
        "5.2.1": {
            "pages": 398,
            "chapter": 16,
            "section": 245,
            "subsection": 215,
            "entry": 1372,
            "statblock": 336,
            "sidebar": 18,
            "unknown_styles": 0,
            "collections": {
                "spells": 339,
                "monsters": 336,
                "magic-items": 258,
                "tables": 251,
                "equipment": 198,
                "rules-glossary": 155,
                "sidebars": 18,
                "feats": 17,
                "classes": 12,
                "species": 9,
                "backgrounds": 4,
            },
            "crossrefs": 632,
            "toc": {"entries": 480, "withPage": 480},
        }
    }
}


def _walk(node: dict, depth: int = 0):
    yield depth, node
    for child in node.get("children", []):
        yield from _walk(child, depth + 1)


def _check_collections(collections_dir, expected: dict) -> list[tuple[str, bool, str]]:
    """Invariantes de las colecciones de dominio."""
    import json as _json

    checks: list[tuple[str, bool, str]] = []
    if not collections_dir.exists():
        return [("colecciones generadas", False, "falta data/processed/<lang>/collections")]

    ids: set[str] = set()
    duplicated: list[str] = []
    for name, count in expected.items():
        path = collections_dir / f"{name}.json"
        if not path.exists():
            checks.append((f"colección {name}", False, "no generada"))
            continue
        records = _json.loads(path.read_text("utf-8"))
        checks.append((f"colección {name}", len(records) == count, f"esperado {count}, obtenido {len(records)}"))
        for record in records:
            if record["id"] in ids:
                duplicated.append(record["id"])
            ids.add(record["id"])
    checks.append(("identificadores únicos", not duplicated, f"{len(duplicated)} repetidos"))

    spells_path = collections_dir / "spells.json"
    if spells_path.exists():
        spells = _json.loads(spells_path.read_text("utf-8"))
        incomplete = [s["name"] for s in spells if not all(
            s.get(k) for k in ("castingTime", "range", "components", "duration"))]
        checks.append(("conjuros con sus 4 propiedades", not incomplete, f"{len(incomplete)} incompletos"))
        no_school = [s["name"] for s in spells if not s.get("school")]
        checks.append(("conjuros con escuela", not no_school, f"{len(no_school)} sin escuela"))

    monsters_path = collections_dir / "monsters.json"
    if monsters_path.exists():
        monsters = _json.loads(monsters_path.read_text("utf-8"))
        bad = [m["name"] for m in monsters if len(m.get("abilities", {})) != 6]
        checks.append(("perfiles con las 6 características", not bad, f"{len(bad)} incompletos"))
        sizeless = [m["name"] for m in monsters if not m.get("size")]
        checks.append(("perfiles con tamaño", not sizeless, f"{len(sizeless)} sin tamaño"))

    classes_path = collections_dir / "classes.json"
    if classes_path.exists():
        classes = _json.loads(classes_path.read_text("utf-8"))
        bad = [c["name"] for c in classes if not c.get("coreTraits") or not c.get("progression")]
        checks.append(("clases con atributos básicos y progresión", not bad, f"{len(bad)} incompletas"))
        short = [c["name"] for c in classes if len(c.get("progression", {}).get("rows", [])) != 20]
        checks.append(("progresión de 20 niveles", not short, f"{len(short)} con otro número"))

    items_path = collections_dir / "magic-items.json"
    if items_path.exists():
        items = _json.loads(items_path.read_text("utf-8"))
        bad = [i["name"] for i in items if not i.get("category") or not i.get("rarity")]
        checks.append(("objetos con categoría y rareza", not bad, f"{len(bad)} incompletos"))

    return checks


def validate(document: dict, fingerprint: dict, lang: Language, collections_dir=None) -> tuple[str, bool]:
    counts: Counter[str] = Counter()
    missing_page: list[str] = []
    empty: list[str] = []

    for _, node in _walk(document):
        kind = node.get("type", "?")
        counts[kind] += 1
        if kind == "document":
            continue
        source = node.get("source")
        if not source or not source.get("page"):
            missing_page.append(f"{kind}: {node.get('title') or node.get('text', '')[:50]}")
        if kind in {"chapter", "section", "subsection", "entry"} and not node.get("title"):
            empty.append(kind)

    expected = EXPECTED.get(lang.code, {}).get(lang.srd_version, {})
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, actual, want) -> None:
        checks.append((label, actual == want, f"esperado {want}, obtenido {actual}"))

    labels = {
        "chapter": "capítulos",
        "section": "secciones",
        "subsection": "subsecciones",
        "entry": "entradas",
        "statblock": "perfiles de criatura",
        "sidebar": "cuadros destacados",
    }
    if expected:
        check("páginas del PDF", fingerprint["pages"], expected["pages"])
        for key, label in labels.items():
            if key in expected:
                check(label, counts.get(key, 0), expected[key])
        check(
            "huellas tipográficas sin clasificar",
            len(fingerprint["unknown_styles"]),
            expected["unknown_styles"],
        )
    if expected.get("toc"):
        from .toc import summarize as toc_summary

        got = toc_summary(document)
        check("entradas del índice", got["entries"], expected["toc"]["entries"])
        check("entradas del índice con página", got["withPage"], expected["toc"]["withPage"])

    checks.append(("todos los nodos con página", not missing_page, f"{len(missing_page)} sin página"))
    checks.append(("títulos no vacíos", not empty, f"{len(empty)} vacíos"))
    # Cualquier bloque con texto que no produzca nodo es contenido perdido.
    # Esta comprobación destapó 47 recuadros de fórmula que se caían del árbol.
    dropped = document.get("dropped") or {}
    checks.append(
        ("bloques sin nodo en el árbol", not dropped, f"{sum(dropped.values())} descartados: {dropped}")
    )

    collection_checks: list[tuple[str, bool, str]] = []
    if collections_dir is not None and expected.get("collections"):
        collection_checks = _check_collections(collections_dir, expected["collections"])
        crossrefs = collections_dir.parent / "indexes" / "crossrefs.json"
        if crossrefs.exists() and expected.get("crossrefs"):
            import json as _json2

            links = _json2.loads(crossrefs.read_text("utf-8"))["links"]
            collection_checks.append(
                ("referencias cruzadas resueltas", links == expected["crossrefs"],
                 f"esperado {expected['crossrefs']}, obtenido {links}")
            )

    ok = all(passed for _, passed, _ in checks + collection_checks)

    lines = [
        f"# Validación — SRD {lang.srd_version} ({lang.name})",
        "",
        f"Fuente: `{fingerprint['source']}`",
        f"SHA-256: `{fingerprint['sha256']}`",
        "",
        "## Invariantes",
        "",
        "| comprobación | resultado | detalle |",
        "|---|---|---|",
    ]
    for label, passed, detail in checks:
        lines.append(f"| {label} | {'OK' if passed else 'FALLA'} | {detail} |")

    if collection_checks:
        lines += ["", "## Colecciones de dominio", "", "| comprobación | resultado | detalle |", "|---|---|---|"]
        for label, passed, detail in collection_checks:
            lines.append(f"| {label} | {'OK' if passed else 'FALLA'} | {detail} |")

    lines += ["", "## Inventario del árbol", "", "| tipo de nodo | n |", "|---|---|"]
    for kind in sorted(counts, key=lambda k: -counts[k]):
        lines.append(f"| {kind} | {counts[kind]} |")

    if fingerprint["unknown_styles"]:
        lines += [
            "",
            "## Huellas tipográficas sin clasificar",
            "",
            "Añádelas a `config/styles.yaml` o confirma que son descartables.",
            "",
            "| fuente | tamaño | color | spans |",
            "|---|---|---|---|",
        ]
        for item in fingerprint["unknown_styles"][:40]:
            lines.append(
                f"| {item['font']} | {item['size']} | #{item['color']:06X} | {item['spans']} |"
            )

    if missing_page:
        lines += ["", "## Nodos sin página", ""] + [f"- {m}" for m in missing_page[:40]]

    return "\n".join(lines) + "\n", ok
