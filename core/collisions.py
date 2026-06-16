"""Collision detection and resolution. No pygame here."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import uniform, random as _random
from core import config as C
from core.entities import (
    UFO,
    UFO_BULLET_OWNER,
    Asteroid,
    Bullet,
    FreezePowerup,
    GiantBullet,
    GiantShotPowerup,
    LaserBeam,
    LaserPowerup,
    PlayerId,
    Shrapnel,
    Ship,
)
from core.utils import Vec, rand_unit_vec, toroidal_delta, wrap_pos


def _segment_circle_hit(
    seg_a: Vec, seg_b: Vec, center: Vec, radius: float
) -> bool:
    """Return True when segment AB intersects a circle at center with radius."""
    ab = seg_b - seg_a
    ac = center - seg_a
    ab_len_sq = ab.length_squared()
    if ab_len_sq < 1e-10:
        return ac.length() < radius
    t = (ac.x * ab.x + ac.y * ab.y) / ab_len_sq
    t = max(0.0, min(1.0, t))
    closest_x = seg_a.x + ab.x * t
    closest_y = seg_a.y + ab.y * t
    dx = center.x - closest_x
    dy = center.y - closest_y
    return dx * dx + dy * dy < radius * radius


@dataclass
class CollisionResult:
    """Outcome of a single collision resolution pass."""

    events: list[str] = field(default_factory=list)
    score_deltas: dict[PlayerId, int] = field(default_factory=dict)
    # PvP frag counter, applied separately from score. A frag is one shooter
    # killing another player's ship; UFO/asteroid kills do not count here.
    frag_deltas: dict[PlayerId, int] = field(default_factory=dict)
    ship_deaths: list[PlayerId] = field(default_factory=list)
    asteroids_to_spawn: list[tuple[Vec, Vec, str]] = field(
        default_factory=list
    )
    # (position, kind) — kind is "asteroid", "ufo", or "ship"; World looks up
    # the count/speed/ttl tuple in core.config and spawns the particles.
    particles_to_spawn: list[tuple[Vec, str]] = field(default_factory=list)
    # (player_id, powerup_pos) pairs for each laser powerup collected this tick.
    powerup_pickups: list[tuple[PlayerId, Vec]] = field(default_factory=list)
    # (player_id, powerup_pos) for each giant-shot powerup collected
    giant_shot_pickups: list[tuple[PlayerId, Vec]] = field(default_factory=list)
    # (shooter_id, victim_id) for each giant bullet that hit an enemy ship
    giant_shot_hits: list[tuple[PlayerId, PlayerId]] = field(default_factory=list)
    powerups_to_apply: list[str] = field(default_factory=list)
    freeze_powerups_to_spawn: list[Vec] = field(default_factory=list)
    # (position, velocity) pairs for shrapnel fragments from red asteroids.
    shrapnel_to_spawn: list[tuple[Vec, Vec]] = field(default_factory=list)


class CollisionManager:
    """Resolves all collisions between game entities."""

    def resolve(
        self,
        ships: dict[PlayerId, Ship],
        bullets: list[Bullet],
        asteroids: list[Asteroid],
        ufos: list[UFO],
        powerups: list[LaserPowerup] | None = None,
        lasers: list[LaserBeam] | None = None,
        giant_shot_powerups: list[GiantShotPowerup] | None = None,
        giant_bullets: list[GiantBullet] | None = None,
        freeze_powerups: list[FreezePowerup] | None = None,
    ) -> CollisionResult:
        result = CollisionResult()
        if giant_shot_powerups is not None:
            self._ship_vs_giant_shot_powerups(ships, giant_shot_powerups, result)
        if giant_bullets:
            self._giant_bullet_vs_ships(ships, giant_bullets, result)
        if powerups is not None:
            self._ship_vs_powerups(ships, powerups, result)
        if freeze_powerups is not None:
            self._ship_vs_freeze_powerups(ships, freeze_powerups, result)
        if lasers:
            self._laser_vs_asteroids(lasers, asteroids, result)
            self._laser_vs_ufos(lasers, ufos, result)
            self._laser_vs_ships(lasers, ships, result)
            for laser in lasers:
                laser.resolved = True
        self._bullets_vs_asteroids(bullets, asteroids, result)
        self._ufo_vs_player_bullets(ufos, bullets, result)
        self._bullets_vs_ships(ships, bullets, result)
        self._ufo_vs_asteroids(ufos, asteroids, result)
        self._ship_vs_asteroids(ships, asteroids, result)
        self._ship_vs_ufos(ships, ufos, result)
        self._ship_vs_ufo_bullets(ships, bullets, result)
        self._ship_vs_ships(ships, result)
        return result

    def _ship_vs_ships(
        self,
        ships: dict[PlayerId, Ship],
        result: CollisionResult,
    ) -> None:
        """Resolve collisions between ships by pushing them apart.

        Uses toroidal-aware distance and normal to support wrapping.
        Applying a small impulse (SHIP_PUSH_STRENGTH) ensures ships
        don't get stuck and provides tactile feedback.
        """
        pids = list(ships.keys())
        for i in range(len(pids)):
            for j in range(i + 1, len(pids)):
                s1 = ships[pids[i]]
                s2 = ships[pids[j]]

                delta = toroidal_delta(s2.pos, s1.pos)
                dist_sq = delta.length_squared()
                min_dist = s1.r + s2.r
                if dist_sq < min_dist * min_dist:
                    dist = delta.length()
                    if dist < 1e-3:
                        normal = Vec(1, 0)
                        dist = 0.1
                    else:
                        normal = delta * (1.0 / dist)

                    # 1. Static resolution: push them apart so they don't overlap.
                    overlap = min_dist - dist
                    s1.pos = wrap_pos(s1.pos + normal * (overlap * 0.5))
                    s2.pos = wrap_pos(s2.pos - normal * (overlap * 0.5))

                    # 2. Dynamic resolution: apply a push impulse.
                    # We add velocity along the normal to separate them.
                    relative_vel = s1.vel - s2.vel
                    vel_along_normal = relative_vel.dot(normal)

                    # Only apply impulse if they aren't already moving apart fast enough.
                    strength = C.SHIP_PUSH_STRENGTH
                    if vel_along_normal < strength:
                        impulse = normal * (strength - max(0.0, vel_along_normal))
                        s1.vel += impulse * 0.5
                        s2.vel -= impulse * 0.5

                    result.events.append("ship_push")

    def _bullets_vs_asteroids(
        self,
        bullets: list[Bullet],
        asteroids: list[Asteroid],
        result: CollisionResult,
    ) -> None:
        for ast in asteroids:
            if not ast.alive:
                continue
            hit_bullets: list[Bullet] = []
            for b in bullets:
                if not b.alive:
                    continue
                if (ast.pos - b.pos).length() < ast.r:
                    hit_bullets.append(b)
            if not hit_bullets:
                continue

            # Kill all bullets that hit this asteroid.
            for b in hit_bullets:
                b.kill()

            if any(b.owner_id == UFO_BULLET_OWNER for b in hit_bullets):
                pos = Vec(ast.pos)
                ast.kill()
                result.events.append("asteroid_explosion")
                result.particles_to_spawn.append((pos, "asteroid"))
                continue

            player_bullets = [b for b in hit_bullets if b.owner_id > 0]
            scorer = player_bullets[0].owner_id if player_bullets else None
            self._split_asteroid(ast, scorer_id=scorer, result=result, asteroids=asteroids)

    def _destroy_ufo(self, ufo: UFO, result: CollisionResult) -> None:
        """Kill a UFO and emit its explosion event + particles.

        Helper shared by the three destruction sites: player bullet,
        asteroid contact, and shield.
        """
        pos = Vec(ufo.pos)
        ufo.kill()
        result.events.append("ship_explosion")
        result.particles_to_spawn.append((pos, "ufo"))

    def _ufo_vs_player_bullets(
        self,
        ufos: list[UFO],
        bullets: list[Bullet],
        result: CollisionResult,
    ) -> None:
        for ufo in ufos:
            if not ufo.alive:
                continue
            for bullet in bullets:
                if not bullet.alive or bullet.owner_id <= 0:
                    continue
                if (ufo.pos - bullet.pos).length() < (ufo.r + bullet.r):
                    score = (
                        C.UFO_SMALL["score"]
                        if ufo.small
                        else C.UFO_BIG["score"]
                    )
                    result.score_deltas[bullet.owner_id] = (
                        result.score_deltas.get(bullet.owner_id, 0) + score
                    )
                    bullet.kill()
                    self._destroy_ufo(ufo, result)
                    break

    def _ufo_vs_asteroids(
        self,
        ufos: list[UFO],
        asteroids: list[Asteroid],
        result: CollisionResult,
    ) -> None:
        """UFO hits asteroid: UFO dies, asteroid splits without score."""
        for ufo in ufos:
            if not ufo.alive:
                continue
            for ast in asteroids:
                if not ast.alive:
                    continue
                if (ufo.pos - ast.pos).length() < (ufo.r + ast.r):
                    self._destroy_ufo(ufo, result)
                    self._split_asteroid(ast, result=result)
                    break

    def _ship_vs_asteroids(
        self,
        ships: dict[PlayerId, Ship],
        asteroids: list[Asteroid],
        result: CollisionResult,
    ) -> None:
        for ship in ships.values():
            if ship.invuln.active:
                continue
            for ast in asteroids:
                if not ast.alive:
                    continue
                if (ast.pos - ship.pos).length() < (ast.r + ship.current_r):
                    if ship.shield.active:
                        # Shield deflects: asteroid splits, no score,
                        # ship survives.
                        self._split_asteroid(ast, result=result)
                        continue
                    result.ship_deaths.append(ship.player_id)
                    return

    def _ship_vs_ufos(
        self,
        ships: dict[PlayerId, Ship],
        ufos: list[UFO],
        result: CollisionResult,
    ) -> None:
        """Active shield destroys any UFO that touches the ship. No score."""
        for ship in ships.values():
            if not ship.shield.active:
                continue
            for ufo in ufos:
                if not ufo.alive:
                    continue
                if (ufo.pos - ship.pos).length() < (ufo.r + ship.current_r):
                    self._destroy_ufo(ufo, result)

    def _ship_vs_ufo_bullets(
        self,
        ships: dict[PlayerId, Ship],
        bullets: list[Bullet],
        result: CollisionResult,
    ) -> None:
        for ship in ships.values():
            if ship.invuln.active:
                continue
            for bullet in bullets:
                if not bullet.alive or bullet.owner_id != UFO_BULLET_OWNER:
                    continue
                if (bullet.pos - ship.pos).length() < (bullet.r + ship.current_r):
                    bullet.kill()
                    if ship.shield.active:
                        continue
                    result.ship_deaths.append(ship.player_id)
                    return

    def _bullets_vs_ships(
        self,
        ships: dict[PlayerId, Ship],
        bullets: list[Bullet],
        result: CollisionResult,
    ) -> None:
        """Player bullet hits another player's ship (deathmatch frag).

        Skips UFO bullets (handled in _ship_vs_ufo_bullets) and the shooter's
        own ship (no auto-kill — the bullet passes through harmlessly).
        """
        for ship in ships.values():
            if ship.invuln.active:
                continue
            for bullet in bullets:
                if not bullet.alive or bullet.owner_id <= 0:
                    continue
                if bullet.owner_id == ship.player_id:
                    continue
                if (bullet.pos - ship.pos).length() < (bullet.r + ship.current_r):
                    bullet.kill()
                    if ship.shield.active:
                        continue
                    result.score_deltas[bullet.owner_id] = (
                        result.score_deltas.get(bullet.owner_id, 0)
                        + C.FRAG_SCORE
                    )
                    result.frag_deltas[bullet.owner_id] = (
                        result.frag_deltas.get(bullet.owner_id, 0) + 1
                    )
                    result.ship_deaths.append(ship.player_id)
                    break

    def _ship_vs_powerups(
        self,
        ships: dict[PlayerId, Ship],
        powerups: list[LaserPowerup],
        result: CollisionResult,
    ) -> None:
        """Ship overlaps laser powerup: powerup is collected."""
        for powerup in powerups:
            if not powerup.alive:
                continue
            for ship in ships.values():
                if (ship.pos - powerup.pos).length() < (ship.current_r + powerup.r):
                    powerup.kill()
                    result.powerup_pickups.append(
                        (ship.player_id, Vec(powerup.pos))
                    )
                    break

    def _ship_vs_freeze_powerups(
        self,
        ships: dict[PlayerId, Ship],
        freeze_powerups: list[FreezePowerup],
        result: CollisionResult,
    ) -> None:
        """Ship overlaps freeze powerup: powerup is collected and freeze effect queued."""
        for powerup in freeze_powerups:
            if not powerup.alive:
                continue
            for ship in ships.values():
                if (ship.pos - powerup.pos).length() < (powerup.width + ship.r):
                    powerup.kill()
                    result.events.append("powerup_acquired")
                    result.powerups_to_apply.append("freeze")
                    break

    def _laser_vs_asteroids(
        self,
        lasers: list[LaserBeam],
        asteroids: list[Asteroid],
        result: CollisionResult,
    ) -> None:
        """Laser beam hits all asteroids along its path."""
        for laser in lasers:
            if not laser.alive or laser.resolved:
                continue
            for ast in asteroids:
                if not ast.alive:
                    continue
                if _segment_circle_hit(laser.pos, laser.end_pos, ast.pos, ast.r):
                    self._split_asteroid(ast, scorer_id=laser.owner_id, result=result, asteroids=asteroids)

    def _laser_vs_ufos(
        self,
        lasers: list[LaserBeam],
        ufos: list[UFO],
        result: CollisionResult,
    ) -> None:
        """Laser beam destroys all UFOs along its path."""
        for laser in lasers:
            if not laser.alive or laser.resolved:
                continue
            for ufo in ufos:
                if not ufo.alive:
                    continue
                if _segment_circle_hit(laser.pos, laser.end_pos, ufo.pos, float(ufo.r)):
                    score = (
                        C.UFO_SMALL["score"] if ufo.small else C.UFO_BIG["score"]
                    )
                    result.score_deltas[laser.owner_id] = (
                        result.score_deltas.get(laser.owner_id, 0) + score
                    )
                    self._destroy_ufo(ufo, result)

    def _laser_vs_ships(
        self,
        lasers: list[LaserBeam],
        ships: dict[PlayerId, Ship],
        result: CollisionResult,
    ) -> None:
        """Laser beam kills enemy ships it crosses (deathmatch frag)."""
        for laser in lasers:
            if not laser.alive or laser.resolved:
                continue
            for ship in ships.values():
                if ship.player_id == laser.owner_id:
                    continue
                if ship.invuln.active or ship.shield.active:
                    continue
                if _segment_circle_hit(laser.pos, laser.end_pos, ship.pos, float(ship.current_r)):
                    result.score_deltas[laser.owner_id] = (
                        result.score_deltas.get(laser.owner_id, 0) + C.FRAG_SCORE
                    )
                    result.frag_deltas[laser.owner_id] = (
                        result.frag_deltas.get(laser.owner_id, 0) + 1
                    )
                    result.ship_deaths.append(ship.player_id)

    def _ship_vs_giant_shot_powerups(
        self,
        ships: dict[PlayerId, Ship],
        powerups: list[GiantShotPowerup],
        result: CollisionResult,
    ) -> None:
        for powerup in powerups:
            if not powerup.alive:
                continue

            for ship in ships.values():
                if (ship.pos - powerup.pos).length() < (ship.r + powerup.r):
                    powerup.kill()
                    result.giant_shot_pickups.append(
                        (ship.player_id, Vec(powerup.pos))
                    )
                    break

                
    def _giant_bullet_vs_ships(
        self,
        ships: dict[PlayerId, Ship],
        giant_bullets: list[GiantBullet],
        result: CollisionResult,
    ) -> None:
        """GiantBullet hits an enemy ship: apply giant debuff, do NOT kill.

        The bullet is destroyed on impact. The victim receives the giant
        debuff (enlarged hitbox + slowed speed) for GIANT_SHOT_DURATION
        seconds. The shooter's own ship is always skipped.
        Invulnerable ships and ships with an active shield are immune.
        """
        from core import config as C  # avoid top-level circular dependency

        for gb in giant_bullets:
            if not gb.alive:
                continue
            for ship in ships.values():
                if ship.player_id == gb.owner_id:
                    continue
                if ship.invuln.active or ship.shield.active:
                    continue
                if (ship.pos - gb.pos).length() < (ship.current_r + gb.r):
                    gb.kill()
                    ship.giant.reset(C.GIANT_SHOT_DURATION)
                    ship.vel = ship.vel * C.GIANT_SHOT_SPEED_MULT
                    result.giant_shot_hits.append((gb.owner_id, ship.player_id))
                    result.events.append("giant_shot_hit")
                    break

    def resolve_shrapnel(
        self,
        shrapnel: list[Shrapnel],
        asteroids: list[Asteroid],
        ships: dict[PlayerId, Ship],
        result: CollisionResult,
    ) -> None:
        """Resolve shrapnel fragments against asteroids and ships.

        Each fragment that hits an asteroid splits it (no score).
        Each fragment that hits a ship kills the ship (respects shield/invuln).
        Fragments are consumed on first hit.
        """
        for frag in shrapnel:
            if not frag.alive:
                continue
            for ast in asteroids:
                if not ast.alive:
                    continue
                if (ast.pos - frag.pos).length() < ast.r + frag.r:
                    frag.kill()
                    self._split_asteroid(ast, result=result, asteroids=asteroids)
                    break
            if not frag.alive:
                continue
            for ship in ships.values():
                if ship.invuln.active:
                    continue
                if (ship.pos - frag.pos).length() < ship.r + frag.r:
                    frag.kill()
                    if not ship.shield.active:
                        result.ship_deaths.append(ship.player_id)
                    break

    def _split_asteroid(
        self,
        ast: Asteroid,
        result: CollisionResult,
        scorer_id: PlayerId | None = None,
        asteroids: list[Asteroid] | None = None,
        ships: dict[PlayerId, Ship] | None = None,
    ) -> None:
        """Split or destroy an asteroid.

        scorer_id=None means no score is awarded (e.g. UFO-asteroid collision).
        asteroids/ships are passed to enable red asteroid area-of-effect logic.
        """
        if scorer_id is not None:
            result.score_deltas[scorer_id] = (
                result.score_deltas.get(scorer_id, 0)
                + C.AST_SIZES[ast.size]["score"]
            )

        split = C.AST_SIZES[ast.size]["split"]
        pos = Vec(ast.pos)
        ast.kill()

        if ast.red:
            result.events.append("red_explosion")
            result.particles_to_spawn.append((pos, "asteroid"))
            for _ in range(C.SHRAPNEL_COUNT):
                dirv = rand_unit_vec()
                speed = uniform(C.SHRAPNEL_SPEED_MIN, C.SHRAPNEL_SPEED_MAX)
                result.shrapnel_to_spawn.append((pos, dirv * speed))
            if ships is not None:
                for ship in ships.values():
                    if ship.invuln.active:
                        continue
                    if (ship.pos - pos).length() < C.RED_EXPLOSION_RADIUS:
                        if ship.shield.active:
                            continue
                        result.ship_deaths.append(ship.player_id)
            if asteroids is not None:
                for other in list(asteroids):
                    if not other.alive or other is ast:
                        continue
                    if (other.pos - pos).length() < C.RED_EXPLOSION_RADIUS:
                        if scorer_id is not None:
                            result.score_deltas[scorer_id] = (
                                result.score_deltas.get(scorer_id, 0)
                                + C.AST_SIZES[other.size]["score"]
                            )
                        self._split_asteroid(
                            other,
                            result=result,
                            scorer_id=scorer_id,
                            asteroids=asteroids,
                            ships=ships,
                        )
            return

        result.events.append("asteroid_explosion")
        result.particles_to_spawn.append((pos, "asteroid"))

        for new_size in split:
            dirv = rand_unit_vec()
            speed = (
                uniform(C.AST_VEL_MIN, C.AST_VEL_MAX) * C.AST_SPLIT_SPEED_MULT
            )
            result.asteroids_to_spawn.append((pos, dirv * speed, new_size))

        if _random() < C.FREEZE_POWERUP_DROP_CHANCE_ASTEROID:
            result.freeze_powerups_to_spawn.append(pos)
