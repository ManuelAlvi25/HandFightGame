"""Dibujo procedural de luchadores (sin sprites externos) a partir de su estado lógico."""
from __future__ import annotations

import math

import pygame

from src.game.character import Character, State

Vec = tuple[float, float]

# Pose base en coordenadas locales: x hacia donde mira, y hacia arriba, origen entre los pies.
GUARD = {
    "hip": (0, 95), "neck": (4, 165), "head": (8, 188),
    "f_el": (30, 138), "f_gl": (44, 160), "b_el": (8, 134), "b_gl": (24, 156),
    "f_knee": (16, 48), "f_foot": (24, 0), "b_knee": (-16, 48), "b_foot": (-26, 0),
}
BLOCK = {**GUARD, "hip": (0, 90), "neck": (2, 160), "head": (4, 182),
         "f_el": (22, 148), "f_gl": (30, 180), "b_el": (14, 142), "b_gl": (24, 172)}
HURT = {**GUARD, "neck": (-10, 160), "head": (-16, 180), "f_el": (12, 130), "f_gl": (20, 150),
        "b_el": (-12, 132), "b_gl": (0, 146)}
LYING = {"hip": (-30, 16), "neck": (-100, 22), "head": (-126, 24), "f_el": (-80, 44), "f_gl": (-60, 34),
         "b_el": (-112, 8), "b_gl": (-140, 10), "f_knee": (12, 26), "f_foot": (52, 8),
         "b_knee": (4, 14), "b_foot": (46, 4)}
VICTORY = {**GUARD, "b_el": (6, 205), "b_gl": (12, 245), "f_el": (30, 130), "f_gl": (36, 158)}


def _lerp(a: Vec, b: Vec, k: float) -> Vec:
    return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k


def _blend(pa: dict, pb: dict, k: float) -> dict:
    return {j: _lerp(pa[j], pb[j], k) for j in pa}


def _shift(p: dict, joints, dx=0.0, dy=0.0) -> dict:
    return {j: (v[0] + dx, v[1] + dy) if j in joints else v for j, v in p.items()}


UPPER = ("neck", "head", "f_el", "f_gl", "b_el", "b_gl")


def compute_pose(ch: Character, t: float) -> dict:
    st, tt = ch.state, ch.state_time
    bob = math.sin(t * 5 + ch.x * 0.01) * 3
    if st == State.ATTACK and ch.move:
        m = ch.move
        heavy = m.name == "heavy"
        arm_el, arm_gl = ("b_el", "b_gl") if heavy else ("f_el", "f_gl")
        ext = {**GUARD, arm_el: (62 if heavy else 52, 162), arm_gl: (112 if heavy else 96, 164),
               "neck": (14, 162), "head": (20, 184), "hip": (4, 94)}
        wind = {**GUARD, arm_el: (-6 if heavy else 18, 140), arm_gl: (-14 if heavy else 24, 156),
                "neck": (-4, 166), "head": (-2, 189)}
        if tt < m.startup:
            return _blend(GUARD, wind, tt / m.startup)
        if tt < m.startup + m.active:
            return _blend(wind, ext, min(1.0, (tt - m.startup) / (m.active * 0.5)))
        return _blend(ext, GUARD, min(1.0, (tt - m.startup - m.active) / m.recovery))
    if st == State.BLOCK:
        return _shift(BLOCK, UPPER, dy=bob * 0.4)
    if st == State.HIT:
        return HURT
    if st == State.KO:
        return _blend(HURT, LYING, min(1.0, tt / 0.45))
    if st == State.VICTORY:
        return _shift(VICTORY, UPPER + ("hip",), dy=abs(math.sin(t * 6)) * 8)
    pose = _shift(GUARD, UPPER, dy=bob)
    if st == State.WALK:
        s = math.sin(tt * 12)
        pose["f_foot"] = (24 + s * 14, max(0.0, math.cos(tt * 12)) * 8)
        pose["b_foot"] = (-26 - s * 14, max(0.0, -math.cos(tt * 12)) * 8)
        pose["f_knee"] = (16 + s * 8, 50)
        pose["b_knee"] = (-16 - s * 8, 50)
    return pose


