# SRD 5.2.1 (es) — Análisis del PDF y propuesta de extracción estructurada

Documento fuente: `source-docs/SP_SRD_CC_v5.2.1.pdf`

Análisis realizado con PyMuPDF sobre el PDF real. Todas las huellas tipográficas,
colores, coordenadas y recuentos de este documento están verificados, no son
suposiciones.

---

## 1. Radiografía del PDF

| Dato | Valor |
|---|---|
| Páginas | 398 |
| Productor | Adobe InDesign 21.0 → Adobe PDF Library 18.0 |
| Marcadores / TOC embebido | **0** (hay que reconstruir la jerarquía) |
| Estructura etiquetada (PDF tagged) | No |
| Imágenes embebidas | **0** — el documento es 100 % texto + vectores |
| Tamaño de página | 594 × 783 pt |
| Maquetación | 2 columnas: col. A x ∈ [63, 291], col. B x ∈ [313, 541] |
| Numeración | El número impreso **coincide** con el índice de página del PDF |

Es la mejor situación posible: no hace falta OCR, la extracción es determinista y el
estilo tipográfico es rigurosamente regular.

### 1.1. Paleta de color (identifica el rol semántico)

| Entero PyMuPDF | Hex | Uso |
|---|---|---|
| 9183776 | `#8C2220` | Granate de todos los títulos de jerarquía |
| 2301728 | `#231F20` | Negro de texto corrido y de tablas |
| 5505024 | `#540000` | Granate oscuro de la cabecera de los perfiles (statblocks) |
| 8422021 | `#808285` | Gris del encabezado y del número de página |
| 6513766 | `#636466` | Gris del subtítulo de perfil y del texto de acciones legendarias |
| 9343123 | `#8E9093` | Gris de los micro-encabezados MOD. / SALV. |

### 1.2. Gráficos vectoriales (delimitan bloques)

| Relleno | Significado |
|---|---|
| `rgb(0.903, 0.907, 0.910)` = `#E7E7E8` | **Cuerpo de tabla.** Su `rect` da los límites exactos |
| `rgb(0.137, 0.122, 0.125)` = `#231F20` (rect grande) | **Marco de cuadro destacado.** Siempre lleva dentro un rect claro |
| `rgb(0.820, 0.826, 0.832)` | Bandas de la tabla de características dentro de un perfil |
| trazo `rgb(0.81, 0.68, 0.44)` = `#CFAE70` | Filete dorado bajo los títulos de nivel 3. Decorativo, ignorable |

Regla práctica: *rect claro solo* → tabla. *Rect oscuro con un rect claro dentro* →
cuadro destacado. Hay **18 cuadros destacados** y **196 tablas con título**.

---

## 2. Catálogo de tipos de contenido

Cada tipo es identificable de forma unívoca por su *huella de estilo*
`(fuente, tamaño, color)` y, en algunos casos, por la geometría.

### 2.1. Jerarquía de títulos

| Tipo | Huella | Nº | Ejemplo |
|---|---|---|---|
| `chapter` (H1) | GillSans-SemiBold 26.0 `#8C2220` | 15 | «Conjuros», «Monstruos de la A a la Z» |
| `section` (H2) | GillSans-SemiBold 18.0 `#8C2220` | 258 | «Combate», «Bárbaro», «Aboleth» |
| `subsection` (H3) | GillSans-SemiBold 14.0 `#8C2220` | 231 | «Pruebas de característica», «Partes de una trampa» |
| `entry` (H4) | GillSans-SemiBold 12.0 `#8C2220` | 1388 | «Bola de fuego», «Nivel 1: Furia», «Agarrado» |
| `minor` (H5) | GillSans-SemiBold/Bold 10.0 `#231F20` | 55 | «CA base», «Percepción pasiva» |

**Ojo:** un H1 o H2 largo se parte en dos líneas físicas («Monstruos de la A / a la Z»).
Hay que fusionar líneas consecutivas de la misma huella y columna.

