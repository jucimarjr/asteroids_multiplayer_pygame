"""Testes de integração — Tarefa 6.4: Fluxo completo do Giant Shot no World.

Cobre o ciclo de vida completo:
  1. World spawna GiantShotPowerup após o timer
  2. Nave coleta o powerup → has_giant_shot = True
  3. Nave atira → GiantBullet aparece em world.giant_bullets
  4. GiantBullet colide com inimigo → victim.giant.active == True
  5. Após 5s de update() → victim.giant.active == False
"""

import pytest

from core import config as C
from core.commands import PlayerCommand
from core.entities import GiantBullet, GiantShotPowerup
from core.utils import Vec
from core.world import World


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _no_cmd() -> PlayerCommand:
    return PlayerCommand()


def _shoot_cmd() -> PlayerCommand:
    return PlayerCommand(shoot=True)


def _advance(world: World, dt: float, steps: int = 1, cmds=None) -> None:
    """Avança o mundo `steps` vezes com `dt` por passo."""
    if cmds is None:
        cmds = {}
    for _ in range(steps):
        world.update(dt, cmds)


# ---------------------------------------------------------------------------
# Pré-requisito: World deve ter as listas e o timer (Tarefa 2)
# ---------------------------------------------------------------------------


def test_world_tem_lista_giant_shot_powerups():
    """World deve ter a lista giant_shot_powerups (implementado na Tarefa 2)."""
    w = World(spawn_default_player=False)
    assert hasattr(w, "giant_shot_powerups")
    assert w.giant_shot_powerups == []


def test_world_tem_lista_giant_bullets():
    """World deve ter a lista giant_bullets (implementado na Tarefa 2)."""
    w = World(spawn_default_player=False)
    assert hasattr(w, "giant_bullets")
    assert w.giant_bullets == []


def test_world_tem_timer_giant_shot():
    """World deve ter o giant_shot_timer (implementado na Tarefa 2)."""
    w = World(spawn_default_player=False)
    assert hasattr(w, "giant_shot_timer")


# ---------------------------------------------------------------------------
# Passo 1: Spawn do powerup via timer (Tarefa 2 §2.4–2.5)
# ---------------------------------------------------------------------------


def test_powerup_spawna_apos_timer():
    """Após o timer disparar, pelo menos um GiantShotPowerup deve aparecer."""
    w = World(spawn_default_player=True, deathmatch=False)
    # Força o timer a disparar imediatamente
    w.giant_shot_timer.reset(0.001)
    _advance(w, dt=0.1)
    assert len(w.giant_shot_powerups) >= 1, (
        "Deve existir pelo menos um GiantShotPowerup após o timer disparar"
    )
    assert isinstance(w.giant_shot_powerups[0], GiantShotPowerup)


# ---------------------------------------------------------------------------
# Passo 2: Coleta do powerup (Tarefa 2 §2.7 + Tarefa 3 §3.4)
# ---------------------------------------------------------------------------


def test_nave_coleta_powerup_via_world_update():
    """Após colisão com powerup, ship.has_giant_shot deve virar True."""
    w = World(spawn_default_player=False, deathmatch=True)
    w.spawn_player(1)
    w.spawn_player(2)  # precisa de 2 jogadores para sair do lobby
    ship = w.ships[1]
    ship.invuln.reset(0.0)
    w.ships[2].invuln.reset(0.0)

    # Tick de aquecimento: lobby → running (neste tick comandos ainda não são processados)
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})
    assert w.match_state == "running"

    powerup = GiantShotPowerup(Vec(ship.pos), Vec(0, 0))
    w.giant_shot_powerups = [powerup]

    # Tick real: powerup deve ser coletado
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})

    assert ship.has_giant_shot is True, (
        "Nave deve ter has_giant_shot=True após coletar o powerup"
    )
    assert not powerup.alive, "Powerup deve ter sido destruído após a coleta"
    assert "giant_shot_pickup" in w.events


# ---------------------------------------------------------------------------
# Passo 3: Disparo → GiantBullet entra em world.giant_bullets (Tarefa 2 §2.6)
# ---------------------------------------------------------------------------