def _dark(c, k=0.55):
    return tuple(int(v * k) for v in c)


def _light(c, add=45):
    return tuple(min(255, v + add) for v in c)


def height_scale(profile: dict) -> float:
    """Escala visual según la estatura (m). Exagerada x1.8 para que la diferencia se note en pantalla."""
    h = profile.get("height")
    return 1.0 + (h - 1.68) * 1.8 if h else 1.0


# Cabeza en coordenadas locales: u hacia donde mira, v hacia arriba, radio 19, ojo en (9, -1).
HAIR = {
    "spiky": [(-20, -6), (-22, 6), (-31, 10), (-21, 14), (-25, 27), (-12, 21), (-8, 35), (0, 22), (8, 33), (10, 20),
              (21, 27), (17, 14), (25, 11), (18, 6), (14, 10), (8, 6), (2, 10), (-4, 4), (-10, 7), (-14, -4)],
    "short": [(-20, -4), (-21, 8), (-16, 17), (-6, 22), (6, 22), (15, 17), (20, 8), (19, 4), (13, 8), (8, 5),
              (3, 9), (-3, 6), (-9, 9), (-14, 2), (-15, -4)],
    "spiky_small": [(-20, -4), (-21, 8), (-27, 14), (-17, 18), (-16, 27), (-6, 21), (0, 28), (5, 20), (14, 25),
                    (13, 15), (22, 14), (18, 6), (12, 9), (6, 6), (0, 10), (-6, 7), (-12, 10), (-15, 0)],
}
CURLS = [(-20, -5), (-19, 5), (-17, 14), (-10, 21), (0, 24), (10, 22), (17, 15), (20, 7), (-12, 11), (-3, 16), (7, 15)]


