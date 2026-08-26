"""Fase 2: líneas -> bloques tipados.

Reglas de agrupación, en orden de prioridad:

1. Un salto vertical mayor que `block_gap` siempre cierra el bloque en curso.
   Es la señal más fiable del documento: el interlineado es 12 pt y la
   separación entre bloques ronda los 17-20 pt.

2. Una línea que empieza por viñeta o por "N:" abre un ítem de lista.

3. Una línea que empieza por una entradilla en negrita abre un ítem de lista de
   definición. Ojo: el SRD usa las dos sangrías posibles —francesa en conjuros
   y glosario, de primera línea en rasgos de clase— así que la sangría NO sirve
   para detectarlos; lo que sirve es la negrita inicial.

4. Una línea sangrada respecto al margen del flujo abre un párrafo nuevo.

5. Cualquier otra cosa continúa el bloque anterior.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import Language, Styles
from .layout import Line, build_lines, needs_space
from .rawdump import load_pages
from .tables import Table, build_table, merge_side_panels
from .textutil import clean, join_lines

BULLET = "•"
STEP_RE = re.compile(r"^\s*\d+\s*:")
PROP_RE = re.compile(r"^\s*([^:]{2,40}):\s*(.*)$", re.S)


@dataclass
class Block:
    type: str
    page: int
    column: int
    lines: list[Line] = field(default_factory=list)
    level: int | None = None
    table: Table | None = None
    region: str | None = None
    role: str | None = None

    @property
    def pages(self) -> list[int]:
        return sorted({l.page for l in self.lines})

    @property
    def text(self) -> str:
        return join_lines([l.raw for l in self.lines])

    @property
    def bbox(self) -> list[float]:
        xs0 = min(l.x0 for l in self.lines)
        xs1 = max(l.x1 for l in self.lines)
        ys = [l.y for l in self.lines]
        size = max(s["s"] for l in self.lines for s in l.spans)
        # se parte de las líneas base (lo único fiable) y se les da altura
        return [round(xs0, 1), round(min(ys) - size, 1), round(xs1, 1), round(max(ys) + size * 0.3, 1)]


def _emphasis_of(role: str | None, styles: Styles) -> str | None:
    if role is None:
        return None
    for kind, roles in styles.inline_emphasis.items():
        if role in roles:
            return kind
    return None


def markdown(block: Block, styles: Styles) -> str:
    """Reconstruye el bloque con marcado inline (**negrita**, *cursiva*).

    Los espacios se sacan fuera de los delimitadores: el SRD mete el espacio
    final dentro del tramo en negrita ("Tentáculo. ") y "*** texto***" no es
    marcado válido en ningún renderizador de markdown.
    """
    runs: list[list] = []
    for index, line in enumerate(block.lines):
        previous_span = None
        for span, role in zip(line.spans, line.roles):
            kind = _emphasis_of(role, styles)
            gap = " " if previous_span is not None and needs_space(previous_span, span) else ""
            previous_span = span
            if runs and runs[-1][0] == kind:
                runs[-1][1] += gap + span["t"]
            else:
                if gap and runs:
                    runs[-1][1] += gap
                runs.append([kind, span["t"]])
        if index + 1 < len(block.lines) and runs:
            runs[-1][1] += "" if line.raw.rstrip().endswith("­") else " "

    out: list[str] = []
    for kind, text in runs:
        text = clean(text)
        if not kind or not text.strip():
            out.append(text)
            continue
        marker = _marker(kind)
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        out.append(f"{lead}{marker}{text.strip()}{marker}{trail}")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _marker(kind: str) -> str:
    return {"strong": "**", "em": "*", "strong_em": "***"}[kind]


def _is_heading(line: Line, styles: Styles) -> bool:
    return line.role in styles.heading_roles


def _starts_strong(line: Line, styles: Styles) -> bool:
    kind = _emphasis_of(line.first_role, styles)
    return kind in {"strong", "strong_em"}


def _list_kind(line: Line) -> str | None:
    text = line.text
    if text.startswith(BULLET):
        return "bullet"
    if STEP_RE.match(text):
        return "step"
    return None


def build_blocks(raw_dir, styles: Styles, lang: Language) -> list[Block]:
    blocks: list[Block] = []
    gap_limit = float(lang.layout["block_gap"])

    for record in load_pages(raw_dir):
        lines = build_lines(record, styles, lang)
        blocks.extend(_page_blocks(lines, styles, lang, gap_limit))

    return _merge_across_pages(blocks, styles)


def _page_blocks(
    lines: list[Line], styles: Styles, lang: Language, gap_limit: float
) -> list[Block]:
    out: list[Block] = []
    current: Block | None = None
    previous: Line | None = None
    after_heading = False

    # Las líneas de tabla se apartan y se procesan por región al final,
    # conservando su posición en el flujo mediante un marcador.
    table_lines: dict[str, list[Line]] = {}
    order: list[object] = []

    for line in lines:
        if line.region and line.region.startswith("table"):
            # cerrar el bloque en curso: si no, el título de la tabla se emite
            # DESPUÉS del marcador y luego no se puede vincular.
            if current:
                out.append(current)
                order.append(current)
                current = None
            if line.region not in table_lines:
                table_lines[line.region] = []
                order.append(line.region)
            table_lines[line.region].append(line)
            previous = line
            continue

        # La sangría se mide RESPECTO A LA LÍNEA ANTERIOR, no al margen de la
        # columna. El SRD abre párrafo sangrando la primera línea, así que lo
        # que marca un párrafo nuevo es que la línea entre más que la de arriba.
        # Comparar contra el margen partía en líneas sueltas cualquier pasaje
        # con sangría más profunda (p. 26) o desplazado (p. 1).
        indent = (line.x0 - previous.x0) if (previous and previous.column == line.column
                                             and previous.region == line.region) else 0.0
        gap = (line.y - previous.y) if (previous and previous.column == line.column) else 1e9
        role = line.role or ""
        block_type = _block_type(line, styles)
        # La línea en cursiva que sigue a un título es el subtítulo de la ficha
        # ("Abjuración de nivel 1 (mago)", "Objeto maravilloso, raro"). Sin
        # tipificarla se pega al primer párrafo del cuerpo, que va a 15.6 pt.
        in_subtitle = current is not None and current.type == "subtitle"
        if (after_heading or in_subtitle) and line.roles and all(r == "body.em" for r in line.roles):
            block_type = "subtitle"  # puede ocupar dos líneas: "…(requiere / sintonización)"

        # Un título largo se parte en dos líneas físicas ("Monstruos de la A /
        # a la Z"). Se fusionan si comparten rol, columna e interlineado normal.
        continues_heading = (
            current is not None
            and current.type == "heading"
            and _is_heading(line, styles)
            and current.role == role
            and current.column == line.column
            and 0 < gap <= line.spans[0]["s"] * 1.8
        )

        # Una entradilla en negrita puede ocupar dos líneas ("2: Los jugadores
        # describen lo que hacen sus / personajes."). La segunda también empieza
        # en negrita, así que sin esto se parte el ítem en dos. La pista es que
        # la línea anterior acaba en negrita y sin punto: el término sigue abierto.
        runin_continues = (
            previous is not None
            and previous.roles
            and _emphasis_of(previous.roles[-1], styles) in {"strong", "strong_em"}
            and not previous.text.rstrip().endswith((".", ":", "!", "?", "”"))
        )

        starts_new = not continues_heading and (
            current is None
            or gap > gap_limit
            or _is_heading(line, styles)
            or (current and current.type == "heading")
            or _list_kind(line) is not None
            or (_starts_strong(line, styles) and not runin_continues and current.type != "heading")
            or (indent > 4.0 and current.type == "paragraph" and not current.lines[-1].fullwidth)
            or (current and current.region != line.region)
            # Un cambio de FAMILIA siempre abre bloque: sin esto el cuerpo de un
            # cuadro destacado se pega a su título (van a solo 13.8 pt) y el
            # encabezado "Acciones" de un perfil se pega a la primera acción.
            # No vale comparar el tipo exacto: las líneas de continuación de un
            # ítem de definición son cuerpo normal y partirían el ítem en dos.
            or (current and _family(block_type) != _family(current.type))
        )

        if starts_new:
            if current:
                out.append(current)
                order.append(current)
            current = Block(
                type=block_type,
                page=line.page,
                column=line.column,
                region=line.region,
                role=role,
                level=styles.level_of(role) if _is_heading(line, styles) else None,
            )
        current.lines.append(line)
        previous = line
        after_heading = current.type == "heading"

    if current:
        out.append(current)
        order.append(current)

    # reconstruir las tablas y colocarlas en su sitio del flujo
    result: list[Block] = []
    for item in order:
        if isinstance(item, Block):
            result.append(item)
            continue
        region_lines = table_lines[item]
        table_block = _table_block(region_lines, result, styles)
        if table_block:
            result.append(table_block)
    return result


# Tipos que comparten flujo de texto: sus líneas de continuación son cuerpo
# normal, así que alternar entre ellos no debe abrir un bloque nuevo.
BODY_FAMILY = {"paragraph", "list.definition", "list.bullet", "list.step"}


def _family(block_type: str) -> str:
    return "body" if block_type in BODY_FAMILY else block_type


def _block_type(line: Line, styles: Styles) -> str:
    role = line.role or ""
    if _is_heading(line, styles):
        return "heading"
    if role == "statblock.name":
        return "statblock.name"
    if role == "statblock.section":
        return "statblock.section"
    if role == "statblock.meta":
        return "statblock.meta"
    if role.startswith("statblock.header"):
        return "statblock.header"
    if role.startswith("statblock.ability"):
        return "statblock.ability"
    if role.startswith("statblock"):
        return "statblock.body"
    if role == "table.caption":
        return "table.caption"
    if role.startswith("prop."):
        return "property"
    if role.startswith("sidebar.title"):
        return "sidebar.title"
    if role.startswith("sidebar"):
        return "sidebar.body"
    if role.startswith("toc"):
        return "toc"
    kind = _list_kind(line)
    if kind:
        return f"list.{kind}"
    if _starts_strong(line, styles):
        return "list.definition"
    return "paragraph"


def _table_block(region_lines: list[Line], emitted: list[Block], styles: Styles) -> Block | None:
    """Separa cabecera y cuerpo de una tabla y recupera su título."""
    if not region_lines:
        return None

    header_roles = {"table.header", "statblock.ability.header"}
    header = [l for l in region_lines if l.role in header_roles]
    body = [l for l in region_lines if l.role not in header_roles]

    # Hay dos orientaciones de tabla en el SRD:
    #  - cabecera arriba: las líneas de cabecera están por encima de todo el cuerpo
    #  - cabecera a la izquierda: las etiquetas van en la primera columna, con el
    #    mismo estilo, intercaladas verticalmente con los valores
    # (p. ej. “Atributos básicos de bárbaro”). En ese caso son filas, no cabecera.
    key_value = bool(header and body and max(l.y for l in header) >= min(l.y for l in body))
    if key_value:
        body = sorted(region_lines, key=lambda l: (l.y, l.x0))
        header = []

    caption_block = _find_caption(region_lines, emitted)
    # El título puede ocupar dos líneas ("Arreos, arneses y vehículos / tirados
    # por animales"): hay que tomar el bloque entero, no su primera línea.
    caption_text = caption_block.text if caption_block else None
    if caption_block:
        emitted.remove(caption_block)

    # La tabla de características de un perfil también va sobre fondo gris, pero
    # no es una tabla independiente: pertenece al perfil y, si se emite suelta,
    # parte el perfil en dos y se pierden rasgos y acciones.
    statblock = sum(1 for l in region_lines if (l.role or "").startswith("statblock."))
    kind = "statblock.ability" if statblock > len(region_lines) / 2 else "table"

    table = build_table(
        caption_text,
        header,
        body,
        full_width=region_lines[0].fullwidth,
        columns_from_body=(kind == "statblock.ability"),
        key_value=key_value,
    )
    if table is None:
        return None

    block = Block(type=kind, page=region_lines[0].page, column=region_lines[0].column)
    block.lines = region_lines
    block.table = table
    block.region = region_lines[0].region
    return block


def _find_caption(region_lines: list[Line], emitted: list[Block]) -> Block | None:
    """Localiza el título de una tabla por geometría, no por adyacencia.

    El orden de lectura de una página con tabla a ancho completo separa el título
    de su tabla (entre medias va toda la segunda columna), así que buscar “el
    bloque anterior” no sirve. Se busca el título más cercano por encima de la
    tabla, en la misma página y solapando horizontalmente.
    """
    page = region_lines[0].page
    top = min(l.y for l in region_lines)
    x0 = min(l.x0 for l in region_lines)
    x1 = max(l.x1 for l in region_lines)

    best: Block | None = None
    for block in emitted:
        if block.type != "table.caption" or block.page != page:
            continue
        line = block.lines[0]
        if not (0 < top - line.y <= 60):
            continue
        if line.x1 < x0 - 8 or line.x0 > x1 + 8:
            continue
        if best is None or line.y > best.lines[0].y:
            best = block
    return best


def _merge_across_pages(blocks: list[Block], styles: Styles) -> list[Block]:
    """Une el párrafo partido por un salto de página o de columna.

    Un párrafo continúa si el bloque anterior no termina en punto y el siguiente
    no empieza por mayúscula de apertura ni es de otro tipo.
    """
    out: list[Block] = []
    for block in blocks:
        previous = out[-1] if out else None
        if (
            previous
            and previous.type == "paragraph"
            and block.type == "paragraph"
            and (previous.page != block.page or previous.column != block.column)
            and not previous.text.rstrip().endswith((".", ":", "!", "?", "”"))
        ):
            previous.lines.extend(block.lines)
            continue
        out.append(block)

    tables = [b.table for b in out if b.type == "table" and b.table]
    merged = {id(t): t for t in merge_side_panels(tables)}
    return [b for b in out if b.type != "table" or (b.table and id(b.table) in merged)]