### 2.2. Texto corrido

| Tipo | Huella | Notas |
|---|---|---|
| `paragraph` | Cambria 10.0 `#231F20` | Primera línea sangrada a x ≈ 71; continuaciones a x = 63 |
| `term-run-in` | Cambria-Bold / Cambria-BoldItalic 10.0 | Entradilla en negrita de un ítem de lista de definición |
| `emphasis` | Cambria-Italic 10.0 | Nombres de conjuros y objetos mágicos → **candidatos a enlace cruzado** |
| `bullet` | Cambria 10.0 que empieza por `•\t` | 143 en total |
| `numbered-step` | Cambria-Bold 10.0 que empieza por `N:\t` | Los pasos «1: … 2: … 3: …» |
| `definition-item` | Línea a x = 63 con entradilla en negrita + continuaciones a x = 71 | Sangría francesa |

La distinción párrafo / ítem de lista es geométrica y **fiable**:

- Párrafo nuevo: primera línea a x ≈ 71, resto a x = 63.
- Ítem de lista de definición: primera línea a x = 63 (con entradilla en negrita), resto a x = 71.

### 2.3. Tablas

| Elemento | Huella |
|---|---|
| `table.caption` | GillSans-SemiBold 10.5 `#231F20` (10.0 dentro de cuadros) |
| `table.header` | GillSans-SemiBold 9.2 `#231F20` |
| `table.cell` | GillSans 9.5 `#231F20` (+ GillSans-Italic 9.5 para «Elige dos:») |
| límites | El `rect` `#E7E7E8` cubre el cuerpo; la cabecera queda justo encima |

Casos que hay que tratar:

- **Tablas a ancho completo** (x 63 → 541) que rompen el flujo de dos columnas.
  Ejemplo: «Rasgos de bárbaro» (p. 32).
- **Tablas partidas en dos paneles** con la cabecera repetida lado a lado.
  Ejemplo: «Modificadores por característica» (p. 6) → hay que reunificarlas verticalmente.
- **Cabeceras multilínea** («Bonificador / por / competencia») → agrupar por coordenada x.
- **Celdas con texto envuelto** en varias líneas (p. 32, «Atributos básicos de bárbaro»).
- Las columnas se reconstruyen por la x de origen de cada span: es constante dentro de una tabla.

### 2.4. Cuadros destacados (*sidebars*)

18 en total. Marco `#231F20` + fondo `#E7E7E8`.

| Elemento | Huella |
|---|---|
| título | GillSans-Bold-SC700 11.0 + 7.7 (versalitas) |
| cuerpo | GillSans 9.0 `#231F20` |
| tabla interna | título en GillSans-SemiBold 10.0 |

Las versalitas parten el texto en spans (11 pt para las mayúsculas, 7.7 pt para el
resto), pero **el texto lógico se conserva**: basta concatenar los spans de la línea.

### 2.5. Perfiles / statblocks de criatura

324 perfiles. Es la estructura más rica del documento y la más valiosa para las herramientas.

| Elemento | Huella |
|---|---|
| nombre | GillSans-SemiBold 14.8 `#8C2220` |
| tamaño / tipo / alineamiento | Optima-Italic 9.0 `#636466` |
| cabecera (CA, PG, Velocidad, Habilidades, Sentidos, Idiomas, VD) | Optima-Bold 9.0 (etiqueta) + Optima-Regular 9.0 (valor), `#540000`, separadas por `\t` |
| tabla de características | GillSans 9.8 + GillSans-SemiBold-SC700 9.8/6.8 `#540000`; micro-cabeceras MOD./SALV. en GillSans 6.0 `#8E9093`; bandas de relleno `0.82` |
| secciones («Atributos», «Acciones», «Acciones adicionales», «Reacciones», «Acciones legendarias») | GillSans 12.0 `#8C2220` (670 en total) |
| nombre de rasgo / acción | Optima-BoldItalic 9.5 `#231F20` |
| cuerpo del rasgo | Optima-Regular 9.5 |
| términos mecánicos («Tirada de ataque cuerpo a cuerpo:», «Acierto:», «Fallo:») | Optima-Italic 9.5 → **parseables a campos** |
| intro de acciones legendarias | Optima-Italic 9.0 `#636466` |