def draw_face(surface, face: dict, hx, hy, f, s, t, hair_col, flash: bool) -> None:
    def L(u, v):
        return hx + f * u * s, hy - v * s

    def W(px):
        return max(1, int(px * s))

    acc = face.get("accessories", [])
    ink = (25, 20, 20)
    # ojo y boca (las gafas de sol los tapan)
    if "sunglasses" not in acc:
        pygame.draw.circle(surface, ink, L(9, -1), W(3))
    pygame.draw.line(surface, _dark(ink, 1), L(11, -10), L(16, -9), W(2))

    if "beard" in acc:
        beard = [(-9, -3), (-8, -12), (-2, -18), (8, -19), (15, -15), (19, -8), (18, -4), (14, -7), (8, -6), (3, -9), (-3, -4)]
        pygame.draw.polygon(surface, hair_col, [L(*p) for p in beard])
        pygame.draw.polygon(surface, _dark(hair_col, 0.5), [L(*p) for p in beard], W(1))
        pygame.draw.line(surface, _light(hair_col, 70), L(10, -10), L(16, -9), W(2))  # boca entre la barba

    # pelo
    style = face.get("hair")
    outline = _dark(hair_col, 0.4) if not flash else (200, 200, 200)
    if style == "curly":
        for u, v in CURLS:
            pygame.draw.circle(surface, outline, L(u, v), W(9.5))
        for u, v in CURLS:
            pygame.draw.circle(surface, hair_col, L(u, v), W(8))
            pygame.draw.arc(surface, _light(hair_col, 50), pygame.Rect(*L(u - 4 * f, v + 4), W(8), W(8)), 0.3, 2.2, W(1.5))
    elif style in HAIR:
        pts = [L(*p) for p in HAIR[style]]
        pygame.draw.polygon(surface, hair_col, pts)
        pygame.draw.polygon(surface, outline, pts, W(2))
        hl = _light(hair_col, 55)  # mechones de brillo
        for a, b in (((-10, 14), (-2, 19)), ((2, 16), (9, 13)), ((-17, 6), (-12, 12))):
            pygame.draw.line(surface, hl, L(*a), L(*b), W(2))

    if "glasses" in acc:
        frame = (35, 35, 40)
        x0, y0 = L(5, 5)
        x1, y1 = L(17, -5)
        lens = pygame.Rect(min(x0, x1), y0, abs(x1 - x0), y1 - y0)
        pygame.draw.rect(surface, (215, 235, 250), lens, border_radius=W(3))
        pygame.draw.circle(surface, ink, L(10, -1), W(3))
        pygame.draw.rect(surface, frame, lens, W(2), border_radius=W(3))
        pygame.draw.line(surface, frame, L(5, 1), L(-12, 2), W(2))
        pygame.draw.line(surface, (255, 255, 255), L(13, 3), L(15, 1), W(1.5))
    if "sunglasses" in acc:
        shades = [(3, 5), (20, 5), (20, -2), (16, -5), (10, -4), (7, -1), (3, -1)]
        pygame.draw.polygon(surface, (15, 15, 20), [L(*p) for p in shades])
        pygame.draw.line(surface, (15, 15, 20), L(3, 2), L(-14, 3), W(2.5))
        pygame.draw.line(surface, (230, 230, 255), L(7, 3), L(11, 3), W(1.5))
        pygame.draw.line(surface, (230, 230, 255), L(13, 3), L(15, 1), W(1.5))
    if "cigarette" in acc:
        pygame.draw.line(surface, (245, 245, 240), L(15, -10), L(29, -12), W(3.5))
        pygame.draw.line(surface, (220, 150, 70), L(15, -10), L(19, -10.6), W(3.5))
        ember = (255, 120 + int(60 * math.sin(t * 12)), 30)
        pygame.draw.circle(surface, ember, L(29.5, -12), W(2.5))
        sw, sh = W(30), W(46)
        smoke = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for i in range(3):
            k = (t * 0.7 + i / 3) % 1.0
            pygame.draw.circle(smoke, (200, 200, 210, int(120 * (1 - k))),
                               (sw / 2 + math.sin(t * 3 + i) * 3 * s, sh - W(6) - k * 32 * s), W(2 + k * 4))
        bx, by = L(30, -12)
        surface.blit(smoke, (bx - sw / 2, by - sh))
    if "headphones" in acc:
        band_col, cup_col = (95, 95, 105), (130, 130, 145)
        arc = [L(-4, 6), L(-7, 15), L(-4, 22), L(3, 24), L(9, 21)]
        pygame.draw.lines(surface, (30, 30, 35), False, arc, W(7))
        pygame.draw.lines(surface, band_col, False, arc, W(4.5))
        cx, cy = L(-4, -1)
        cup = pygame.Rect(0, 0, W(13), W(19))
        cup.center = (cx, cy)
        pygame.draw.ellipse(surface, (30, 30, 35), cup.inflate(W(3), W(3)))
        pygame.draw.ellipse(surface, cup_col, cup)
        pygame.draw.ellipse(surface, _dark(cup_col, 0.6), cup.inflate(-W(6), -W(8)))


