"""Testes unitários — Tarefa 6.3: Serialização/Desserialização (Snapshot).

Cobre:
  - world_to_snapshot: campos giant_remaining, has_giant_shot,
    giant_shot_powerups e giant_bullets
  - snapshot_to_world: reconstrução correta dos valores acima
  - Round-trip: serializar → desserializar preserva o estado
"""

import pytest

from core.entities import GiantBullet, GiantShotPowerup
from core.utils import Vec
from core.world import World
from multiplayer.snapshot import snapshot_to_world
from server.protocol import world_to_snapshot


# ---------------------------------------------------------------------------
# Snapshot base reutilizável
# ---------------------------------------------------------------------------

EMPTY_SNAPSHOT = {
    "ships": [],
    "bullets": [],
    "asteroids": [],
    "ufos": [],
    "scores": {},
    "lives": {},
    "deaths": {},
    "frags": {},
    "respawning": [],
    "events": [],
    "audio_events": [],
    "names": {},
    "match_state": "running",
    "time_remaining": 0.0,
    "winner_id": None,
    "wave": 0,
    "game_over": False,
}


def _snapshot(**overrides):
    return {**EMPTY_SNAPSHOT, **overrides}


# ---------------------------------------------------------------------------
# Desserialização: snapshot_to_world (Tarefa 4 §4.2)
# ---------------------------------------------------------------------------


def test_snapshot_aplica_giant_remaining_na_nave():
    """snapshot_to_world deve restaurar o campo giant.remaining da nave."""
    w = World(spawn_default_player=False)
    snap = _snapshot(
        ships=[
            {
                "player_id": 1,
                "x": 100, "y": 200,
                "vx": 0, "vy": 0,
                "angle": 0.0,
                "shield_active": False,
                "invuln_active": False,
                "shield_cd_remaining": 0.0,
                "laser_remaining": 0.0,
                "giant_remaining": 3.5,
                "has_giant_shot": False,
            }
        ]
    )
    snapshot_to_world(snap, w)
    ship = w.ships[1]
    assert abs(ship.giant.remaining - 3.5) < 1e-6, (
        "giant.remaining deve ser restaurado do snapshot"
    )
    assert ship.giant.active is True


def test_snapshot_aplica_has_giant_shot_true():
    """snapshot_to_world deve restaurar has_giant_shot=True."""
    w = World(spawn_default_player=False)
    snap = _snapshot(
        ships=[
            {
                "player_id": 1,
                "x": 100, "y": 200,
                "vx": 0, "vy": 0,
                "angle": 0.0,
                "shield_active": False,
                "invuln_active": False,
                "shield_cd_remaining": 0.0,
                "laser_remaining": 0.0,
                "giant_remaining": 0.0,
                "has_giant_shot": True,
            }
        ]
    )
    snapshot_to_world(snap, w)
    assert w.ships[1].has_giant_shot is True


def test_snapshot_aplica_has_giant_shot_false_por_padrao():
    """Se has_giant_shot estiver ausente no snapshot (legado), deve ser False."""
    w = World(spawn_default_player=False)
    snap = _snapshot(
        ships=[
            {
                "player_id": 1,
                "x": 100, "y": 200,
                "vx": 0, "vy": 0,
                "angle": 0.0,
                "shield_active": False,
                "invuln_active": False,
                "shield_cd_remaining": 0.0,
                "laser_remaining": 0.0,
                # giant_remaining e has_giant_shot ausentes
            }
        ]
    )
    snapshot_to_world(snap, w)
    assert w.ships[1].has_giant_shot is False


def test_snapshot_reconstroi_giant_shot_powerups():
    """snapshot_to_world deve reconstruir a lista giant_shot_powerups no World."""
    w = World(spawn_default_player=False)
    snap = _snapshot(
        giant_shot_powerups=[
            {"x": 300, "y": 400, "vx": 0, "vy": 0, "ttl": 10.0},
            {"x": 600, "y": 800, "vx": 5, "vy": 5, "ttl": 7.5},
        ]
    )
    snapshot_to_world(snap, w)
    assert len(w.giant_shot_powerups) == 2
    p0 = w.giant_shot_powerups[0]
    assert (p0.pos.x, p0.pos.y) == (300, 400)
    assert p0.ttl == 10.0
    p1 = w.giant_shot_powerups[1]
    assert (p1.vel.x, p1.vel.y) == (5, 5)


def test_snapshot_reconstroi_giant_bullets():
    """snapshot_to_world deve reconstruir a lista giant_bullets no World."""
    w = World(spawn_default_player=False)
    snap = _snapshot(
        giant_bullets=[
            {"owner_id": 2, "x": 100, "y": 200, "vx": 350, "vy": 0},
        ]
    )
    snapshot_to_world(snap, w)
    assert len(w.giant_bullets) == 1
    gb = w.giant_bullets[0]
    assert gb.owner_id == 2
    assert (gb.pos.x, gb.pos.y) == (100, 200)
    assert abs(gb.vel.x - 350) < 0.01


def test_snapshot_giant_shot_powerups_ausente_nao_crasha():
    """Snapshot sem o campo giant_shot_powerups (legado) não deve crashar."""
    w = World(spawn_default_player=False)
    snap = _snapshot()  # sem giant_shot_powerups
    snapshot_to_world(snap, w)
    assert hasattr(w, "giant_shot_powerups")
    assert w.giant_shot_powerups == []


