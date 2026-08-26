"""Reconstrucción de la geometría de la página: regiones, líneas y orden de lectura.

Tres problemas que resuelve este módulo, y que son los que hacen fracasar una
extracción ingenua del SRD:

1. Los bloques que devuelve PyMuPDF mezclan títulos con cuerpo de texto y llegan
   intercalados entre las dos columnas. Se trabaja a nivel de span y se reagrupa
   por línea base.

2. Los `bbox` de la fuente Cambria son inservibles (métricas infladas, se
   solapan e invierten entre líneas consecutivas). Se usa `origin`.

3. Algunas tablas ocupan el ancho completo y rompen el flujo de dos columnas.
   Se detectan por su rectángulo de fondo y se ordena la página en bandas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Language, Styles
from .textutil import clean

FILL_TOLERANCE = 0.02

# Hueco horizontal mínimo entre dos spans para considerarlo un espacio.
SPAN_GAP = 0.9

# Medianil entre columnas. Por debajo de esto, dos trozos a la misma altura son
# una única línea a ancho de página, no dos columnas.
COLUMN_GUTTER = 12.0


def needs_space(previous: dict, span: dict) -> bool:
    if previous["t"].endswith((" ", "\t", "­")) or span["t"].startswith((" ", "\t")):
        return False
    return span["x"] - previous["bbox"][2] > SPAN_GAP


def spans_text(spans: list[dict]) -> str:
    parts: list[str] = []
    previous: dict | None = None
    for span in spans:
        if previous is not None and needs_space(previous, span):
            parts.append(" ")
        parts.append(span["t"])
        previous = span
    return "".join(parts)


@dataclass
class Region:
    kind: str  # 'table' | 'sidebar'
    index: int
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.index}"

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    def contains(
        self,
        x: float,
        y: float,
        pad: float = 2.0,
        pad_top: float | None = None,
        pad_bottom: float | None = None,
    ) -> bool:
        # El relleno vertical es asimétrico a propósito. Por arriba debe ser
        # corto: el fondo gris de la tabla de características de un perfil llega
        # casi hasta la línea "Velocidad:", que NO es parte de la tabla. Por
        # abajo debe ser mayor: la línea base de la última fila cae unos puntos
        # por debajo del borde del rectángulo.
        top = pad if pad_top is None else pad_top
        bottom = pad if pad_bottom is None else pad_bottom
        return self.x0 - pad <= x <= self.x1 + pad and self.y0 - top <= y <= self.y1 + bottom


@dataclass
class Line:
    page: int
    column: int
    y: float
    spans: list[dict]
    region: str | None = None
    fullwidth: bool = False
    roles: list[str] = field(default_factory=list)

    @property
    def x0(self) -> float:
        return self.spans[0]["x"]

    @property
    def x1(self) -> float:
        return max(s["bbox"][2] for s in self.spans)

    @property
    def raw(self) -> str:
        """Texto sin normalizar; conserva el guión blando final de línea.

        Los spans en versalitas (fuentes `*-SC700`) NO contienen espacios: la
        separación entre palabras se consigue posicionando cada fragmento, así
        que “Las excepciones se imponen” llega como
        ['L','as','excepciones','se','imponen']. Hay que reponer el espacio
        cuando entre dos spans queda un hueco horizontal real.
        """
        return spans_text(self.spans)

    @property
    def text(self) -> str:
        return clean(self.raw).strip()

    @property
    def role(self) -> str | None:
        """Rol dominante de la línea: el del span con más caracteres."""
        if not self.roles:
            return None
        weight: dict[str, int] = {}
        for span, role in zip(self.spans, self.roles):
            if role:
                weight[role] = weight.get(role, 0) + len(span["t"])
        return max(weight, key=weight.get) if weight else None

    @property
    def first_role(self) -> str | None:
        return self.roles[0] if self.roles else None


def _fill_is(fill: list[float], targets: list[float]) -> bool:
    return any(abs(fill[0] - t) <= FILL_TOLERANCE for t in targets)


def page_regions(record: dict, styles: Styles, lang: Language) -> list[Region]:
    """Deriva las regiones de la página a partir de los rectángulos de relleno.

    Un cuadro destacado es un rectángulo oscuro con otro claro dentro; una tabla
    es un rectángulo claro suelto. El rectángulo claro interior de un cuadro no
    debe confundirse con una tabla, de ahí el filtro por contención.
    """
    sidebars: list[Region] = []
    for rect in record["rects"]:
        if _fill_is(rect["fill"], styles.fills["sidebar_frame"]) and rect["rect"][2] - rect["rect"][0] > 50:
            x0, y0, x1, y1 = rect["rect"]
            sidebars.append(Region("sidebar", len(sidebars), x0, y0, x1, y1))

    tables: list[Region] = []
    for rect in record["rects"]:
        if not _fill_is(rect["fill"], styles.fills["table_body"]):
            continue
        x0, y0, x1, y1 = rect["rect"]
        # el fondo interior de un cuadro destacado no es una tabla
        if any(s.contains(x0 + 1, y0 + 1, pad=6) and s.contains(x1 - 1, y1 - 1, pad=6) for s in sidebars):
            continue
        tables.append(Region("table", len(tables), x0, y0, x1, y1))

    return sidebars + tables


def _column_of(x: float, lang: Language) -> int:
    return 0 if x < lang.column_split else 1


def build_lines(record: dict, styles: Styles, lang: Language) -> list[Line]:
    """Agrupa los spans de una página en líneas y las devuelve en orden de lectura."""
    regions = page_regions(record, styles, lang)
    tables = [r for r in regions if r.kind == "table"]
    sidebars = [r for r in regions if r.kind == "sidebar"]

    buckets: dict[tuple, list[dict]] = {}
    meta: dict[tuple, tuple[str | None, bool, int]] = {}

    for span in record["spans"]:
        rule = styles.match(span["f"], span["s"], span["c"])
        if rule is not None and rule.discard:
            continue

        x, y = span["x"], span["y"]
        # El pad horizontal debe ser corto: dos tablas en paneles laterales están
        # separadas por solo 7 pt y con un pad generoso se fusionan en una sola.
        # El vertical puede ser mayor, para recoger la cabecera que va encima.
        role = rule.role if rule else ""
        # El título va fuera de la tabla. Y la tabla de características de un
        # perfil, pese a ir sobre el mismo fondo gris, NO es una tabla: su
        # rectángulo no cubre la columna de abreviaturas (“Fue 21” cae a la
        # izquierda del borde), así que tratarla como tal pierde datos. Se deja
        # como bloque de perfil y la fase `collect` la parseará por posición.
        skip_region = role == "table.caption" or role.startswith("statblock.ability")
        table = (
            None
            if skip_region
            else next((t for t in tables if t.contains(x, y, pad=4, pad_top=3, pad_bottom=12)), None)
        )
        # La cabecera de una tabla queda FUERA del rectángulo de fondo: en las
        # tablas a ancho completo va hasta 40 pt por encima. Se adjunta span a
        # span, no línea a línea, porque una misma línea de cabecera puede
        # abarcar dos tablas contiguas en paneles laterales.
        if table is None and role == "table.header":
            table = next(
                (t for t in tables if t.x0 - 4 <= x <= t.x1 + 4 and 0 < t.y0 - y <= 60),
                None,
            )

        sidebar = next((s for s in sidebars if s.contains(x, y)), None)
        region = table.id if table else (sidebar.id if sidebar else None)
        fullwidth = bool(table and table.width >= lang.full_width_min)

        # Las filas de una tabla a ancho completo no se parten por columna.
        column = -1 if fullwidth else _column_of(x, lang)
        # La región forma parte de la clave: dos tablas en paneles laterales
        # comparten línea base, y sin esto sus celdas se agrupan en una sola
        # línea que acaba asignada a una región u otra según el orden en que
        # el PDF liste los spans.
        key = (region, column, round(y, 1))
        buckets.setdefault(key, []).append(span)
        meta[key] = (region, fullwidth, column)

    lines: list[Line] = []
    for key, spans in buckets.items():
        spans.sort(key=lambda s: s["x"])
        region, fullwidth, column = meta[key]
        line = Line(
            page=record["page"],
            column=column,
            y=key[2],
            spans=spans,
            region=region,
            fullwidth=fullwidth,
        )
        line.roles = [
            (lambda r: r.role if r else None)(styles.match(s["f"], s["s"], s["c"])) for s in spans
        ]
        lines.append(line)

    _merge_columns(lines)
    _merge_superscripts(lines)
    return _reading_order(lines, lang)


def _merge_columns(lines: list[Line]) -> None:
    """Reúne las líneas que en realidad son una sola a ancho de página.

    No todas las páginas van a dos columnas: la de información legal es de una
    sola, y cortar por x=302 partía cada línea en dos mitades que luego se
    ordenaban por separado. La pista es el hueco: entre dos columnas de verdad
    hay un medianil de unos 22 pt, mientras que dentro de una línea continua la
    separación entre palabras es de pocos puntos.
    """
    by_key: dict[tuple, list[Line]] = {}
    for line in lines:
        if line.column < 0:
            continue
        by_key.setdefault((line.region, line.y), []).append(line)

    for group in by_key.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda l: l.x0)
        left, right = group[0], group[1]
        if right.x0 - left.x1 > COLUMN_GUTTER:
            continue
        left.spans = left.spans + right.spans
        left.roles = left.roles + right.roles
        lines.remove(right)


def _merge_superscripts(lines: list[Line]) -> None:
    """Adjunta los superíndices a la línea a la que pertenecen.

    Un superíndice («250 m²», llamadas a nota) va sobre una línea base propia,
    unos 3 pt por encima de la del texto, así que forma una línea suelta que
    acaba ordenada delante del párrafo: el conjuro «Guardas y guardias» empezaba
    por un «2» huérfano en lugar de decir «250 m²».
    """
    hosts = [l for l in lines if l.role != "body.superscript"]
    for line in [l for l in lines if l.role == "body.superscript"]:
        candidates = [
            h
            for h in hosts
            if h.column == line.column and h.region == line.region and 0 <= h.y - line.y <= 5
        ]
        if not candidates:
            continue
        host = min(candidates, key=lambda h: h.y - line.y)
        merged = sorted(
            zip(host.spans + line.spans, host.roles + line.roles),
            key=lambda pair: pair[0]["x"],
        )
        host.spans = [span for span, _ in merged]
        host.roles = [role for _, role in merged]
        lines.remove(line)


def _reading_order(lines: list[Line], lang: Language) -> list[Line]:
    """Ordena la página en bandas: lo que rompe las columnas separa dos bloques.

    Sin esto, una tabla a ancho completo (como “Rasgos de bárbaro”, p. 32) se
    intercala en mitad del texto de la primera columna.
    """
    full = sorted((l for l in lines if l.fullwidth), key=lambda l: l.y)
    rest = [l for l in lines if not l.fullwidth]

    if not full:
        return sorted(rest, key=lambda l: (l.column, l.y, l.x0))

    # agrupar las líneas a ancho completo en bandas contiguas
    bands: list[list[Line]] = [[full[0]]]
    for line in full[1:]:
        if line.y - bands[-1][-1].y <= 40:
            bands[-1].append(line)
        else:
            bands.append([line])

    out: list[Line] = []
    top = float("-inf")
    for band in bands:
        y0, y1 = band[0].y, band[-1].y
        above = [l for l in rest if top < l.y < y0]
        out += sorted(above, key=lambda l: (l.column, l.y, l.x0))
        out += sorted(band, key=lambda l: l.y)
        top = y1
    out += sorted([l for l in rest if l.y > top], key=lambda l: (l.column, l.y, l.x0))
    return out


def base_x_map(lines: list[Line]) -> dict[tuple, float]:
    """Margen izquierdo de cada flujo (página, columna, región).

    Se calcula en vez de fijarse en config porque el margen cambia dentro de los
    cuadros destacados (72 en lugar de 63) y en las tablas.

    Se toma la MODA, no el mínimo. Un solo elemento que sobresalga por la
    izquierda —el título de una tabla empieza 4.5 pt antes que el texto— bastaba
    para correr el margen de toda la columna, y entonces cada línea del cuerpo
    parecía sangrada y abría un párrafo nuevo. En la página 35 eso partía
    “Presencia intimidante” en once párrafos de una línea.
    """
    groups: dict[tuple, list[float]] = {}
    for line in lines:
        groups.setdefault((line.page, line.column, line.region), []).append(round(line.x0, 1))

    out: dict[tuple, float] = {}
    for key, xs in groups.items():
        counts: dict[float, int] = {}
        for x in xs:
            counts[x] = counts.get(x, 0) + 1
        # más frecuente; ante empate, el más a la izquierda
        out[key] = min(counts, key=lambda x: (-counts[x], x))
    return out