La tabla de 6 características se reconstruye por posición x: tres grupos de
`abreviatura / puntuación / modificador / salvación` repartidos en dos filas.

### 2.6. Fichas de conjuro (341 conjuros, pp. 118–193)

```
Alarma                                       ← H4 GillSans-SemiBold 12.0
Abjuración de nivel 1 (explorador, mago)     ← Cambria-Italic 10.0
Tiempo de lanzamiento: 1 minuto o un ritual  ← GillSans-SemiBold 9.5 + GillSans 9.5
Alcance: 9 m
Componentes: V, S, M (una campana e hilo de plata)
Duración: 8 horas
<cuerpo en Cambria 10.0>
```

El subtítulo se parsea con una sola expresión regular a `{escuela, nivel, clases[]}`;
los trucos usan la forma «Truco de X».

Algunos conjuros (*Objeto animado*, *Corcel sobrenatural*…) **incrustan un statblock**
en las pp. 121, 155, 159 y 160 — el mismo parser de perfiles sirve.

### 2.7. Objetos mágicos (260, pp. 228–277)

Mismo patrón: H4 con el nombre + Cambria-Italic con
`tipo, rareza (requiere sintonización…)` + cuerpo.

### 2.8. Otros tipos

| Tipo | Ubicación | Notas |
|---|---|---|
| `class` | pp. 32–88 | 12 clases; cada una con tabla «Atributos básicos de X», tabla de progresión de 20 niveles y rasgos H4 con formato `Nivel N: Nombre` |
| `background` / `species` | pp. 89–93 | 4 trasfondos + 9 especies |
| `feat` | pp. 94–96 | 17 dotes |
| `equipment` | pp. 97–113 | Tablas de armas, armaduras, herramientas, equipo, monturas |
| `rule` | pp. 194–210 | 152 entradas del glosario de reglas |
| `trap` | pp. 218–220 | Etiquetas propias en GillSans-Bold 9.5 («Activador:», «Duración:») |
| `toc` | pp. 2–4 | Índice general + «Índice de perfiles» con líderes de puntos → `nombre → página` |
| `running-header` | todas | GillSans 11.0 `#808285` — **descartar** |
| `page-number` | todas | GillSans-SemiBold 11.0 `#808285` — **descartar** |

### 2.9. Mapa de capítulos

| Págs. | Capítulo |
|---|---|
| 1 | Información legal (licencia CC BY 4.0) |
| 2–4 | Contenido + Índice de perfiles |
| 5–20 | Cómo jugar |
| 21–31 | Creación de personajes |
| 32–88 | Clases |
| 89–93 | Orígenes de personaje |
| 94–96 | Dotes |
| 97–113 | Equipo |
| 114–193 | Conjuros |
| 194–210 | Glosario de reglas |
| 211–222 | Herramientas del juego |
| 223–277 | Objetos mágicos |
| 278–282 | Monstruos (cómo leer un perfil) |
| 283–376 | Monstruos de la A a la Z |
| 376–398 | Animales |

---

## 3. Trampas técnicas detectadas (y su solución)

Son las que harían fracasar una extracción ingenua. Todas están verificadas en el PDF real.

1. **Los `bbox` de PyMuPDF son inservibles para la fuente Cambria.** Sus métricas de
   ascendente/descendente están infladas, y los `bbox` de líneas consecutivas se solapan
   e incluso se invierten: en la p. 5 una línea da `y0 = 194` y la siguiente `y0 = 186`.
   → **Ordenar siempre por `span["origin"][1]` (línea base), nunca por `bbox`.**

