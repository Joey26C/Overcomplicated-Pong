#!/usr/bin/env python3
"""
OVERCOMPLICATED PONG
====================
Pong, but nobody asked for this much.

Version history
  2.2  POWER SURGE: new rare chaos event that rolls a random 1.1x-3x multiplier and stretches every
       power-up (running ones and any collected during the event).
  2.1  THE CHAOS UPDATE: ball speed menu (px/s), adjustable chaos / power-up frequency and
       max power-ups on the board, ROAMING PADDLES chaos event, rare OVERTIME power-up,
       new IMPOSSIBLE bot + reaction times for every AI, flashing timers with tenths,
       power-up timers freeze between points, smoother paddle-corner hits, random splash texts.
  2.0  THE POWER-UP UPGRADE: rarity tiers (common -> mythic) with a rarity checklist in
       the menu, drawn icons, dud power-ups, new REAL GRAVITY power-up, fire trail on
       smashes, dash/charge on-off setting, AIs never concede an untouched ball,
       no ball curving unless it is AI-vs-AI, and lots of smaller fixes.
  1.1  Ball curving/anti-loop tweaks now only apply to AI-vs-AI matches.
       New ASSISTANT power-up (a yellow mini AI helps you for 5 seconds).
  1.0  Everything up to this point.

    pip install pygame
    python overcomplicated_pong.py

Features (a partial list, because the list itself got out of hand):
  * 11 control schemes per player: WASD, ARROWS, IJKL, MOUSE, GAMEPAD,
    two slippery INERTIA modes, LANES (teleport between 5 lanes) and 3 AI levels
  * Dash, and a charge-then-release SMASH on every control scheme that has buttons
  * Rally speed-up, speed cap, and a little ball curve in AI-vs-AI so they can't loop forever
  * 13 power-ups in rarity tiers, 7 chaos events, gravity wells, moving bumpers, portals
  * Particles, trails, screen shake, procedurally generated sound effects
"""
import array
import math
import os
import random
import sys

try:
    import pygame
except ImportError:
    import importlib
    import subprocess
    print("pygame not found - installing it now (one-time)...")
    try:
        for pkg in ("pygame-ce", "pygame"):  # pygame-ce has wheels for newer Pythons
            if subprocess.call([sys.executable, "-m", "pip", "install", "--only-binary", ":all:", pkg]) == 0:
                break
        importlib.invalidate_caches()
        import pygame
    except Exception as exc:
        print("\nCould not install pygame automatically:", exc)
        print("Open a terminal and run:   python -m pip install pygame-ce")
        input("Press Enter to close...")
        sys.exit(1)
from pygame import Vector2 as V

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pong_debug.log")


def breadcrumb(msg):
    """Append a line to pong_debug.log so we can see how far startup got."""
    try:
        with open(LOG_PATH, "a") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


try:  # also records hard crashes (segfaults) that Python can't catch
    import faulthandler
    _fh = open(LOG_PATH, "a")
    faulthandler.enable(file=_fh)
except Exception:
    pass

VERSION = "2.2"
VERSION_NAME = "Power Surge"
W, H = 1100, 700
FPS = 60
COUNTDOWN = 3.0  # seconds of 3-2-1 before every serve
MAX_SPEED = 1700
# Ball speed is in px/s measured at 1080p (1920 wide); the game scales it to its own field.
SPEED_PRESETS = [("SNAIL", 60), ("TURTLE", 300), ("SLOW", 660), ("NORMAL", 910), ("FAST", 1190),
                 ("INSANE", 1570), ("LUDICROUS", 2400), ("PLAID", 3200), ("LIGHT SPEED", 4096)]
SPEED_MIN, SPEED_MAX = 60, 4096
OLD_SPEEDS = [380, 520, 680, 900]  # only used if an old-style speed index is passed in
FREQ_MIN, FREQ_MAX = 1, 2048       # seconds, for chaos / power-up frequency
NICE_SECONDS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 75, 90, 120, 150, 180, 240,
                300, 420, 600, 900, 1200, 1800, 2048]
IMPOSSIBLE_V = 16000.0  # how fast the impossible bot's paddle may move (px/s)
WIN_SCORES = [5, 7, 11, 15, 21]
# Presets only touch match settings, never the players' controls.
# score is an index into WIN_SCORES; speed is in px/s (at 1080p).
PRESETS = [
    ("CLASSIC", dict(score=2, powerups=False, chaos=False, obstacles=False, speed=910, abilities=False),
     "Plain old pong: no extras, no dash or charge, normal speed, first to 11"),
    ("POWER-UPS", dict(score=1, powerups=True, chaos=False, obstacles=False, speed=910, abilities=True),
     "Normal pong plus power-ups, first to 7"),
    ("OBSTACLE COURSE", dict(score=1, powerups=False, chaos=False, obstacles=True, speed=910, abilities=True),
     "Bumpers and portals, nothing else, first to 7"),
    ("EVERYTHING", dict(score=1, powerups=True, chaos=True, obstacles=True, speed=910, abilities=True),
     "Power-ups, chaos events and obstacles at normal speed, first to 7"),
    ("SPEED DEMON", dict(score=1, powerups=False, chaos=False, obstacles=False, speed=1570, abilities=True),
     "Plain pong at insane ball speed, first to 7"),
    ("CRAZY", dict(score=1, powerups=True, chaos=True, obstacles=True, speed=1570, abilities=True),
     "Everything on, insane ball speed, first to 7. Good luck."),
]

BG = (8, 10, 22)
C_LEFT = (80, 200, 255)
C_RIGHT = (255, 110, 170)
WHITE = (240, 244, 255)
YELLOW = (255, 220, 80)
GREY = (120, 130, 160)

K = pygame
SCHEMES = ["WASD", "ARROWS", "IJKL", "MOUSE", "GAMEPAD", "INERTIA-WS",
           "INERTIA-ARROWS", "LANES", "AI-EASY", "AI-HARD", "AI-NIGHTMARE", "AI-IMPOSSIBLE"]
# up, down, dash, charge
KEYMAP = {
    "WASD": (K.K_w, K.K_s, K.K_LSHIFT, K.K_SPACE),
    "ARROWS": (K.K_UP, K.K_DOWN, K.K_RSHIFT, K.K_RETURN),
    "IJKL": (K.K_i, K.K_k, K.K_u, K.K_o),
    "INERTIA-WS": (K.K_w, K.K_s, K.K_LSHIFT, K.K_SPACE),
    "INERTIA-ARROWS": (K.K_UP, K.K_DOWN, K.K_RSHIFT, K.K_RETURN),
}
LANE_KEYS = [
    [K.K_1, K.K_2, K.K_3, K.K_4, K.K_5],
    [K.K_6, K.K_7, K.K_8, K.K_9, K.K_0],
]
# left / right keys (used by the ROAMING PADDLES chaos event: they move you forward and back)
KEYMAP_X = {
    "WASD": (K.K_a, K.K_d),
    "ARROWS": (K.K_LEFT, K.K_RIGHT),
    "IJKL": (K.K_j, K.K_l),
    "INERTIA-WS": (K.K_a, K.K_d),
    "INERTIA-ARROWS": (K.K_LEFT, K.K_RIGHT),
}
LANES_X = [(K.K_a, K.K_d), (K.K_LEFT, K.K_RIGHT)]
XHINT = {"WASD": "A / D", "ARROWS": "LEFT / RIGHT", "IJKL": "J / L", "MOUSE": "MOUSE LEFT / RIGHT",
         "GAMEPAD": "STICK LEFT / RIGHT", "INERTIA-WS": "A / D", "INERTIA-ARROWS": "LEFT / RIGHT",
         "LANES-0": "A / D", "LANES-1": "LEFT / RIGHT"}
# speed: top paddle speed (px/s) | react: scales a human-ish 100-300 ms reaction time (0 = instant)
# aim: how far from centre of the paddle it likes to hit | err: aiming error (in half-paddles)
# wild: chance per decision of a big over/under-shoot | xspeed: forward/back speed when roaming
AI_LEVELS = {
    "AI-EASY": dict(speed=520, react=1.0, aim=0.5, err=0.35, wild=0.25, fancy=False, xspeed=350),
    "AI-HARD": dict(speed=760, react=0.7, aim=0.7, err=0.20, wild=0.0, fancy=True, xspeed=600),
    "AI-NIGHTMARE": dict(speed=900, react=0.3, aim=0.8, err=0.12, wild=0.0, fancy=True, xspeed=800),
    "AI-IMPOSSIBLE": dict(speed=IMPOSSIBLE_V, react=0.0, aim=0.0, err=0.0, wild=0.0, fancy=True, xspeed=5000),
}
HELP = {
    "WASD": "W/S move | LSHIFT dash | hold+release SPACE = SMASH",
    "ARROWS": "UP/DOWN move | RSHIFT dash | hold+release ENTER = SMASH",
    "IJKL": "I/K move | U dash | hold+release O = SMASH",
    "MOUSE": "Mouse moves | RIGHT CLICK dash | hold+release LEFT CLICK = SMASH",
    "GAMEPAD": "Left stick | B dash | hold+release A = SMASH",
    "INERTIA-WS": "W/S accelerate (slippery!) | LSHIFT dash | SPACE smash",
    "INERTIA-ARROWS": "UP/DOWN accelerate (slippery!) | RSHIFT dash | ENTER smash",
    "LANES-0": "Keys 1-5 teleport between 5 lanes (no dash, no smash)",
    "LANES-1": "Keys 6-0 teleport between 5 lanes (no dash, no smash)",
    "AI-EASY": "The computer. It is not very good.",
    "AI-HARD": "The computer. Dashes and smashes.",
    "AI-NIGHTMARE": "The computer. Very hard to beat. Is sorry.",
    "AI-IMPOSSIBLE": "The computer. It cannot be scored on. Really.",
}

# Rarity tiers: name, colour, natural spawn weight (%), glows?
# (the weights add up to 78.75 because MYTHIC has no power-ups yet; odds are scaled to 100%)
RARITIES = [
    ("COMMON", (150, 156, 172), 40.0, False),
    ("UNCOMMON", (90, 220, 110), 20.0, False),
    ("RARE", (80, 140, 255), 10.0, False),
    ("EPIC", (180, 100, 255), 5.0, False),
    ("LEGENDARY", (255, 225, 60), 2.5, True),
    ("MYTHIC", (255, 60, 160), 1.25, True),  # reserved for future power-ups
]
POWERUPS = {  # kind: (display name, rarity index)
    "BIG": ("BIG PADDLE", 0),
    "SHRINK": ("SHRINK RAY", 0),
    "SLOW": ("SLOW-MO", 0),
    "GHOST": ("GHOST BALL", 0),
    "MAGNET": ("MAGNET", 1),
    "WELL": ("GRAVITY WELL", 1),
    "SHIELD": ("GOAL SHIELD", 2),
    "TURBO": ("TURBO", 2),
    "MULTI": ("MULTIBALL", 2),
    "OVERTIME": ("OVERTIME", 2),
    "REVERSE": ("REVERSE CONTROLS", 3),
    "GRAVITY": ("REAL GRAVITY", 3),
    "ASSIST": ("ASSISTANT", 4),
}
TIERS = [[k for k, (_, r) in POWERUPS.items() if r == i] for i in range(len(RARITIES))]
DUD_CHANCE = 0.10
DUD_LINES = ["OBSOLETE!", "DUD!", "OUT OF STOCK!", "EXPIRED!", "BATTERIES NOT INCLUDED!",
             "WRONG BOX!", "RECALLED!", "NICE TRY!", "JUST A RUMOR", "UNDER CONSTRUCTION",
             "POWER NOT FOUND", "FREE TRIAL ENDED"]
GRAV = 1200.0       # REAL GRAVITY pull (px/s^2)
GRAV_REST = 0.88    # how bouncy the floor is under REAL GRAVITY (ping-pong-ish)
FIRE_COLS = [(255, 220, 90), (255, 160, 40), (255, 90, 20), (220, 40, 10)]
# name, length in seconds, weight (a lower weight = a rarer event)
CHAOS_EVENTS = [("GRAVITY SHIFT", 7.0, 1.0), ("WIND", 7.0, 1.0), ("CONTROL SWAP", 7.0, 1.0),
                ("TURBO", 7.0, 1.0), ("FOG", 7.0, 1.0), ("ROAMING PADDLES", 15.0, 1.0),
                ("POWER SURGE", 10.0, 0.15)]
