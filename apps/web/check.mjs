/**
 * Prueba de humo del sitio compilado.
 *
 * Sirve `dist/` y lo recorre con un navegador real, fallando con código distinto
 * de cero si algo no está bien. Se ejecuta con `npm run check` (o `make web-check`).
 *
 * Requiere haber compilado antes (`npm run build`): la búsqueda no existe hasta
 * que Pagefind genera su índice, así que probarla contra `astro dev` daría un
 * falso negativo.
 *
 * El servidor va DENTRO de este proceso en lugar de lanzar `astro preview` como
 * subproceso, por dos motivos: escucha en un puerto que asigna el sistema, así
 * que nunca choca con otra cosa; y no deja servidores huérfanos, que es lo que
 * pasa en Windows cuando se mata un subproceso lanzado a través del shell.
 */

import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright";

const RAIZ = "dist";
const TIPOS = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".wasm": "application/wasm",
  ".svg": "image/svg+xml",
};

const comprobaciones = [];
function comprobar(nombre, ok, detalle = "") {
  comprobaciones.push({ nombre, ok });
  console.log(`${ok ? "  OK  " : " FALLA"}  ${nombre}${detalle ? `  — ${detalle}` : ""}`);
}

const servidor = createServer(async (req, res) => {
  const ruta = decodeURIComponent(new URL(req.url, "http://x").pathname);
  let fichero = normalize(join(RAIZ, ruta));
  if (!fichero.startsWith(normalize(RAIZ))) {
    res.writeHead(403).end();
    return;
  }
  try {
    if ((await stat(fichero)).isDirectory()) fichero = join(fichero, "index.html");
    const cuerpo = await readFile(fichero);
    res.writeHead(200, {
      "content-type": TIPOS[extname(fichero)] ?? "application/octet-stream",
    }).end(cuerpo);
  } catch {
    res.writeHead(404).end("no encontrado");
  }
});

await new Promise((listo) => servidor.listen(0, "127.0.0.1", listo));
const BASE = `http://127.0.0.1:${servidor.address().port}`;

