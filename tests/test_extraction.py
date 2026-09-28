"""Pruebas doradas sobre el árbol generado.

Fijan contenido concreto de páginas representativas, elegidas porque cada una
cubre una de las trampas del PDF. Si un cambio en el extractor las rompe, el
fallo señala exactamente qué mecanismo se ha estropeado.

Requieren haber ejecutado `python -m extractor build`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCUMENT = ROOT / "data" / "processed" / "es" / "document.json"


@pytest.fixture(scope="module")
def document() -> dict:
    if not DOCUMENT.exists():
        pytest.skip("ejecuta antes: python -m extractor build")
    return json.loads(DOCUMENT.read_text("utf-8"))


def walk(node: dict):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def find(document: dict, **match):
    for node in walk(document):
        if all(node.get(k) == v for k, v in match.items()):
            return node
    raise AssertionError(f"no encontrado: {match}")


# --- estructura global -------------------------------------------------------


def test_recuentos_de_la_jerarquia(document):
    counts: dict[str, int] = {}
    for node in walk(document):
        counts[node["type"]] = counts.get(node["type"], 0) + 1
    assert counts["chapter"] == 16
    assert counts["section"] == 245
    assert counts["subsection"] == 215
    assert counts["entry"] == 1372
    assert counts["statblock"] == 336
    assert counts["sidebar"] == 18


def test_todos_los_nodos_llevan_pagina(document):
    """Es la invariante que sostiene la trazabilidad de todo el proyecto."""
    for node in walk(document):
        if node["type"] == "document":
            continue
        assert node.get("source", {}).get("page"), node


# --- p. 119: ficha de conjuro ------------------------------------------------


def test_conjuro_con_sus_cuatro_propiedades(document):
    alarma = find(document, title="Alarma")
    assert alarma["source"]["page"] == 119
    props = {c["label"]: c["value"] for c in alarma["children"] if c["type"] == "property"}
    assert props["Tiempo de lanzamiento"] == "1 minuto o un ritual"
    assert props["Alcance"] == "9 m"
    assert props["Componentes"] == "V, S, M (una campana e hilo de plata)"
    assert props["Duración"] == "8 horas"


def test_subtitulo_separado_del_cuerpo(document):
    """La línea en cursiva bajo el título es el subtítulo de la ficha.

    Va a solo 15.6 pt del primer párrafo, así que sin tipificarla se fusiona con
    él y la fase `collect` pierde escuela, nivel, clases, tipo y rareza.
    """
    for titulo, esperado in [
        ("Alarma", "*Abjuración de nivel 1 (explorador, mago)*"),
        ("Bola de fuego", "*Evocación de nivel 3 (hechicero, mago)*"),
        ("Agujero portátil", "*Objeto maravilloso, raro*"),
    ]:
        ficha = find(document, title=titulo)
        assert ficha["children"][0]["type"] == "subtitle"
        assert ficha["children"][0]["md"] == esperado


def test_conjuro_conserva_los_items_de_definicion(document):
    alarma = find(document, title="Alarma")
    definiciones = [c for c in alarma["children"] if c["type"] == "definition"]
    assert len(definiciones) == 2
    assert definiciones[0]["md"].startswith("**Alarma mental.**")


# --- p. 32: tabla a ancho completo y tabla con cabecera en columna ------------


def test_tabla_a_ancho_completo(document):
    """Rompe el flujo de dos columnas: comprueba el orden por bandas."""
    tabla = find(document, type="table", caption="Rasgos de bárbaro")
    assert tabla["layout"]["fullWidth"] is True
    assert tabla["header"][0] == "Nivel"
    assert tabla["header"][1] == "Bonificador por competencia"
    assert len(tabla["rows"]) == 20
    assert tabla["rows"][0][2] == "Defensa sin armadura, Furia, Maestría con armas"
    assert tabla["rows"][19] == ["20", "+6", "Campeón primordial", "6", "+4", "4"]


def test_tabla_con_etiquetas_en_la_primera_columna(document):
    tabla = find(document, type="table", caption="Atributos básicos de bárbaro")
    assert tabla["header"] == []
    filas = dict(tabla["rows"])
    assert filas["Característica principal"] == "Fuerza"
    assert filas["Dado de puntos de golpe"] == "1d12 por nivel de bárbaro"
    # la palabra partida por guión blando dentro de una celda se une sin espacio
    assert "Intimidación" in filas["Competencias en habilidades"]


# --- p. 6: tabla partida en dos paneles laterales ----------------------------


def test_paneles_laterales_se_reunifican_verticalmente(document):
    """La tabla va partida en dos paneles con la cabecera repetida al lado.

    Deben salir 16 filas de 2 columnas (de 1 a 30), no 8 filas de 4 columnas.
    """
    tabla = find(document, type="table", caption="Modificadores por característica")
    assert tabla["header"] == ["Puntuación", "Modificador"]
    assert len(tabla["rows"]) == 16
    assert tabla["rows"][0] == ["1", "−5"]
    assert tabla["rows"][-1] == ["30", "+10"]


# --- p. 283: perfil de criatura ----------------------------------------------


def test_perfil_completo_con_sus_secciones(document):
    aboleth = find(document, type="statblock", name="Aboleth")
    assert aboleth["id"] == "statblock.aboleth"
    tipos = [p["type"] for p in aboleth["parts"]]
    assert tipos[0] == "meta"
    assert "ability" in tipos
    secciones = [p["text"] for p in aboleth["parts"] if p["type"] == "section"]
    assert secciones == ["Atributos", "Acciones", "Acciones legendarias"]


def test_tabla_de_caracteristicas_del_perfil(document):
    """Las seis características, con puntuación, modificador y salvación.

    Su rectángulo de fondo no cubre la columna de abreviaturas, así que tratarla
    como una tabla normal se comía “Fue 21” e “Int 18”.
    """
    aboleth = find(document, type="statblock", name="Aboleth")
    ability = next(p for p in aboleth["parts"] if p["type"] == "ability")["text"]
    for fragmento in ["Fue 21 +5 +5", "Des 9 −1 +3", "Con 15 +2 +6",
                      "Int 18 +4 +8", "Sab 15 +2 +6", "Car 18 +4 +4"]:
        assert fragmento in ability, (fragmento, ability)


def test_marcado_inline_valido(document):
    """Los delimitadores de markdown no pueden quedar pegados a un espacio.

    El SRD mete el espacio final dentro del tramo en negrita ("Tentáculo. "), lo
    que producía "***Tentáculo. ****Tirada…": cuatro asteriscos seguidos, que
    ningún renderizador interpreta. La secuencia de 4+ asteriscos es la firma
    inequívoca de ese fallo.
    """
    aboleth = find(document, type="statblock", name="Aboleth")
    tentaculo = next(p for p in aboleth["parts"] if p["md"].startswith("***Tentáculo"))
    assert tentaculo["md"].startswith("***Tentáculo.*** *Tirada de ataque")

    culpables = [
        node
        for node in walk(document)
        if re.search(r"\*{4,}", node.get("md", ""))
    ]
    assert not culpables, culpables[:3]


# --- pp. 2-4: los dos índices ------------------------------------------------


def test_indice_separado_en_entradas(document):
    """El índice va a TRES columnas y une título y página con puntos.

    El resto del libro va a dos columnas, así que sin un paso propio las
    entradas de dos columnas distintas se funden en una sola línea.
    """
    indices = [n for n in walk(document) if n["type"] == "toc"]
    assert len(indices) == 5

    general = next(i for i in indices if i["source"]["page"] == 2 and len(i["entries"]) > 100)
    titulos = [e["title"] for e in general["entries"]]
    # Orden de lectura: por columnas, no por filas.
    assert titulos[:4] == [
        "Información legal", "Cómo jugar", "El ritmo de juego", "Las seis características",
    ]
    assert general["entries"][0] == {"title": "Información legal", "page": 1, "level": 1}
    # El peso de la fuente distingue capítulo de sección.
    assert general["entries"][2]["level"] == 2

    # Ni puntos de relleno ni números pegados al título.
    for entrada in general["entries"]:
        assert ".." not in entrada["title"], entrada
        assert " " not in entrada["title"], entrada


def test_el_indice_conserva_el_texto_original(document):
    """Limpiar no es perder: el texto tal cual viene del PDF sigue ahí."""
    general = next(
        n for n in walk(document)
        if n["type"] == "toc" and n["source"]["page"] == 2 and len(n["entries"]) > 100
    )
    assert "...." in general["text"]
    assert "Información legal" in general["text"]


def test_indice_de_perfiles_completo(document):
    """Las 330 criaturas del índice de perfiles, con su página.

    Arranca al pie de la página 2, bajo el índice general, y sigue en la 3 y la
    4: por eso se busca por capítulo y no por número de página.
    """
    capitulo = find(document, type="chapter", title="Índice de perfiles")
    entradas = [e for n in walk(capitulo) if n["type"] == "toc" for e in n["entries"]]
    assert len(entradas) == 330
    assert all(e["page"] for e in entradas)
    assert entradas[0]["title"] == "Aboleth" and entradas[0]["page"] == 283
    assert entradas[-1]["title"] == "Zombi"


# --- p. 5: cuadro destacado y versalitas -------------------------------------


def test_cuadro_destacado_separa_titulo_y_cuerpo(document):
    """Las versalitas no traen espacios: se reponen por el hueco entre spans."""
    cuadro = find(document, type="sidebar", title="Las excepciones se imponen a las reglas generales")
    assert cuadro["source"]["page"] == 5
    assert len(cuadro["children"]) >= 1
    assert cuadro["children"][0]["text"].startswith("Las reglas generales rigen")
