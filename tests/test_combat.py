import pytest

from src.game.actions import dispatch
from src.game.character import State
from src.game.combat import CombatSystem, Match
from src.game.player import Player
from tests.helpers import fighter, step

DT = 1 / 60


def run_fight(a, b, seconds, cs=None):
    cs = cs or CombatSystem(-1000, 1000, 70)
    events = []
    for _ in range(int(seconds / DT)):
        a.update(DT)
        b.update(DT)
        events += cs.resolve(a, b)
    return events


def test_hit_in_range_applies_damage_once():
    a, b = fighter(0, 1), fighter(100, -1)
    assert a.request_attack("punch")
    ev = run_fight(a, b, 0.5)
    assert [e.kind for e in ev] == ["hit"]
    assert b.health == pytest.approx(93)
    assert a.hits_landed == 1


def test_out_of_range_or_wrong_facing_misses():
    a, b = fighter(0, 1), fighter(200, -1)
    a.request_attack("punch")
    assert run_fight(a, b, 0.5) == [] and b.health == 100
    a, b = fighter(0, -1), fighter(100, -1)  # de espaldas
    a.request_attack("punch")
    assert run_fight(a, b, 0.5) == [] and b.health == 100


def test_block_reduces_damage():
    a, b = fighter(0, 1), fighter(100, -1)
    b.set_blocking(True)
    a.request_attack("punch")
    ev = run_fight(a, b, 0.5)
    assert ev[0].kind == "block"
    assert b.health == pytest.approx(100 - 7 * 0.2)
    assert b.state == State.BLOCK  # el bloqueo no causa aturdimiento


def test_hitstun_then_recovery():
    a, b = fighter(0, 1), fighter(100, -1)
    a.request_attack("punch")
    run_fight(a, b, 0.2)
    assert b.state == State.HIT
    assert not b.request_attack("punch")  # aturdido no puede atacar
    step([b], 0.3)
    assert b.state == State.IDLE and b.request_attack("punch")


def test_attack_recovery_and_cooldown():
    a = fighter()
    assert a.request_attack("punch")
    assert not a.request_attack("punch")  # en plena animación
    step([a], 0.41)  # duración total del puñetazo = 0.40
    assert a.state == State.IDLE
    assert not a.request_attack("punch")  # cooldown de 0.15 s
    step([a], 0.16)
    assert a.request_attack("punch")


def test_ko_and_health_never_negative_and_match_result():
    a, b = fighter(0, 1), fighter(100, -1, health=5)
    a.request_attack("punch")
    ev = run_fight(a, b, 0.5)
    assert [e.kind for e in ev] == ["hit", "ko"]
    assert b.health == 0 and b.state == State.KO and not b.alive
    assert Match(99).update(DT, a, b) == "player"


def test_reset_restores_health():
    b = fighter(health=50)
    b.health = 3
    b.reset(10, -1)
    assert b.health == b.max_health and b.state == State.IDLE and b.x == 10


def test_time_over_winner_by_health_pct():
    a, b = fighter(), fighter()
    b.health = 40
    m = Match(1)
    assert m.update(0.5, a, b) is None
    assert m.update(0.6, a, b) == "player"


def test_constrain_bounds_separation_and_facing():
    cs = CombatSystem(0, 500, 70)
    a, b = fighter(-50, 1), fighter(20, 1)
    cs.constrain(a, b)
    assert a.x == 0 and b.x == pytest.approx(70)  # contra la pared, el otro se aparta
    assert a.facing == 1 and b.facing == -1
    a.x, b.x = 300, 250
    cs.constrain(a, b)
    assert abs(a.x - b.x) >= 70 - 1e-6 and a.facing == -1 and b.facing == 1


def test_attack_block_neutral_transitions_via_actions():
    p = fighter(cls=Player)
    dispatch(p, [], {"block"})
    assert p.state == State.BLOCK
    dispatch(p, [], set())
    assert p.state == State.IDLE           # sin gesto: neutral
    dispatch(p, [], {"block"})
    dispatch(p, ["attack"], {"block"})
    assert p.state == State.ATTACK         # se puede atacar saliendo de la guardia
    dispatch(p, ["no_existe"], {"tampoco"})  # acciones desconocidas se ignoran
    assert p.state == State.ATTACK
