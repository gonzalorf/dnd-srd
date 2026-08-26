"""Pruebas doradas sobre las colecciones de dominio.

Fijan fichas concretas con sus valores parseados. Requieren haber ejecutado
`python -m extractor build`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
COLLECTIONS = ROOT / "data" / "processed" / "es" / "collections"


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


# --- conjuros ----------------------------------------------------------------


def test_conjuro_con_todos_sus_campos():
    bola = by_name(load("spells"), "Bola de fuego")
    assert bola["id"] == "spell.bola-de-fuego"
    assert bola["level"] == 3
    assert bola["school"] == "Evocación"
    assert bola["classes"] == ["hechicero", "mago"]
    assert bola["ritual"] is False
    assert bola["concentration"] is False
    assert bola["castingTime"]["kind"] == "action"
    assert bola["range"] == {"raw": "45 m", "kind": "ranged", "meters": 45}
    assert bola["components"]["v"] and bola["components"]["s"] and bola["components"]["m"]
    assert "guano de murciélago" in bola["components"]["material"]
    assert bola["duration"]["kind"] == "instantaneous"
    assert bola["source"]["page"] == 125


def test_truco_es_nivel_cero():
    truco = by_name(load("spells"), "Toque helado")
    assert truco["level"] == 0
    assert truco["cantrip"] is True
    assert truco["school"] == "Nigromancia"


def test_ritual_y_concentracion():
    spells = load("spells")
    alarma = by_name(spells, "Alarma")
    assert alarma["ritual"] is True
    assert alarma["range"]["meters"] == 9
    volar = by_name(spells, "Volar")
    assert volar["concentration"] is True
    assert volar["duration"]["concentration"] is True


def test_alcances_no_numericos():
    spells = load("spells")
    assert by_name(spells, "Curar heridas")["range"]["kind"] == "touch"
    kinds = {s["range"]["kind"] for s in spells}
    assert kinds <= {"self", "touch", "ranged", "sight", "unlimited", "special"}


def test_todos_los_conjuros_bien_formados():
    spells = load("spells")
    assert len(spells) == 339
    assert {s["level"] for s in spells} == set(range(10))
    assert len({s["school"] for s in spells}) == 8
    assert all(s["classes"] for s in spells)


# --- perfiles de criatura ----------------------------------------------------


def test_perfil_con_todos_sus_campos():
    aboleth = by_name(load("monsters"), "Aboleth")
    assert aboleth["size"] == "Grande"
    assert aboleth["type"] == "Aberración"
    assert aboleth["alignment"] == "legal malvada"
    assert aboleth["ac"] == 17
    assert aboleth["hp"] == {"raw": "150 (20d10 + 40)", "average": 150, "formula": "20d10 + 40"}
    assert aboleth["speeds"] == {"caminando": 3.0, "nadar": 12.0}
    assert aboleth["abilities"]["fue"] == {"score": 21, "mod": 5, "save": 5}
    assert aboleth["abilities"]["des"] == {"score": 9, "mod": -1, "save": 3}
    assert aboleth["skills"] == {"Historia": 12, "Percepción": 10}
    assert aboleth["senses"]["passivePerception"] == 20
    assert aboleth["challenge"]["cr"] == 10
    assert aboleth["challenge"]["xp"] == 5900
    assert aboleth["challenge"]["proficiencyBonus"] == 4


def test_perfil_con_secciones():
    aboleth = by_name(load("monsters"), "Aboleth")
    assert [t["name"] for t in aboleth["traits"]][0] == "Anfibio"
    assert [a["name"] for a in aboleth["actions"]] == [
        "Ataque múltiple", "Tentáculo", "Consumir recuerdos", "Dominar la mente",
    ]
    assert aboleth["legendary"]["uses"] == 3
    assert [a["name"] for a in aboleth["legendary"]["actions"]] == ["Drenaje psíquico", "Latigazo"]


def test_tamano_normalizado_a_una_forma():
    """El PDF escribe el tamaño en masculino o femenino según el tipo."""
    monsters = load("monsters")
    assert {m["size"] for m in monsters} == {
        "Diminuto", "Pequeño", "Mediano", "Grande", "Enorme", "Gargantuesco",
    }
    assert by_name(monsters, "Kraken")["size"] == "Gargantuesco"  # "Gargantuesca" en el PDF


def test_valores_no_numericos_conservan_su_texto():
    """Hay perfiles con PG o VD no numéricos: no se pueden perder."""
    avatar = by_name(load("monsters"), "Avatar de la muerte")
    assert "average" not in avatar["hp"]
    assert avatar["hp"]["raw"] == "la mitad de los pg máximos de su invocador"


def test_alineamiento_tras_la_ultima_coma():
    """Hay tipos con coma dentro: 'Celestial, feérico o infernal Grande, neutral'."""
    corcel = by_name(load("monsters"), "Corcel sobrenatural")
    assert corcel["size"] == "Grande"
    assert corcel["alignment"] == "neutral"


# --- objetos mágicos ---------------------------------------------------------


def test_objeto_magico_simple():
    agujero = by_name(load("magic-items"), "Agujero portátil")
    assert agujero["category"] == "Objeto maravilloso"
    assert agujero["rarity"] == "raro"
    assert agujero["attunement"] is False


def test_objeto_con_variante_y_sintonizacion():
    items = load("magic-items")
    con_variante = [i for i in items if i.get("variant")]
    assert con_variante, "ninguna categoría con variante entre paréntesis"
    assert all(i["rarity"] for i in con_variante)
    restringidos = [i for i in items if i.get("attunementRequires")]
    assert len(restringidos) == 20


def test_rarezas_normalizadas():
    """El PDF alterna género según la categoría: 'raro' / 'rara'."""
    rarities = {i["rarity"] for i in load("magic-items")}
    assert rarities == {"común", "infrecuente", "raro", "muy raro", "legendario", "artefacto", "varía"}


# --- índices -----------------------------------------------------------------


def test_indices_transversales():
    indexes = COLLECTIONS.parent / "indexes"
    if not indexes.exists():
        pytest.skip("ejecuta antes: python -m extractor build")
    by_id = json.loads((indexes / "by-id.json").read_text("utf-8"))
    by_page = json.loads((indexes / "by-page.json").read_text("utf-8"))
    assert by_id["spell.bola-de-fuego"]["page"] == 125
    assert by_id["spell.bola-de-fuego"]["path"] == "spells/bola-de-fuego.json"
    assert "monster.aboleth" in by_page["283"]
    assert (COLLECTIONS / by_id["monster.aboleth"]["path"]).exists()
