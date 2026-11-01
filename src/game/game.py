"""Bucle principal y escenas del juego. Orquesta juego, visión, controles y hardware
sin que las clases de combate conozcan a ninguno de ellos."""
from __future__ import annotations

import logging
import random
import time
from enum import Enum
from pathlib import Path

import pygame

from src.controls.input_manager import InputManager
from src.controls.movement_controller import MovementController
from src.game.ai import EnemyAI
from src.game.arena import Arena
from src.game.character import Move, build_character
from src.game.combat import CombatSystem, Match
from src.game.enemy import Enemy, apply_intent
from src.game.player import Player
from src.hardware import create_hardware
from src.hardware.hardware_simulator import SimulatedHardware
from src.hardware.led_controller import LedController
from src.hardware.ultrasonic_sensor import UltrasonicSensor
from src.ui import menus, theme
from src.ui.camera_panel import CameraPanel
from src.ui.effects import Effects
from src.ui.fighter_renderer import draw_fighter
from src.ui.hud import HUD
from src.ui.sound import SoundBank
from src.vision.vision_service import CameraStatus, VisionSnapshot

log = logging.getLogger(__name__)


class Scene(Enum):
    SPLASH = 0
    TITLE = 1
    SELECT = 2
    FIGHT = 3
    PAUSE = 4
    RESULT = 5


