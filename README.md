# SRD 5.2.1 — extracción estructurada

Extrae el contenido del SRD 5.2.1 en español desde el PDF a una estructura de
datos accesible elemento a elemento, con la página de origen de cada fragmento.

Estado: **pipeline completo y sitio web funcionando**. De PDF a colecciones de
dominio y sitio estático navegable con buscador.
51/51 pruebas y 31/31 invariantes en verde.

**Todo se regenera desde el PDF con un solo comando.** No hay ni un dato del
libro escrito a mano: ver [Reproducibilidad](#reproducibilidad).

## Uso

```bash
pip install -r requirements.txt
python -m extractor build          # pipeline completo

python -m extractor extract        # PDF -> data/raw/es/pages.jsonl
python -m extractor blocks         # -> data/interim/es/blocks.json
python -m extractor document       # -> data/processed/es/document.json
python -m extractor collect        # -> data/processed/es/collections/
python -m extractor export         # -> schemas/, srd.sqlite, markdown/
python -m extractor validate       # -> reports/validation-es.md
python -m pytest tests -q

cd apps/web && npm install         # solo la primera vez
npm run build                      # compila el sitio estático (apps/web/dist)
npm run preview                    # lo sirve para verlo
npm run check                      # prueba de humo del sitio en un navegador
```

Ver [Levantar el sitio](#levantar-el-sitio) para el detalle.

`--lang es` es el valor por defecto. Añadir otro idioma del SRD consiste en
crear `config/lang/<code>.yaml`: el mapa de estilos es compartido porque la
maquetación es idéntica en todas las traducciones.

## Qué produce

| Artefacto | Contenido |
|---|---|
| `data/raw/es/pages.jsonl` | Un registro por página con todos los spans y los rectángulos de relleno |
| `data/raw/es/fingerprint.json` | SHA-256 del PDF e inventario de huellas tipográficas |
| `data/interim/es/blocks.json` | Bloques tipados en orden de lectura |
| `data/processed/es/document.json` | Árbol jerárquico fiel al documento (6,5 MB) |
| `data/processed/es/collections/` | 11 colecciones de dominio, en tres granularidades |
| `data/processed/es/indexes/` | `by-page.json`, `by-id.json`, `crossrefs.json` |
| `data/processed/es/srd.sqlite` | Base con FTS5 para búsqueda sin backend (6,8 MB) |
| `data/processed/es/markdown/` | Un fichero por capítulo, para comparar versiones |
| `schemas/es/` | Un JSON Schema por colección |
| `config/ids.es.lock.json` | Identificadores fijados entre versiones |
| `reports/validation-es.md` | 31 invariantes del árbol y de las colecciones |

### Colecciones

Cada colección se escribe en tres granularidades, una por modo de consumo:

- `<nombre>.json` — la colección entera, para empaquetar en build
- `<nombre>.index.json` — índice ligero, para listar, filtrar y buscar
- `<nombre>/<slug>.json` — una ficha por fichero, para carga bajo demanda

| Colección | Fichas | Tamaño |
|---|---:|---:|
| `spells` | 339 | 1128 KB |
| `monsters` | 336 | 1121 KB |
| `magic-items` | 258 | 722 KB |
| `tables` | 251 | 277 KB |
| `equipment` | 198 | 188 KB |
| `rules-glossary` | 155 | 257 KB |
| `sidebars` | 18 | 28 KB |
| `feats` | 17 | 29 KB |
| `classes` | 12 | 538 KB |
| `species` | 9 | 42 KB |
| `backgrounds` | 4 | 3 KB |

**1597 entidades** con identificador estable (`spell.bola-de-fuego`,
`monster.aboleth`, `item.agujero-portatil`, `weapon.daga`, `rule.agarrado`…) y
**632 referencias cruzadas** resueltas entre ellas.

Ejemplo de ficha de conjuro:

```jsonc
{
  "id": "spell.bola-de-fuego", "name": "Bola de fuego",
  "level": 3, "cantrip": false, "school": "Evocación",
  "classes": ["hechicero", "mago"],
  "ritual": false, "concentration": false,
  "castingTime": { "raw": "Acción", "kind": "action", "ritual": false },
  "range": { "raw": "45 m", "kind": "ranged", "meters": 45 },
  "components": { "raw": "V, S, M (una pelota de guano de murciélago y azufre)",
                  "v": true, "s": true, "m": true,
                  "material": "una pelota de guano de murciélago y azufre",
                  "consumed": false },
  "duration": { "raw": "Instantáneo", "kind": "instantaneous", "concentration": false },
  "blocks": [ { "type": "paragraph", "page": 125, "md": "Una ráfaga brillante…" } ],
  "text": "Una ráfaga brillante…",
  "refs": ["spell.…"],
  "source": { "book": "SRD 5.2.1 es", "page": 125 }
}
```

Ejemplo de perfil de criatura:

```jsonc
{
  "id": "monster.aboleth", "name": "Aboleth",
  "size": "Grande", "type": "Aberración", "alignment": "legal malvada",
  "ac": 17, "hp": { "raw": "150 (20d10 + 40)", "average": 150, "formula": "20d10 + 40" },
  "speeds": { "caminando": 3.0, "nadar": 12.0 },
  "abilities": { "fue": { "score": 21, "mod": 5, "save": 5 }, "…": {} },
  "skills": { "Historia": 12, "Percepción": 10 },
  "senses": { "raw": "…", "passivePerception": 20 },
  "challenge": { "raw": "10 (5900 PX o 7200 en la guarida; BC +4)",
                 "cr": 10, "xp": 5900, "xpInLair": 7200, "proficiencyBonus": 4 },
  "traits": [ { "name": "Anfibio", "md": "***Anfibio.*** El aboleth…", "page": 283 } ],
  "actions": [ { "name": "Tentáculo", "md": "***Tentáculo.*** *Tirada de ataque…" } ],
  "legendary": { "uses": 3, "usesInLair": 4, "actions": [ … ] },
  "source": { "book": "SRD 5.2.1 es", "page": 283 }
}
```

Clases y equipo:

```jsonc
{ "id": "class.barbaro", "name": "Bárbaro",
  "coreTraits": { "Característica principal": "Fuerza",
                  "Dado de puntos de golpe": "1d12 por nivel de bárbaro", "…": "…" },
  "progression": { "header": ["Nivel", "Bonificador por competencia", "…"],
                   "rows": [ ["1", "+2", "Defensa sin armadura, Furia, …"], … ] },
  "features": [ { "level": 1, "name": "Furia", "blocks": [ … ], "page": 33 } ],
  "subclasses": [ { "name": "Subclase de bárbaro: Senda del berserker", "features": [ … ] } ],
  "spellLists": [ … ] }

{ "id": "weapon.daga", "name": "Daga", "kind": "weapon",
  "group": "Armas cuerpo a cuerpo sencillas",
  "price": { "raw": "2 po", "amount": 2.0, "coin": "po", "gp": 2.0 },
  "weight": { "raw": "0,5 kg", "kg": 0.5 },
  "fields": { "Daño": "1d4 perforante", "Propiedades": "Arrojadiza (alcance 6/18), ligera, sutil",
              "Maestría": "Mellar" } }
```

**Tres reglas del contrato de datos:**

- Cada campo interpretado conserva su `raw`. Hay perfiles con valores no
  numéricos legítimos («PG: la mitad de los pg máximos de su invocador»,
  «VD: ninguno») y perderlos sería peor que no parsearlos.
- El contenido no se duplica: los bloques guardan solo markdown, y el texto
  plano se publica una vez por ficha para indexar y buscar.
- Los identificadores están fijados en `config/ids.es.lock.json`. Un id que
  desaparezca en una versión futura no se borra: se marca como retirado, para
  poder redirigir en vez de romper enlaces y personajes guardados.

### Búsqueda sin backend

`srd.sqlite` se sirve como fichero estático y se consulta desde el navegador con
sql.js. Trae las 1597 entidades con su JSON completo, el grafo de referencias y
un índice FTS5 con `remove_diacritics`, así que buscar «sintonizacion» encuentra
«Sintonización».

```sql
SELECT name FROM search WHERE search MATCH 'bola fuego' ORDER BY rank;

SELECT name FROM entity
WHERE collection = 'monsters' AND json_extract(data, '$.challenge.cr') >= 20;

SELECT count(*) FROM ref WHERE target = 'spell.detectar-magia';   -- 40
```

### Árbol del documento

`document.json` es fiel al PDF y agnóstico de dominio; las colecciones se
derivan de él. **Todos sus nodos llevan página**, que es la invariante que
sostiene la trazabilidad del proyecto.

```
16    capítulos       336  perfiles de criatura   131  ítems de viñeta
245   secciones       251  tablas                  22  pasos numerados
215   subsecciones     18  cuadros destacados      21  entradas de índice
1372  entradas       1498  propiedades
2646  párrafos        969  ítems de definición
684   subtítulos
```

## Cómo funciona

El PDF no trae índice ni estructura etiquetada, pero su tipografía es
rigurosamente regular: cada tipo de contenido tiene una huella única
`(fuente, tamaño, color)`. Ese mapa vive en `config/styles.yaml`, fuera del
código, para poder adaptarse a una versión futura sin tocar Python.

```
config/styles.yaml        huella tipográfica -> rol semántico
config/lang/es.yaml       todo lo que depende del idioma
config/ids.es.lock.json   identificadores fijados entre versiones

extractor/
  rawdump.py    fase 1: PDF -> spans + rectángulos
  layout.py     regiones, líneas, columnas y orden de lectura
  tables.py     reconstrucción de tablas por geometría
  blocks.py     fase 2: líneas -> bloques tipados
  document.py   fase 3: bloques -> árbol jerárquico
  collect/      fase 4: árbol -> colecciones de dominio
    spells.py  monsters.py  magic_items.py  classes.py  equipment.py
    simple.py  crossrefs.py  idlock.py  common.py
  export/       esquemas JSON, SQLite con FTS5, markdown
  validate.py   invariantes
```

### Las trampas que resuelve

Están documentadas en el código, porque son el motivo de que una extracción
directa del PDF no funcione:

1. **Los `bbox` de la fuente Cambria son inservibles.** Sus métricas vienen
   infladas y los rectángulos de líneas consecutivas se solapan e incluso se
   invierten. Todo el pipeline ordena por `origin` (la línea base).

2. **Los bloques de PyMuPDF mezclan títulos con cuerpo** y llegan intercalados
   entre las dos columnas. Se trabaja a nivel de span.

3. **Las tablas a ancho completo rompen el flujo de dos columnas.** La página se
   ordena en bandas separadas por esos bloques.

4. **Las versalitas no contienen espacios**: la separación entre palabras es
   posicional. Hay que reponerlos por el hueco horizontal entre spans.

5. **4344 guiones blandos** (U+00AD), también dentro de palabras. Se comprueba si
   la línea termina en uno ANTES de eliminarlo, para unirla sin espacio.

6. **`GillSans-SemiBold 12` es una entrada de contenido y `GillSans 12` es un
   encabezado de perfil**: mismo tamaño y color, distinto peso. Sin el matiz, los
   670 «Acciones»/«Atributos» se cuelan en el árbol como entradas.

7. **La tabla de características de un perfil desborda su rectángulo de fondo**
   por la izquierda: «Fue 21» cae fuera. Tratarla como tabla normal pierde datos
   y parte el perfil en dos.

8. **El reparto de saltos verticales en una tabla es trimodal** (misma fila /
   celda envuelta / fila nueva), no bimodal.

9. **Dos tablas en paneles laterales comparten línea base.** La región tiene que
   formar parte de la clave de agrupación de líneas; si no, las celdas de ambas
   se funden en una sola línea.

10. **La cabecera de una tabla queda fuera de su rectángulo de fondo** (hasta
    40 pt por encima en las tablas a ancho completo), y una misma línea de
    cabecera puede abarcar dos tablas contiguas. Se adjunta span a span.

11. **El subtítulo en cursiva de una ficha va a 15.6 pt del primer párrafo**, por
    debajo del umbral de separación de bloques: sin tipificarlo se fusiona con el
    cuerpo y se pierden escuela, nivel, clases, tipo y rareza.

12. **Los superíndices tienen línea base propia**, unos 3 pt por encima de la del
    texto, así que forman una línea suelta que se ordena delante del párrafo. El
    «²» de «250 m²» aparecía como un «2» huérfano al principio del conjuro.

13. **El SRD usa tres grises distintos para el fondo de una tabla.** Con solo el
    principal se perdían 12 tablas enteras: las monturas y los arreos (p. 109),
    los efectos del sombrero de trucos (pp. 269-270) y varias listas de conjuros
    de subclase.

14. **Una celda ancha puentea el hueco entre columnas.** En la tabla «Armas» los
    nombres largos pegaban «Nombre» con «Daño». La cabecera es corta y está bien
    separada, así que cuando distingue más columnas que el cuerpo, manda ella.

15. **En una tabla clave/valor la etiqueta puede tocar la columna del valor.**
    En brujo y druida salía «Característica Carisma principal». Ahí las columnas
    se reparten por el ROL tipográfico —etiqueta en negrita, valor en redonda—,
    que es inmune al problema.

16. **Una entradilla en negrita puede ocupar dos líneas.** La segunda también
    empieza en negrita, así que partía el ítem en dos. La pista es que la línea
    anterior acaba en negrita y sin punto: el término sigue abierto.

17. **El margen de la columna es la MODA, no el mínimo.** El título de una tabla
    empieza 4,5 pt antes que el texto, y eso bastaba para correr el margen de
    toda la columna: entonces cada línea del cuerpo parecía sangrada y abría
    párrafo. En la página 35 partía «Presencia intimidante» en once párrafos.

18. **La sangría se mide respecto a la línea anterior, no al margen.** Un pasaje
    entero con sangría más profunda (p. 26) se troceaba línea a línea.

19. **No todas las páginas van a dos columnas.** La de información legal es de
    una sola, y cortar por x=302 partía cada línea en dos mitades. Entre dos
    columnas de verdad hay un medianil de unos 22 pt; dentro de una línea
    continua la separación es de pocos puntos.

### Irregularidades del propio PDF

No son fallos de extracción, son inconsistencias del documento fuente que la
fase `collect` normaliza:

- **«Toque helado» (p. 189)** tiene sus cuatro propiedades maquetadas con Cambria
  en vez de GillSans. El árbol es fiel al PDF, así que las propiedades de conjuro
  se buscan por etiqueta y no por tipo de bloque.
- **El tamaño de criatura concuerda en género con el tipo**: «Monstruosidad
  Gargantuesca» frente a «Dragón Gargantuesco». Se normaliza a una forma única
  para que sea filtrable.
- **La rareza de un objeto mágico concuerda con su categoría**: «raro» / «rara».
- **El alineamiento va tras la ÚLTIMA coma**, no tras la primera: hay tipos con
  coma dentro («Celestial, feérico o infernal Grande (a tu elección), neutral»).
- **Las herramientas y las monturas no tienen tabla**: son entradas con el precio
  metido en el título, «Herramientas de albañil (10 po)».

## Reproducibilidad

**La única entrada es el PDF.** El pipeline lee `source-docs/*.pdf`,
`config/styles.yaml` y `config/lang/es.yaml`, y nada más. Borrar `data/` y
ejecutar `python -m extractor build` lo reconstruye todo.

Comprobado: dos reconstrucciones desde cero producen salidas **idénticas byte a
byte**.

### Qué está escrito a mano y qué sale del PDF

Ningún contenido del libro está escrito a mano. De los nombres de entidad
generados, solo 20 aparecen en `extractor/` o `config/`, y todos son vocabulario
de parseo (`Acciones`, `Alcance`, `Velocidad`, `Truco`…) o ejemplos citados en
comentarios. Ni un conjuro, ni un perfil, ni una celda de tabla.

Lo que sí es interpretación mía es la **calibración**, y vive toda en sitios
concretos y revisables:

| Dónde | Qué |
|---|---|
| `config/styles.yaml` | 50 reglas `(fuente, tamaño, color) -> rol`, 38 roles, 6 colores, 3 rellenos |
| `config/lang/es.yaml` → `layout` | 8 constantes de geometría (`column_split_x: 302`, `block_gap: 16`…) |
| `config/lang/es.yaml` → vocabulario | etiquetas de perfil, secciones, propiedades de conjuro, títulos de sección |
| `layout.py`, `tables.py`, `rawdump.py` | 6 umbrales geométricos |
| `collect/monsters.py`, `collect/magic_items.py`, `collect/equipment.py` | mapas de normalización y de tipos de tabla |
| `validate.py` → `EXPECTED` | las cifras esperadas |

### Cómo se controla esa calibración

- **`extract` inventaría las 49 huellas tipográficas del PDF** y avisa de
  cualquiera que `config/styles.yaml` no cubra. Una versión futura con
  tipografía retocada no puede colarse en silencio.
- **`extract` calcula el SHA-256 del PDF** y lo guarda en `fingerprint.json`.
- **`validate` comprueba 30 invariantes**: cifras del árbol y de cada colección,
  identificadores únicos, conjuros con sus cuatro propiedades y su escuela,
  perfiles con las seis características y tamaño, clases con progresión de 20
  niveles, objetos con categoría y rareza, y el número de referencias cruzadas.

### Las tres capas de prueba

`tests/` tiene 51 pruebas repartidas en tres niveles, y solo el tercero
demuestra corrección:

1. **`test_extraction.py` (12)** — fija el árbol sobre páginas elegidas por
   cubrir cada una de las trampas de arriba.
2. **`test_collections.py` (14)** y **`test_export.py` (15)** — fijan fichas
   concretas y las exportaciones: Bola de fuego, Aboleth, Bárbaro, Daga.
3. **`test_independent.py` (10)** — **no usa el extractor**. Abre el PDF con
   PyMuPDF y, con una implementación mínima y separada, verifica que:
   - los recuentos de perfiles y de cuadros salen igual contándolos a mano
     sobre el PDF;
   - cada conjuro, perfil, objeto y regla aparece **en la página que su ficha
     declara**;
   - la CA y los PG de cada perfil, y el alcance, componentes y duración de cada
     conjuro, están **literalmente** en esa página;
   - las primeras palabras del texto de cada ficha existen tal cual en el PDF.

La distinción importa: las cifras de `validate.py` y las pruebas doradas se
midieron sobre la salida del propio extractor, así que sirven para detectar
deriva pero no prueban por sí solas que la interpretación sea correcta. El
tercer nivel sí, porque contrasta contra el documento fuente.

Esa tercera capa ya encontró un fallo real: el conjuro «Guardas y guardias»
empezaba por un «2» huérfano, por el superíndice de «250 m²».

### Comparar dos versiones del SRD

`data/processed/es/markdown/` es un fichero por capítulo, con la página anotada
en cada título y saltos de línea LF. No es un formato de consumo: es lo que hace
que un `git diff` entre dos ejecuciones diga qué ha cambiado en el libro. Un
diff de `document.json` no dice nada.

## El sitio web (`apps/web/`)

Sitio estático con Astro. Se sube a cualquier hosting de ficheros —GitHub Pages,
Cloudflare Pages, Netlify— sin backend, sin base de datos y sin coste de
servidor.

### Levantar el sitio

**Requisito previo: los datos.** `src/lib/srd.ts` lee `data/processed/es/` en
tiempo de compilación, así que sin `python -m extractor build` el sitio no
compila.

```bash
python -m extractor build      # genera los datos que consume el sitio

cd apps/web
npm install                    # solo la primera vez

npm run dev                    # desarrollo, con recarga en caliente
npm run build                  # compila: astro build + índice de búsqueda
npm run preview                # sirve dist/: el sitio real
npm run check                  # prueba de humo en un navegador
```

Los objetivos `make web`, `web-dev`, `web-preview` y `web-check` hacen lo mismo,
si tienes `make` (en Windows no viene de serie).

| Modo | Comando | Compila | Buscador |
|---|---|---|---|
| Desarrollo | `npm run dev` | al vuelo | **no funciona** |
| Vista previa | `npm run build` + `npm run preview` | completo (~50 s) | sí |

**El tropiezo más probable:** en modo desarrollo la página `/buscar/` sale vacía
y sin errores. No es un fallo del sitio: `astro dev` no genera el índice de
Pagefind, que solo existe tras `astro build && pagefind --site dist`. Para probar
la búsqueda hay que usar `web` + `web-preview`.

Detalle menor: `astro preview` escucha en IPv6, así que hay que abrir la URL con
`localhost` —la que él mismo imprime— y no con `127.0.0.1`.

`npm run check` sirve `dist/` en un puerto que asigna el sistema, lo recorre con
Chromium y comprueba que la búsqueda responde e ignora los acentos, que los
filtros cuentan bien (16 conjuros de nivel 9, 12 de mago), que un enlace cruzado
navega, que ninguna página deja contenido sin renderizar y que no hay errores de
JavaScript. Sale con código distinto de cero si algo falla.

| | |
|---|---|
| Páginas generadas | 2037 |
| Peso total | 28 MB (9 MB el índice de búsqueda, 1,1 MB imágenes y fuentes) |
| Página mediana | 4 KB |
| Página más pesada | 103 KB |
| Páginas con JavaScript | 4 de 2033: los tres listados filtrables y el buscador |

**Qué hay:**

- **Portada e identidad visual** tomadas del concepto
  `docs/Tapa Concept de D&D SRD 2024.pdf`: papel blanco, tinta negra, rojo puro
  como único acento y las dos familias del documento, Jost y Barlow Condensed,
  autoalojadas (198 KB, y el navegador solo descarga el subconjunto que usa).
- **Índice del libro a la izquierda**, fijo al desplazarse. Muestra los 16
  capítulos y despliega las secciones del capítulo en el que estás, resaltando
  la actual. No lista las 245 secciones de golpe a propósito: repetirlas en cada
  una de las 2033 páginas añadiría más de 30 MB al sitio para duplicar lo que ya
  hay en `/libro/`. Va después del contenido en el HTML y es `grid` quien lo
  coloca a la izquierda, así que en móvil cae al final y no hace falta
  JavaScript para plegarlo.
- **El libro completo, navegable.** Una página por sección; las secciones con
  más de 40 entradas (conjuros, objetos, monstruos) se convierten en índice y
  cada entrada recibe página propia. Cada título lleva su página del PDF y un
  ancla enlazable.
- **1436 enlaces cruzados** repartidos por el texto: las cursivas del SRD que
  nombran un conjuro o un objeto se convierten en enlaces a su ficha. Es lo que
  el PDF no puede hacer.
- **Listados filtrables** de conjuros (nivel, escuela, clase, ritual,
  concentración), monstruos (tipo, tamaño, VD) y objetos (categoría, rareza,
  sintonización). El filtro actúa sobre la tabla ya renderizada: sin JavaScript
  la tabla sigue completa y usable.
- **Búsqueda de texto completo** con Pagefind. El índice se genera al compilar y
  se descarga por fragmentos según se escribe; una sesión de búsqueda mueve unos
  340 KB, no el libro entero. Es insensible a acentos: «sintonizacion» encuentra
  «Sintonización».

Comprobado en un navegador real con Playwright (`npm run check`, 11
comprobaciones): la búsqueda devuelve resultados e ignora los acentos, los
filtros cuentan bien (16 conjuros de nivel 9, 12 de ellos de mago), los enlaces
cruzados navegan, la portada y su lámina cargan, el índice lateral lista los 16
capítulos y resalta dónde estás, y no hay ni un error de JavaScript.

### Sobre la portada y las marcas

El concepto se reproduce salvo en dos puntos, a propósito:

- **No se usa el logotipo de Dungeons & Dragons.** La CC BY 4.0 del SRD cubre el
  contenido, pero su cláusula 2(b)(2) excluye expresamente las marcas. El rótulo
  va compuesto con tipografía, que es uso nominativo del nombre del juego.
- **No aparece «Publicado por Wizards of the Coast LLC».** El propio SRD pide no
  añadir más atribuciones a Wizards que la declaración obligatoria, y en un sitio
  no oficial daría a entender que lo publica Wizards.

El pie de cada página lleva la atribución exigida y deja claro que es un sitio no
oficial. La lámina de portada procede del documento de concepto, no del SRD: el
PDF del SRD no contiene ni una imagen.


## Pendiente

- Colección de trampas, peligros y estados del capítulo «Herramientas del juego».
- Paquete `packages/srd-data` y tipos de TypeScript generados desde `schemas/`.
- Comando `diff` que compare dos ejecuciones y produzca un changelog legible.
- Filtros nativos de Pagefind (`data-pagefind-filter`) para acotar la búsqueda
  por colección.

## Licencia del contenido

El SRD 5.2.1 se publica bajo **Creative Commons Attribution 4.0**. Cualquier
salida pública debe incluir la atribución. Ver `LICENSE-CONTENT.md`.