2. **Los bloques de PyMuPDF mezclan títulos y cuerpo.** Un mismo bloque puede contener
   el H2 y el primer párrafo, o el párrafo y el H3 del final.
   → Trabajar a nivel de *span*, reagrupando en líneas por línea base.

3. **Orden de lectura entre columnas.** Los bloques llegan intercalados entre columna A
   y B. → Asignar columna por `origin.x` (umbral x = 302) y ordenar por
   `(columna, línea base)`. Las tablas a ancho completo se extraen **antes** y se
   insertan por su posición y.

4. **4344 guiones blandos (U+00AD)** de partición silábica de InDesign. Aparecen tanto a
   final de línea («ata­ques») como *dentro* de palabras («­asegura»).
   → Eliminar todos los U+00AD al unir líneas; unir sin espacio si la línea termina en uno.

5. **10 125 espacios duros (U+00A0)** → normalizar a espacio normal.

6. **2551 tabuladores** que actúan como separador de columna en la cabecera de los
   perfiles («CA: 17\tIniciativa: +7 (17)») y tras las viñetas.

7. **Signo menos U+2212** en los modificadores («−5») y **rayas U+2013/U+2014** en los
   rangos («2–3»). → Normalizar a ASCII solo en los campos numéricos parseados;
   conservar el original en el texto de presentación.

8. **Versalitas (fuentes `*-SC700`)** parten el texto en spans de dos tamaños.
   → Concatenar los spans de la línea; el texto lógico resultante es correcto.

9. **Dos entradas H4 pueden compartir línea base** en columnas distintas (p. 89:
   «Goliat» y «Humano»). → Confirma que hay que agrupar por `(columna, y)`, no solo por `y`.

---

## 4. Modelo de datos propuesto

Tres capas. Cada una es un artefacto en disco, reproducible y comparable entre versiones.

### Capa 0 — volcado crudo (`data/raw/pages.jsonl`)

Una línea JSON por página con **todos** los spans (texto, fuente, tamaño, color,
`origin`, `bbox`, flags) y todos los `drawings` relevantes. Permite reejecutar las
fases siguientes sin volver a abrir el PDF, depurar cómodamente y comparar dos
versiones del documento fuente.

### Capa 1 — documento estructurado (`data/processed/document.json`)

Árbol fiel al documento, agnóstico de dominio. Un nodo por unidad de contenido:

```jsonc
{
  "id": "spell.bola-de-fuego",
  "type": "entry",            // chapter|section|subsection|entry|paragraph|list|
                              // table|sidebar|statblock|callout|toc
  "title": "Bola de fuego",
  "source": { "page": 129, "column": 1, "bbox": [313, 48.7, 541, 320.4] },
  "text": "…",                // texto plano, para búsqueda
  "md": "…",                  // markdown con **negrita** e *itálica*, para render
  "runs": [                   // opcional: fidelidad total de estilos inline
    { "t": "Tienes resistencia al daño ", "s": [] },
    { "t": "contundente", "s": ["i"] }
  ],
  "children": [ /* … */ ]
}
```

Puntos clave:

- **`source.page` en absolutamente todos los nodos** (y `source.pages: [a, b]` si abarca
  varias). Es el requisito de trazabilidad que pediste: cualquier fragmento reutilizado
  en una web o en una tarjeta puede citar «SRD 5.2.1, p. 129».
- `bbox` + `page` permiten además recortar la región como imagen para previsualizaciones.
- `md` es la fuente canónica de renderizado; `text` alimenta el índice de búsqueda.

### Capa 2 — colecciones tipadas (`data/processed/collections/*.json`)

Derivadas de la capa 1 por parsers de dominio. **Son las que consumen la web y las herramientas.**

| Fichero | Registros |
|---|---|
| `spells.json` | 341 |
| `monsters.json` | 324 |
| `magic-items.json` | 260 |
| `rules-glossary.json` | 152 |
| `classes.json` | 12 (con progresión y rasgos por nivel) |
| `feats.json` | 17 |
| `backgrounds.json` / `species.json` | 4 / 9 |
| `equipment.json` | armas, armaduras, herramientas, equipo, monturas |
| `tables.json` | 196 tablas con título, accesibles por separado |
| `traps.json`, `conditions.json`, `hazards.json` | del cap. Herramientas del juego |

