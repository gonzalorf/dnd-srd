"""Pruebas de clases, equipo, referencias cruzadas y exportaciones.

Requieren haber ejecutado `python -m extractor build && python -m extractor export`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed" / "es"
COLLECTIONS = PROCESSED / "collections"


def load(name: str) -> list[dict]:
    path = COLLECTIONS / f"{name}.json"
    if not path.exists():
        pytest.skip("ejecuta antes: python -m extractor build")
    return json.loads(path.read_text("utf-8"))


def by_name(records: list[dict], name: str) -> dict:
    for record in records:
        if record.get("name") == name:
            return record
    raise AssertionError(f"no encontrado: {name}")


# --- clases ------------------------------------------------------------------


def test_clase_completa():
    barbaro = by_name(load("classes"), "Bárbaro")
    assert barbaro["coreTraits"]["Característica principal"] == "Fuerza"
    assert barbaro["coreTraits"]["Dado de puntos de golpe"] == "1d12 por nivel de bárbaro"
    assert len(barbaro["progression"]["rows"]) == 20
    assert barbaro["progression"]["header"][0] == "Nivel"
    assert [f["name"] for f in barbaro["features"]][:3] == [
        "Defensa sin armadura", "Furia", "Maestría con armas",
    ]
    assert barbaro["subclasses"][0]["features"]


def test_tabla_clave_valor_no_funde_etiqueta_y_valor():
    """En brujo y druida la etiqueta es tan ancha que toca la columna del valor."""
    for name, ability in (("Brujo", "Carisma"), ("Druida", "Sabiduría")):
        clase = by_name(load("classes"), name)
        assert clase["coreTraits"]["Característica principal"] == ability


def test_todas_las_clases_bien_formadas():
    classes = load("classes")
    assert len(classes) == 12
    for clase in classes:
        assert clase["coreTraits"], clase["name"]
        assert len(clase["progression"]["rows"]) == 20, clase["name"]
        assert clase["features"], clase["name"]


def test_listas_de_conjuros_por_clase():
    bardo = by_name(load("classes"), "Bardo")
    niveles = sorted(s["level"] for s in bardo["spellLists"])
    assert niveles == list(range(10))


# --- equipo ------------------------------------------------------------------


def test_arma_con_precio_y_peso():
    daga = by_name(load("equipment"), "Daga")
    assert daga["kind"] == "weapon"
    assert daga["group"] == "Armas cuerpo a cuerpo sencillas"
    assert daga["price"]["gp"] == 2.0
    assert daga["weight"]["kg"] == 0.5
    assert daga["fields"]["Daño"] == "1d4 perforante"


def test_montura_desde_tabla_sin_gris_principal():
    """La tabla de monturas usa un gris distinto (0.937) al del resto."""
    caballo = by_name(load("equipment"), "Caballo de guerra")
    assert caballo["kind"] == "mount"
    assert caballo["price"]["gp"] == 400.0


def test_herramienta_con_precio_en_el_titulo():
    """Las herramientas no tienen tabla: el precio va en el título de la entrada."""
    tool = by_name(load("equipment"), "Herramientas de albañil")
    assert tool["kind"] == "tool"
    assert tool["price"]["gp"] == 10.0
    assert tool["text"]


# --- referencias cruzadas ----------------------------------------------------


def test_referencias_cruzadas_resueltas():
    path = PROCESSED / "indexes" / "crossrefs.json"
    if not path.exists():
        pytest.skip("ejecuta antes: python -m extractor build")
    graph = json.loads(path.read_text("utf-8"))
    assert graph["links"] > 500
    agujero = by_name(load("magic-items"), "Agujero portátil")
    assert "item.bolsa-de-contencion" in agujero["refs"]


def test_una_ficha_no_se_enlaza_a_si_misma():
    for name in ("spells", "magic-items"):
        for record in load(name):
            assert record["id"] not in record.get("refs", [])


def test_los_terminos_mecanicos_no_son_referencias():
    """'*Acierto:*' va en cursiva pero es una etiqueta, no un enlace."""
    path = PROCESSED / "indexes" / "crossrefs.json"
    if not path.exists():
        pytest.skip("ejecuta antes: python -m extractor build")
    unresolved = json.loads(path.read_text("utf-8"))["unresolved"]
    assert "acierto" not in unresolved or unresolved["acierto"] < 5
    assert len(unresolved) < 40


# --- exportaciones -----------------------------------------------------------


def test_sqlite_busca_sin_acentos():
    db_path = PROCESSED / "srd.sqlite"
    if not db_path.exists():
        pytest.skip("ejecuta antes: python -m extractor export")
    db = sqlite3.connect(db_path)
    try:
        rows = db.execute(
            "SELECT name FROM search WHERE search MATCH ? ORDER BY rank LIMIT 1", ("aboleth",)
        ).fetchall()
        assert rows and rows[0][0] == "Aboleth"
        # 'sintonizacion' sin tilde tiene que encontrar 'Sintonización'
        rows = db.execute(
            "SELECT name FROM search WHERE search MATCH ? ORDER BY rank LIMIT 1", ("sintonizacion",)
        ).fetchall()
        assert rows and rows[0][0] == "Sintonización"
    finally:
        db.close()


def test_sqlite_permite_consultas_estructuradas():
    db_path = PROCESSED / "srd.sqlite"
    if not db_path.exists():
        pytest.skip("ejecuta antes: python -m extractor export")
    db = sqlite3.connect(db_path)
    try:
        nivel9 = db.execute(
            "SELECT count(*) FROM entity WHERE collection='spells' "
            "AND json_extract(data,'$.level')=9"
        ).fetchone()[0]
        assert nivel9 == 16
        entrantes = db.execute(
            "SELECT count(*) FROM ref WHERE target='spell.detectar-magia'"
        ).fetchone()[0]
        assert entrantes > 20
    finally:
        db.close()


def test_esquemas_json_generados():
    schemas = ROOT / "schemas" / "es"
    if not schemas.exists():
        pytest.skip("ejecuta antes: python -m extractor export")
    spell = json.loads((schemas / "spells.schema.json").read_text("utf-8"))
    props = spell["items"]["properties"]
    assert "level" in props and props["level"]["type"] == "integer"
    assert set(props["school"]["enum"]) >= {"Evocación", "Nigromancia"}
    assert "name" in spell["items"]["required"]


def test_export_markdown_por_capitulo():
    md = PROCESSED / "markdown"
    if not md.exists():
        pytest.skip("ejecuta antes: python -m extractor export")
    files = sorted(md.glob("*.md"))
    assert len(files) == 16
    texto = (md / "04-como-jugar.md").read_text("utf-8")
    assert texto.startswith("# Cómo jugar  <!-- p5 -->")
    # una entradilla partida en dos líneas no debe romper el bloque
    assert "**2: Los jugadores describen lo que hacen sus personajes.**" in texto


# --- lock de identificadores -------------------------------------------------


def test_lock_de_ids():
    lock_path = ROOT / "config" / "ids.es.lock.json"
    if not lock_path.exists():
        pytest.skip("ejecuta antes: python -m extractor build")
    lock = json.loads(lock_path.read_text("utf-8"))
    assert lock["ids"]["spell.bola-de-fuego"]["collection"] == "spells"
    assert lock["ids"]["monster.aboleth"]["since"] == "5.2.1"
    assert not lock["retired"]
