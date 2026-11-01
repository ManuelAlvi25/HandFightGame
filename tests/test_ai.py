import random

from src.game.ai import AIState, EnemyAI
from src.game.character import State
from src.game.combat import CombatSystem
from src.game.enemy import Enemy
from src.utils.config_loader import load_config
from tests.helpers import fighter

DT = 1 / 60
DIFFS = load_config("game_config.json")["difficulties"]


def enemy(x, params, seed=0):
    return fighter(x, -1, cls=Enemy, ai=EnemyAI(params, random.Random(seed), -1000, 1000))


def test_approaches_when_out_of_range():
    e, p = enemy(600, DIFFS["normal"]), fighter(0, 1)
    for _ in range(120):
        e.think(DT, p)
        e.update(DT)
    assert e.x < 600
    assert e.ai.state in (AIState.APPROACH, AIState.ATTACK, AIState.RECOVER, AIState.IDLE)


def test_attacks_when_in_range():
    e, p = enemy(100, {**DIFFS["normal"], "aggression": 1.0}), fighter(0, 1)
    started = 0
    for _ in range(180):
        e.think(DT, p)
        e.update(DT)
        started = e.attacks_started
    assert started >= 1


def test_blocks_incoming_attack_when_block_chance_is_1():
    e = enemy(100, {**DIFFS["normal"], "block_chance": 1.0, "reaction_time": 0.0, "aggression": 0.0})
    p = fighter(0, 1)
    e.ai.state, e.ai.timer = AIState.IDLE, 5.0
    p.request_attack("punch")
    e.think(DT, p)
    e.think(DT, p)
    assert e.ai.state == AIState.DEFEND and e.state == State.BLOCK


def test_never_reacts_with_block_chance_0():
    e = enemy(100, {**DIFFS["normal"], "block_chance": 0.0, "aggression": 0.0, "retreat_chance": 0.0})
    p = fighter(0, 1)
    for _ in range(10):
        p.reset(0, 1)
        p.request_attack("punch")
        for _ in range(30):
            e.think(DT, p)
            assert e.ai.state != AIState.DEFEND


def test_victory_and_defeat_states():
    e, p = enemy(100, DIFFS["normal"]), fighter(0, 1)
    p.health = 0
    e.think(DT, p)
    assert e.ai.state == AIState.VICTORY
    p.health, e.health = 100, 0
    e.think(DT, p)
    assert e.ai.state == AIState.DEFEAT


def count_attacks(params, seed):
    e, p = enemy(100, params, seed), fighter(0, 1, health=10_000)
    for _ in range(int(20 / DT)):
        e.think(DT, p)
        e.update(DT)
    return e.attacks_started


def test_harder_difficulty_is_more_aggressive():
    easy = sum(count_attacks(DIFFS["facil"], s) for s in range(5))
    hard = sum(count_attacks(DIFFS["dificil"], s) for s in range(5))
    assert hard > easy * 1.5


def simulate_duel(params, seed, seconds=99):
    """Jugador sencillo que se acerca y golpea en cuanto puede, contra la IA."""
    cs = CombatSystem(90, 1190, 70)
    p, e = fighter(420, 1), enemy(860, params, seed)
    for _ in range(int(seconds / DT)):
        if not (p.alive and e.alive):
            break
        if abs(e.x - p.x) > 110:
            p.walk(1 if e.x > p.x else -1, DT)
        else:
            p.walk(0, DT)
            p.request_attack("punch")
        e.think(DT, p)
        p.update(DT)
        e.update(DT)
        cs.constrain(p, e)
        cs.resolve(p, e)
    return p.health_pct, e.health_pct


def test_easy_ai_is_beatable_and_hard_ai_defends_better():
    easy = [simulate_duel(DIFFS["facil"], s) for s in range(6)]
    hard = [simulate_duel(DIFFS["dificil"], s) for s in range(6)]
    assert sum(pe == 0 for _, pe in easy) >= 4                          # se le puede ganar
    assert sum(pp for pp, _ in hard) < sum(pp for pp, _ in easy)        # la difícil hace más daño