Ejemplo de conjuro:

```jsonc
{
  "id": "spell.alarma",
  "name": "Alarma",
  "level": 1,
  "school": "Abjuración",
  "ritual": true,
  "classes": ["explorador", "mago"],
  "castingTime": { "raw": "1 minuto o un ritual", "value": 1, "unit": "minuto" },
  "range": { "raw": "9 m", "meters": 9 },
  "components": { "raw": "V, S, M (una campana e hilo de plata)",
                  "v": true, "s": true, "m": "una campana e hilo de plata" },
  "duration": { "raw": "8 horas", "hours": 8, "concentration": false },
  "description": { "md": "…", "text": "…" },
  "source": { "book": "SRD 5.2.1 es", "page": 119 }
}
```

Ejemplo de perfil (resumido):

```jsonc
{
  "id": "monster.aboleth",
  "name": "Aboleth",
  "size": "Grande", "type": "Aberración", "alignment": "legal malvada",
  "ac": 17, "initiative": { "mod": 7, "score": 17 },
  "hp": { "average": 150, "formula": "20d10 + 40" },
  "speeds": { "walk": 3, "swim": 12 },
  "abilities": {
    "fue": { "score": 21, "mod":  5, "save": 5 },
    "des": { "score":  9, "mod": -1, "save": 3 },
    "con": { "score": 15, "mod":  2, "save": 6 },
    "int": { "score": 18, "mod":  4, "save": 8 },
    "sab": { "score": 15, "mod":  2, "save": 6 },
    "car": { "score": 18, "mod":  4, "save": 4 }
  },
  "skills": { "Historia": 12, "Percepción": 10 },
  "senses": { "raw": "visión en la oscuridad 36 m", "passivePerception": 20 },
  "languages": ["habla de las profundidades", "telepatía 36 m"],
  "cr": 10, "xp": 5900, "proficiencyBonus": 4,
  "traits":  [ { "name": "Anfibio", "md": "…" } ],
  "actions": [ { "name": "Tentáculo", "md": "…",
                 "attack": { "kind": "melee", "bonus": 9, "reach": 4.5,
                             "hit": { "average": 12, "formula": "2d6 + 5",
                                      "type": "contundente" } } } ],
  "legendary": { "uses": 3, "usesInLair": 4, "actions": [ /* … */ ] },
  "source": { "page": 283, "column": 0 }
}
```

### Índices auxiliares (`data/processed/indexes/`)

- `by-page.json`: página → ids de todo lo que aparece en ella.
- `by-id.json`: id → ruta dentro de `document.json` (resolución O(1)).
- `search.json` o `srd.sqlite` (FTS5): búsqueda de texto completo sin backend.
- `crossrefs.json`: enlaces resueltos. Todo span en Cambria-Italic que coincida con el
  nombre de un conjuro o de un objeto se convierte en `{ "ref": "spell.bola-de-fuego" }`.
  Esto es lo que convierte el SRD en un hipertexto navegable.

### Identificadores estables

`tipo.slug` (`spell.bola-de-fuego`, `monster.aboleth`, `table.rasgos-de-barbaro`).
Se guarda `config/ids.lock.json` para que **los IDs no cambien** si una futura versión
del PDF reordena contenido: el pipeline reporta altas y bajas en vez de romper enlaces.

---

## 5. El script de extracción: viable y repetible

**Sí, es perfectamente viable**, y en condiciones inmejorables: PDF sin OCR, sin
imágenes, con estilos rigurosamente consistentes. La expectativa razonable es superar
el 98 % de precisión estructural, con el resto acotado a casos raros que el propio
validador señala en un informe.

### Stack