EVENTS = [e[0] for e in CHAOS_EVENTS]

SPLASHES = [
    "done your homework?",
    "a game nobody asked to be this complicated",
    "error404: 2cool4u",
    "a game of chaos... and luck",
    "six sevennnn....",
    "huh? who said that",
    "edfvijhsu...",
    "1 sheep... 2 sheep... 3 sheep...",
    "this game was made by me! but... you don't know who me is...",
    "this message is very rare... like super duper rare",
    "insert text here",
    "hey dude!",
    "fun fact! this game is not affiliated in any way with the ukrainian mafia!",
    "you would not believe your eyes... if 9,999,999 fireflies...",
    "pog",
    "housekeeping!",
    "tell your cat i said pspsps...",
    "psst... i hid my stash of money in th-... dies",
    "pong time!",
    "why did the bicycle fall over? because it was two-tired... ha... ha...",
    "yeet",
    "this is a tribute to zachary ware and mason murphy, my two very good friends...",
]
RARE_SPLASH = "this message is very rare... like super duper rare"  # ~0.1% of the time
ITALIC_SPLASH = "insert text here"                                  # the only italic one
_fonts = {}
VIEW = {"scale": 1.0, "ox": 0.0, "oy": 0.0}  # how the 1100x700 game is placed in the real window


def mouse_x():
    """Mouse position along the field, in game coordinates."""
    return (pygame.mouse.get_pos()[0] - VIEW["ox"]) / VIEW["scale"]


DIGIT_KEYS = {getattr(pygame, f"K_{i}"): i for i in range(10)}
DIGIT_KEYS.update({getattr(pygame, f"K_KP{i}"): i for i in range(10)})


def digit_of(k):
    return DIGIT_KEYS.get(k)


def pick_splash():
    """Random splash text (even odds, except the rare one at ~0.1%) and whether it is italic."""
    others = len(SPLASHES) - 1
    rare_w = others * 0.001 / 0.999
    weights = [rare_w if t == RARE_SPLASH else 1.0 for t in SPLASHES]
    t = random.choices(SPLASHES, weights)[0]
    return t, t == ITALIC_SPLASH


def fmt_timer(t, now):
    """Timer text: whole seconds, then below 1s it shows tenths and flashes. Returns (text, visible)."""
    if t >= 1:
        return f"{int(t)}s", True
    tenths = max(0.1, math.floor(t * 10) / 10)
    return f"{tenths:.1f}s", int(now * 8) % 2 == 0


def mouse_y():
    """Mouse height in game coordinates, even when the window is resized or fullscreen."""
    return (pygame.mouse.get_pos()[1] - VIEW["oy"]) / VIEW["scale"]


def font(size, italic=False):
    f = _fonts.get((size, italic))
    if f is None:
        f = _fonts[(size, italic)] = pygame.font.Font(None, size)
        f.set_italic(italic)
    return f


def text(surf, msg, size, color, pos, anchor="center", italic=False):
    img = font(size, italic).render(msg, True, color)
    surf.blit(img, img.get_rect(**{anchor: pos}))


