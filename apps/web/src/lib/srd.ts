/**
 * Carga de los datos generados por el extractor.
 *
 * El sitio consume `data/processed/es/` y nada más. No hay backend ni base de
 * datos: todo se resuelve en tiempo de compilación y lo que se publica son
 * ficheros estáticos.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

const DATA = join(process.cwd(), "..", "..", "data", "processed", "es");

function read<T>(...parts: string[]): T {
  return JSON.parse(readFileSync(join(DATA, ...parts), "utf-8")) as T;
}

export interface Source {
  page: number;
  pages?: number[];
  column?: number;
  bbox?: number[];
}

export interface Node {
  id?: string;
  type: string;
  level?: number;
  title?: string;
  name?: string;
  text?: string;
  md?: string;
  label?: string;
  value?: string;
  caption?: string;
  header?: string[];
  rows?: string[][];
  parts?: Node[];
  children?: Node[];
  source: Source;
}

export interface Entry {
  collection: string;
  name: string;
  page: number;
  path: string;
}

export const document = read<Node & { children: Node[] }>("document.json");
export const byId = read<Record<string, Entry>>("indexes", "by-id.json");

/** Colecciones que tienen página propia en el sitio. */
export const ROUTES: Record<string, string> = {
  spells: "/conjuros",
  monsters: "/monstruos",
  "magic-items": "/objetos",
};

export const collections = {
  spells: () => read<any[]>("collections", "spells.json"),
  monsters: () => read<any[]>("collections", "monsters.json"),
  magicItems: () => read<any[]>("collections", "magic-items.json"),
  spellIndex: () => read<any[]>("collections", "spells.index.json"),
  monsterIndex: () => read<any[]>("collections", "monsters.index.json"),
  itemIndex: () => read<any[]>("collections", "magic-items.index.json"),
};

/** Slug estable, el mismo criterio que usa el extractor para los ids. */
export function slugify(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function slugOf(id: string): string {
  return id.slice(id.indexOf(".") + 1);
}

export function hrefOf(id: string): string | null {
  const entry = byId[id];
  if (!entry) return null;
  const route = ROUTES[entry.collection];
  return route ? `${route}/${slugOf(id)}/` : null;
}

/**
 * Índice nombre normalizado -> destino, para convertir en enlaces las cursivas.
 *
 * El SRD pone en cursiva el nombre de un conjuro o de un objeto cada vez que lo
 * menciona; eso es justo lo que hace navegable el libro. Solo se enlaza lo que
 * coincide entero, para no convertir «bola de fuego retardada» en un enlace a
 * «bola de fuego».
 */
const linkIndex = new Map<string, { href: string; name: string }>();
for (const [id, entry] of Object.entries(byId)) {
  const href = hrefOf(id);
  if (!href) continue;
  const key = slugify(entry.name ?? "");
  if (key && !linkIndex.has(key)) linkIndex.set(key, { href, name: entry.name });
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Convierte el markdown de un bloque a HTML.
 *
 * El extractor emite un subconjunto muy pequeño (`***negrita cursiva***`,
 * `**negrita**`, `*cursiva*`), así que no hace falta un parser: una pasada con
 * tres expresiones regulares basta y no arrastra ninguna dependencia.
 *
 * Al cerrar una cursiva se mira si su contenido es el nombre de una ficha; si
 * lo es, se emite un enlace en vez de un `<em>`.
 */
export function renderMd(md: string, selfId?: string): string {
  let html = escapeHtml(md);
  html = html.replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, (_all, inner: string) => {
    const trimmed = inner.replace(/[.,;:]+$/, "");
    const target = linkIndex.get(slugify(trimmed));
    if (target && target.href !== hrefOf(selfId ?? "")) {
      const tail = inner.slice(trimmed.length);
      return `<a class="ref" href="${target.href}"><em>${trimmed}</em></a>${tail}`;
    }
    return `<em>${inner}</em>`;
  });
  return html;
}

/** Recorre el árbol devolviendo cada nodo con sus ancestros. */
export function* walk(node: Node, ancestors: Node[] = []): Generator<[Node[], Node]> {
  yield [ancestors, node];
  for (const child of node.children ?? []) yield* walk(child, [...ancestors, node]);
}

export interface Section {
  slug: string;
  title: string;
  page: number;
  chapter: string;
  chapterSlug: string;
  node: Node;
  /** Si tiene muchas entradas, cada una recibe su propia página. */
  split: boolean;
}

const SPLIT_THRESHOLD = 40;

/**
 * Divide el libro en páginas web.
 *
 * Una página por sección: es la unidad que se lee de un tirón y la que mantiene
 * el HTML por debajo de unos cientos de KB. Las secciones con muchísimas
 * entradas (los 339 conjuros) se convierten en índice y cada entrada pasa a
 * tener página propia.
 */
export function bookSections(): Section[] {
  const out: Section[] = [];
  for (const chapter of document.children ?? []) {
    if (chapter.type !== "chapter") continue;
    const chapterSlug = slugify(chapter.title ?? "");
    const sections = (chapter.children ?? []).filter((c) => c.type === "section");
    if (sections.length === 0) {
      out.push({
        slug: chapterSlug,
        title: chapter.title ?? "",
        page: chapter.source.page,
        chapter: chapter.title ?? "",
        chapterSlug,
        node: chapter,
        split: false,
      });
      continue;
    }
    for (const section of sections) {
      const entries = (section.children ?? []).filter((c) => c.type === "entry");
      out.push({
        slug: `${chapterSlug}/${slugify(section.title ?? "")}`,
        title: section.title ?? "",
        page: section.source.page,
        chapter: chapter.title ?? "",
        chapterSlug,
        node: section,
        split: entries.length > SPLIT_THRESHOLD,
      });
    }
  }
  return out;
}

export function chapters() {
  return (document.children ?? [])
    .filter((c) => c.type === "chapter")
    .map((chapter) => ({
      slug: slugify(chapter.title ?? ""),
      title: chapter.title ?? "",
      page: chapter.source.page,
      sections: (chapter.children ?? [])
        .filter((c) => c.type === "section")
        .map((s) => ({ title: s.title ?? "", slug: slugify(s.title ?? ""), page: s.source.page })),
    }));
}