- **Python 3.11+**
- **PyMuPDF** (`pymupdf`) — ya instalado y verificado en esta máquina. Da spans con
  fuente, tamaño, color, flags y `origin`, además de los `drawings` vectoriales que
  delimitan tablas y cuadros. Es la única dependencia crítica.
- `pydantic` para validar y serializar el modelo, `jsonschema` para los contratos
  publicados, `pytest` para las pruebas doradas, `typer` para la CLI.
- **Sin `camelot` ni `tabula`**: no hacen falta y aquí funcionan peor. Las tablas se
  reconstruyen por geometría usando los rects de fondo, que son exactos.

### Fases (cada una un comando y un artefacto)

```
srd extract    → data/raw/pages.jsonl          (PDF → spans + vectores)
srd blocks     → data/interim/blocks.jsonl     (spans → líneas → bloques clasificados)
srd document   → data/processed/document.json  (bloques → árbol jerárquico)
srd collect    → data/processed/collections/   (árbol → entidades de dominio)
srd link       → indexes/crossrefs.json        (resolución de referencias cruzadas)
srd validate   → reports/validation.md         (esquemas + recuentos + huérfanos)
srd export     → markdown / sqlite             (formatos derivados)
```

`srd build` los encadena todos.

### Cómo se garantiza la repetibilidad ante una nueva versión del PDF

1. **El mapa de estilos vive en `config/styles.yaml`, no en el código.** Adaptarse a una
   versión con tipografías retocadas es editar un YAML.
2. **`srd extract` calcula el SHA-256 del PDF** y lo guarda en `fingerprint.json`.
3. **Modo `--check`:** compara el inventario de huellas `(fuente, tamaño, color)` del PDF
   nuevo contra el calibrado. Si aparece una huella desconocida o desaparece una conocida,
   **falla con un informe** en lugar de producir datos silenciosamente malos. Este es el
   mecanismo que hace segura la reejecución sobre una actualización.
4. **`srd validate`** comprueba invariantes duras: 341 conjuros, 324 perfiles, 196 tablas,
   cero spans sin clasificar, todo nodo con `page`, todo perfil con sus 6 características,
   todo conjuro con sus 4 propiedades. Cualquier desviación sale en `reports/validation.md`.
5. **Pruebas doradas** (`tests/golden/`): un puñado de páginas y entidades representativas
   (5, 32, 119, 218, 283) con su JSON esperado. Detectan regresiones al tocar el parser.
6. **`srd diff v5.2.1 v5.3`**: compara dos ejecuciones y produce un changelog legible
   («conjuro X modificado», «monstruo Y nuevo»). Es lo que convierte actualizar el PDF
   fuente en una operación de rutina en vez de un salto al vacío.

### Coste realista

Nada exótico: el volumen es pequeño (398 páginas de texto). La ejecución completa
debería quedar en pocos segundos. El esfuerzo está en los parsers de dominio,
sobre todo el de perfiles y el de tablas.

---

## 6. Estructura de carpetas propuesta

Pensada para que el pipeline de datos, la web y las herramientas convivan sin pisarse,
y para que los datos sean un **paquete versionado** que todo lo demás consume.