def test_disparo_giant_shot_adiciona_bullet_a_lista():
    """Ao atirar com has_giant_shot=True, GiantBullet deve aparecer em world.giant_bullets."""
    w = World(spawn_default_player=False, deathmatch=True)
    w.spawn_player(1)
    w.spawn_player(2)  # precisa de 2 jogadores para sair do lobby
    ship = w.ships[1]

    # Tick de aquecimento: lobby → running
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})

    ship.invuln.reset(0.0)
    ship.cool.reset(0.0)
    ship.has_giant_shot = True

    _advance(w, dt=0.016, cmds={1: _shoot_cmd(), 2: _no_cmd()})

    assert len(w.giant_bullets) == 1, (
        "Deve existir exatamente 1 GiantBullet em world.giant_bullets"
    )
    assert isinstance(w.giant_bullets[0], GiantBullet)
    assert w.giant_bullets[0].owner_id == 1


def test_disparo_emite_evento_giant_shot_fire():
    """O evento 'giant_shot_fire' deve ser emitido ao disparar o Giant Shot."""
    w = World(spawn_default_player=False, deathmatch=True)
    w.spawn_player(1)
    w.spawn_player(2)  # precisa de 2 jogadores para sair do lobby
    ship = w.ships[1]

    # Tick de aquecimento: lobby → running
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})

    ship.invuln.reset(0.0)
    ship.cool.reset(0.0)
    ship.has_giant_shot = True

    _advance(w, dt=0.016, cmds={1: _shoot_cmd(), 2: _no_cmd()})

    assert "giant_shot_fire" in w.events


# ---------------------------------------------------------------------------
# Passo 4: GiantBullet colide com inimigo → debuff (Tarefa 2 + Tarefa 3)
# ---------------------------------------------------------------------------


def test_giant_bullet_aplica_debuff_via_world():
    """GiantBullet colidindo com nave inimiga no world.update deve ativar giant."""
    w = World(spawn_default_player=False, deathmatch=True)
    w.spawn_player(1)
    w.spawn_player(2)

    # Tick de aquecimento: lobby → running
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})

    victim = w.ships[2]
    victim.invuln.reset(0.0)

    gb = GiantBullet(owner_id=1, pos=Vec(victim.pos), vel=Vec(0, 0))
    w.giant_bullets = [gb]

    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})

    assert victim.giant.active is True, (
        "Vítima deve ter giant.active=True após ser atingida pelo GiantBullet"
    )
    assert not gb.alive, "GiantBullet deve ser destruída após acertar"
    assert "giant_shot_hit" in w.events


def test_giant_bullet_nao_mata_vitima_via_world():
    """A vítima atingida pelo GiantBullet não deve morrer, mas deve ficar giant."""
    w = World(spawn_default_player=False, deathmatch=True)
    w.spawn_player(1)
    w.spawn_player(2)

    # Tick de aquecimento: lobby → running
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})

    victim = w.ships[2]
    victim.invuln.reset(0.0)

    gb = GiantBullet(owner_id=1, pos=Vec(victim.pos), vel=Vec(0, 0))
    w.giant_bullets = [gb]

    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})

    # Em deathmatch, morrer remove a nave de w.ships
    assert 2 in w.ships, "Vítima não deve morrer ao ser atingida pelo GiantBullet"
    assert victim.giant.active is True, (
        "Vítima deve ter giant.active=True mesmo sem ter morrido"
    )


# ---------------------------------------------------------------------------
# Passo 5: Expiração do debuff
# ---------------------------------------------------------------------------


def test_debuff_giant_expira_apos_duracao_no_world():
    """Após GIANT_SHOT_DURATION segundos de ticks, victim.giant deve desativar."""
    # Usa single-player (não-deathmatch): sem match timer, sem lobby
    w = World(spawn_default_player=False, deathmatch=False)
    w.spawn_player(1)
    victim = w.ships[1]
    victim.invuln.reset(0.0)
    # Ativa o debuff manualmente
    victim.giant.reset(C.GIANT_SHOT_DURATION)

    assert victim.giant.active is True

    dt = 0.016
    steps = int((C.GIANT_SHOT_DURATION + 0.5) / dt)
    _advance(w, dt=dt, steps=steps, cmds={1: _no_cmd()})

    assert victim.giant.active is False, (
        f"Debuff deve ter expirado após {C.GIANT_SHOT_DURATION}s"
    )
    assert victim.current_r == float(victim.r), (
        "Hitbox deve voltar ao normal após o debuff expirar"
    )


