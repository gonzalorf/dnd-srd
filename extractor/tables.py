"""Reconstrucción de tablas por geometría.

El SRD no marca las tablas de ninguna forma: son texto posicionado sobre un
rectángulo de fondo gris. Las columnas se recuperan agrupando las coordenadas x
de origen, que son constantes dentro de una misma tabla.

Dos casos que hay que tratar:

- Celdas con texto envuelto en varias líneas. Se distinguen de una fila nueva
  por el salto vertical: dentro de una celda el interlineado es menor que entre
  filas. Cuando los saltos son claramente bimodales se corta por el punto medio.

- Tablas partidas en dos paneles laterales con la cabecera repetida (p. ej.
  “Modificadores por característica”, p. 6). Se reunifican verticalmente cuando
  dos tablas contiguas comparten cabecera.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .layout import Line
from .textutil import join_lines

COLUMN_TOLERANCE = 6.0
COLUMN_GAP_MIN = 7.0


@dataclass
class Table:
    caption: str | None
    header: list[str]
    rows: list[list[str]]
    page: int
    pages: list[int] = field(default_factory=list)
    column_x: list[list[float]] = field(default_factory=list)
    full_width: bool = False

    def to_dict(self) -> dict:
        return {
            "type": "table",
            "caption": self.caption,
            "header": self.header,
            "rows": self.rows,
            "layout": {"fullWidth": self.full_width, "columnX": self.column_x},
        }


def _columns_by_projection(lines: list[Line]) -> list[tuple[float, float]]:
    """Detecta las columnas por los huecos verticales de la proyección horizontal.

    Agrupar por la x de origen no vale: las columnas numéricas van alineadas a la
    derecha o centradas, así que el origen varía varios puntos de fila a fila
    (“10–11” empieza en x=78 y “1” en x=87 dentro de la misma columna).

    Lo que sí es estable es que entre dos columnas siempre queda una banda
    vertical vacía. Se proyectan los intervalos [x0, x1] de todos los spans y se
    corta por cada hueco de al menos GAP_MIN puntos.
    """
    spans = [(s["x"], max(s["bbox"][2], s["x"] + 1)) for line in lines for s in line.spans]
    if not spans:
        return []
    spans.sort()
    merged: list[list[float]] = [list(spans[0])]
    for x0, x1 in spans[1:]:
        if x0 <= merged[-1][1] + COLUMN_GAP_MIN:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    return [(a, b) for a, b in merged]


def _row_split_threshold(ys: list[float]) -> float:
    """Punto de corte entre 'salto de línea dentro de celda' y 'fila nueva'.

    El reparto de saltos es TRIMODAL, no bimodal:

      0-2 pt   dos celdas de la misma fila con la línea base ligeramente distinta
      10-13 pt salto de línea dentro de una celda envuelta
      15 pt    fila nueva

    Por eso mín/máx no sirve: el mínimo cae en el primer modo y el punto medio
    parte las celdas envueltas. Se descarta la cola baja y se corta por el mayor
    salto relativo de la parte alta, que es la frontera envoltura/fila.
    """
    gaps = sorted(round(b - a, 1) for a, b in zip(ys, ys[1:]) if b - a > 0.5)
    if not gaps:
        return 0.0
    upper = [g for g in gaps if g >= gaps[-1] * 0.5]
    best_ratio, cut = 1.0, None
    for a, b in zip(upper, upper[1:]):
        if a > 0 and b / a > best_ratio:
            best_ratio, cut = b / a, (a + b) / 2.0
    if cut is None or best_ratio < 1.15:
        return upper[0] - 1.0  # saltos homogéneos: cada línea es una fila
    return cut


def _assign_by_role(line: Line) -> list[str]:
    """Reparte una fila clave/valor por el ROL de cada span, no por su posición.

    En las tablas “Atributos básicos de X” la etiqueta va en negrita
    (`table.header`) y el valor en redonda (`table.cell`). Cuando la etiqueta es
    larga llega a tocar la columna del valor y la proyección funde las dos en
    una sola: “Característica Carisma principal”. El rol no se ve afectado.
    """
    label = "".join(s["t"] for s, r in zip(line.spans, line.roles) if r == "table.header")
    value = "".join(s["t"] for s, r in zip(line.spans, line.roles) if r != "table.header")
    return [label, value]


def _assign(line: Line, columns: list[tuple[float, float]]) -> list[str]:
    cells = [""] * len(columns)
    for span in line.spans:
        mid = (span["x"] + max(span["bbox"][2], span["x"] + 1)) / 2.0
        idx = 0
        best = 1e9
        for i, (a, b) in enumerate(columns):
            distance = 0.0 if a <= mid <= b else min(abs(mid - a), abs(mid - b))
            if distance < best:
                best, idx = distance, i
        cells[idx] += span["t"]
    return cells


def build_table(
    caption: str | None,
    header_lines: list[Line],
    body_lines: list[Line],
    full_width: bool,
    columns_from_body: bool = False,
    key_value: bool = False,
) -> Table | None:
    if not body_lines:
        return None

    # Las micro-etiquetas MOD./SALV. de la tabla de características van a 6 pt y
    # pegadas entre sí, así que puentean el hueco entre columnas y las fusionan.
    columns = _columns_by_projection(body_lines if columns_from_body else header_lines + body_lines)

    # Una celda muy ancha puede llegar a tocar la columna siguiente y fundir las
    # dos en la proyección: en la tabla “Armas” los nombres largos pegaban
    # “Nombre” con “Daño”. La cabecera es corta y está bien separada, así que
    # cuando distingue más columnas que el cuerpo, manda ella.
    if header_lines and not columns_from_body:
        by_header = _columns_by_projection(header_lines)
        if len(by_header) > len(columns):
            columns = by_header
    if not columns:
        return None

    # Cabecera: puede ocupar varias líneas ("Bonificador / por / competencia").
    header_cells = [""] * len(columns)
    for line in header_lines:
        for i, part in enumerate(_assign(line, columns)):
            if part.strip():
                header_cells[i] = (header_cells[i] + " " + part).strip()
    header = [join_lines([c]) for c in header_cells]
    if not any(h.strip() for h in header):
        header = []  # tabla con las etiquetas en la primera columna

    ys = [l.y for l in body_lines]
    threshold = _row_split_threshold(ys)
    if key_value:
        columns = [(0.0, 0.0), (0.0, 0.0)]

    rows: list[list[list[str]]] = []
    previous_y: float | None = None
    for line in body_lines:
        cells = _assign_by_role(line) if key_value else _assign(line, columns)
        if previous_y is None or (line.y - previous_y) > threshold:
            rows.append([[c] for c in cells])
        else:
            for i, part in enumerate(cells):  # celda envuelta: continúa la fila
                rows[-1][i].append(part)
        previous_y = line.y

    return Table(
        caption=caption or None,
        header=header,
        rows=[[join_lines(cell) for cell in row] for row in rows],
        page=body_lines[0].page,
        pages=sorted({l.page for l in body_lines}),
        column_x=[[round(a, 1), round(b, 1)] for a, b in columns],
        full_width=full_width,
    )


def merge_side_panels(tables: list[Table]) -> list[Table]:
    """Reunifica las tablas partidas en paneles laterales con cabecera repetida."""
    out: list[Table] = []
    for table in tables:
        previous = out[-1] if out else None
        same_header = previous and previous.header == table.header and previous.header != [""]
        same_page = previous and previous.page == table.page
        no_caption = table.caption is None
        if same_header and same_page and no_caption:
            previous.rows.extend(table.rows)
            continue
        out.append(table)
    return out