```
SRD_es/
├─ README.md
├─ LICENSE-CONTENT.md            # CC BY 4.0 + atribución obligatoria
├─ pyproject.toml
├─ Makefile                      # make build / validate / diff
│
├─ source-docs/
│  └─ SP_SRD_CC_v5.2.1.pdf       # fuentes, una por versión
│
├─ config/
│  ├─ styles.yaml                # huella tipográfica → tipo de contenido
│  ├─ sections.yaml              # capítulo → parser de dominio
│  ├─ normalization.yaml         # guiones blandos, NBSP, menos unicode…
│  └─ ids.lock.json              # IDs estables entre versiones
│
├─ extractor/                    # el paquete Python
│  ├─ cli.py
│  ├─ pdf/        raw.py  layout.py  columns.py  drawings.py
│  ├─ model/      nodes.py  richtext.py  table.py  statblock.py
│  ├─ parse/      document.py  tables.py  sidebars.py  statblocks.py
│  │              spells.py  monsters.py  magic_items.py  classes.py
│  │              feats.py  origins.py  equipment.py  glossary.py  traps.py
│  ├─ links/      crossrefs.py  slugs.py
│  └─ export/     json_out.py  markdown.py  sqlite.py
│
├─ schemas/                      # JSON Schema público de cada colección
│  └─ spell.schema.json  monster.schema.json  …
│
├─ data/
│  ├─ raw/          pages.jsonl  fingerprint.json
│  ├─ interim/      blocks.jsonl
│  └─ processed/
│     ├─ document.json
│     ├─ collections/   spells.json  monsters.json  magic-items.json  …
│     ├─ indexes/       by-page.json  by-id.json  crossrefs.json
│     ├─ srd.sqlite     # FTS5 para búsqueda
│     └─ markdown/      # export legible, ideal para diffs entre versiones
│
├─ tests/
│  └─ fixtures/  golden/  test_*.py
│
├─ reports/                      # validation.md, diff-v5.2.1-v5.3.md
│
├─ packages/                     # artefactos consumibles (monorepo JS)
│  ├─ srd-data/                  # envuelve data/processed, publicable como npm
│  ├─ srd-types/                 # tipos TS autogenerados desde schemas/
│  └─ ui/                        # componentes compartidos (StatBlock, SpellCard…)
│
├─ apps/
│  ├─ web/                       # sitio de consulta del SRD
│  └─ api/                       # opcional, solo si algo necesita backend
│
├─ tools/
│  ├─ character-builder/         # generador de personajes
│  ├─ spell-cards/               # tarjetas de conjuro imprimibles (PDF/PNG)
│  ├─ statblock-cards/           # tarjetas de criatura
│  └─ encounter-builder/         # cálculo de dificultad de encuentros
│
├─ assets/                       # fuentes, iconos, plantillas de tarjeta
└─ docs/
   ├─ analisis-y-propuesta.md    # este documento
   ├─ taxonomia-de-contenido.md
   ├─ esquema-datos.md
   └─ adr/                       # decisiones de arquitectura
```

### Por qué así

- **`data/processed/` es el contrato.** Todo lo de `packages/`, `apps/` y `tools/`
  depende solo de ahí, nunca del PDF ni del extractor. Se puede reescribir el extractor
  entero sin tocar la web.
- **`packages/srd-types` generado desde `schemas/`** garantiza que los tipos de
  TypeScript y los datos no se desincronicen nunca.
- **`packages/ui` compartido** evita reimplementar el render de un statblock tres veces
  (web, generador de tarjetas, constructor de personajes).
- **`srd.sqlite` con FTS5** permite una búsqueda decente en una web estática
  (vía sql.js / WASM) sin montar servidor.
- **`tools/` separado de `apps/`**: las herramientas son generadores (producen PDFs,
  imágenes, fichas); las apps son interfaces. Ciclos de vida distintos.
- **`reports/` versionado** convierte cada actualización del SRD en un changelog
  revisable, en lugar de un cambio opaco de miles de líneas de JSON.

### Nota legal

El SRD 5.2.1 se publica bajo **Creative Commons Attribution 4.0** (p. 1 del PDF).
Cualquier salida pública —web, tarjetas, generadores— debe incluir la atribución.
Conviene fijar el texto exacto en `LICENSE-CONTENT.md` y que los exportadores lo
inyecten automáticamente en pies de página y metadatos, para no depender de acordarse.

---

## 6.bis. Cómo consume una aplicación estos datos

Sí: **el formato final es JSON en `data/processed/`, y una aplicación lo consume
directamente.** No hace falta base de datos ni backend. Conviene, eso sí, distinguir
qué fichero es para qué.

### Qué se publica y para quién