let navegador;
try {
  const inicio = await fetch(BASE + "/").catch(() => null);
  if (!inicio?.ok) {
    console.error("No hay sitio compilado en dist/. Ejecuta antes: npm run build");
    process.exit(1);
  }

  navegador = await chromium.launch();
  const pagina = await navegador.newPage();
  const erroresJs = [];
  pagina.on("pageerror", (e) => erroresJs.push(String(e)));

  // --- la búsqueda ---------------------------------------------------------
  // Va primero porque es lo único que depende del índice de Pagefind, y por
  // tanto lo único que no funcionaría si se hubiera saltado el `build`.
  await pagina.goto(`${BASE}/buscar/`, { waitUntil: "networkidle" });
  await pagina.fill(".pagefind-ui__search-input", "resistencia legendaria");
  await pagina.waitForTimeout(2500);
  const resultados = await pagina.locator(".pagefind-ui__result").count();
  comprobar("la búsqueda devuelve resultados", resultados > 0, `${resultados} resultados`);

  // El índice se genera con `remove_diacritics`, así que buscar sin tildes
  // tiene que encontrar la entrada acentuada.
  await pagina.fill(".pagefind-ui__search-input", "sintonizacion");
  await pagina.waitForTimeout(2500);
  const primero = (
    await pagina.locator(".pagefind-ui__result-title").first().innerText().catch(() => "")
  ).trim();
  comprobar("la búsqueda ignora los acentos", primero === "Sintonización", `«${primero}»`);

  // --- los filtros ---------------------------------------------------------
  await pagina.goto(`${BASE}/conjuros/`, { waitUntil: "networkidle" });
  await pagina.selectOption("select[name=nivel]", "9");
  await pagina.waitForTimeout(300);
  const nivel9 = await pagina.locator("table.fichas tbody tr:visible").count();
  comprobar("filtro por nivel", nivel9 === 16, `${nivel9} conjuros de nivel 9, esperados 16`);

  await pagina.selectOption("select[name=clase]", "mago");
  await pagina.waitForTimeout(300);
  const nivel9Mago = await pagina.locator("table.fichas tbody tr:visible").count();
  comprobar("filtros combinados", nivel9Mago === 12, `${nivel9Mago} de mago, esperados 12`);

  // --- los enlaces cruzados ------------------------------------------------
  // Son lo que convierte el libro en hipertexto: si se rompen, el sitio deja de
  // aportar lo único que el PDF no puede dar.
  await pagina.goto(`${BASE}/objetos/agujero-portatil/`, { waitUntil: "networkidle" });
  const destino = await pagina.locator("a.ref").first().getAttribute("href");
  await pagina.locator("a.ref").first().click();
  await pagina.waitForLoadState("networkidle");
  const titulo = await pagina.locator("h1").innerText();
  comprobar(
    "un enlace cruzado navega a su ficha",
    destino === "/objetos/bolsa-de-contencion/" && titulo === "Bolsa de contención",
    `${destino} → «${titulo}»`,
  );

  // --- la portada y el indice lateral --------------------------------------
  await pagina.goto(`${BASE}/`, { waitUntil: "networkidle" });
  // `innerText` devuelve el texto tal como se pinta, y el rotulo va en versales
  // por CSS, asi que se compara sin distinguir caja.
  const rotulo = (await pagina.locator(".portada .rotulo").innerText()).replace(/\s+/g, " ").trim();
  comprobar(
    "la portada lleva el rotulo del concepto",
    rotulo.toLowerCase() === "dungeons & dragons",
    `«${rotulo}»`,
  );

  // La lamina es el elemento con mas peso de la portada: si su ruta se rompe,
  // la pagina sigue maquetando bien y el fallo pasa desapercibido.
  const lamina = await pagina.locator(".portada .ilustracion").evaluate(
    (img) => img.complete && img.naturalWidth > 0,
  );
  comprobar("la ilustracion de portada carga", lamina === true);

  const capitulos = await pagina.locator(".indice-lateral > ol > li.cap").count();
  comprobar("el indice lateral lista los 16 capitulos", capitulos === 16, `${capitulos} capitulos`);

  // --- el indice resalta donde estas ---------------------------------------
  await pagina.goto(`${BASE}/libro/clases/barbaro/`, { waitUntil: "networkidle" });
  const capActivo = await pagina.locator(".indice-lateral li.cap.aqui > a").innerText();
  const secActiva = await pagina.locator(".indice-lateral .subsecciones li.aqui > a").innerText();
  const hermanas = await pagina.locator(".indice-lateral .subsecciones li").count();
  comprobar(
    "el indice resalta el capitulo y la seccion actuales",
    capActivo.trim() === "Clases" && secActiva.trim() === "Bárbaro" && hermanas === 12,
    `${capActivo.trim()} › ${secActiva.trim()}, ${hermanas} secciones desplegadas`,
  );

  // --- nada sin renderizar -------------------------------------------------
  // `Bloques.astro` marca con la clase `sin-cubrir` cualquier tipo de nodo que
  // no sepa dibujar, en vez de descartarlo en silencio.
  let sinCubrir = 0;
  for (const ruta of ["/libro/clases/barbaro/", "/monstruos/aboleth/", "/conjuros/bola-de-fuego/"]) {
    await pagina.goto(BASE + ruta, { waitUntil: "domcontentloaded" });
    sinCubrir += await pagina.locator(".sin-cubrir").count();
  }
  comprobar("ningún tipo de contenido sin renderizar", sinCubrir === 0, `${sinCubrir} bloques`);

  comprobar("sin errores de JavaScript", erroresJs.length === 0, erroresJs.slice(0, 2).join(" | "));
} catch (error) {
  // El fallo más probable es haber saltado el `build`: sin el índice de
  // Pagefind el buscador ni siquiera se dibuja, y la espera vence sin más.
  const pista = String(error).includes("pagefind")
    ? "falta el índice de búsqueda; ejecuta npm run build"
    : String(error).split("\n")[0];
  comprobar("la prueba llegó al final", false, pista);
} finally {
  await navegador?.close();
  servidor.close();
}

const fallos = comprobaciones.filter((c) => !c.ok).length;
console.log(`\n${comprobaciones.length - fallos}/${comprobaciones.length} comprobaciones correctas`);
process.exit(fallos === 0 ? 0 : 1);
