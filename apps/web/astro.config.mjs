import { defineConfig } from "astro/config";

export default defineConfig({
  // Sitio 100% estático: se sube a cualquier hosting de ficheros.
  output: "static",
  build: { format: "directory" },
  // Sin islas ni framework: el HTML que sale es HTML, y eso es lo que hace
  // que funcione igual de bien en un navegador moderno que en un lector lento.
  compressHTML: true,
});