| Artefacto | Tamaño estimado | ¿Lo consume una app? |
|---|---|---|
| `document.json` | ~8–12 MB | **No directamente.** Es el árbol de fidelidad total (texto + markdown + runs + bbox de cada nodo). Sirve de fuente para las demás salidas, para reconstruir una página tal cual y para diffs entre versiones |
| `collections/*.json` | 0,2–1 MB cada uno | **Sí.** Es el formato de consumo normal |
| `collections/<tipo>/<slug>.json` | 1–8 KB | **Sí**, para carga bajo demanda (una ficha, una tarjeta) |
| `collections/<tipo>.index.json` | 20–60 KB | **Sí.** Índice ligero (nombre, nivel, escuela, VD, página…) para listados, filtros y buscadores sin bajar el cuerpo de texto |
| `srd.sqlite` | ~3–5 MB | Opcional, para búsqueda de texto completo con FTS5 desde el navegador (sql.js / WASM) |

El texto bruto del PDF son 1,59 M de caracteres. Repartido: conjuros ~344 KB,
monstruos y animales ~430 KB, objetos mágicos ~236 KB, clases ~197 KB. Con la
sobrecarga de JSON, `spells.json` queda en torno a 600–700 KB y `monsters.json`
alrededor de 0,8–1 MB.

### Los tres modos de consumo

1. **Empaquetado en build** (sitio estático, Next/Astro/SvelteKit).
   `import spells from '@srd/data/spells.json'` y se prerenderizan las 341 páginas de
   conjuro. Cero peticiones en runtime, cero servidor.
2. **Carga bajo demanda** (SPA o app móvil). Se baja el `*.index.json` al arrancar —
   suficiente para listar, filtrar y buscar por nombre— y solo se pide
   `spells/bola-de-fuego.json` al abrir la ficha. Es el modo recomendado para el
   generador de personajes y el de tarjetas.
3. **Búsqueda de texto completo.** `srd.sqlite` con FTS5 servido como fichero estático
   y consultado con sql.js en el navegador. Sigue sin haber backend.

Los tres son ficheros estáticos: se sirven desde cualquier CDN o desde GitHub Pages,
se cachean de forma indefinida y se versionan con la propia release de los datos.

### Por qué el paquete `packages/srd-data`

Para que las apps no importen rutas relativas hacia `../../data/processed/…`. El paquete
envuelve la carpeta, expone puntos de entrada limpios y fija la versión de los datos:

```ts
import { spells, monsters } from '@srd/data'
import type { Spell } from '@srd/types'   // generado desde schemas/
```

Así, cuando salga el SRD 5.3 se sube la versión del paquete y cada app decide cuándo
adoptarla, en vez de romperse todas a la vez.

### Un límite que conviene tener claro desde el principio

Estos JSON son **solo lectura e inmutables**: son el SRD. Todo lo que genere el usuario
—personajes creados, favoritos, mazos de tarjetas, encuentros guardados— vive fuera
(localStorage, IndexedDB o una base de datos propia) y **referencia el SRD por `id`**
(`"spell.bola-de-fuego"`), nunca copia su contenido. Esto es lo que permite actualizar
el SRD sin invalidar los datos del usuario.

---

## 7. Orden de trabajo recomendado

1. Andamiaje del repo + `config/styles.yaml` con las huellas ya identificadas aquí.
2. Fases `extract` → `blocks` → `document` (texto, títulos, párrafos, listas).
   Con esto ya se tiene todo el SRD navegable y con referencia de página.
3. Reconstructor de tablas (196) y de cuadros destacados (18).
4. Parser de perfiles (324) — el de mayor valor para las herramientas.
5. Parsers de conjuros (341) y objetos mágicos (260).
6. Resto de colecciones: clases, dotes, orígenes, equipo, glosario.
7. `validate` + pruebas doradas + `diff`.
8. `packages/srd-data` y `srd-types`; a partir de ahí, web y herramientas.

Los pasos 2 y 4 son los que más valor entregan por esfuerzo invertido.
