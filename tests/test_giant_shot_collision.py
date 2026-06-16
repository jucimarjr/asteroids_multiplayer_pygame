"""Testes unitários — Tarefa 6.2: Colisões do Giant Shot.

Cobre:
  - CollisionResult: campos giant_shot_pickups e giant_shot_hits
  - _ship_vs_giant_shot_powerups: nave coleta o powerup
  - _giant_bullet_vs_ships: tiro aplica debuff giant
  - Tiro não acerta o próprio atirador
  - Tiro não acerta nave com invuln ou shield ativo
  - Hitbox giant (current_r) usada nas colisões existentes
"""

import pytest

from core import config as C
from core.collisions import CollisionManager, CollisionResult
from core.entities import Asteroid, GiantBullet, GiantShotPowerup, Ship
from core.utils import Vec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ship(player_id: int = 1, pos=(500, 500)) -> Ship:
    s = Ship(player_id, Vec(*pos))
    s.invuln.reset(0.0)
    return s


# ---------------------------------------------------------------------------
# CollisionResult: novos campos (Tarefa 3 §3.2)
# ---------------------------------------------------------------------------


def test_collision_result_tem_campo_giant_shot_pickups():
    """CollisionResult deve ter o campo giant_shot_pickups."""
    result = CollisionResult()
    assert hasattr(result, "giant_shot_pickups")
    assert result.giant_shot_pickups == []


def test_collision_result_tem_campo_giant_shot_hits():
    """CollisionResult deve ter o campo giant_shot_hits."""
    result = CollisionResult()
    assert hasattr(result, "giant_shot_hits")
    assert result.giant_shot_hits == []


# ---------------------------------------------------------------------------
# _ship_vs_giant_shot_powerups (Tarefa 3 §3.4)
# ---------------------------------------------------------------------------


def test_nave_coleta_powerup_quando_sobrepostos():
    """Nave sobre o powerup deve coletá-lo e popular giant_shot_pickups."""
    cm = CollisionManager()
    ship = _make_ship(player_id=1, pos=(300, 300))
    powerup = GiantShotPowerup(Vec(300, 300), Vec(0, 0))

    result = cm.resolve(
        ships={1: ship},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_shot_powerups=[powerup],
    )

    assert not powerup.alive, "Powerup deve ter sido coletado (killed)"
    assert len(result.giant_shot_pickups) == 1
    pid, pos = result.giant_shot_pickups[0]
    assert pid == 1


def test_powerup_nao_coletado_quando_distante():
    """Powerup distante da nave não deve ser coletado."""
    cm = CollisionManager()
    ship = _make_ship(player_id=1, pos=(300, 300))
    powerup = GiantShotPowerup(Vec(1000, 1000), Vec(0, 0))

    result = cm.resolve(
        ships={1: ship},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_shot_powerups=[powerup],
    )

    assert powerup.alive, "Powerup distante não deve ser coletado"
    assert result.giant_shot_pickups == []


def test_powerup_morto_nao_e_coletado_novamente():
    """Powerup já morto (alive=False) deve ser ignorado."""
    cm = CollisionManager()
    ship = _make_ship(player_id=1, pos=(300, 300))
    powerup = GiantShotPowerup(Vec(300, 300), Vec(0, 0))
    powerup.kill()  # já coletado anteriormente

    result = cm.resolve(
        ships={1: ship},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_shot_powerups=[powerup],
    )

    assert result.giant_shot_pickups == []


# ---------------------------------------------------------------------------
# _giant_bullet_vs_ships (Tarefa 3 §3.5)
# ---------------------------------------------------------------------------


def test_giant_bullet_aplica_debuff_giant_na_vitima():
    """GiantBullet acertando nave inimiga deve ativar ship.giant."""
    cm = CollisionManager()
    shooter = _make_ship(player_id=1, pos=(100, 100))
    victim = _make_ship(player_id=2, pos=(500, 500))
    gb = GiantBullet(owner_id=1, pos=Vec(500, 500), vel=Vec(0, 0))

    result = cm.resolve(
        ships={1: shooter, 2: victim},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_bullets=[gb],
    )

    assert not gb.alive, "GiantBullet deve ser destruída ao acertar"
    assert victim.giant.active is True, "A vítima deve ter o debuff giant ativado"


def test_giant_bullet_reduz_velocidade_da_vitima():
    """Ao acertar, a velocidade da vítima deve ser multiplicada por GIANT_SHOT_SPEED_MULT."""
    cm = CollisionManager()
    shooter = _make_ship(player_id=1, pos=(100, 100))
    victim = _make_ship(player_id=2, pos=(500, 500))
    victim.vel = Vec(300, 0)  # velocidade alta antes do hit
    gb = GiantBullet(owner_id=1, pos=Vec(500, 500), vel=Vec(0, 0))

    cm.resolve(
        ships={1: shooter, 2: victim},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_bullets=[gb],
    )

    expected_spd = 300.0 * C.GIANT_SHOT_SPEED_MULT
    assert abs(victim.vel.x - expected_spd) < 1.0, (
        f"Velocidade esperada ≈ {expected_spd}, obtida {victim.vel.x}"
    )