# ---------------------------------------------------------------------------
# Fluxo completo integrado
# ---------------------------------------------------------------------------


def test_fluxo_completo_giant_shot():
    """Testa o ciclo completo: spawn powerup → coleta → disparo → debuff → expiração."""
    w = World(spawn_default_player=False, deathmatch=True)
    w.spawn_player(1)
    w.spawn_player(2)
    shooter = w.ships[1]
    victim = w.ships[2]
    shooter.invuln.reset(0.0)
    victim.invuln.reset(0.0)

    # Tick de aquecimento: lobby → running
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})

    # --- Etapa 1: Injetar powerup na posição do atirador ---
    powerup = GiantShotPowerup(Vec(shooter.pos), Vec(0, 0))
    w.giant_shot_powerups = [powerup]
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})
    assert shooter.has_giant_shot is True, "Etapa 1: powerup deve ter sido coletado"

    # --- Etapa 2: Atirar ---
    shooter.cool.reset(0.0)
    _advance(w, dt=0.016, cmds={1: _shoot_cmd(), 2: _no_cmd()})
    assert len(w.giant_bullets) >= 1, "Etapa 2: GiantBullet deve ter sido criada"

    # --- Etapa 3: Mover a bala até a vítima ---
    w.giant_bullets[0].pos.xy = (victim.pos.x, victim.pos.y)
    _advance(w, dt=0.016, cmds={1: _no_cmd(), 2: _no_cmd()})
    assert victim.giant.active is True, "Etapa 3: debuff deve estar ativo na vítima"

    # --- Etapa 4: Aguardar expiração ---
    dt = 0.016
    steps = int((C.GIANT_SHOT_DURATION + 0.5) / dt)
    _advance(w, dt=dt, steps=steps, cmds={1: _no_cmd(), 2: _no_cmd()})
    assert victim.giant.active is False, "Etapa 4: debuff deve ter expirado"


# ---------------------------------------------------------------------------
# Reset na morte (Tarefa 2 §2.10)
# ---------------------------------------------------------------------------


def test_giant_e_has_giant_shot_resetados_ao_morrer():
    """Ao morrer, giant.remaining e has_giant_shot devem ser zerados.

    Implementado na Tarefa 2 §2.10: _ship_die limpa giant e has_giant_shot.
    """
    w = World(spawn_default_player=False, deathmatch=False)
    w.spawn_player(1)
    ship = w.ships[1]
    ship.invuln.reset(0.0)

    ship.giant.reset(C.GIANT_SHOT_DURATION)
    ship.has_giant_shot = True

    w._ship_die(ship)

    assert not ship.giant.active, "giant deve ser resetado quando a nave morre"
    assert ship.has_giant_shot is False, "has_giant_shot deve ser False quando a nave morre"


# ---------------------------------------------------------------------------
# Purge das listas (Tarefa 2 §2.8)
# ---------------------------------------------------------------------------


def test_purge_dead_remove_powerups_mortos():
    """_purge_dead deve remover GiantShotPowerups com alive=False.

    Implementado na Tarefa 2 §2.8.
    """
    w = World(spawn_default_player=False)
    p_alive = GiantShotPowerup(Vec(100, 100), Vec(0, 0))
    p_dead = GiantShotPowerup(Vec(200, 200), Vec(0, 0))
    p_dead.kill()
    w.giant_shot_powerups = [p_alive, p_dead]
    w._purge_dead()
    assert len(w.giant_shot_powerups) == 1
    assert w.giant_shot_powerups[0] is p_alive


def test_purge_dead_remove_giant_bullets_mortas():
    """_purge_dead deve remover GiantBullets com alive=False.

    Implementado na Tarefa 2 §2.8.
    """
    w = World(spawn_default_player=False)
    gb_alive = GiantBullet(1, Vec(100, 100), Vec(0, 0))
    gb_dead = GiantBullet(1, Vec(200, 200), Vec(0, 0))
    gb_dead.kill()
    w.giant_bullets = [gb_alive, gb_dead]
    w._purge_dead()
    assert len(w.giant_bullets) == 1
    assert w.giant_bullets[0] is gb_alive