def lerp_col(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_glow = {}


def glow(radius, color):
    key = (radius, color)
    s = _glow.get(key)
    if s is None:
        s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for i in range(radius, 0, -2):
            a = int(110 * (1 - i / radius) ** 2)
            pygame.draw.circle(s, (*color, a), (radius, radius), i)
        _glow[key] = s
    return s


def fold(y):
    """Predict where a ball ends up after bouncing between the walls."""
    p = 2 * H
    y %= p
    return y if y <= H else p - y


def predict_y(b, t, game):
    """Where the ball will be (height) in t seconds, for the AI."""
    if game.grav_t <= 0:
        return fold(b.pos.y + b.vel.y * t)
    y, vy, r = b.pos.y, b.vel.y, b.r
    for _ in range(min(240, int(t * 60) + 1)):
        vy += GRAV / 60
        y += vy / 60
        if y > H - r:
            y, vy = H - r, -abs(vy) * GRAV_REST
            if abs(vy) < 80:
                vy = 0.0
        elif y < r:
            y, vy = r, abs(vy)
    return y


def rarity_odds(rar_on, keep):
    """% of spawns that belong to each rarity for the current checklist."""
    existing = [i for i in range(len(RARITIES)) if TIERS[i]]
    out = [0.0] * len(RARITIES)
    if keep:  # natural odds, scaled so the tiers that exist add up to 100%
        total = sum(RARITIES[i][2] for i in existing)
        for i in existing:
            if rar_on[i]:
                out[i] = 100.0 * RARITIES[i][2] / total
    else:  # spread evenly over the ticked rarities
        pick = [i for i in existing if rar_on[i]]
        for i in pick:
            out[i] = 100.0 / len(pick)
    return out


def roll_powerup(rar_on, keep):
    """Pick a power-up kind, or None when nothing should spawn this time."""
    existing = [i for i in range(len(RARITIES)) if TIERS[i]]
    allowed = [i for i in existing if rar_on[i]]
    if not allowed:
        return None
    if keep:  # normal odds; landing on an unticked rarity means nothing pops up
        tier = random.choices(existing, [RARITIES[i][2] for i in existing])[0]
        if not rar_on[tier]:
            return None
    else:
        tier = random.choice(allowed)
    return random.choice(TIERS[tier])


def player_label(scheme):
    return scheme if scheme.startswith("AI-") else "HUMAN"


def help_text(key, abilities=True):
    t = HELP[key]
    if abilities:
        return t
    if key.startswith("AI-"):
        return "The computer."
    return t.split(" | ")[0]


def draw_icon(s, kind, c, col):
    """Little vector icon for each power-up, roughly 24x24 px around centre c."""
    cx, cy = int(c[0]), int(c[1])

    def P(*pts):
        return [(cx + x, cy + y) for x, y in pts]

    dim = lerp_col(BG, col, 0.45)
    ink = (10, 12, 26)
    if kind == "BIG":  # tall paddle + arrows growing outwards
        pygame.draw.rect(s, col, (cx - 9, cy - 10, 6, 20), border_radius=2)
        pygame.draw.polygon(s, col, P((6, -10), (2, -4), (10, -4)))
        pygame.draw.polygon(s, col, P((6, 10), (2, 4), (10, 4)))
    elif kind == "SHRINK":  # short paddle + arrows squeezing inwards
        pygame.draw.rect(s, col, (cx - 9, cy - 5, 6, 10), border_radius=2)
        pygame.draw.polygon(s, col, P((6, -3), (2, -10), (10, -10)))
        pygame.draw.polygon(s, col, P((6, 3), (2, 10), (10, 10)))
    elif kind == "MULTI":  # three balls, each with a trail
        for y in (-8, 0, 8):
            pygame.draw.polygon(s, dim, P((-11, y), (3, y - 3), (3, y + 3)))
            pygame.draw.circle(s, col, (cx + 7, cy + y), 4)
    elif kind == "SLOW":  # hourglass
        pygame.draw.polygon(s, dim, P((-8, -10), (8, -10), (0, 0)))
        pygame.draw.polygon(s, dim, P((-8, 10), (8, 10), (0, 0)))
        pygame.draw.polygon(s, col, P((-4, 10), (4, 10), (0, 4)))
        pygame.draw.polygon(s, col, P((-8, -10), (8, -10), (0, 0)), 2)
        pygame.draw.polygon(s, col, P((-8, 10), (8, 10), (0, 0)), 2)
        pygame.draw.line(s, col, (cx - 10, cy - 10), (cx + 10, cy - 10), 2)
        pygame.draw.line(s, col, (cx - 10, cy + 10), (cx + 10, cy + 10), 2)
    elif kind == "SHIELD":
        pts = P((-9, -9), (9, -9), (9, 1), (0, 11), (-9, 1))
        pygame.draw.polygon(s, dim, pts)
        pygame.draw.polygon(s, col, pts, 2)
        pygame.draw.line(s, col, (cx, cy - 6), (cx, cy + 5), 2)
    elif kind == "REVERSE":  # one arrow up, one arrow down
        pygame.draw.line(s, col, (cx - 5, cy + 9), (cx - 5, cy - 4), 3)
        pygame.draw.polygon(s, col, P((-5, -11), (-10, -3), (0, -3)))
        pygame.draw.line(s, col, (cx + 5, cy - 9), (cx + 5, cy + 4), 3)
        pygame.draw.polygon(s, col, P((5, 11), (0, 3), (10, 3)))
    elif kind == "GHOST":
        pygame.draw.circle(s, col, (cx, cy - 3), 8)
        pygame.draw.polygon(s, col, P((-8, -3), (-8, 10), (-4, 6), (0, 10), (4, 6), (8, 10), (8, -3)))
        pygame.draw.circle(s, ink, (cx - 3, cy - 3), 2)
        pygame.draw.circle(s, ink, (cx + 3, cy - 3), 2)
    elif kind == "MAGNET":  # horseshoe magnet
        pygame.draw.arc(s, col, pygame.Rect(cx - 9, cy - 10, 18, 18), 0, math.pi, 4)
        pygame.draw.line(s, col, (cx - 8, cy - 2), (cx - 8, cy + 6), 4)
        pygame.draw.line(s, col, (cx + 8, cy - 2), (cx + 8, cy + 6), 4)
        pygame.draw.rect(s, (255, 90, 90), (cx - 11, cy + 7, 7, 4))
        pygame.draw.rect(s, WHITE, (cx + 4, cy + 7, 7, 4))
    elif kind == "WELL":  # swirl
        pygame.draw.arc(s, col, pygame.Rect(cx - 11, cy - 11, 22, 22), 0.4, 5.6, 2)
        pygame.draw.arc(s, col, pygame.Rect(cx - 7, cy - 7, 14, 14), 2.5, 7.7, 2)
        pygame.draw.circle(s, col, (cx, cy), 2)
    elif kind == "TURBO":  # lightning bolt
        pygame.draw.polygon(s, col, P((2, -11), (-7, 1), (-1, 1), (-3, 11), (7, -3), (1, -3)))
    elif kind == "ASSIST":  # a paddle with a smaller one in front of it
        pygame.draw.rect(s, col, (cx - 9, cy - 10, 6, 20), border_radius=2)
        pygame.draw.rect(s, lerp_col(col, WHITE, 0.6), (cx + 3, cy - 5, 4, 10), border_radius=2)
    elif kind == "OVERTIME":  # stopwatch with a plus
        pygame.draw.circle(s, col, (cx - 2, cy + 2), 9, 2)
        pygame.draw.line(s, col, (cx - 2, cy + 2), (cx - 2, cy - 3), 2)
        pygame.draw.line(s, col, (cx - 2, cy + 2), (cx + 2, cy + 4), 2)
        pygame.draw.rect(s, col, (cx - 4, cy - 12, 4, 3))
        pygame.draw.line(s, col, (cx + 7, cy - 10), (cx + 7, cy - 4), 2)
        pygame.draw.line(s, col, (cx + 4, cy - 7), (cx + 10, cy - 7), 2)
    elif kind == "GRAVITY":  # ball dropping onto the floor
        pygame.draw.circle(s, col, (cx, cy - 7), 4)
        pygame.draw.line(s, col, (cx, cy - 2), (cx, cy + 2), 2)
        pygame.draw.polygon(s, col, P((0, 7), (-5, 1), (5, 1)))
        pygame.draw.line(s, col, (cx - 10, cy + 10), (cx + 10, cy + 10), 2)


# --------------------------------------------------------------------------- sound
SOUNDS = {
    "hit": (520, 70, 0.35, 200), "wall": (260, 45, 0.25, 0),
    "score": (220, 450, 0.35, -150), "power": (500, 220, 0.3, 900),
    "smash": (120, 200, 0.45, 400), "dash": (900, 90, 0.2, -600),
    "portal": (700, 160, 0.25, -400), "bump": (380, 80, 0.3, 300),
    "event": (150, 500, 0.3, 100), "shield": (300, 120, 0.3, 500),
    "win": (440, 900, 0.35, 500), "menu": (600, 40, 0.2, 0), "tick": (700, 70, 0.25, 0), "dud": (180, 300, 0.3, -120), "go": (1000, 220, 0.3, 300),
}


class Sfx:
    def __init__(self):
        self.ok = False
        self.muted = False
        self.cache = {}
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self.ok = True
        except pygame.error:
            pass

    def play(self, name):
        if not self.ok or self.muted:
            return
        try:
            self._play(name)
        except Exception:
            self.ok = False  # broken audio setup: just go silent

    def _play(self, name):
        snd = self.cache.get(name)
        if snd is None:
            freq, ms, vol, slide = SOUNDS[name]
            n = int(44100 * ms / 1000)
            buf = array.array("h")
            for i in range(n):
                t = i / 44100
                env = (1 - i / n) ** 1.5
                f = freq + slide * t * (1000 / ms)
                buf.append(int(32767 * vol * env * math.sin(2 * math.pi * f * t)))
            snd = self.cache[name] = pygame.mixer.Sound(buffer=buf.tobytes())
        snd.play()


# --------------------------------------------------------------------------- input
class Input:
    __slots__ = ("move", "target", "speed", "inertia", "dash", "charge", "movex", "xtarget", "xspeed")

    def __init__(self):
        self.move = 0.0
        self.target = None
        self.speed = 640.0
        self.inertia = False
        self.dash = False
        self.charge = False
        self.movex = 0.0      # forward/back movement (only used by the ROAMING PADDLES event)
        self.xtarget = None
        self.xspeed = 560.0


class Controller:
    def __init__(self, scheme, side):
        self.scheme = scheme
        self.side = side
        self.lane = 2
        self.err = 0.0
        self.err_t = 0.0
        self.aim = 0.0      # where on the paddle the AI tries to hit (-1 top .. +1 bottom)
        self.cur = None     # id of the ball currently being tracked
        self.react_roll = random.uniform(0.10, 0.30)  # human-ish reaction time, 100-300 ms
        self.prev_btn = False
        self.joy = None
        if scheme == "GAMEPAD" and pygame.joystick.get_count():
            try:
                self.joy = pygame.joystick.Joystick(min(side, pygame.joystick.get_count() - 1))
                self.joy.init()
            except pygame.error:
                self.joy = None

    def read(self, paddle, game, keys):
        s = self.scheme
        inp = Input()
        if s in KEYMAP:
            up, dn, dash, chg = KEYMAP[s]
            inp.move = float(int(bool(keys[dn])) - int(bool(keys[up])))
            lk, rk = KEYMAP_X[s]
            inp.movex = float(int(bool(keys[rk])) - int(bool(keys[lk])))
            inp.dash = dash in game.keydowns
            inp.charge = bool(keys[chg])
            inp.inertia = s.startswith("INERTIA")
        elif s == "MOUSE":
            inp.target = mouse_y()
            inp.xtarget = mouse_x()
            inp.speed = 1100
            inp.charge = bool(pygame.mouse.get_pressed()[0])
            inp.dash = 3 in game.mousedowns
        elif s == "GAMEPAD":
            if self.joy:
                try:
                    ax = self.joy.get_axis(1)
                    inp.move = ax if abs(ax) > 0.15 else 0.0
                    ax = self.joy.get_axis(0)
                    inp.movex = ax if abs(ax) > 0.15 else 0.0
                    inp.charge = bool(self.joy.get_button(0))
                    b = bool(self.joy.get_button(1))
                    inp.dash = b and not self.prev_btn
                    self.prev_btn = b
                except pygame.error:
                    pass
        elif s == "LANES":
            for i, k in enumerate(LANE_KEYS[self.side]):
                if k in game.keydowns:
                    self.lane = i
            inp.target = H * (self.lane + 0.5) / 5
            inp.speed = 2000
            lk, rk = LANES_X[self.side]
            inp.movex = float(int(bool(keys[rk])) - int(bool(keys[lk])))
        else:
            self.ai(inp, paddle, game, AI_LEVELS[s])
        return inp

    def ai(self, inp, paddle, game, lv):
        h2 = paddle.h / 2
        # aiming error, re-rolled every so often; the "wild" ones are the big over/under-shoots
        self.err_t -= game.dt
        if self.err_t <= 0:
            self.err_t = random.uniform(0.25, 0.6)
            e = random.uniform(-1, 1) * lv["err"] * h2
            if random.random() < lv["wild"]:
                e = random.choice((-1, 1)) * random.uniform(0.8, 1.3) * h2
            self.err = e
        # a new approach (judged from the real ball): new reaction time, new spot on the paddle
        real, rt = None, 1e9
        for b in game.balls:
            if (b.vel.x < 0) == (paddle.side == 0) and b.vel.x != 0:
                t = abs(paddle.x - b.pos.x) / max(1.0, abs(b.vel.x))
                if t < rt:
                    rt, real = t, b
        rid = None if real is None else id(real)
        # what the bot can see is delayed by its reaction time (0 for the impossible bot)
        delay = self.react_roll * lv["react"]
        best, bt = None, 1e9
        for b in game.seen(delay):
            toward = b.vel.x < 0 if paddle.side == 0 else b.vel.x > 0
            if toward:
                t = abs(paddle.x - b.pos.x) / max(1.0, abs(b.vel.x))
                if t < bt:
                    bt, best = t, b
        if rid != self.cur:
            self.cur = rid
            self.react_roll = random.uniform(0.10, 0.30)
            if self.scheme == "AI-IMPOSSIBLE":  # aim away from wherever the opponent is standing
                opp = game.paddles[1 - paddle.side]
                self.aim = 0.9 if opp.y < H / 2 else -0.9
            else:
                self.aim = random.uniform(-lv["aim"], lv["aim"])
        if best is None:
            # nothing coming: drift very slowly back towards the middle
            inp.target = H / 2
            inp.speed = 70
        elif best.touched:
            inp.target = predict_y(best, bt, game) - self.aim * h2 + self.err
            inp.speed = lv["speed"]
        else:  # nobody has hit it yet: no aiming errors, never miss the serve
            inp.target = predict_y(best, bt, game) - self.aim * 0.4 * h2
            inp.speed = max(lv["speed"], 1500)
        if lv["fancy"] and best is not None:
            eta = max(0.0, bt - delay)  # how long until it really arrives
            if abs(inp.target - paddle.y) > 220 and paddle.dash_cd <= 0:
                inp.dash = True
            inp.charge = 0.15 < eta < 0.8
        if game.event == "ROAMING PADDLES":  # use the forward/back movement too
            inp.xspeed = lv["xspeed"]
            inp.xtarget = paddle.home_x if best is not None else paddle.home_x + paddle.d * 110


# --------------------------------------------------------------------------- entities
class Ball:
    def __init__(self, pos, vel):
        self.pos = V(pos)
        self.vel = V(vel)
        self.spin = 0.0
        self.r = 10
        self.trail = []
        self.last = None
        self.ghost = 0.0
        self.portal_cd = 0.0
        self.fire = False     # on fire after a charged smash, until it hits something
        self.touched = False  # has any paddle hit it yet?
        self.scale = 1.0      # multiball extras are a bit slower


class Snap:
    """A frozen copy of a ball, used so bots can react to what the ball looked like a moment ago."""
    __slots__ = ("bid", "pos", "vel", "r", "touched")

    def __init__(self, b):
        self.bid = id(b)
        self.pos = V(b.pos)
        self.vel = V(b.vel)
        self.r = b.r
        self.touched = b.touched


class Pickup:
    def __init__(self, kind, pos):
        self.kind = kind
        self.pos = V(pos)
        self.ttl = 12.0
        self.t = random.random() * 6


class Bumper:
    def __init__(self, x, amp, freq, phase):
        self.x, self.amp, self.freq, self.phase = x, amp, freq, phase
        self.r = 30
        self.pos = V(x, H / 2)


class Well:
    def __init__(self, pos):
        self.pos = V(pos)
        self.ttl = 8.0
        self.radius = 190


class Paddle:
    def __init__(self, side):
        self.side = side
        self.d = 1 if side == 0 else -1
        self.x = 44 if side == 0 else W - 44
        self.home_x = self.x
        self.vx = 0.0
        self.owner = None   # set for the assistant paddle: it follows its owner
        self.immune = False  # the impossible bot can't have its controls reversed
        self.xmin, self.xmax = (28, W / 2 - 60) if side == 0 else (W / 2 + 60, W - 28)
        self.y = H / 2
        self.vy = 0.0
        self.w = 16
        self.base_h = 110
        self.score = 0
        self.shield = 0
        self.timers = {"big": 0.0, "small": 0.0, "reverse": 0.0, "magnet": 0.0}
        self.dash_cd = 0.0
        self.dash_t = 0.0
        self.dash_dir = 1
        self.charge = 0.0
        self.charging = False
        self.smash = 0.0
        self.smash_t = 0.0
        self.flash = 0.0

    @property
    def h(self):
        h = self.base_h
        if self.timers["big"] > 0:
            h *= 1.55
        if self.timers["small"] > 0:
            h *= 0.6
        return h

    @property
    def color(self):
        return C_LEFT if self.side == 0 else C_RIGHT

    def update(self, dt, inp, game):
        if self.immune:
            self.timers["reverse"] = 0.0
        if game.serve_t <= 0:  # no power-up timer ticks down while waiting for the next serve
            for k in self.timers:
                self.timers[k] = max(0.0, self.timers[k] - dt)
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.flash = max(0.0, self.flash - dt)
        move, target = inp.move, inp.target
        if self.timers["reverse"] > 0:
            move = -move
            if target is not None:
                target = H - target
        speed = inp.speed * (1 - 0.45 * self.charge)

        if self.dash_t > 0:
            self.dash_t -= dt
            self.vy = self.dash_dir * 1600
            game.burst((self.x, self.y), WHITE, 2, 60, 0.3, 3)
        elif target is not None:
            dy = target - self.y
            step = max(-speed * dt, min(speed * dt, dy))
            self.vy = step / dt if dt > 0 else 0.0
        elif inp.inertia:
            self.vy += move * 2800 * dt
            self.vy *= math.exp(-2.4 * dt)
            self.vy = max(-950, min(950, self.vy))
        else:
            self.vy = move * speed

        if inp.dash and self.dash_cd <= 0 and self.dash_t <= 0:
            if move != 0:
                d = 1 if move > 0 else -1
            elif target is not None:
                d = 1 if target > self.y else -1
            else:
                d = 1 if self.vy >= 0 else -1
            self.dash_dir, self.dash_t, self.dash_cd = d, 0.13, 1.5
            game.sfx.play("dash")

        self.y += self.vy * dt
        half = self.h / 2
        if self.y < half:
            self.y, self.vy = half, (-self.vy * 0.3 if inp.inertia else 0.0)
        elif self.y > H - half:
            self.y, self.vy = H - half, (-self.vy * 0.3 if inp.inertia else 0.0)

        # forward / back movement
        if self.owner is not None:  # assistant paddle: just stands in front of its owner
            self.x = max(self.xmin, min(self.xmax, self.owner.x + self.owner.d * 50))
        elif game.event == "ROAMING PADDLES":
            mx, xt = inp.movex, inp.xtarget
            if self.timers["reverse"] > 0:
                mx = -mx
                if xt is not None:
                    xt = W - xt
            xs = inp.xspeed * (1 - 0.45 * self.charge)
            if xt is not None:
                step = max(-xs * dt, min(xs * dt, xt - self.x))
                self.vx = step / dt if dt > 0 else 0.0
            elif inp.inertia:
                self.vx += mx * 2800 * dt
                self.vx *= math.exp(-2.4 * dt)
                self.vx = max(-950, min(950, self.vx))
            else:
                self.vx = mx * xs
            self.x += self.vx * dt
            if self.x < self.xmin:
                self.x, self.vx = self.xmin, 0.0
            elif self.x > self.xmax:
                self.x, self.vx = self.xmax, 0.0
        elif abs(self.home_x - self.x) > 0.5:  # event over: slide back home
            self.x += max(-700 * dt, min(700 * dt, self.home_x - self.x))
            self.vx = 0.0

        if inp.charge:
            self.charge = min(1.0, self.charge + dt / 1.1)
            self.charging = True
            self.smash = 0.0
            self.smash_t = 0.0
        else:
            if self.charging and self.charge > 0.12:
                self.smash, self.smash_t = self.charge, 0.3
            self.charge, self.charging = 0.0, False
            if self.smash_t > 0:
                self.smash_t -= dt
                if self.smash_t <= 0:
                    self.smash = 0.0


class Helper(Paddle):
    """The ASSISTANT power-up: a small yellow AI paddle that stands just in front of its owner."""

    def __init__(self, owner, ttl=5.0):
        super().__init__(owner.side)
        self.owner = owner
        self.xmin, self.xmax = (28, W / 2 - 20) if owner.side == 0 else (W / 2 + 20, W - 28)
        self.x = owner.x + owner.d * 50
        self.y = owner.y
        self.base_h = 72
        self.w = 12
        self.ttl = ttl
        self.ctrl = Controller("AI-HARD", owner.side)

    @property
    def color(self):
        return YELLOW


# --------------------------------------------------------------------------- game
class Game:
    def __init__(self, settings, sfx):
        self.s = settings
        self.sfx = sfx
        self.controllers = [Controller(SCHEMES[settings["left"]], 0),
                            Controller(SCHEMES[settings["right"]], 1)]
        self.paddles = [Paddle(0), Paddle(1)]
        self.ai_only = all(c.scheme.startswith("AI-") for c in self.controllers)
        n_r = len(RARITIES)
        self.rar = list(settings.get("rar") or [bool(settings.get("powerups", True))] * n_r)
        self.keep_rarity = settings.get("keep_rarity", False)
        self.abilities = settings.get("abilities", True)
        sp = settings.get("speed", 910)
        if sp < SPEED_MIN:  # an old-style speed index
            sp = OLD_SPEEDS[max(0, min(len(OLD_SPEEDS) - 1, int(sp)))] * 1920 / W
        self.base_speed = sp * W / 1920.0   # px/s at 1080p -> this field's own pixels
        self.max_speed = max(MAX_SPEED, self.base_speed * 1.9)
        self.pu_freq = float(settings.get("pu_freq", 7))
        self.pu_max = int(settings.get("pu_max", 3))
        self.chaos_freq = float(settings.get("chaos_freq", 18))
        # pickups normally vanish after 12s; with a big "max on board" they last long enough to reach it
        self.pickup_ttl = 12.0 if self.pu_max <= 3 else max(12.0, 1.15 * self.pu_freq * self.pu_max)
        self.ext_mult = [1.0, 1.0]   # OVERTIME: duration multiplier per player...
        self.ext_t = [0.0, 0.0]      # ...and how long it lasts
        self.surge = 1.0             # POWER SURGE chaos event: power-up length multiplier
        self.owner = {}              # who caused the global effects (slow / turbo / grav)
        self.history = []            # recent ball snapshots, for delayed-reaction bots
        self.has_impossible = any(c.scheme == "AI-IMPOSSIBLE" for c in self.controllers)
        self.powerups_on = any(self.rar[i] and TIERS[i] for i in range(n_r))
        self.grav_t = 0.0
        self.floats = []   # little floating texts: [text, x, y, ttl, colour, size]
        self.helpers = []
        self.balls, self.pickups, self.wells = [], [], []
        self.particles, self.banners = [], []
        self.bumpers, self.portals = [], []
        self.keydowns, self.mousedowns = set(), set()
        self.t = self.dt = 0.0
        self.shake = 0.0
        self.rally = self.best_rally = 0
        self.slow_t = self.turbo_t = 0.0
        self.event, self.event_t = None, 0.0
        self.gdir, self.wind = 1, 1
        self.next_event = self.chaos_freq * random.uniform(0.8, 1.2)
        self.next_pickup = self.pu_freq * random.uniform(0.5, 0.9)
        self.serve_t = COUNTDOWN
        self.count_shown = None
        self.serve_dir = random.choice((-1, 1))
        self.winner = None
        self.hint_t = 8.0
        if settings["obstacles"]:
            self.bumpers = [Bumper(W * 0.38, 170, 0.9, 0.0), Bumper(W * 0.62, 170, 0.9, math.pi)]
            self.portals = [V(W * 0.5, 170), V(W * 0.5, H - 170)]

    # ---- helpers
    def banner(self, msg, color=WHITE, ttl=2.2):
        self.banners.append([msg, ttl, color])
        del self.banners[:-3]

    def burst(self, pos, color, n=12, speed=220, life=0.5, size=3):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(0.2, 1.0) * speed
            l = random.uniform(0.5, 1.0) * life
            self.particles.append([pos[0], pos[1], math.cos(a) * sp, math.sin(a) * sp, l, l, color, size])

    def serve(self):
        speed = self.base_speed
        ang = random.uniform(-0.45, 0.45)
        self.balls = [Ball((W / 2, H / 2), (self.serve_dir * math.cos(ang) * speed, math.sin(ang) * speed))]
        self.rally = 0

    def record(self):
        self.history.append((self.t, [Snap(b) for b in self.balls]))
        while len(self.history) > 1 and self.history[0][0] < self.t - 0.6:
            self.history.pop(0)

    def seen(self, delay):
        """The balls as they looked `delay` seconds ago (what a bot with that reaction time perceives)."""
        if delay <= 0:
            return self.balls
        target = self.t - delay
        for t, snaps in reversed(self.history):
            if t <= target:
                return snaps
        return []  # it hasn't had time to notice anything yet

    # ---- main update
    def update(self, dt, keys):
        self.dt = dt
        self.t += dt
        ins = [c.read(p, self, keys) for c, p in zip(self.controllers, self.paddles)]
        if self.event == "CONTROL SWAP":
            ins.reverse()
        for p, i in zip(self.paddles, ins):
            idx = 1 - p.side if self.event == "CONTROL SWAP" else p.side
            p.immune = self.controllers[idx].scheme == "AI-IMPOSSIBLE"
            self.gate(i)
            p.update(dt, i, self)
        for hp in self.helpers:
            hi = hp.ctrl.read(hp, self, keys)
            self.gate(hi)
            hp.update(dt, hi, self)
            if self.balls and self.serve_t <= 0:  # the 5 seconds only tick while a ball is in play
                hp.ttl -= dt
        for hp in self.helpers[:]:
            if hp.ttl <= 0:
                self.burst((hp.x, hp.y), YELLOW, 14, 220, 0.5)
                self.helpers.remove(hp)
        self.hint_t = max(0.0, self.hint_t - dt)
        self.shake = max(0.0, self.shake - dt * 40)
        if self.serve_t <= 0:  # nothing ticks down during the break between points
            self.slow_t = max(0.0, self.slow_t - dt)
            self.turbo_t = max(0.0, self.turbo_t - dt)
            self.grav_t = max(0.0, self.grav_t - dt)
            for sd in (0, 1):
                self.ext_t[sd] = max(0.0, self.ext_t[sd] - dt)

        ts = (0.45 if self.slow_t > 0 else 1.0) * (1.35 if (self.turbo_t > 0 or self.event == "TURBO") else 1.0)
        sdt = dt * ts
        if not self.winner:
            if self.serve_t > 0:
                self.serve_t -= dt
                if self.serve_t <= 0:
                    self.serve()
                    self.sfx.play("go")
                    self.banner("GO!", WHITE, 0.7)
                else:
                    n = math.ceil(self.serve_t)
                    if n != self.count_shown:
                        self.count_shown = n
                        self.sfx.play("tick")
            else:
                self.update_balls(sdt)
            self.record()
            self.update_world(dt)
        self.update_particles(dt)
        for b in self.banners:
            b[1] -= dt
        self.banners = [b for b in self.banners if b[1] > 0]
        for f in self.floats:
            f[2] -= 45 * dt
            f[3] -= dt
        self.floats = [f for f in self.floats if f[3] > 0]
        self.keydowns.clear()
        self.mousedowns.clear()

    def gate(self, inp):
        """Dash and charge can be switched off in the menu."""
        if not self.abilities:
            inp.dash = False
            inp.charge = False

    def ai_controls(self, p):
        idx = 1 - p.side if self.event == "CONTROL SWAP" else p.side
        return self.controllers[idx].scheme.startswith("AI-")

    def guard_goal(self, b):
        """An AI never lets a ball that nobody has hit yet roll into its goal."""
        for p in self.paddles:
            if b.vel.x * p.d < 0 and abs(b.pos.x - p.x) < 240 and self.ai_controls(p):
                dy = b.pos.y - p.y
                if abs(dy) > p.h * 0.3:
                    step = max(-8000 * self.dt, min(8000 * self.dt, dy))  # strong enough to beat REVERSE controls
                    half = p.h / 2
                    p.y = max(half, min(H - half, p.y + step))

    def impossible_step(self, h):
        """The impossible bot re-aims its paddle at the most urgent ball before every ball sub-step,
        so it can make several corrections inside a single frame."""
        for p in self.paddles:
            idx = 1 - p.side if self.event == "CONTROL SWAP" else p.side
            c = self.controllers[idx]
            if c.scheme != "AI-IMPOSSIBLE":
                continue
            best, bt = None, 1e9
            for b in self.balls:
                if b.vel.x * p.d < 0:
                    t = abs(p.x - b.pos.x) / max(1.0, abs(b.vel.x))
                    if t < bt:
                        bt, best = t, b
            if best is None:
                continue
            half = p.h / 2
            target = max(half, min(H - half, best.pos.y - c.aim * half))
            reach = IMPOSSIBLE_V * h
            p.y += max(-reach, min(reach, target - p.y))

    def update_balls(self, sdt):
        live = []
        for b in self.balls[:]:
            if self.grav_t > 0:
                b.vel.y += GRAV * sdt
            if not b.touched:
                self.guard_goal(b)
            if self.event == "GRAVITY SHIFT":
                b.vel.y += self.gdir * 700 * sdt
            if self.event == "WIND":
                b.vel.x += self.wind * 350 * sdt
            for w in self.wells:
                d = w.pos - b.pos
                dist = d.length()
                if 1 < dist < w.radius:
                    b.vel += d / dist * 1500 * (1 - dist / w.radius) * sdt
            for p in self.paddles:
                if p.timers["magnet"] > 0 and b.vel.x * p.d < 0 and abs(b.pos.x - p.x) < W * 0.55:
                    b.vel.y += math.copysign(650, p.y - b.pos.y) * sdt
            if abs(b.spin) > 0.01 and b.vel.length_squared() > 1:
                b.vel = b.vel.rotate_rad(b.spin * 0.22 * sdt)
            b.spin *= math.exp(-0.6 * sdt)

            spd = b.vel.length()
            if spd > self.max_speed:
                b.vel *= self.max_speed / spd
                spd = self.max_speed
            if abs(b.vel.x) < 130:
                b.vel.x = math.copysign(130, b.vel.x or random.choice((-1, 1)))
            live.append((b, spd))
        if not live:
            return

        # all balls move together, sub-step by sub-step
        n = max(1, int(max(s for _, s in live) * sdt / 6) + 1)
        h = sdt / n
        gone = set()
        for _ in range(n):
            for b, _s in live:
                if id(b) not in gone:
                    b.pos += b.vel * h
            if self.has_impossible:
                self.impossible_step(h)
            for b, _s in live:
                if id(b) not in gone and self.collide(b):
                    gone.add(id(b))
        for b, _s in live:
            if id(b) in gone:
                continue
            b.portal_cd = max(0.0, b.portal_cd - sdt)
            b.ghost = max(0.0, b.ghost - sdt)
            b.trail.append(V(b.pos))
            if len(b.trail) > 20:
                b.trail.pop(0)
            if b.fire:
                for _ in range(3):
                    self.particles.append([b.pos.x + random.uniform(-4, 4), b.pos.y + random.uniform(-4, 4),
                                           -b.vel.x * 0.08 + random.uniform(-40, 40),
                                           -b.vel.y * 0.08 + random.uniform(-80, 10),
                                           0.45, 0.45, random.choice(FIRE_COLS), 5])

    def collide(self, b):
        """Returns True if the ball left the game."""
        r = b.r
        if b.pos.y < r:
            b.fire = False
            b.pos.y, b.vel.y, b.spin = r, abs(b.vel.y), b.spin * 0.7
            self.sfx.play("wall")
            self.burst(b.pos, GREY, 4, 120, 0.25, 2)
        elif b.pos.y > H - r:
            b.fire = False
            vy_in = abs(b.vel.y)
            rest = GRAV_REST if self.grav_t > 0 else 1.0  # ping-pong ball bounce under REAL GRAVITY
            b.pos.y, b.vel.y, b.spin = H - r, -vy_in * rest, b.spin * 0.7
            if self.grav_t > 0 and abs(b.vel.y) < 80:
                b.vel.y = 0.0  # settles and rolls along the floor
            if self.grav_t <= 0 or vy_in > 150:
                self.sfx.play("wall")
                self.burst(b.pos, GREY, 4, 120, 0.25, 2)

        for bp in self.bumpers:
            dv = b.pos - bp.pos
            dist = dv.length()
            mind = r + bp.r
            if 0 < dist < mind:
                n = dv / dist
                b.pos = bp.pos + n * (mind + 0.5)
                if b.vel.dot(n) < 0:
                    b.vel = b.vel.reflect(n) * 1.05 + n * 70
                b.fire = False
                self.sfx.play("bump")
                self.burst(b.pos, YELLOW, 8, 200, 0.35)
                self.shake = max(self.shake, 2)

        if self.portals and b.portal_cd <= 0:
            for i, pt in enumerate(self.portals):
                if (b.pos - pt).length() < 26:
                    other = self.portals[1 - i]
                    dirn = b.vel.normalize() if b.vel.length() > 0 else V(1, 0)
                    self.burst(pt, (170, 110, 255), 14, 200, 0.5)
                    b.pos = other + dirn * (26 + r + 4)
                    b.portal_cd = 0.4
                    b.trail.clear()
                    self.burst(other, (170, 110, 255), 14, 200, 0.5)
                    self.sfx.play("portal")
                    break

        for p in self.paddles + self.helpers:
            if b.vel.x * p.d >= 0:
                continue
            if p.d * (b.pos.x - p.x) < -p.w / 2:
                continue
            left, right = p.x - p.w / 2, p.x + p.w / 2
            top, bot = p.y - p.h / 2, p.y + p.h / 2
            cx = max(left, min(right, b.pos.x))
            cy = max(top, min(bot, b.pos.y))
            nx, ny = b.pos.x - cx, b.pos.y - cy
            if nx * nx + ny * ny >= r * r:
                continue
            front = (top <= b.pos.y <= bot) or (p.d * nx > abs(ny))
            if not front:
                # the ball only clipped the corner / end of the paddle: bounce off it like a real corner
                n = V(nx, ny)
                n = n.normalize() if n.length() > 0 else V(0, -1 if b.pos.y < p.y else 1)
                b.pos = V(cx, cy) + n * (r + 0.5)
                if b.vel.dot(n) < 0:
                    b.vel = b.vel.reflect(n) * 1.03
                b.fire = False
                b.touched = True
                b.last = p.side
                self.rally += 1
                self.best_rally = max(self.best_rally, self.rally)
                p.flash = 0.15
                self.sfx.play("hit")
                self.burst(b.pos, p.color, 6, 180, 0.3)
                continue
            offset = max(-1.0, min(1.0, (b.pos.y - p.y) / (p.h / 2)))
            a = offset * math.radians(58)
            if self.ai_only:  # break up endless identical AI-vs-AI rallies
                a += math.radians(random.uniform(-5, 5))
                if abs(a) < math.radians(8):  # never fly perfectly flat
                    a = math.copysign(math.radians(8), a or random.choice((-1, 1)))
            b.fire = False
            speed = max(b.vel.length() * 1.045, self.base_speed * b.scale)
            if p.dash_t > 0:
                speed *= 1.15
            if p.smash > 0:
                speed *= 1 + 0.8 * p.smash
                if p.smash > 0.25:
                    self.shake = max(self.shake, 8 + 8 * p.smash)
                    self.burst((p.x + p.d * 12, b.pos.y), YELLOW, 24, 420, 0.6, 4)
                    self.sfx.play("smash")
                    self.banner("SMASH!", YELLOW, 0.8)
                    b.fire = True  # flaming trail until it hits something
                p.smash = p.smash_t = 0.0
            speed = min(speed, self.max_speed)
            b.vel = V(p.d * math.cos(a), math.sin(a)) * speed
            spin = 0.0  # no curving at all unless it's AI-vs-AI
            if self.ai_only:
                spin = b.spin * 0.3 + p.vy * 0.007 + random.uniform(-2.0, 2.0)
            b.spin = max(-9.0, min(9.0, spin))
            b.touched = True
            b.pos.x = p.x + p.d * (p.w / 2 + r + 1)
            b.last = p.side
            self.rally += 1
            self.best_rally = max(self.best_rally, self.rally)
            p.flash = 0.15
            self.sfx.play("hit")
            self.burst(b.pos, p.color, 8, 220, 0.35)
            self.shake = max(self.shake, 2)

        for p in self.paddles:
            if p.shield > 0:
                if p.side == 0 and b.pos.x < r and b.vel.x < 0:
                    b.vel.x = abs(b.vel.x)
                    p.shield -= 1
                elif p.side == 1 and b.pos.x > W - r and b.vel.x > 0:
                    b.vel.x = -abs(b.vel.x)
                    p.shield -= 1
                else:
                    continue
                b.fire = False
                self.sfx.play("shield")
                self.burst(b.pos, (80, 240, 240), 20, 300, 0.5)
                self.banner("SHIELD SAVE!", (80, 240, 240), 1.2)
                self.shake = max(self.shake, 6)

        if b.pos.x < -r * 2:
            self.score(1, b)
            return True
        if b.pos.x > W + r * 2:
            self.score(0, b)
            return True
        return False

    def score(self, side, ball):
        self.paddles[side].score += 1
        if ball in self.balls:
            self.balls.remove(ball)
        x = 0 if side == 1 else W
        self.burst((x, ball.pos.y), self.paddles[side].color, 30, 450, 0.8, 4)
        self.sfx.play("score")
        if not self.balls and self.paddles[side].score >= WIN_SCORES[self.s["score"]]:
            self.shake = 0.0  # no screen shake on the match-winning point
        else:
            self.shake = max(self.shake, 10)
        if not self.balls:
            self.slow_t = self.turbo_t = self.grav_t = 0.0
            self.wells.clear()
            if self.paddles[side].score >= WIN_SCORES[self.s["score"]]:
                self.winner = side
                self.sfx.play("win")
                return
            self.serve_t = COUNTDOWN
            self.count_shown = None
            self.serve_dir = -1 if side == 1 else 1
            self.rally = 0

    def update_world(self, dt):
        frozen = self.serve_t > 0  # nothing ticks down while waiting for the next serve
        for bp in self.bumpers:
            bp.pos.y = H / 2 + bp.amp * math.sin(self.t * bp.freq + bp.phase)
        if not frozen:
            for w in self.wells:
                w.ttl -= dt
            self.wells = [w for w in self.wells if w.ttl > 0]

        if self.powerups_on:
            if not frozen:
                self.next_pickup -= dt
                if self.next_pickup <= 0:
                    self.next_pickup = self.pu_freq * random.uniform(0.7, 1.3)
                    if len(self.pickups) < self.pu_max:
                        kind = roll_powerup(self.rar, self.keep_rarity)
                        if kind:
                            pk = Pickup(kind, (random.uniform(320, W - 320), random.uniform(90, H - 90)))
                            pk.ttl = self.pickup_ttl
                            self.pickups.append(pk)
            for pk in self.pickups[:]:
                pk.t += dt
                if not frozen:
                    pk.ttl -= dt
                if POWERUPS[pk.kind][1] >= 4 and random.random() < 0.25:  # legendary+ sparkle
                    self.particles.append([pk.pos.x + random.uniform(-20, 20), pk.pos.y + random.uniform(-20, 20),
                                           0, -30, 0.6, 0.6, RARITIES[POWERUPS[pk.kind][1]][1], 2])
                hit = None
                for b in self.balls:
                    if (b.pos - pk.pos).length() < 20 + b.r:
                        hit = b
                        break
                if hit:
                    side = hit.last if hit.last is not None else random.randint(0, 1)
                    if random.random() < DUD_CHANCE:
                        self.dud(pk, side)
                    else:
                        self.apply_pickup(pk, side, hit)
                    self.pickups.remove(pk)
                elif pk.ttl <= 0:
                    self.pickups.remove(pk)

        if self.s["chaos"] and not frozen:
            if self.event:
                self.event_t -= dt
                if self.event_t <= 0:
                    self.event = None
                    self.next_event = self.chaos_freq * random.uniform(0.8, 1.2)
            else:
                self.next_event -= dt
                if self.next_event <= 0 and self.balls:
                    pool = [e for e in CHAOS_EVENTS if not (self.has_impossible and e[0] == "CONTROL SWAP")
                            and not (e[0] == "POWER SURGE" and not self.powerups_on)]
                    name, dur, _ = random.choices(pool, [e[2] for e in pool])[0]
                    self.event, self.event_t = name, dur
                    self.gdir = random.choice((-1, 1))
                    self.wind = random.choice((-1, 1))
                    if name == "POWER SURGE":
                        self.start_surge()
                    self.banner("CHAOS: " + self.event + (f" x{self.surge:.1f}" if name == "POWER SURGE" else ""),
                                (255, 90, 90), 2.5)
                    self.sfx.play("event")
                    self.shake = max(self.shake, 8)

    def start_surge(self):
        """POWER SURGE: roll 1.1x-3.0x and stretch every power-up that is already running."""
        m = random.randint(11, 30) / 10
        self.surge = m
        for p in self.paddles:
            for k in p.timers:
                p.timers[k] *= m
        for h in self.helpers:
            h.ttl *= m
        self.slow_t *= m
        self.turbo_t *= m
        self.grav_t *= m
        for w in self.wells:
            w.ttl *= m

    def ext_factor(self, side):
        """OVERTIME: how much longer this player's power-ups currently last."""
        f = self.ext_mult[side] if self.ext_t[side] > 0 else 1.0
        return f * (self.surge if self.event == "POWER SURGE" else 1.0)

    def apply_pickup(self, pk, side, ball):
        me, opp = self.paddles[side], self.paddles[1 - side]
        kind = pk.kind
        f = self.ext_factor(side)
        extra = ""
        if kind == "BIG":
            me.timers["big"] = 10 * f
        elif kind == "SHRINK":
            opp.timers["small"] = 10 * f
        elif kind == "MULTI":
            for ang in (-0.35, 0.35):
                if len(self.balls) < 6:
                    nb = Ball(ball.pos, ball.vel.rotate_rad(ang) * 0.78)  # extras are a bit slower
                    nb.last, nb.touched, nb.scale = ball.last, ball.touched, 0.78
                    self.balls.append(nb)
        elif kind == "SLOW":
            self.slow_t = 5 * f
            self.owner["slow"] = side
        elif kind == "SHIELD":
            me.shield = min(2, me.shield + 1)
        elif kind == "REVERSE":
            opp.timers["reverse"] = 6 * f
        elif kind == "GHOST":
            for b in self.balls:
                b.ghost = 3 * f
        elif kind == "MAGNET":
            me.timers["magnet"] = 7 * f
        elif kind == "GRAVITY":
            self.grav_t = 10.0 * f
            self.owner["grav"] = side
        elif kind == "WELL":
            w = Well((W / 2 + random.uniform(-120, 120), random.uniform(150, H - 150)))
            w.ttl *= f
            w.owner = side
            self.wells.append(w)
        elif kind == "TURBO":
            self.turbo_t = 5 * f
            self.owner["turbo"] = side
        elif kind == "ASSIST":
            self.helpers = [h for h in self.helpers if h.side != side]  # a new pickup refreshes the timer
            self.helpers.append(Helper(me, ttl=5.0 * f))
        elif kind == "OVERTIME":
            m = random.randint(1, 30) / 10  # 0.1 .. 3.0
            eff = m if m >= 1 else 1 + m    # below 1x it never shortens anything: it adds that many extra times
            self.ext_mult[side], self.ext_t[side] = eff, 45.0
            extra = f" x{eff:.1f}"
            for tname in ("big", "magnet"):          # stretch what is already running for this player
                me.timers[tname] *= eff
            for tname in ("small", "reverse"):       # (shrink / reverse on the opponent came from this player)
                opp.timers[tname] *= eff
            for h in self.helpers:
                if h.side == side:
                    h.ttl *= eff
            for key, attr in (("slow", "slow_t"), ("turbo", "turbo_t"), ("grav", "grav_t")):
                if self.owner.get(key) == side:
                    setattr(self, attr, getattr(self, attr) * eff)
            for w in self.wells:
                if getattr(w, "owner", None) == side:
                    w.ttl *= eff
        name, rar = POWERUPS[kind]
        rcol = RARITIES[rar][1]
        self.banner(f"{'LEFT' if side == 0 else 'RIGHT'}: {name}{extra}", rcol, 1.8)
        self.burst(pk.pos, rcol, 22 + 10 * rar, 300, 0.6, 3)
        self.sfx.play("power")

    def dud(self, pk, side):
        """The power-up fizzles out."""
        self.floats.append([random.choice(DUD_LINES), min(W - 150, max(150, pk.pos.x)), pk.pos.y - 24, 1.8,
                            (210, 214, 230), 36])
        self.burst(pk.pos, GREY, 14, 160, 0.5, 3)
        self.sfx.play("dud")

    def update_particles(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.96
            p[3] *= 0.96
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]

    # ---- drawing
    def draw(self, s):
        s.fill(BG)
        for x in range(0, W, 50):
            pygame.draw.line(s, (14, 18, 38), (x, 0), (x, H))
        for y in range(0, H, 50):
            pygame.draw.line(s, (14, 18, 38), (0, y), (W, y))
        for y in range(0, H, 36):
            pygame.draw.rect(s, (30, 36, 70), (W // 2 - 2, y, 4, 20))
        if self.event:
            pulse = 120 + int(80 * math.sin(self.t * 8))
            pygame.draw.rect(s, (pulse, 40, 40), (0, 0, W, H), 4)

        for p in self.paddles:
            for i in range(p.shield):
                x = 2 + i * 5 if p.side == 0 else W - 5 - i * 5
                pygame.draw.rect(s, (80, 240, 240), (x, 0, 3, H))

        for pt in self.portals:
            for i in range(3):
                rad = int(26 - i * 7 + 2 * math.sin(self.t * 4 + i))
                pygame.draw.circle(s, (170, 110, 255), pt, rad, 2)
            s.blit(glow(60, (170, 110, 255)), (pt.x - 60, pt.y - 60))
        for w in self.wells:
            s.blit(glow(int(w.radius), (170, 110, 255)), (w.pos.x - w.radius, w.pos.y - w.radius))
            for i in range(4):
                rad = int(((self.t * 60 + i * 45) % 180))
                pygame.draw.circle(s, (120, 80, 200), w.pos, max(2, 180 - rad), 1)
            pygame.draw.circle(s, (20, 10, 40), w.pos, 12)
        for bp in self.bumpers:
            s.blit(glow(70, YELLOW), (bp.pos.x - 70, bp.pos.y - 70))
            pygame.draw.circle(s, (60, 50, 10), bp.pos, bp.r)
            pygame.draw.circle(s, YELLOW, bp.pos, bp.r, 3)
            pygame.draw.circle(s, YELLOW, bp.pos, 8)

        for pk in self.pickups:
            _, rar = POWERUPS[pk.kind]
            _, col, _, glowy = RARITIES[rar]
            r = 20 + int(2 * math.sin(pk.t * 5))
            if pk.ttl < 3 and int(pk.t * 8) % 2:
                continue
            if glowy:  # legendary / mythic: big pulsing glow and ripple rings
                pulse = 0.5 + 0.5 * math.sin(pk.t * 4)
                big = int(62 + 14 * pulse)
                s.blit(glow(big, col), (pk.pos.x - big, pk.pos.y - big))
                s.blit(glow(big, col), (pk.pos.x - big, pk.pos.y - big))
                ring = int((pk.t * 40) % 40)
                pygame.draw.circle(s, lerp_col(BG, col, 1 - ring / 40), pk.pos, r + ring, 2)
            else:
                s.blit(glow(40, col), (pk.pos.x - 40, pk.pos.y - 40))
            pygame.draw.circle(s, (10, 12, 26), pk.pos, r)
            pygame.draw.circle(s, col, pk.pos, r, 3)
            draw_icon(s, pk.kind, pk.pos, lerp_col(col, WHITE, 0.5))

        fog = self.event == "FOG"
        for b in self.balls:
            visible = True
            if b.ghost > 0:
                visible = int(self.t * 18) % 5 == 0
            if fog and 280 < b.pos.x < W - 280:
                visible = int(self.t * 10) % 4 == 0
            col = lerp_col((90, 200, 255), (255, 80, 80), b.vel.length() / self.max_speed)
            if b.fire:
                col = (255, 140, 40)
            if visible:
                for i, tp in enumerate(b.trail):
                    f = i / max(1, len(b.trail))
                    if b.fire:  # flames replace the normal trail
                        c = lerp_col((150, 25, 10), (255, 215, 80), f)
                        pos = (tp.x + random.uniform(-2, 2), tp.y + random.uniform(-2, 2))
                        pygame.draw.circle(s, c, pos, int(b.r * (0.5 + 0.9 * f)))
                    else:
                        pygame.draw.circle(s, lerp_col(BG, col, f * 0.6), tp, int(b.r * f) + 1)
                gl = 52 if b.fire else 36
                s.blit(glow(gl, col), (b.pos.x - gl, b.pos.y - gl))
                pygame.draw.circle(s, WHITE, b.pos, b.r)
                pygame.draw.circle(s, col, b.pos, b.r, 2)

        for p in self.paddles:
            rect = pygame.Rect(0, 0, p.w, p.h)
            rect.center = (p.x, p.y)
            col = WHITE if (p.dash_t > 0 or p.flash > 0) else p.color
            s.blit(glow(int(p.h * 0.55), p.color), (p.x - p.h * 0.55, p.y - p.h * 0.55))
            pygame.draw.rect(s, col, rect, border_radius=6)
            if p.smash_t > 0:
                pygame.draw.rect(s, YELLOW, rect.inflate(8, 8), 3, border_radius=8)
            if p.timers["reverse"] > 0:
                pygame.draw.rect(s, (255, 90, 230), rect.inflate(6, 6), 2, border_radius=8)
            if p.charge > 0:
                bh = p.h * p.charge
                pygame.draw.rect(s, YELLOW, (p.x + p.d * (p.w / 2 + 5) - 2, p.y + p.h / 2 - bh, 5, bh))

        for hp in self.helpers:
            if hp.ttl < 1.2 and int(self.t * 10) % 2:
                continue  # blink when about to leave
            rect = pygame.Rect(0, 0, hp.w, hp.h)
            rect.center = (hp.x, hp.y)
            rad = int(hp.h * 0.6)
            s.blit(glow(rad, YELLOW), (hp.x - rad, hp.y - rad))
            pygame.draw.rect(s, WHITE if (hp.flash > 0 or hp.dash_t > 0) else YELLOW, rect, border_radius=5)
            if hp.charge > 0:
                bh = hp.h * hp.charge
                pygame.draw.rect(s, WHITE, (hp.x + hp.d * (hp.w / 2 + 4) - 2, hp.y + hp.h / 2 - bh, 4, bh))

        for q in self.particles:
            f = q[4] / q[5]
            pygame.draw.circle(s, lerp_col(BG, q[6], f), (q[0], q[1]), max(1, int(q[7] * f)))

        for msg, fx, fy, ttl, col, size in self.floats:
            text(s, msg, size, lerp_col(BG, col, min(1.0, ttl / 0.6)), (fx, fy))

        self.draw_hud(s)

    def hud_timer(self, s, label, t, col, size, pos, anchor="center"):
        """Draws 'LABEL 8s'; under 1s it shows tenths and flashes on and off."""
        if t is None:
            text(s, label, size, col, pos, anchor)
            return
        tx, visible = fmt_timer(t, self.t)
        if visible:
            text(s, f"{label} {tx}", size, col, pos, anchor)

    def draw_hud(self, s):
        text(s, str(self.paddles[0].score), 84, C_LEFT, (W / 2 - 120, 50))
        text(s, str(self.paddles[1].score), 84, C_RIGHT, (W / 2 + 120, 50))
        img = font(20).render(f"FIRST TO {WIN_SCORES[self.s['score']]}", True, GREY)
        box = img.get_rect(center=(W / 2, 50))
        pygame.draw.rect(s, BG, box.inflate(16, 10))  # hides the dashed centre line behind the text
        s.blit(img, box)
        if self.rally > 1:
            text(s, f"RALLY {self.rally}", 30, YELLOW, (W / 2, 100))
        if self.balls:
            sp = max(b.vel.length() for b in self.balls)
            pygame.draw.rect(s, (30, 36, 70), (W / 2 - 80, H - 22, 160, 8), border_radius=4)
            pygame.draw.rect(s, lerp_col((90, 200, 255), (255, 80, 80), sp / self.max_speed),
                             (W / 2 - 80, H - 22, 160 * min(1, sp / self.max_speed), 8), border_radius=4)
        tags = []
        if self.slow_t > 0:
            tags.append(("SLOW-MO", self.slow_t, (110, 160, 255)))
        if self.turbo_t > 0:
            tags.append(("TURBO", self.turbo_t, WHITE))
        if self.grav_t > 0:
            tags.append(("REAL GRAVITY", self.grav_t, RARITIES[3][1]))
        for i, (label, t, col) in enumerate(tags):
            self.hud_timer(s, label, t, col, 22, (W / 2, 126 + i * 20))
        if self.event:
            self.hud_timer(s, self.event + (f" x{self.surge:.1f}" if self.event == "POWER SURGE" else ""), self.event_t, (255, 110, 110), 26, (W / 2, H - 50))

        for p in self.paddles:
            x = 24 if p.side == 0 else W - 24
            anchor = "topleft" if p.side == 0 else "topright"
            text(s, player_label(self.controllers[p.side].scheme), 20, p.color, (x, 14), anchor)
            lines = []
            if p.timers["big"] > 0: lines.append(("BIG", p.timers["big"]))
            if p.timers["small"] > 0: lines.append(("SHRUNK", p.timers["small"]))
            if p.timers["reverse"] > 0: lines.append(("REVERSED", p.timers["reverse"]))
            if p.timers["magnet"] > 0: lines.append(("MAGNET", p.timers["magnet"]))
            if p.shield > 0: lines.append((f"SHIELD x{p.shield}", None))
            for hp in self.helpers:
                if hp.side == p.side:
                    lines.append(("ASSISTANT", max(0.0, hp.ttl)))
            if self.ext_t[p.side] > 0:
                lines.append((f"OVERTIME x{self.ext_mult[p.side]:.1f}", self.ext_t[p.side]))
            for i, (label, t) in enumerate(lines):
                self.hud_timer(s, label, t, WHITE, 20, (x, 38 + i * 20), anchor)
            if self.abilities:
                bx = 24 if p.side == 0 else W - 24 - 120
                pygame.draw.rect(s, (30, 36, 70), (bx, H - 30, 120, 6), border_radius=3)
                ready = 1 - p.dash_cd / 1.5
                pygame.draw.rect(s, WHITE if ready >= 1 else GREY, (bx, H - 30, 120 * ready, 6), border_radius=3)
                pygame.draw.rect(s, (30, 36, 70), (bx, H - 20, 120, 6), border_radius=3)
                pygame.draw.rect(s, YELLOW, (bx, H - 20, 120 * p.charge, 6), border_radius=3)
                text(s, "DASH / CHARGE", 14, GREY, (bx, H - 42), "topleft")

        if self.event == "ROAMING PADDLES":
            for p in self.paddles:
                sch = self.controllers[p.side].scheme
                if not sch.startswith("AI-"):
                    key = f"LANES-{p.side}" if sch == "LANES" else sch
                    x = 24 if p.side == 0 else W - 24
                    text(s, f"{XHINT[key]}: FORWARD / BACK", 20, p.color, (x, H - 78),
                         "bottomleft" if p.side == 0 else "bottomright")

        if self.hint_t > 0:
            for p in self.paddles:
                c = self.controllers[p.side]
                key = f"LANES-{p.side}" if c.scheme == "LANES" else c.scheme
                x = 24 if p.side == 0 else W - 24
                anchor = "bottomleft" if p.side == 0 else "bottomright"
                text(s, help_text(key, self.abilities), 18, lerp_col(BG, p.color, min(1, self.hint_t / 2)),
                     (x, H - 56), anchor)

        for i, (msg, ttl, col) in enumerate(self.banners):
            text(s, msg, 40, lerp_col(BG, col, min(1.0, ttl)), (W / 2, 200 + i * 40))
        if self.serve_t > 0 and not self.winner:
            n = math.ceil(self.serve_t)
            frac = self.serve_t - (n - 1)  # 1 -> 0 during each second
            col = lerp_col(BG, YELLOW if n == 1 else WHITE, 0.35 + 0.65 * frac)
            text(s, str(n), int(150 + 70 * frac), col, (W / 2, H / 2))
            text(s, "GET READY", 30, GREY, (W / 2, H / 2 + 110))


# --------------------------------------------------------------------------- menu
class Menu:
    ROWS = ["PRESET", "LEFT PLAYER", "RIGHT PLAYER", "WIN SCORE", "POWER-UPS", "POWER-UP FREQ",
            "MAX POWER-UPS", "CHAOS EVENTS", "CHAOS FREQ", "OBSTACLES", "BALL SPEED",
            "DASH & CHARGE", "START MATCH"]
    # number rows: setting key, minimum, maximum, unit, help text
    NUM = {
        "POWER-UP FREQ": ("pu_freq", FREQ_MIN, FREQ_MAX, "s",
                          "Seconds between power-up spawns (1-2048). Type a number or use LEFT/RIGHT"),
        "MAX POWER-UPS": ("pu_max", 0, 20, "",
                          "Most power-ups allowed on the board at once (0-20). Type a number or use LEFT/RIGHT"),
        "CHAOS FREQ": ("chaos_freq", FREQ_MIN, FREQ_MAX, "s",
                       "Seconds between chaos events (1-2048). Type a number or use LEFT/RIGHT"),
    }

    def __init__(self):
        self.s = {"left": 0, "right": SCHEMES.index("AI-HARD"), "score": 1,
                  "rar": [True] * len(RARITIES), "keep_rarity": False,
                  "chaos": True, "obstacles": True, "speed": 910, "abilities": True,
                  "pu_freq": 7, "pu_max": 3, "chaos_freq": 18}
        self.sel = 0
        self.popup = None    # None, "rar" (rarity checklist) or "speed" (ball speed list)
        self.psel = 0
        self.ssel = 0
        self.sbuf = ""       # digits typed into the custom ball speed box
        self.nbuf = ""       # digits typed into a number row
        self.t = 0.0
        self.reroll_splash()

    def reroll_splash(self):
        self.splash, self.splash_italic = pick_splash()

    # ---- presets (they never touch left / right player controls)
    def _matches(self, cfg):
        for key, val in cfg.items():
            if key == "powerups":
                ok = all(self.s["rar"]) if val else not any(self.s["rar"])
            else:
                ok = self.s[key] == val
            if not ok:
                return False
        return True

    def current_preset(self):
        """Index of the preset matching the current settings, or -1 for CUSTOM."""
        for i, (_, cfg, _) in enumerate(PRESETS):
            if self._matches(cfg):
                return i
        return -1

    def cycle_preset(self, d):
        cur = self.current_preset()
        if cur == -1:
            new = 0 if d > 0 else len(PRESETS) - 1
        else:
            new = (cur + d) % len(PRESETS)
        for key, val in PRESETS[new][1].items():
            if key == "powerups":
                self.s["rar"] = [bool(val)] * len(RARITIES)
            else:
                self.s[key] = val

    def powerups_label(self):
        rar = self.s["rar"]
        if all(rar):
            return "ALL"
        if not any(rar):
            return "OFF"
        names = [RARITIES[i][0] for i in range(len(RARITIES)) if rar[i]]
        label = ", ".join(names)
        if len(label) > 24:
            label = f"{len(names)} OF {len(RARITIES)} RARITIES"
        return label + (" (KEEP ODDS)" if self.s["keep_rarity"] else "")

    def speed_label(self):
        v = self.s["speed"]
        name = next((n for n, sv in SPEED_PRESETS if sv == v), None)
        return f"{name} ({v} px/s)" if name else f"{v} px/s"

    # ---- number rows
    def commit_num(self, row):
        key, lo, hi, _, _ = self.NUM[row]
        if self.nbuf:
            self.s[key] = max(lo, min(hi, int(self.nbuf)))
        self.nbuf = ""

    def step_num(self, row, d):
        key, lo, hi, _, _ = self.NUM[row]
        v = self.s[key]
        if key == "pu_max":
            v = max(lo, min(hi, v + d))
        elif d > 0:
            v = next((n for n in NICE_SECONDS if n > v), hi)
        else:
            v = next((n for n in reversed(NICE_SECONDS) if n < v), lo)
        self.s[key] = v

    def num_key(self, row, k):
        """Typing digits on a number row. Returns True if the key was used up here."""
        dg = digit_of(k)
        if dg is not None:
            if len(self.nbuf) < 4:
                self.nbuf += str(dg)
            return True
        if k == K.K_BACKSPACE:
            self.nbuf = self.nbuf[:-1]
            return True
        if k == K.K_ESCAPE and self.nbuf:
            self.nbuf = ""
            return True
        if k in (K.K_RETURN, K.K_SPACE):
            self.commit_num(row)
            return True
        if k in (K.K_UP, K.K_DOWN, K.K_LEFT, K.K_RIGHT):
            self.commit_num(row)  # then the arrow does its normal thing
        return False

    # ---- keys
    def key(self, k):
        if self.popup == "rar":
            return self.popup_key(k)
        if self.popup == "speed":
            return self.speed_key(k)
        row = self.ROWS[self.sel]
        if row in self.NUM and self.num_key(row, k):
            return None
        if k == K.K_UP:
            self.sel = (self.sel - 1) % len(self.ROWS)
        elif k == K.K_DOWN:
            self.sel = (self.sel + 1) % len(self.ROWS)
        elif k in (K.K_LEFT, K.K_RIGHT, K.K_RETURN, K.K_SPACE):
            d = -1 if k == K.K_LEFT else 1
            s = self.s
            if row == "PRESET": self.cycle_preset(d)
            elif row == "LEFT PLAYER": s["left"] = (s["left"] + d) % len(SCHEMES)
            elif row == "RIGHT PLAYER": s["right"] = (s["right"] + d) % len(SCHEMES)
            elif row == "WIN SCORE": s["score"] = (s["score"] + d) % len(WIN_SCORES)
            elif row == "POWER-UPS":
                self.popup, self.psel = "rar", 0
            elif row in self.NUM: self.step_num(row, d)
            elif row == "CHAOS EVENTS": s["chaos"] = not s["chaos"]
            elif row == "OBSTACLES": s["obstacles"] = not s["obstacles"]
            elif row == "BALL SPEED":
                self.popup = "speed"
                self.sbuf = ""
                self.ssel = next((i for i, (_, sv) in enumerate(SPEED_PRESETS) if sv == s["speed"]),
                                 len(SPEED_PRESETS))
            elif row == "DASH & CHARGE": s["abilities"] = not s["abilities"]
            elif row == "START MATCH" and k in (K.K_RETURN, K.K_SPACE):
                return "start"
        elif k == K.K_ESCAPE:
            return "quit"
        return None

    def speed_key(self, k):
        n = len(SPEED_PRESETS)  # rows 0..n-1 are the named speeds, row n is the custom box
        dg = digit_of(k)
        if dg is not None:
            self.ssel = n
            if len(self.sbuf) < 4:
                self.sbuf += str(dg)
        elif k == K.K_BACKSPACE:
            self.sbuf = self.sbuf[:-1]
        elif k == K.K_UP:
            self.ssel = (self.ssel - 1) % (n + 1)
        elif k == K.K_DOWN:
            self.ssel = (self.ssel + 1) % (n + 1)
        elif k == K.K_ESCAPE:
            self.popup, self.sbuf = None, ""
        elif k in (K.K_RETURN, K.K_SPACE):
            if self.ssel < n:
                self.s["speed"] = SPEED_PRESETS[self.ssel][1]
                self.popup = None
            elif self.sbuf:
                self.s["speed"] = max(SPEED_MIN, min(SPEED_MAX, int(self.sbuf)))
                self.popup, self.sbuf = None, ""
        return None

    def popup_key(self, k):
        n = len(RARITIES)  # rows: 0 select all, 1 deselect all, 2..n+1 rarities, n+2 keep rarity, n+3 done
        if k == K.K_UP:
            self.psel = (self.psel - 1) % (n + 4)
        elif k == K.K_DOWN:
            self.psel = (self.psel + 1) % (n + 4)
        elif k == K.K_ESCAPE:
            self.popup = None
        elif k in (K.K_LEFT, K.K_RIGHT, K.K_RETURN, K.K_SPACE):
            i, press = self.psel, k in (K.K_RETURN, K.K_SPACE)
            if i == 0 and press:
                self.s["rar"] = [True] * n
            elif i == 1 and press:
                self.s["rar"] = [False] * n
            elif 2 <= i <= n + 1:
                self.s["rar"][i - 2] = not self.s["rar"][i - 2]
            elif i == n + 2:
                self.s["keep_rarity"] = not self.s["keep_rarity"]
            elif i == n + 3 and press:
                self.popup = None
        return None

    # ---- drawing
    def draw(self, s, dt):
        self.t += dt
        s.fill(BG)
        for x in range(0, W, 50):
            pygame.draw.line(s, (14, 18, 38), (x, 0), (x, H))
        for y in range(0, H, 50):
            pygame.draw.line(s, (14, 18, 38), (0, y), (W, y))
        text(s, "OVERCOMPLICATED", 80, lerp_col(C_LEFT, C_RIGHT, 0.5 + 0.5 * math.sin(self.t * 2)),
             (W / 2, 58 + 5 * math.sin(self.t * 3)))
        text(s, "P O N G", 100, WHITE, (W / 2, 132 + 5 * math.sin(self.t * 3 + 1)))
        text(s, self.splash, 24, GREY, (W / 2, 184), italic=self.splash_italic)

        cur = self.current_preset()
        vals = [PRESETS[cur][0] if cur >= 0 else "CUSTOM",
                SCHEMES[self.s["left"]], SCHEMES[self.s["right"]], str(WIN_SCORES[self.s["score"]]),
                self.powerups_label(), f"{self.s['pu_freq']}s", str(self.s["pu_max"]),
                "ON" if self.s["chaos"] else "OFF", f"{self.s['chaos_freq']}s",
                "ON" if self.s["obstacles"] else "OFF", self.speed_label(),
                "ON" if self.s["abilities"] else "OFF", ""]
        for i, (row, val) in enumerate(zip(self.ROWS, vals)):
            y = 228 + i * 31
            sel = i == self.sel and not self.popup
            col = YELLOW if sel else WHITE
            if row == "START MATCH":
                text(s, ">> START MATCH <<" if sel else "START MATCH", 36, col, (W / 2, y + 10))
            else:
                text(s, row, 28, col, (W / 2 - 40, y), "midright")
                shown = val
                if row in self.NUM and sel and self.nbuf:
                    shown = self.nbuf + "_ " + self.NUM[row][3]
                elif row in ("POWER-UPS", "BALL SPEED"):
                    shown = val + ("  [ENTER]" if sel else "")
                elif sel:
                    shown = "< " + val + " >"
                text(s, shown, 28, col, (W / 2 + 40, y), "midleft")

        row = self.ROWS[self.sel]
        if row == "PRESET":
            desc = PRESETS[cur][2] if cur >= 0 else "Your own mix of settings (pick a preset to replace it)"
            text(s, desc, 24, YELLOW, (W / 2, H - 60))
        elif row == "POWER-UPS":
            text(s, "ENTER: choose which rarities of power-up can spawn", 24, YELLOW, (W / 2, H - 60))
        elif row in self.NUM:
            text(s, self.NUM[row][4], 22, YELLOW, (W / 2, H - 60))
        elif row == "BALL SPEED":
            text(s, "ENTER: pick a named speed or type your own (60-4096 px/s, measured at 1080p)", 22,
                 YELLOW, (W / 2, H - 60))
        elif row == "DASH & CHARGE":
            text(s, "OFF = plain paddles: no dash, no charged smash", 24, YELLOW, (W / 2, H - 60))
        elif row in ("LEFT PLAYER", "RIGHT PLAYER"):
            side = 0 if row == "LEFT PLAYER" else 1
            sch = SCHEMES[self.s["left" if side == 0 else "right"]]
            text(s, HELP[f"LANES-{side}" if sch == "LANES" else sch], 24, C_LEFT if side == 0 else C_RIGHT,
                 (W / 2, H - 60))
        text(s, f"v{VERSION}  {VERSION_NAME}", 20, GREY, (W - 16, 14), "topright")
        text(s, "UP/DOWN select | LEFT/RIGHT change | type numbers | ENTER start | P pause | M mute | F11 fullscreen",
             20, GREY, (W / 2, H - 24))
        if self.popup == "rar":
            self.draw_popup(s)
        elif self.popup == "speed":
            self.draw_speed_popup(s)

    def draw_speed_popup(self, s):
        n = len(SPEED_PRESETS)
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 200))
        s.blit(veil, (0, 0))
        panel = pygame.Rect(W // 2 - 400, 50, 800, 600)
        pygame.draw.rect(s, (14, 18, 38), panel, border_radius=14)
        pygame.draw.rect(s, GREY, panel, 2, border_radius=14)
        text(s, "BALL SPEED", 44, WHITE, (W / 2, 90))
        text(s, "pixels per second, measured at 1080p (scaled to your screen)", 20, GREY, (W / 2, 124))
        step, y0 = 40, 170
        for i in range(n + 1):
            y = y0 + i * step
            sel = i == self.ssel
            if sel:
                pygame.draw.rect(s, (30, 36, 70), (panel.x + 20, y - 19, panel.w - 40, 38), border_radius=8)
            if i < n:
                name, v = SPEED_PRESETS[i]
                col = lerp_col((90, 200, 255), (255, 80, 80), math.log(v / SPEED_MIN) / math.log(SPEED_MAX / SPEED_MIN))
                if v == self.s["speed"]:
                    pygame.draw.circle(s, YELLOW, (panel.x + 44, y), 6)
                text(s, name, 30, YELLOW if sel else col, (panel.x + 66, y), "midleft")
                text(s, f"{v} px/s", 28, WHITE, (panel.x + 400, y), "midright")
                text(s, f"crosses the screen in {1920 / v:.2f}s", 18, GREY, (panel.right - 36, y), "midright")
            else:
                text(s, "CUSTOM", 30, YELLOW if sel else WHITE, (panel.x + 66, y), "midleft")
                box = pygame.Rect(panel.x + 270, y - 16, 130, 32)
                pygame.draw.rect(s, (10, 12, 26), box, border_radius=6)
                pygame.draw.rect(s, YELLOW if sel else GREY, box, 2, border_radius=6)
                shown = self.sbuf + ("_" if sel and int(self.t * 2) % 2 == 0 else "")
                text(s, shown, 28, WHITE, (box.right - 10, y), "midright")
                text(s, f"{SPEED_MIN} - {SPEED_MAX}", 18, GREY, (panel.right - 36, y), "midright")
        text(s, "UP/DOWN move | ENTER choose | type digits for a custom speed | ESC cancel", 18, GREY,
             (W / 2, panel.bottom - 28))

    def draw_popup(self, s):
        n = len(RARITIES)
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 200))
        s.blit(veil, (0, 0))
        panel = pygame.Rect(W // 2 - 400, 50, 800, 600)
        pygame.draw.rect(s, (14, 18, 38), panel, border_radius=14)
        pygame.draw.rect(s, GREY, panel, 2, border_radius=14)
        text(s, "POWER-UP RARITIES", 44, WHITE, (W / 2, 92))
        odds = rarity_odds(self.s["rar"], self.s["keep_rarity"])
        step, y0 = 42, 150
        for i in range(n + 4):
            y = y0 + i * step
            sel = i == self.psel
            if sel:
                pygame.draw.rect(s, (30, 36, 70), (panel.x + 20, y - 19, panel.w - 40, 38), border_radius=8)
            col = YELLOW if sel else WHITE
            if i in (0, 1):
                text(s, "SELECT ALL" if i == 0 else "DESELECT ALL", 30, col, (panel.x + 56, y), "midleft")
            elif i == n + 3:
                text(s, "DONE", 32, col, (W / 2, y))
            else:
                if i <= n + 1:
                    idx = i - 2
                    name, rc, _, glowy = RARITIES[idx]
                    checked = self.s["rar"][idx]
                    label, lcol = name, rc
                    if glowy:
                        s.blit(glow(28, rc), (panel.x + 72 - 28, y - 28))
                else:
                    checked, label, lcol = self.s["keep_rarity"], "KEEP RARITY", col
                box = pygame.Rect(0, 0, 24, 24)
                box.center = (panel.x + 72, y)
                pygame.draw.rect(s, (10, 12, 26), box, border_radius=4)
                pygame.draw.rect(s, lcol, box, 2, border_radius=4)
                if checked:
                    pygame.draw.lines(s, lcol, False, [(box.x + 5, box.y + 12), (box.x + 10, box.y + 18),
                                                       (box.x + 19, box.y + 6)], 3)
                text(s, label, 30, lcol, (panel.x + 100, y), "midleft")
                if i <= n + 1:
                    items = ", ".join(POWERUPS[k][0] for k in TIERS[idx]) or "(no power-ups yet)"
                    text(s, items, 16, GREY, (panel.x + 290, y), "midleft")
                    pct = odds[idx]
                    text(s, f"{pct:.1f}%" if pct > 0 else "-", 26, lcol if pct > 0 else GREY,
                         (panel.right - 36, y), "midright")
        if self.s["keep_rarity"]:
            wasted = sum(100.0 * RARITIES[i][2] / sum(RARITIES[j][2] for j in range(n) if TIERS[j])
                         for i in range(n) if TIERS[i] and not self.s["rar"][i])
            line1 = "ON: odds stay normal. Rolling an unticked rarity means nothing spawns."
            line2 = f"{wasted:.0f}% of spawn rolls currently produce nothing."
        else:
            line1 = "OFF: spawns are spread evenly across the ticked rarities."
            line2 = "UP/DOWN move | ENTER or LEFT/RIGHT tick | ESC or DONE closes"
        text(s, line1, 18, GREY, (W / 2, panel.bottom - 40))
        text(s, line2, 18, GREY, (W / 2, panel.bottom - 20))


# --------------------------------------------------------------------------- main
def main():
    breadcrumb("---- start | v%s | python %s | pygame %s" % (VERSION, sys.version.split()[0], pygame.version.ver))
    pygame.init()
    breadcrumb("pygame.init done")
    pygame.display.set_caption(f"Overcomplicated Pong v{VERSION} - {VERSION_NAME}")
    def open_window(full):
        if full:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        return pygame.display.set_mode((W, H), pygame.RESIZABLE)

    fullscreen = False
    screen = open_window(False)
    breadcrumb("window created")
    clock = pygame.time.Clock()
    canvas = pygame.Surface((W, H))
    sfx = Sfx()
    pygame.joystick.init()
    menu = Menu()
    state, game = "menu", None
    breadcrumb("entering main loop")

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 1 / 30)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                breadcrumb("exit: window close / QUIT event")
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_m:
                    sfx.muted = not sfx.muted
                elif e.key == pygame.K_F11:
                    try:
                        fullscreen = not fullscreen
                        open_window(fullscreen)
                    except pygame.error:
                        fullscreen = False
                        open_window(False)
                if state == "menu":
                    r = menu.key(e.key)
                    sfx.play("menu")
                    if r == "start":
                        game, state = Game(menu.s, sfx), "play"
                    elif r == "quit":
                        breadcrumb("exit: ESC on menu")
                        pygame.quit()
                        return
                elif state == "play":
                    game.keydowns.add(e.key)
                    if e.key in (pygame.K_p, pygame.K_ESCAPE):
                        state = "pause"
                elif state == "pause":
                    if e.key in (pygame.K_p, pygame.K_RETURN, pygame.K_SPACE):
                        state = "play"
                    elif e.key == pygame.K_ESCAPE:
                        state = "menu"
                        menu.reroll_splash()
                    elif e.key == pygame.K_r:
                        game, state = Game(menu.s, sfx), "play"
                elif state == "over":
                    if e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                        game, state = Game(menu.s, sfx), "play"
                    elif e.key == pygame.K_ESCAPE:
                        state = "menu"
                        menu.reroll_splash()
            elif e.type == pygame.MOUSEBUTTONDOWN and state == "play":
                game.mousedowns.add(e.button)

        if state == "menu":
            menu.draw(canvas, dt)
        else:
            if state == "play":
                game.update(dt, pygame.key.get_pressed())
                if game.winner is not None:
                    state = "over"
            game.draw(canvas)
            if state == "pause":
                veil = pygame.Surface((W, H), pygame.SRCALPHA)
                veil.fill((0, 0, 0, 150))
                canvas.blit(veil, (0, 0))
                text(canvas, "PAUSED", 100, WHITE, (W / 2, H / 2 - 30))
                text(canvas, "P / ENTER resume | R restart | ESC menu", 28, GREY, (W / 2, H / 2 + 40))
            elif state == "over":
                veil = pygame.Surface((W, H), pygame.SRCALPHA)
                veil.fill((0, 0, 0, 160))
                canvas.blit(veil, (0, 0))
                col = C_LEFT if game.winner == 0 else C_RIGHT
                text(canvas, ("LEFT" if game.winner == 0 else "RIGHT") + " PLAYER WINS", 90, col, (W / 2, H / 2 - 40))
                text(canvas, f"{game.paddles[0].score} - {game.paddles[1].score}   |   longest rally: {game.best_rally}",
                     32, WHITE, (W / 2, H / 2 + 30))
                text(canvas, "ENTER rematch | ESC menu", 28, GREY, (W / 2, H / 2 + 80))

        sh = game.shake if (game and state in ("play", "pause")) else 0
        screen = pygame.display.get_surface()
        sw, sh_px = screen.get_size()
        scale = min(sw / W, sh_px / H)
        dw, dh = int(W * scale), int(H * scale)
        if dw < 2 or dh < 2:  # minimised
            continue
        ox, oy = (sw - dw) // 2, (sh_px - dh) // 2
        VIEW.update(scale=scale, ox=ox, oy=oy)
        frame = canvas if (dw, dh) == (W, H) else pygame.transform.smoothscale(canvas, (dw, dh))
        shx, shy = (random.uniform(-sh, sh), random.uniform(-sh, sh)) if sh > 0.5 else (0, 0)
        screen.fill((0, 0, 0))
        screen.blit(frame, (ox + shx * scale, oy + shy * scale))
        pygame.display.flip()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        err = traceback.format_exc()
        print(err)
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pong_crash.log"), "w") as fh:
                fh.write(err)
        except OSError:
            pass
        input("\nThe game crashed (details above, also saved to pong_crash.log). Press Enter to close...")
