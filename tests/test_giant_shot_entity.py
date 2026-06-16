"""Testes unitários — Tarefa 6.1: Entidades do Giant Shot.

Cobre GiantShotPowerup, GiantBullet e a integração com Ship._try_fire.
"""

from core import config as C
from core.commands import PlayerCommand
from core.entities import GiantBullet, GiantShotPowerup, Ship
from core.utils import Vec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ship(player_id: int = 1, pos=(500, 500)) -> Ship:
    """Cria uma nave sem invulnerabilidade e com cooldown zerado."""
    s = Ship(player_id, Vec(*pos))
    s.invuln.reset(0.0)  # remove invulnerabilidade pós-spawn
    s.cool.reset(0.0)    # garante que pode atirar imediatamente
    return s


def _shoot(ship: Ship, bullets=None) -> "GiantBullet | object | None":
    """Dispara um tiro da nave via apply_command com shoot=True."""
    if bullets is None:
        bullets = []
    cmd = PlayerCommand(shoot=True)
    return ship.apply_command(cmd, dt=0.016, bullets=bullets)


# ---------------------------------------------------------------------------
# GiantShotPowerup
# ---------------------------------------------------------------------------


class TestGiantShotPowerup:
    def test_nasce_alive(self):
        p = GiantShotPowerup(Vec(100, 100), Vec(0, 0))
        assert p.alive is True

    def test_tem_raio_correto(self):
        p = GiantShotPowerup(Vec(100, 100), Vec(0, 0))
        assert p.r == int(C.GIANT_SHOT_POWERUP_RADIUS)

    def test_tem_ttl_correto_por_padrao(self):
        p = GiantShotPowerup(Vec(100, 100), Vec(0, 0))
        assert p.ttl == C.GIANT_SHOT_POWERUP_TTL

    def test_ttl_customizavel(self):
        p = GiantShotPowerup(Vec(0, 0), Vec(0, 0), ttl=3.0)
        assert p.ttl == 3.0

    def test_se_move_conforme_velocidade(self):
        p = GiantShotPowerup(Vec(100, 100), Vec(10, 0))
        p.update(dt=1.0)
        assert abs(p.pos.x - 110.0) < 0.01

    def test_morre_quando_ttl_expira(self):
        p = GiantShotPowerup(Vec(100, 100), Vec(0, 0), ttl=0.1)
        p.update(dt=0.2)
        assert p.alive is False

    def test_nao_morre_antes_do_ttl(self):
        p = GiantShotPowerup(Vec(100, 100), Vec(0, 0), ttl=5.0)
        p.update(dt=1.0)
        assert p.alive is True

    def test_ttl_decresce_a_cada_update(self):
        p = GiantShotPowerup(Vec(100, 100), Vec(0, 0), ttl=2.0)
        p.update(dt=0.5)
        assert abs(p.ttl - 1.5) < 1e-6

    def test_kill_seta_alive_false(self):
        p = GiantShotPowerup(Vec(0, 0), Vec(0, 0))
        p.kill()
        assert p.alive is False


# ---------------------------------------------------------------------------
# GiantBullet
# ---------------------------------------------------------------------------


class TestGiantBullet:
    def test_nasce_alive(self):
        gb = GiantBullet(1, Vec(200, 200), Vec(0, 0))
        assert gb.alive is True

    def test_armazena_owner_id(self):
        gb = GiantBullet(42, Vec(0, 0), Vec(0, 0))
        assert gb.owner_id == 42

    def test_tem_raio_correto(self):
        gb = GiantBullet(1, Vec(0, 0), Vec(0, 0))
        assert gb.r == int(C.GIANT_SHOT_BULLET_RADIUS)

    def test_tem_ttl_correto_por_padrao(self):
        gb = GiantBullet(1, Vec(0, 0), Vec(0, 0))
        assert gb.ttl == C.GIANT_SHOT_BULLET_TTL

    def test_se_move_conforme_velocidade(self):
        gb = GiantBullet(1, Vec(100, 100), Vec(50, 0))
        gb.update(dt=1.0)
        assert abs(gb.pos.x - 150.0) < 0.01

    def test_morre_quando_ttl_expira(self):
        gb = GiantBullet(1, Vec(0, 0), Vec(0, 0), ttl=0.1)
        gb.update(dt=0.5)
        assert gb.alive is False

    def test_nao_morre_antes_do_ttl(self):
        gb = GiantBullet(1, Vec(0, 0), Vec(0, 0), ttl=2.0)
        gb.update(dt=0.5)
        assert gb.alive is True

    def test_ttl_decresce_a_cada_update(self):
        gb = GiantBullet(1, Vec(0, 0), Vec(0, 0), ttl=1.5)
        gb.update(dt=0.5)
        assert abs(gb.ttl - 1.0) < 1e-6

    def test_raio_maior_que_bullet_normal(self):
        """O projétil especial deve ter raio maior que uma bala normal."""
        assert C.GIANT_SHOT_BULLET_RADIUS > C.BULLET_RADIUS


# ---------------------------------------------------------------------------
# Ship.has_giant_shot e _try_fire
# ---------------------------------------------------------------------------