def test_snapshot_giant_bullets_ausente_nao_crasha():
    """Snapshot sem o campo giant_bullets (legado) não deve crashar."""
    w = World(spawn_default_player=False)
    snap = _snapshot()  # sem giant_bullets
    snapshot_to_world(snap, w)
    assert hasattr(w, "giant_bullets")
    assert w.giant_bullets == []


# ---------------------------------------------------------------------------
# Serialização: world_to_snapshot (Tarefa 4 §4.1)
# ---------------------------------------------------------------------------


def test_world_to_snapshot_serializa_giant_remaining():
    """world_to_snapshot deve incluir giant_remaining no payload da nave."""
    w = World(spawn_default_player=False)
    w.spawn_player(1)
    w.ships[1].giant.reset(2.5)

    snap = world_to_snapshot(w)
    ship_data = snap["ships"][0]
    assert "giant_remaining" in ship_data, (
        "giant_remaining deve estar serializado no snapshot"
    )
    assert abs(ship_data["giant_remaining"] - 2.5) < 0.2


def test_world_to_snapshot_serializa_has_giant_shot():
    """world_to_snapshot deve incluir has_giant_shot no payload da nave."""
    w = World(spawn_default_player=False)
    w.spawn_player(1)
    w.ships[1].has_giant_shot = True

    snap = world_to_snapshot(w)
    ship_data = snap["ships"][0]
    assert "has_giant_shot" in ship_data, (
        "has_giant_shot deve estar serializado no snapshot"
    )
    assert ship_data["has_giant_shot"] is True


def test_world_to_snapshot_serializa_giant_shot_powerups():
    """world_to_snapshot deve incluir a lista giant_shot_powerups no snapshot."""
    w = World(spawn_default_player=False)
    w.spawn_player(1)
    w.giant_shot_powerups = [GiantShotPowerup(Vec(300, 400), Vec(0, 0), ttl=9.0)]

    snap = world_to_snapshot(w)
    assert "giant_shot_powerups" in snap, "Snapshot deve conter giant_shot_powerups"
    assert len(snap["giant_shot_powerups"]) == 1
    p = snap["giant_shot_powerups"][0]
    assert p["x"] == 300.0
    assert p["y"] == 400.0


def test_world_to_snapshot_serializa_giant_bullets():
    """world_to_snapshot deve incluir a lista giant_bullets no snapshot."""
    w = World(spawn_default_player=False)
    w.spawn_player(1)
    w.giant_bullets = [GiantBullet(1, Vec(100, 200), Vec(350, 0))]

    snap = world_to_snapshot(w)
    assert "giant_bullets" in snap, "Snapshot deve conter giant_bullets"
    assert len(snap["giant_bullets"]) == 1
    gb = snap["giant_bullets"][0]
    assert gb["owner_id"] == 1
    assert gb["x"] == 100.0
    assert abs(gb["vx"] - 350) < 1.0


# ---------------------------------------------------------------------------
# Round-trip: serializar → desserializar
# ---------------------------------------------------------------------------


def test_roundtrip_giant_shot_powerup():
    """Serializar e desserializar um GiantShotPowerup deve preservar posição e TTL."""
    w_server = World(spawn_default_player=False)
    w_server.spawn_player(1)
    w_server.giant_shot_powerups = [
        GiantShotPowerup(Vec(500, 600), Vec(2, 3), ttl=12.0)
    ]

    snap = world_to_snapshot(w_server)

    w_client = World(spawn_default_player=False)
    snapshot_to_world(snap, w_client)

    assert len(w_client.giant_shot_powerups) == 1
    p = w_client.giant_shot_powerups[0]
    assert abs(p.pos.x - 500) < 1.0
    assert abs(p.pos.y - 600) < 1.0
    assert abs(p.ttl - 12.0) < 0.5


def test_roundtrip_giant_bullet():
    """Serializar e desserializar um GiantBullet deve preservar owner_id, pos e vel."""
    w_server = World(spawn_default_player=False)
    w_server.spawn_player(1)
    w_server.giant_bullets = [GiantBullet(1, Vec(200, 300), Vec(350, 0))]

    snap = world_to_snapshot(w_server)

    w_client = World(spawn_default_player=False)
    snapshot_to_world(snap, w_client)

    assert len(w_client.giant_bullets) == 1
    gb = w_client.giant_bullets[0]
    assert gb.owner_id == 1
    assert abs(gb.pos.x - 200) < 1.0
    assert abs(gb.vel.x - 350) < 1.0


def test_roundtrip_giant_debuff_na_nave():
    """giant_remaining e has_giant_shot devem sobreviver ao round-trip."""
    from core import config as C

    w_server = World(spawn_default_player=False)
    w_server.spawn_player(1)
    w_server.ships[1].giant.reset(3.0)
    w_server.ships[1].has_giant_shot = True

    snap = world_to_snapshot(w_server)

    w_client = World(spawn_default_player=False)
    snapshot_to_world(snap, w_client)

    ship = w_client.ships[1]
    assert ship.giant.active is True
    assert abs(ship.giant.remaining - 3.0) < 0.2
    assert ship.has_giant_shot is True