def draw_fighter(surface: pygame.Surface, ch: Character, floor_y: float, t: float, offset: Vec = (0, 0),
                 label: str = "", label_color=(255, 255, 255), scale: float = 1.0) -> None:
    scale *= height_scale(ch.profile)
    colors = ch.profile.get("colors", {})
    if ch.flash > 0:
        colors = {k: (255, 255, 255) for k in ("skin", "shirt", "pants", "gloves", "band", "hair")}
    skin = tuple(colors.get("skin", (230, 190, 150)))
    shirt = tuple(colors.get("shirt", (60, 120, 220)))
    pants = tuple(colors.get("pants", (30, 40, 80)))
    gloves = tuple(colors.get("gloves", (220, 40, 40)))
    band = tuple(colors.get("band", (255, 255, 255)))
    pose = compute_pose(ch, t)
    f = ch.facing
    ox, oy = ch.x + offset[0], floor_y + offset[1]

    def P(j):
        x, y = pose[j]
        return ox + f * x * scale, oy - y * scale

    def limb(a, b, w, col):
        w = max(2, int(w * scale))
        pygame.draw.line(surface, _dark(col, 0.35), a, b, w + 4)
        pygame.draw.circle(surface, _dark(col, 0.35), a, (w + 4) // 2)
        pygame.draw.circle(surface, _dark(col, 0.35), b, (w + 4) // 2)
        pygame.draw.line(surface, col, a, b, w)
        pygame.draw.circle(surface, col, a, w // 2)
        pygame.draw.circle(surface, col, b, w // 2)

    # sombra
    shadow = pygame.Surface((int(110 * scale), int(22 * scale)), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 110), shadow.get_rect())
    surface.blit(shadow, shadow.get_rect(center=(ox, oy + 2)))

    hip, neck = P("hip"), P("neck")
    shoulder_b = _lerp(neck, hip, 0.12)
    shoulder_f = (shoulder_b[0] + f * 8 * scale, shoulder_b[1])
    # brazo trasero y pierna trasera
    limb(shoulder_b, P("b_el"), 13, _dark(skin, 0.85))
    limb(P("b_el"), P("b_gl"), 12, _dark(skin, 0.85))
    pygame.draw.circle(surface, _dark(gloves, 0.8), P("b_gl"), int(13 * scale))
    limb(hip, P("b_knee"), 18, _dark(pants, 0.85))
    limb(P("b_knee"), P("b_foot"), 15, _dark(pants, 0.85))
    # torso
    limb(hip, neck, 34, shirt)
    pygame.draw.circle(surface, pants, hip, int(19 * scale))
    # pierna delantera
    limb(hip, P("f_knee"), 18, pants)
    limb(P("f_knee"), P("f_foot"), 15, pants)
    foot = P("f_foot")
    pygame.draw.ellipse(surface, (30, 30, 30), pygame.Rect(foot[0] - 10 * scale, foot[1] - 6 * scale, 22 * scale, 10 * scale))
    # cabeza
    hx, hy = P("head")
    r = int(19 * scale)
    pygame.draw.circle(surface, _dark(skin, 0.35), (hx, hy), r + 2)
    pygame.draw.circle(surface, skin, (hx, hy), r)
    face = ch.profile.get("face")
    if face:
        draw_face(surface, face, hx, hy, f, scale, t, colors.get("hair", (30, 30, 40)), ch.flash > 0)
    else:  # luchador sin cara definida: cinta clásica
        pygame.draw.line(surface, band, (hx - r, hy - 6 * scale), (hx + r, hy - 6 * scale), max(2, int(6 * scale)))
        tail = (hx - f * (r + 12 * scale), hy - 2 * scale + math.sin(t * 9) * 3)
        pygame.draw.line(surface, band, (hx - f * r, hy - 6 * scale), tail, max(2, int(4 * scale)))
        pygame.draw.circle(surface, (20, 20, 20), (hx + f * 9 * scale, hy - 1 * scale), max(2, int(3 * scale)))
    # brazo delantero
    limb(shoulder_f, P("f_el"), 14, skin)
    limb(P("f_el"), P("f_gl"), 13, skin)
    g = P("f_gl")
    pygame.draw.circle(surface, _dark(gloves, 0.4), g, int(16 * scale))
    pygame.draw.circle(surface, gloves, g, int(14 * scale))
    pygame.draw.circle(surface, (255, 255, 255), (g[0] - 4 * scale, g[1] - 5 * scale), max(1, int(3 * scale)))

    if label and ch.state != State.KO:
        top = oy - 230 * scale
        pygame.draw.polygon(surface, label_color, [(ox - 8, top), (ox + 8, top), (ox, top + 10)])
        from src.ui.theme import text
        text(surface, label, (ox, top - 2), 18, label_color, anchor="midbottom")