def test_giant_bullet_popula_giant_shot_hits():
    """Acerto deve aparecer em result.giant_shot_hits."""
    cm = CollisionManager()
    shooter = _make_ship(player_id=1, pos=(100, 100))
    victim = _make_ship(player_id=2, pos=(500, 500))
    gb = GiantBullet(owner_id=1, pos=Vec(500, 500), vel=Vec(0, 0))

    result = cm.resolve(
        ships={1: shooter, 2: victim},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_bullets=[gb],
    )

    assert (1, 2) in result.giant_shot_hits


def test_giant_bullet_nao_acerta_proprio_atirador():
    """GiantBullet não deve acertar a própria nave que atirou."""
    cm = CollisionManager()
    shooter = _make_ship(player_id=1, pos=(500, 500))
    gb = GiantBullet(owner_id=1, pos=Vec(500, 500), vel=Vec(0, 0))

    result = cm.resolve(
        ships={1: shooter},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_bullets=[gb],
    )

    assert gb.alive, "GiantBullet não deve atingir o próprio atirador"
    assert not shooter.giant.active, (
        "Atirador não deve receber o debuff de sua própria bala"
    )
    assert result.giant_shot_hits == []


def test_giant_bullet_nao_acerta_nave_invuln():
    """GiantBullet não deve acertar nave com invulnerabilidade ativa."""
    cm = CollisionManager()
    shooter = _make_ship(player_id=1, pos=(100, 100))
    victim = _make_ship(player_id=2, pos=(500, 500))
    victim.invuln.reset(C.SAFE_SPAWN_TIME)  # invulnerável
    gb = GiantBullet(owner_id=1, pos=Vec(500, 500), vel=Vec(0, 0))

    result = cm.resolve(
        ships={1: shooter, 2: victim},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_bullets=[gb],
    )

    assert gb.alive, "GiantBullet não deve acertar nave invulnerável"
    assert not victim.giant.active
    assert result.giant_shot_hits == []


def test_giant_bullet_nao_acerta_nave_com_shield():
    """GiantBullet não deve acertar nave com shield ativo."""
    cm = CollisionManager()
    shooter = _make_ship(player_id=1, pos=(100, 100))
    victim = _make_ship(player_id=2, pos=(500, 500))
    victim.shield.reset(C.SHIELD_DURATION)  # shield ativo
    gb = GiantBullet(owner_id=1, pos=Vec(500, 500), vel=Vec(0, 0))

    result = cm.resolve(
        ships={1: shooter, 2: victim},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_bullets=[gb],
    )

    assert gb.alive, "GiantBullet não deve penetrar o shield"
    assert not victim.giant.active
    assert result.giant_shot_hits == []


def test_giant_bullet_emite_evento_giant_shot_hit():
    """Acerto deve adicionar o evento 'giant_shot_hit' à lista de eventos."""
    cm = CollisionManager()
    shooter = _make_ship(player_id=1, pos=(100, 100))
    victim = _make_ship(player_id=2, pos=(500, 500))
    gb = GiantBullet(owner_id=1, pos=Vec(500, 500), vel=Vec(0, 0))

    result = cm.resolve(
        ships={1: shooter, 2: victim},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_bullets=[gb],
    )

    assert "giant_shot_hit" in result.events


def test_giant_bullet_nao_mata_vitima():
    """GiantBullet aplica debuff mas NÃO mata a nave (ship_deaths deve estar vazio)."""
    cm = CollisionManager()
    shooter = _make_ship(player_id=1, pos=(100, 100))
    victim = _make_ship(player_id=2, pos=(500, 500))
    gb = GiantBullet(owner_id=1, pos=Vec(500, 500), vel=Vec(0, 0))

    result = cm.resolve(
        ships={1: shooter, 2: victim},
        bullets=[],
        asteroids=[],
        ufos=[],
        giant_bullets=[gb],
    )

    assert result.ship_deaths == [], "GiantBullet não deve matar — apenas aplicar debuff"


# ---------------------------------------------------------------------------
# Hitbox aumentada com current_r (Tarefa 3 §3.6)
# ---------------------------------------------------------------------------


def test_nave_gigante_tem_hitbox_maior_contra_asteroides():
    """Nave sob debuff giant deve ser atingida por asteroides que normalmente
    passariam longe — porque current_r é 3× maior que r."""
    cm = CollisionManager()
    victim = _make_ship(player_id=1, pos=(500, 500))
    victim.giant.reset(C.GIANT_SHOT_DURATION)  # debuff ativo → hitbox 3×
    giant_r = victim.current_r

    # Posiciona o asteroide fora do raio normal mas dentro do raio gigante
    ast_r = C.AST_SIZES["S"]["r"]  # 12
    gap = 5
    dist = victim.r + ast_r + gap  # fora do raio normal
    assert dist < giant_r + ast_r, "Configuração do teste inválida: ajuste a posição"
    ast = Asteroid(Vec(500 + dist, 500), Vec(0, 0), "S")

    result = cm.resolve(
        ships={1: victim},
        bullets=[],
        asteroids=[ast],
        ufos=[],
    )

    assert 1 in result.ship_deaths, (
        "Nave gigante deve ser atingida pelo asteroide dentro da hitbox aumentada"
    )