class Game:
    def __init__(self, game_cfg: dict, gesture_cfg: dict, hw_cfg: dict, use_camera: bool = True,
                 demo: bool = False, difficulty: str | None = None):
        self.cfg = game_cfg
        pygame.init()
        win = game_cfg["window"]
        self.w, self.h = win["width"], win["height"]
        self.screen = pygame.display.set_mode((self.w, self.h))
        pygame.display.set_caption(win.get("title", "Gesture Fighter"))
        self.clock = pygame.time.Clock()
        self.fps_target = win.get("fps", 60)

        a = game_cfg["arena"]
        self.arena = Arena(self.w, self.h, a["left"], a["right"], a["floor_y"])
        self.background = self.arena.render_background()
        self.combat = CombatSystem(a["left"], a["right"], a["min_separation"])
        self.moves = {k: Move.from_dict(k, v) for k, v in game_cfg["moves"].items()}
        self.roster = game_cfg["roster"]
        self.previews = menus.make_previews(self.roster, self.moves)
        self.difficulties = [(k, v["label"]) for k, v in game_cfg["difficulties"].items()]
        keys = [k for k, _ in self.difficulties]
        self.diff_idx = keys.index(difficulty or game_cfg.get("default_difficulty", keys[0]))
        self.sel = 0

        # hardware (simulado o Arduino) — el juego solo usa la interfaz
        self.hw_cfg = hw_cfg
        self.hardware = create_hardware(hw_cfg)
        self.hardware.connect()
        self.sim = isinstance(self.hardware, SimulatedHardware)
        self.sensor = UltrasonicSensor(hw_cfg["ultrasonic"])
        self.sensor_cm: float | None = None
        self.leds = LedController(hw_cfg["leds"])
        self.led_frame = None
        self.movement = MovementController(game_cfg["movement"], hw_cfg["ultrasonic"], a["left"], a["right"])

        # visión (hilo aparte; si falla, el juego sigue con teclado)
        self.vision = None
        vcfg = game_cfg["vision"]
        if use_camera and vcfg.get("enabled", True):
            try:
                from src.vision.gesture_manager import GestureManager
                from src.vision.vision_service import VisionService
                self.vision = VisionService(vcfg, GestureManager.from_config(gesture_cfg))
                self.vision.start()
            except Exception:
                log.exception("Visión desactivada por un error de configuración")
                self.vision = None
        self.input = InputManager(game_cfg["keyboard"], self.vision)

        self.hud = HUD(self.w, self.h)
        self.effects = Effects()
        audio = game_cfg.get("audio", {})
        self.sounds = SoundBank(audio.get("enabled", True), audio.get("volume", 0.5))
        self.camera_panel = CameraPanel(pygame.Rect(self.w - 302, 104, 288, 216),
                                        vcfg.get("panel_visible", True) and self.vision is not None)

        self.logo = self._load_logo()
        self.splash_t = 0.0
        self.scene = Scene.SPLASH if self.logo else Scene.TITLE
        self.t = 0.0
        self.demo = demo
        self.player: Player | None = None
        self.enemy: Enemy | None = None
        self.player_ai: EnemyAI | None = None
        self._profiles = None
        self._dragging = False
        self.running = True

    SPLASH_TIME, SPLASH_FADE = 2.0, 0.6

    def _load_logo(self) -> pygame.Surface | None:
        path = Path(__file__).resolve().parents[2] / "assets" / "logo" / "netsu_games.png"
        try:
            img = pygame.image.load(str(path)).convert_alpha()
        except (pygame.error, FileNotFoundError):
            log.warning("Logo no encontrado (%s); se omite la intro", path)
            return None
        w = int(self.w * 0.55)
        return pygame.transform.smoothscale(img, (w, int(img.get_height() * w / img.get_width())))

    def _draw_splash(self) -> None:
        t, fade = self.splash_t, self.SPLASH_FADE
        k = min(1.0, t / fade, (self.SPLASH_TIME - t) / fade)  # entra, se mantiene y sale desvaneciéndose
        self.screen.fill((0, 0, 0))
        self.logo.set_alpha(int(255 * max(0.0, k)))
        self.screen.blit(self.logo, self.logo.get_rect(center=(self.w // 2, self.h // 2)))

    # --- combate --------------------------------------------------------------
    def start_fight(self, rematch: bool = False) -> None:
        if not rematch or self._profiles is None:
            prof = self.roster[self.sel]
            self._profiles = (prof, random.choice([p for p in self.roster if p is not prof]))
        pprof, eprof = self._profiles
        a, combat_cfg = self.cfg["arena"], self.cfg["combat"]
        dparams = self.cfg["difficulties"][self.difficulties[self.diff_idx][0]]
        left, right = a["left"], a["right"]
        self.player = build_character(Player, pprof, self.moves, combat_cfg, a["player_start"], 1)
        self.enemy = build_character(Enemy, eprof, self.moves, combat_cfg, a["enemy_start"], -1,
                                     ai=EnemyAI(dparams, arena_left=left, arena_right=right),
                                     damage_mult=dparams.get("damage_mult", 1.0))
        self.player_ai = EnemyAI(self.cfg["difficulties"]["normal"], arena_left=left, arena_right=right)
        self.match = Match(self.cfg["match"]["round_time"])
        self.countdown = self.cfg["match"]["countdown"]
        self.ko_timer: float | None = None
        self.hitstop = 0.0
        self.elapsed = 0.0
        self.banner = ""
        self.hud.reset()
        self.effects.clear()
        self.movement.reset()
        if self.sim:  # el sensor simulado arranca donde está el jugador
            us = self.hw_cfg["ultrasonic"]
            k = (a["player_start"] - left) / (right - left)
            k = 1 - k if us.get("invert") else k
            self.hardware.set_distance(us["min_cm"] + k * (us["max_cm"] - us["min_cm"]))
        self.scene = Scene.FIGHT

    def _update_fight(self, dt, triggers, holds, axis, snap: VisionSnapshot) -> None:
        p, e = self.player, self.enemy
        if self.countdown > -0.6:
            prev = self.countdown
            self.countdown -= dt
            if prev > 0 >= self.countdown:
                self.sounds.play("fight")
        if self.hitstop > 0:
            self.hitstop -= dt
            return
        fighting = self.countdown <= 0 and self.match.result is None

        walk_axis = axis
        if self.movement.source == "ultrasonic" and self.sim:
            if axis:
                self.hardware.adjust(axis * self.cfg["movement"].get("keyboard_sim_speed_cm", 30) * dt)
            walk_axis = 0.0
        hand_x = snap.hand_x if snap.status == CameraStatus.ACTIVE else None
        target = self.movement.update(dt, self.sensor_cm, hand_x)

        attacks_before = p.attacks_started + e.attacks_started
        if fighting:
            if self.demo:
                apply_intent(p, self.player_ai.update(dt, p, e), dt)
            else:
                p.apply_input(triggers, holds, target, walk_axis, dt)
            e.think(dt, p)
        if p.attacks_started + e.attacks_started > attacks_before:
            self.sounds.play("whoosh")
        for c in (p, e):
            c.update(dt)
        self.combat.constrain(p, e)

        fy = self.arena.floor_y
        for ev in self.combat.resolve(p, e):
            if ev.kind == "hit":
                self.effects.impact(ev.x, fy - 150, ev.heavy)
                self.effects.popup(ev.defender.x, fy - 250, f"-{ev.damage:.0f}", theme.ACCENT)
                self.sounds.play("hit")
                self.hitstop = self.cfg["match"]["hitstop"] * (2 if ev.heavy else 1)
            elif ev.kind == "block":
                self.effects.block(ev.x, fy - 170)
                self.effects.popup(ev.defender.x, fy - 250, "BLOQUEO", (140, 210, 255), 22)
                self.sounds.play("block")
            elif ev.kind == "ko":
                self.effects.ko()
                self.sounds.play("ko")
                self.hitstop = 0.3

        if fighting:
            self.elapsed += dt
            result = self.match.update(dt, p, e)
            if result:
                self.ko_timer = self.cfg["match"]["ko_delay"]
                self.banner = "K.O." if not (p.alive and e.alive) else "¡TIEMPO!"
                if result == "player":
                    p.win()
                elif result == "enemy":
                    e.win()
        if self.ko_timer is not None:
            self.ko_timer -= dt
            if self.ko_timer <= 0:
                self.scene = Scene.RESULT
        self.hud.update(p, e, dt)

    # --- eventos ------------------------------------------------------------------
    def _on_key(self, key) -> None:
        s = self.scene
        if s == Scene.SPLASH:
            self.scene = Scene.TITLE  # cualquier tecla salta la intro
        elif s == Scene.TITLE:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.sounds.play("select")
                self.scene = Scene.SELECT
            elif key == pygame.K_ESCAPE:
                self.running = False
        elif s == Scene.SELECT:
            if key in (pygame.K_LEFT, pygame.K_a):
                self.sel = (self.sel - 1) % len(self.roster)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.sel = (self.sel + 1) % len(self.roster)
            elif key in (pygame.K_UP, pygame.K_w):
                self.diff_idx = (self.diff_idx - 1) % len(self.difficulties)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.diff_idx = (self.diff_idx + 1) % len(self.difficulties)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start_fight()
                return
            elif key == pygame.K_ESCAPE:
                self.scene = Scene.TITLE
            self.sounds.play("select")
        elif s == Scene.FIGHT:
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.scene = Scene.PAUSE
        elif s == Scene.PAUSE:
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.scene = Scene.FIGHT
            elif key == pygame.K_r:
                self.start_fight(rematch=True)
            elif key == pygame.K_q:
                self.scene = Scene.SELECT
        elif s == Scene.RESULT:
            if key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start_fight(rematch=True)
            elif key == pygame.K_q:
                self.scene = Scene.SELECT
            elif key == pygame.K_ESCAPE:
                self.running = False
        if s in (Scene.FIGHT, Scene.PAUSE):
            if key == pygame.K_c:
                self.camera_panel.visible = not self.camera_panel.visible
            elif key == pygame.K_m:
                log.info("Fuente de movimiento: %s", self.movement.cycle_source())
            elif key == pygame.K_F2:
                self.demo = not self.demo

    def _on_mouse(self, ev) -> None:
        if not (self.sim and self.scene == Scene.FIGHT and self.movement.source == "ultrasonic"):
            return
        sl = self.hud.slider
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and sl.inflate(20, 30).collidepoint(ev.pos):
            self._dragging = True
        elif ev.type == pygame.MOUSEBUTTONUP:
            self._dragging = False
        if self._dragging and ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
            us = self.hw_cfg["ultrasonic"]
            k = min(1.0, max(0.0, (ev.pos[0] - sl.x) / sl.w))
            self.hardware.set_distance(us["min_cm"] + k * (us["max_cm"] - us["min_cm"]))

    # --- dibujo -------------------------------------------------------------------
    def _draw(self, snap: VisionSnapshot, fps: float) -> None:
        scr = self.screen
        if self.scene == Scene.SPLASH:
            self._draw_splash()
            pygame.display.flip()
            return
        off = self.effects.offset()
        scr.fill(theme.BG)
        scr.blit(self.background, off)
        if self.scene == Scene.TITLE:
            menus.draw_title(scr, self.t, snap.status.value, self.hardware.describe())
        elif self.scene == Scene.SELECT:
            menus.draw_select(scr, self.roster, self.previews, self.sel, self.difficulties, self.diff_idx, self.t)
        else:
            p, e = self.player, self.enemy
            fy = self.arena.floor_y
            order = sorted((p, e), key=lambda c: c.state.value == "attack")  # quien ataca, delante
            for c in order:
                draw_fighter(scr, c, fy, self.t, off, "P1" if c is p else "CPU", theme.P1 if c is p else theme.CPU)
                if c.is_blocking:
                    shield = pygame.Surface((90, 160), pygame.SRCALPHA)
                    pygame.draw.ellipse(shield, (120, 200, 255, 70), shield.get_rect())
                    pygame.draw.ellipse(shield, (170, 230, 255, 160), shield.get_rect(), 3)
                    scr.blit(shield, shield.get_rect(center=(c.x + c.facing * 45 + off[0], fy - 140 + off[1])))
            self.effects.draw(scr, off)
            self.hud.draw_top(scr, p, e, self.match.time_left, self.t)
            self.hud.draw_panel(scr, snap, self.hardware, self.led_frame, self.sensor_cm, self.movement, self.t, fps, self.sim)
            self.camera_panel.draw(scr, snap)
            if self.demo:
                theme.text(scr, "MODO DEMO (F2)", (self.w // 2, 92), 20, theme.WARN, "midtop")
            if self.countdown > 0:
                menus.draw_banner(scr, "ROUND 1", f"{p.name}  vs  {e.name}", theme.ACCENT, self.t)
            elif self.countdown > -0.6:
                menus.draw_banner(scr, "¡PELEA!", "", theme.BAD, self.t)
            elif self.ko_timer is not None and self.scene == Scene.FIGHT:
                menus.draw_banner(scr, self.banner, "", theme.BAD, self.t)
            if self.scene == Scene.PAUSE:
                menus.draw_pause(scr)
            elif self.scene == Scene.RESULT:
                menus.draw_result(scr, self.match.result, p, e, self.elapsed)
        pygame.display.flip()

    # --- bucle ---------------------------------------------------------------------
    def run(self, max_frames: int | None = None, auto: bool = False, screenshot_dir: str | None = None) -> None:
        """auto=True salta los menús y reinicia tras cada combate (pruebas/demostración)."""
        if auto:
            self.start_fight()
        frame = 0
        disabled = VisionSnapshot(status=CameraStatus.DISABLED)
        try:
            while self.running:
                dt = min(self.clock.tick(self.fps_target) / 1000.0, 1 / 30)
                self.t += dt
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        self.running = False
                    elif ev.type == pygame.KEYDOWN:
                        self._on_key(ev.key)
                    elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                        self._on_mouse(ev)
                    self.input.handle_event(ev)
                triggers, holds, axis = self.input.collect()
                snap = self.vision.snapshot() if self.vision else disabled
                if self.vision:
                    self.vision.want_debug_frame = self.camera_panel.visible and self.scene in (Scene.FIGHT, Scene.PAUSE)

                self.hardware.update(dt)
                self.sensor_cm = self.sensor.process(self.hardware.read_distance(), time.monotonic())
                if self.scene == Scene.SPLASH:
                    self.splash_t += dt
                    if self.splash_t >= self.SPLASH_TIME:
                        self.scene = Scene.TITLE
                elif self.scene == Scene.FIGHT:
                    self._update_fight(dt, triggers, holds, axis, snap)
                if auto and self.scene == Scene.RESULT:
                    self.start_fight(rematch=True)
                self.effects.update(dt)

                pp, ep = (self.player.health_pct, self.enemy.health_pct) if self.player else (1.0, 1.0)
                self.led_frame = self.leds.update(pp, ep, self.t)
                self.hardware.send_leds(self.led_frame)
                self.hardware.send_health(pp, ep)

                self._draw(snap, self.clock.get_fps())
                frame += 1
                if screenshot_dir and frame % 150 == 0:
                    Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
                    pygame.image.save(self.screen, str(Path(screenshot_dir) / f"frame_{frame:05d}.png"))
                if max_frames and frame >= max_frames:
                    break
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self.vision:
            self.vision.stop()
        self.hardware.disconnect()
        pygame.quit()