class TestShipGiantShot:
    def test_has_giant_shot_comeca_false(self):
        ship = _make_ship()
        assert ship.has_giant_shot is False

    def test_giant_inativo_por_padrao(self):
        ship = _make_ship()
        assert ship.giant.active is False

    def test_disparar_sem_giant_shot_retorna_bullet_normal(self):
        from core.entities import Bullet
        ship = _make_ship()
        shot = _shoot(ship)
        assert isinstance(shot, Bullet)

    def test_disparar_com_has_giant_shot_retorna_giant_bullet(self):
        ship = _make_ship()
        ship.has_giant_shot = True
        shot = _shoot(ship)
        assert isinstance(shot, GiantBullet), (
            "Com has_giant_shot=True, _try_fire deve retornar GiantBullet"
        )

    def test_giant_bullet_tem_owner_id_correto(self):
        ship = _make_ship(player_id=7)
        ship.has_giant_shot = True
        shot = _shoot(ship)
        assert isinstance(shot, GiantBullet)
        assert shot.owner_id == 7

    def test_has_giant_shot_vira_false_apos_disparo(self):
        """O tiro é único — após disparar, a flag deve ser consumida."""
        ship = _make_ship()
        ship.has_giant_shot = True
        _shoot(ship)
        assert ship.has_giant_shot is False, (
            "has_giant_shot deve ser consumido (False) após o primeiro disparo"
        )

    def test_segundo_disparo_apos_giant_shot_retorna_bullet_normal(self):
        """Depois de consumir o tiro especial, o próximo tiro é normal."""
        from core.entities import Bullet
        ship = _make_ship()
        ship.has_giant_shot = True
        _shoot(ship)     # consome o giant shot
        # Zera o cooldown para permitir outro tiro imediato
        ship.cool.reset(0.0)
        shot = _shoot(ship)
        assert isinstance(shot, Bullet), (
            "Após consumir o Giant Shot, o tiro seguinte deve ser Bullet normal"
        )

    def test_giant_shot_tem_prioridade_sobre_laser(self):
        """Giant shot tem prioridade sobre laser (conforme plan §1.4c)."""
        from core.entities import LaserBeam
        ship = _make_ship()
        ship.has_giant_shot = True
        ship.laser.reset(C.LASER_DURATION)  # laser também ativo
        shot = _shoot(ship)
        assert isinstance(shot, GiantBullet), (
            "Giant shot deve ter prioridade sobre o laser"
        )
        assert not isinstance(shot, LaserBeam)

    def test_giant_shot_nao_dispara_quando_em_cooldown(self):
        """Se a nave estiver em cooldown, não deve disparar nada."""
        ship = _make_ship()
        ship.has_giant_shot = True
        ship.cool.reset(C.SHIP_FIRE_RATE)  # força cooldown ativo
        shot = _shoot(ship)
        assert shot is None, (
            "Cooldown ativo deve impedir o disparo mesmo com has_giant_shot=True"
        )
        # A flag não deve ser consumida se o tiro não ocorreu
        assert ship.has_giant_shot is True, (
            "has_giant_shot não deve ser consumido se o tiro foi bloqueado por cooldown"
        )

    def test_giant_bullet_velocidade_soma_nave_mais_constante(self):
        """Velocidade do projétil = vel_nave + dirv * GIANT_SHOT_BULLET_SPEED."""
        ship = _make_ship()
        ship.angle = 0.0   # aponta para a direita (+x)
        ship.vel = Vec(10, 0)  # nave se move para a direita
        ship.has_giant_shot = True
        shot = _shoot(ship)
        assert isinstance(shot, GiantBullet)
        # vel.x deve ser ≈ nave_vx + GIANT_SHOT_BULLET_SPEED
        expected_x = 10.0 + C.GIANT_SHOT_BULLET_SPEED
        assert abs(shot.vel.x - expected_x) < 1.0, (
            f"Esperado vel.x ≈ {expected_x}, obtido {shot.vel.x}"
        )

    # --- current_r e efeito giant ---

    def test_current_r_igual_a_r_sem_debuff(self):
        ship = _make_ship()
        assert ship.current_r == float(ship.r)

    def test_current_r_multiplicado_quando_giant_ativo(self):
        ship = _make_ship()
        ship.giant.reset(C.GIANT_SHOT_DURATION)
        expected = ship.r * C.GIANT_SHOT_SCALE
        assert abs(ship.current_r - expected) < 1e-6

    def test_giant_expira_apos_duracao(self):
        """Após GIANT_SHOT_DURATION segundos de update, o efeito deve terminar."""
        ship = _make_ship()
        ship.giant.reset(C.GIANT_SHOT_DURATION)
        assert ship.giant.active is True
        # Avança o tempo além da duração
        ship.update(dt=C.GIANT_SHOT_DURATION + 0.1)
        assert ship.giant.active is False
        assert ship.current_r == float(ship.r)

    def test_velocidade_cappada_quando_giant_ativo(self):
        """Ship.update() deve limitar a velocidade ao cap quando giant está ativo."""
        ship = _make_ship()
        ship.giant.reset(C.GIANT_SHOT_DURATION)
        # Dá uma velocidade muito alta à nave
        max_spd = C.SHIP_THRUST * C.GIANT_SHOT_SPEED_MULT
        ship.vel = Vec(max_spd * 10, 0)
        ship.update(dt=0.016)
        spd = ship.vel.length()
        assert spd <= max_spd + 0.01, (
            f"Velocidade {spd:.2f} excede o cap {max_spd:.2f} durante o debuff giant"
        )

    def test_velocidade_nao_cappada_sem_giant(self):
        """Sem o debuff, velocidades altas não são cortadas pelo cap do giant."""
        ship = _make_ship()
        assert not ship.giant.active
        max_spd = C.SHIP_THRUST * C.GIANT_SHOT_SPEED_MULT
        ship.vel = Vec(max_spd * 10, 0)
        spd_antes = ship.vel.length()
        ship.update(dt=0.016)
        # Sem giant, a velocidade alta não deve ser cortada pelo cap do giant
        # (pode diminuir por atrito, mas não será reduzida ao cap do giant)
        spd_depois = ship.vel.length()
        assert spd_depois > max_spd, (
            "Sem debuff giant, a velocidade não deve ser cortada pelo cap do giant"
        )
