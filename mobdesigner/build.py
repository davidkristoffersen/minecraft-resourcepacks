#!/usr/bin/env python3
"""
Build MobDesigner: a look for every designed mob of the CustomDifficulty Mob Designer, and a
spawn egg for each, needing no mods.

What the plugin can and cannot do to a mob's look
-------------------------------------------------
A vanilla client draws a zombie from one texture and nothing the server sends can pick another
per entity - there is no "custom skin" for a monster. What the client DOES draw per entity is the
armour layer: every item in an armour slot that carries an `equippable` component with an
`asset_id` is rendered over the mob as `assets/<ns>/equipment/<id>.json` says, with textures of
its own, inflated a pixel over the body (the hat part half a pixel more). So a designed mob's
"skin" is a costume: the plugin puts a carrier item with `equippable {slot, asset_id:
mobdesigner:<variant>}` into every empty armour slot of a humanoid design (zombie, husk, drowned,
skeleton and their kin - creepers have no armour layer at all), and this pack draws the costume.

  assets/mobdesigner/equipment/<variant>.json        humanoid + humanoid_baby + humanoid_leggings layers
  assets/mobdesigner/textures/entity/equipment/humanoid/<variant>.png          head, body, arms, boots
  assets/mobdesigner/textures/entity/equipment/humanoid_baby/<variant>.png     the same sheet, for baby zombies
  assets/mobdesigner/textures/entity/equipment/humanoid_leggings/<variant>.png legs and belt

An unknown asset id renders nothing (EquipmentAssetManager.get falls back to an empty
definition, read from the 26.2 client), so without the pack the mob simply looks like its
vanilla self. The sheets are the 64x32 armour layout (head at 0,0, hat at 32,0, body at 16,16,
arm at 40,16, leg at 0,16; the left limbs mirror the right); anything left transparent shows
the mob's own skin through it, which is why a costume can be a hood, a coat and boots and still
fit a zombie, a husk and a drowned alike. Painted pixels are solid - the layer is a cutout, so
there is no translucent wash, and a tinted face is the mob's own head copied and recoloured.

The eggs
--------
A variant's egg is the vanilla spawn egg of its base mob with `custom_model_data` strings[0] =
the variant id. The pack overrides the five item definitions (zombie, husk, drowned, skeleton,
creeper eggs) with a `select` on that string and the running client's own definition as the
fallback, so a real egg is untouched and a client without the pack sees a plain egg called by
the design's name. Every variant's case is in all five definitions: which egg the plugin picks
is then its business, and the picture is always that variant's.

  assets/minecraft/items/<mob>_spawn_egg.json
  assets/mobdesigner/models/item/egg/<variant>.json
  assets/mobdesigner/textures/item/egg/<variant>.png

26.2's eggs are little portraits of the mob, so each variant egg is its base portrait with the
skin, clothes and trousers recoloured by luminance (shading kept), the costume's strongest
piece drawn over it (a hood, a mask, glowing eyes) and a badge of its emblem in the corner.

Art
---
`VARIANTS` below: one entry per design, a list of costume features (functions in the feature
library, each painting one part of the two sheets) and the egg's colours and badge. Emblems and
badges are the small `GLYPHS`. `preview.png` next to this script shows every egg at 4x beside a
front view of the dressed mob at 3x - look at it after every change. `bump.py mobdesigner minor`
for a new design or feature, patch for a redraw.

Building
--------
`python3 build.py` writes `src/`, `MobDesigner-<v>.zip` and `preview.png`. Shared code in
`../themelib.py`. Keep `VARIANTS` in step with `Skins.SKINS` in the CustomDifficulty plugin -
that list is how the plugin knows which variants have a costume to wear.
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import themelib as T  # noqa: E402

NAME = "MobDesigner"
VERSION = "1.0.0"         # bumped with ../bump.py, never by hand
NS = "mobdesigner"

# ---------------------------------------------------------------- pixels

def clamp(v):
    return 0 if v < 0 else 255 if v > 255 else int(round(v))


def shade(c, f):
    return (clamp(c[0] * f), clamp(c[1] * f), clamp(c[2] * f))


def blank(w, h):
    return (w, h, [bytearray(w * 4) for _ in range(h)])


def put(img, x, y, c):
    w, h, rows = img
    if 0 <= x < w and 0 <= y < h:
        rows[y][x * 4:x * 4 + 4] = bytes((c[0], c[1], c[2], 255))


def get(img, x, y):
    w, h, rows = img
    if 0 <= x < w and 0 <= y < h:
        return tuple(rows[y][x * 4:x * 4 + 4])
    return (0, 0, 0, 0)


def rect(img, x0, y0, w, h, c):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            put(img, x, y, c)


def face(img, r, c, rows=None, cols=None):
    """Paint one box face (x, y, w, h) with a little vertical shading so it reads as cloth, not a
    flat blob: lighter at the top, darker at the bottom, a darker last column for depth. `rows` and
    `cols` limit it to a slice of the face (relative to the face)."""
    x0, y0, w, h = r
    rows = range(h) if rows is None else [y for y in rows if 0 <= y < h]
    cols = range(w) if cols is None else [x for x in cols if 0 <= x < w]
    for y in rows:
        f = 1.10 - 0.22 * (y / max(1, h - 1))
        for x in cols:
            g = f * (0.93 if x == w - 1 else 1.0)
            put(img, x0 + x, y0 + y, shade(c, g))


def lum(px):
    return 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]


def noise(seed):
    """Deterministic pseudo-random 0..1 stream - the same art on every build (same sha1)."""
    state = seed * 1103515245 + 12345

    def nxt():
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return state / 0x7FFFFFFF
    return nxt


# ---------------------------------------------------------------- humanoid armour layout (64x32)

def faces(u, v, w, h, d):
    return {
        "top": (u + d, v, w, d),
        "bottom": (u + d + w, v, w, d),
        "right": (u, v + d, d, h),
        "front": (u + d, v + d, w, h),
        "left": (u + d + w, v + d, d, h),
        "back": (u + d + w + d, v + d, w, h),
    }


HEAD = faces(0, 0, 8, 8, 8)
HAT = faces(32, 0, 8, 8, 8)
BODY = faces(16, 16, 8, 12, 4)
ARM = faces(40, 16, 4, 12, 4)
LEG = faces(0, 16, 4, 12, 4)
SIDES = ("right", "front", "left", "back")
SHEET_W, SHEET_H = 64, 32


class Sheets:
    """The two textures a costume is: `outer` (helmet, chest, boots - the humanoid layer) and
    `inner` (leggings). Features paint into these."""

    def __init__(self):
        self.outer = blank(SHEET_W, SHEET_H)
        self.inner = blank(SHEET_W, SHEET_H)


# ---------------------------------------------------------------- feature library
# every feature is  lambda s: ...  painting into s.outer / s.inner

def hood(c, brow=2):
    def f(s):
        for side in ("top", "right", "left", "back"):
            face(s.outer, HAT[side], c)
        face(s.outer, HAT["front"], c, rows=range(brow))
    return f


def cap(c, depth=3):
    def f(s):
        face(s.outer, HAT["top"], c)
        for side in SIDES:
            face(s.outer, HAT[side], c, rows=range(depth))
    return f


def band(c, rows=(2, 3)):
    def f(s):
        for side in SIDES:
            face(s.outer, HAT[side], c, rows=range(rows[0], rows[1] + 1))
    return f


def crown(c, jewel=None):
    def f(s):
        for side in SIDES:
            face(s.outer, HAT[side], c, rows=range(1, 3))
            for x in range(0, 8, 2):
                put(s.outer, HAT[side][0] + x, HAT[side][1], shade(c, 1.15))
        if jewel:
            put(s.outer, HAT["front"][0] + 3, HAT["front"][1] + 1, jewel)
            put(s.outer, HAT["front"][0] + 4, HAT["front"][1] + 1, jewel)
    return f


def hair(c, peak=True):
    """Slicked-back hair on the hat layer: top, back, upper sides, one row of fringe with a
    widow's peak."""
    def f(s):
        face(s.outer, HAT["top"], c)
        face(s.outer, HAT["back"], c, rows=range(5))
        for side in ("right", "left"):
            face(s.outer, HAT[side], c, rows=range(3))
        face(s.outer, HAT["front"], c, rows=range(1))
        if peak:
            put(s.outer, HAT["front"][0] + 3, HAT["front"][1] + 1, c)
            put(s.outer, HAT["front"][0] + 4, HAT["front"][1] + 1, c)
    return f


def helm(c, brow=3, rivets=None):
    """A close helmet on the head layer: everything but the face below the brow."""
    def f(s):
        for side in ("top", "right", "left", "back"):
            face(s.outer, HEAD[side], c)
        face(s.outer, HEAD["front"], c, rows=range(brow))
        if rivets:
            for x in (1, 6):
                put(s.outer, HEAD["front"][0] + x, HEAD["front"][1] + brow - 1, rivets)
    return f


def mask(c, top=4, dots=None):
    """A bandana over the lower face and round the sides."""
    def f(s):
        for side in ("right", "front", "left"):
            face(s.outer, HEAD[side], c, rows=range(top, 8))
        face(s.outer, HEAD["back"], c, rows=range(top, 6))
        if dots:
            for x in (1, 4, 7):
                put(s.outer, HEAD["front"][0] + x, HEAD["front"][1] + top + 1, dots)
                put(s.outer, HEAD["front"][0] + x - 1 if x > 0 else 0, HEAD["front"][1] + top + 3, dots)
    return f


def eyes(c, glow=None):
    """The eye pixels of a humanoid face, painted over on the head layer (a pixel out, so they
    cover the mob's own)."""
    def f(s):
        x0, y0 = HEAD["front"][0], HEAD["front"][1]
        for x in (1, 2, 5, 6):
            put(s.outer, x0 + x, y0 + 4, c)
        if glow:
            for x in (1, 6):
                put(s.outer, x0 + x, y0 + 4, glow)
    return f


def face_pixels(points, c):
    def f(s):
        for x, y in points:
            put(s.outer, HEAD["front"][0] + x, HEAD["front"][1] + y, c)
    return f


def head_paint(c):
    """The whole head solid - for a shadow."""
    def f(s):
        for side in ("top", "bottom", "right", "front", "left", "back"):
            face(s.outer, HEAD[side], c)
    return f


def head_copy(mob, tint=None, strength=1.0, keep_eyes=True):
    """The base mob's own head, recoloured: luminance kept, hue and saturation from `tint`."""
    def f(s):
        src = MOB_SKINS[mob]
        for side in ("top", "bottom", "right", "front", "left", "back"):
            x0, y0, w, h = HEAD[side]
            for y in range(h):
                for x in range(w):
                    px = get(src, x0 + x, y0 + y)
                    if px[3] == 0:
                        continue
                    if tint is None:
                        c = px[:3]
                    else:
                        i = lum(px) / 255
                        c = tuple(clamp(t * i * 1.15) for t in tint)
                        c = tuple(clamp(a * strength + b * (1 - strength)) for a, b in zip(c, px[:3]))
                    if keep_eyes and side == "front" and y == 4 and x in (1, 2, 5, 6):
                        c = px[:3]
                    put(s.outer, x0 + x, y0 + y, c)
    return f


def vest(c, rows=(0, 12), sides=True, back=True):
    def f(s):
        face(s.outer, BODY["front"], c, rows=range(rows[0], rows[1]))
        if back:
            face(s.outer, BODY["back"], c, rows=range(rows[0], rows[1]))
        if sides:
            for side in ("right", "left"):
                face(s.outer, BODY[side], c, rows=range(rows[0], rows[1]))
        if rows[0] == 0:
            face(s.outer, BODY["top"], c)
    return f


def coat(c):
    return vest(c)


def cape(c, lining=None):
    """A cape: the back of the body and the tops of the shoulders; an optional lining shows as a
    stripe down each edge of the front."""
    def f(s):
        face(s.outer, BODY["back"], c)
        face(s.outer, BODY["top"], c)
        face(s.outer, ARM["top"], c)
        for side in ("right", "left"):
            face(s.outer, BODY[side], c, cols=range(3, 4))
        if lining:
            face(s.outer, BODY["front"], lining, cols=range(0, 1))
            face(s.outer, BODY["front"], lining, cols=range(7, 8))
    return f


def shoulders(c, depth=2):
    def f(s):
        face(s.outer, ARM["top"], c)
        for side in SIDES:
            face(s.outer, ARM[side], c, rows=range(depth))
    return f


def sleeves(c, rows=(0, 12)):
    def f(s):
        for side in SIDES:
            face(s.outer, ARM[side], c, rows=range(rows[0], rows[1]))
        if rows[0] == 0:
            face(s.outer, ARM["top"], c)
    return f


def gloves(c, height=3):
    def f(s):
        for side in SIDES:
            face(s.outer, ARM[side], c, rows=range(12 - height, 12))
        face(s.outer, ARM["bottom"], c)
    return f


def boots(c, height=4, sole=None):
    def f(s):
        for side in SIDES:
            face(s.outer, LEG[side], c, rows=range(12 - height, 12))
            if sole:
                face(s.outer, LEG[side], sole, rows=range(11, 12))
        face(s.outer, LEG["bottom"], sole or c)
    return f


def pants(c, belt=None):
    """Leggings: the legs on the inner sheet, a belt round the waist."""
    def f(s):
        for side in SIDES + ("top", "bottom"):
            face(s.inner, LEG[side], c)
        if belt:
            for side in SIDES:
                face(s.inner, BODY[side], belt, rows=range(10, 12))
    return f


def belt(c, buckle=None):
    def f(s):
        for side in SIDES:
            face(s.inner, BODY[side], c, rows=range(10, 12))
        if buckle:
            put(s.inner, BODY["front"][0] + 3, BODY["front"][1] + 10, buckle)
            put(s.inner, BODY["front"][0] + 4, BODY["front"][1] + 10, buckle)
    return f


def stripes(part, c1, c2, sheet="outer", rows=(0, 12), every=2):
    def f(s):
        img = s.outer if sheet == "outer" else s.inner
        for side in SIDES:
            for y in range(rows[0], rows[1]):
                face(img, part[side], c1 if (y // every) % 2 == 0 else c2, rows=range(y, y + 1))
    return f


def half(part, c_left, c_right, seam=None):
    """Two colours split down the middle of the front and back."""
    def f(s):
        for side in ("front", "back"):
            x0, y0, w, h = part[side]
            face(s.outer, part[side], c_left, cols=range(w // 2))
            face(s.outer, part[side], c_right, cols=range(w // 2, w))
            if seam:
                for y in range(h):
                    put(s.outer, x0 + w // 2 - 1 + (y % 2), y0 + y, seam)
        face(s.outer, part["right"], c_left)
        face(s.outer, part["left"], c_right)
        face(s.outer, part["top"], c_left, cols=range(part["top"][2] // 2))
        face(s.outer, part["top"], c_right, cols=range(part["top"][2] // 2, part["top"][2]))
    return f


def speckle(parts, colours, seed, density=0.18, sheet="outer", rows=None):
    """Random dots over the given parts' side faces - boils, scales, embers."""
    def f(s):
        img = s.outer if sheet == "outer" else s.inner
        rnd = noise(seed)
        for part in parts:
            for side in SIDES:
                x0, y0, w, h = part[side]
                for y in range(h):
                    if rows is not None and y not in rows:
                        continue
                    for x in range(w):
                        r = rnd()
                        if r < density:
                            put(img, x0 + x, y0 + y, colours[int(rnd() * len(colours)) % len(colours)])
    return f


def scales(parts, dark, light, sheet="outer"):
    def f(s):
        img = s.outer if sheet == "outer" else s.inner
        for part in parts:
            for side in SIDES + ("top",):
                x0, y0, w, h = part[side]
                for y in range(h):
                    for x in range(w):
                        put(img, x0 + x, y0 + y, light if (x + y) % 2 == 0 else dark)
    return f


def rainbow(parts, sheet="outer", start=0):
    colours = [(230, 60, 60), (240, 150, 40), (240, 230, 60), (70, 200, 80), (60, 130, 240), (150, 70, 220)]

    def f(s):
        img = s.outer if sheet == "outer" else s.inner
        for part in parts:
            for side in SIDES + ("top", "bottom"):
                x0, y0, w, h = part[side]
                for y in range(h):
                    face(img, part[side], colours[(y // 2 + start) % len(colours)], rows=range(y, y + 1))
    return f


def seam(c):
    """A stitched line down the middle of head and body - something sewn together."""
    def f(s):
        for part in (HEAD, BODY):
            for side in ("front", "back"):
                x0, y0, w, h = part[side]
                for y in range(h):
                    put(s.outer, x0 + w // 2 - 1 + (y % 2), y0 + y, c)
    return f


def emblem(glyph, c, hi=None, at=(1, 3), sheet="outer"):
    """A small glyph on the chest."""
    def f(s):
        img = s.outer if sheet == "outer" else s.inner
        draw_glyph(img, BODY["front"][0] + at[0], BODY["front"][1] + at[1], glyph, c, hi)
    return f


def paint(part, side, c, rows=None, cols=None, sheet="outer"):
    def f(s):
        img = s.outer if sheet == "outer" else s.inner
        face(img, part[side], c, rows=rows, cols=cols)
    return f


# ---------------------------------------------------------------- glyphs (# = colour, + = highlight)

GLYPHS = {
    "bow": ["..#...", ".#.#..", "#..+#.", "#..+.#", ".#.#..", "..#..."],
    "eye": [".####.", "#.##.#", "#+##.#", ".####.", "......", "......"],
    "heart": [".#..#.", "#+####", "######", ".####.", "..##..", "......"],
    "target": [".####.", "#....#", "#.##.#", "#.##.#", "#....#", ".####."],
    "skull": [".####.", "#.##.#", "######", ".####.", ".#.#..", "......"],
    "bomb": ["....+.", "...#..", ".####.", "######", "######", ".####."],
    "spider": ["#.##.#", ".####.", "#+##+#", ".####.", "#.##.#", "......"],
    "chevron": ["#....#", ".#..#.", "..##..", "#....#", ".#..#.", "..##.."],
    "star": ["..#...", "..#...", "#####.", ".###..", ".#.#..", "#...#."],
    "bat": ["#....#", "##..##", "######", ".#..#.", "......", "......"],
    "anvil": ["######", ".####.", "..##..", "..##..", ".####.", "######"],
    "bio": [".#..#.", "######", ".#..#.", "..##..", "..##..", "......"],
    "wave": ["......", "#.....", "##.##.", ".###.#", "..#...", "......"],
    "flame": ["..#...", ".##+..", "#+##..", "####+.", ".###..", "..#..."],
    "bag": ["..##..", ".#..#.", "######", "#+###.", "######", ".####."],
    "question": [".###..", "#...#.", "...#..", "..#...", "......", "..#..."],
    "bolt": ["...##.", "..##..", ".####.", "...#..", "..#...", ".#...."],
    "mute": ["#.#...", "##.#.#", "##.##.", "##.#.#", "#.#...", "......"],
    "split": ["#....#", "##..##", "###.##", "##..##", "#....#", "......"],
    "fist": [".####.", "######", "######", ".####.", "......", "......"],
    "baby": ["..##..", ".#..#.", ".#.+#.", "..##..", ".####.", "......"],
    "hex": ["..##..", ".#..#.", "#.##.#", "#.##.#", ".#..#.", "..##.."],
    "hourglass": ["####..", ".##...", "..#...", ".##...", "####..", "......"],
}


def draw_glyph(img, x0, y0, glyph, c, hi=None, outline=None):
    rows = GLYPHS[glyph]
    if outline:
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in "#+":
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nx, ny = x + dx, y + dy
                        if not (0 <= ny < len(rows) and 0 <= nx < len(row) and row_at(rows, nx, ny) in "#+"):
                            put(img, x0 + nx, y0 + ny, outline)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                put(img, x0 + x, y0 + y, c)
            elif ch == "+":
                put(img, x0 + x, y0 + y, hi or shade(c, 1.35))


def row_at(rows, x, y):
    return rows[y][x] if 0 <= y < len(rows) and 0 <= x < len(rows[y]) else "."


# ---------------------------------------------------------------- colours

BLACK = (18, 16, 20)
SOOT = (34, 30, 34)
IRON = (140, 144, 150)
DARK_IRON = (78, 82, 90)
GOLD = (222, 180, 60)
LEATHER = (110, 72, 38)
DARK_LEATHER = (70, 44, 24)
BONE = (200, 198, 190)
FOREST = (44, 92, 40)
MOSS = (88, 128, 60)
TEAL = (30, 140, 140)
CYAN = (60, 220, 230)
AQUA = (0, 200, 200)
MAGENTA = (220, 40, 220)
VIOLET = (72, 30, 110)
PURPLE = (108, 44, 160)
BLOOD = (140, 12, 20)
RED = (200, 40, 40)
ORANGE = (240, 120, 30)
EMBER = (255, 190, 60)
WHITE = (240, 240, 236)
PALE = (206, 210, 200)
PINK = (240, 150, 190)
BABY_BLUE = (150, 200, 240)
YELLOW = (240, 220, 80)
OLIVE = (96, 104, 44)
SICK = (150, 200, 40)
MUD = (86, 70, 46)
NAVY = (32, 44, 90)
SLATE = (60, 66, 80)

# ---------------------------------------------------------------- the designs
# id: dict(mob=base mob for the doll and the egg portrait, features=[...], egg=dict(...))
#   egg: skin / cloth / pants = the portrait's three colour classes recoloured (None = as vanilla),
#        over=[egg overlays], badge=(glyph, colour)

VARIANTS = {
    "archer": dict(mob="zombie", features=[
        hood(FOREST), vest(DARK_LEATHER, rows=(0, 12), sides=False, back=False), emblem("bow", GOLD),
        paint(BODY, "front", LEATHER, cols=range(5, 7)), gloves(LEATHER), boots(LEATHER, sole=DARK_LEATHER),
        pants(MOSS, belt=DARK_LEATHER),
    ], egg=dict(skin=None, cloth=DARK_LEATHER, pants=MOSS, over=[("hood", FOREST)], badge=("bow", GOLD))),

    "blinker": dict(mob="zombie", features=[
        eyes(MAGENTA, glow=(255, 150, 255)), cape(VIOLET, lining=MAGENTA), hood(VIOLET, brow=1),
        gloves(VIOLET), boots(VIOLET, sole=MAGENTA), pants((50, 20, 80)),
    ], egg=dict(skin=None, cloth=VIOLET, pants=(50, 20, 80), over=[("hood", VIOLET), ("eyes", MAGENTA)],
                badge=("eye", MAGENTA))),

    "baby-army": dict(mob="zombie", features=[
        cap(BABY_BLUE, depth=4), vest(YELLOW, rows=(0, 6), sides=False, back=False), emblem("baby", WHITE, at=(1, 0)),
        boots(WHITE, height=2, sole=BABY_BLUE), pants(BABY_BLUE),
    ], egg=dict(skin=None, cloth=YELLOW, pants=BABY_BLUE, over=[("cap", BABY_BLUE)], badge=("baby", WHITE))),

    "splitter": dict(mob="zombie", features=[
        half(BODY, TEAL, OLIVE, seam=BLACK), half(ARM, TEAL, OLIVE), seam(BLACK),
        face_pixels([(1, 4), (2, 4)], YELLOW), face_pixels([(5, 4), (6, 4)], RED),
        boots(TEAL, height=3), pants(OLIVE, belt=BLACK),
    ], egg=dict(skin=None, cloth=TEAL, pants=OLIVE, over=[("seam", BLACK)], badge=("split", WHITE))),

    "pacifist": dict(mob="zombie", features=[
        crown(MOSS), paint(HAT, "top", PINK, rows=range(0, 1), cols=range(1, 3)),
        paint(HAT, "top", YELLOW, rows=range(0, 1), cols=range(5, 7)),
        paint(HAT, "front", PINK, rows=range(1, 2), cols=range(1, 2)), paint(HAT, "front", WHITE, rows=range(1, 2), cols=range(6, 7)),
        paint(HAT, "back", YELLOW, rows=range(1, 2), cols=range(3, 4)),
        vest(PINK, sides=True), emblem("heart", WHITE, RED), boots(WHITE, height=3), pants((120, 170, 120)),
    ], egg=dict(skin=None, cloth=PINK, pants=(120, 170, 120), over=[("band", MOSS)], badge=("heart", WHITE))),

    "armored-archer": dict(mob="zombie", features=[
        helm(DARK_IRON, brow=3, rivets=IRON), eyes((230, 60, 60)), vest(SLATE), emblem("target", RED, WHITE),
        shoulders(DARK_IRON), gloves(DARK_LEATHER), boots(DARK_IRON, sole=BLACK), pants(NAVY, belt=DARK_LEATHER),
    ], egg=dict(skin=None, cloth=SLATE, pants=NAVY, over=[("helm", DARK_IRON)], badge=("target", RED))),

    "brute": dict(mob="zombie", features=[
        head_copy("zombie", tint=(180, 60, 50), strength=0.85), eyes((255, 230, 120)),
        face_pixels([(0, 1), (1, 2), (2, 3), (6, 6), (7, 7)], (235, 150, 140)),
        shoulders(DARK_IRON, depth=3), paint(ARM, "top", IRON), belt(DARK_LEATHER, buckle=GOLD),
        boots(DARK_IRON, sole=BLACK), pants((70, 30, 30)),
    ], egg=dict(skin=(180, 60, 50), cloth=DARK_IRON, pants=(70, 30, 30), over=[("eyes", (255, 230, 120))],
                badge=("fist", IRON))),

    "spider-rider": dict(mob="skeleton", features=[
        vest(SOOT), emblem("spider", WHITE, RED, at=(1, 2)), paint(BODY, "back", WHITE, rows=range(2, 3)),
        paint(BODY, "back", WHITE, rows=range(6, 7)), paint(BODY, "back", WHITE, cols=range(3, 4)),
        gloves(DARK_LEATHER), boots(DARK_LEATHER, sole=BLACK), pants(SOOT, belt=RED),
    ], egg=dict(skin=None, cloth=SOOT, pants=SOOT, over=[], badge=("spider", WHITE))),

    "swift": dict(mob="zombie", features=[
        band(AQUA, rows=(2, 3)), vest(WHITE), paint(BODY, "front", AQUA, cols=range(0, 2)),
        paint(BODY, "back", AQUA, cols=range(0, 2)), emblem("chevron", AQUA, at=(1, 3)),
        sleeves(AQUA, rows=(0, 4)), boots(AQUA, height=3, sole=WHITE), pants(WHITE, belt=AQUA),
    ], egg=dict(skin=None, cloth=WHITE, pants=WHITE, over=[("band", AQUA)], badge=("chevron", AQUA))),

    "warlock": dict(mob="skeleton", features=[
        hood(VIOLET, brow=2), coat(PURPLE), paint(BODY, "front", GOLD, cols=range(0, 1)),
        paint(BODY, "front", GOLD, cols=range(7, 8)), emblem("star", GOLD, at=(1, 3)),
        sleeves(PURPLE), gloves(GOLD, height=1), pants(PURPLE, belt=GOLD), paint(LEG, "front", GOLD, rows=range(11, 12), sheet="inner"),
    ], egg=dict(skin=None, cloth=PURPLE, pants=PURPLE, over=[("hood", VIOLET)], badge=("star", GOLD))),

    "vampire": dict(mob="zombie", features=[
        head_copy("zombie", tint=PALE, strength=0.9), eyes(RED, glow=(255, 90, 90)), hair(BLACK),
        vest(WHITE, sides=False, back=False), cape(BLACK, lining=BLOOD), emblem("bat", BLACK, at=(1, 3)),
        sleeves(BLACK), boots(BLACK, sole=SOOT), pants(BLACK, belt=BLOOD),
    ], egg=dict(skin=PALE, cloth=WHITE, pants=BLACK, over=[("hair", BLACK), ("eyes", RED)], badge=("bat", (200, 40, 40)))),

    "stalker": dict(mob="zombie", features=[
        head_paint(BLACK), eyes(WHITE), coat(BLACK), sleeves(BLACK), gloves(SOOT), boots(BLACK), pants(BLACK),
    ], egg=dict(skin=BLACK, cloth=BLACK, pants=BLACK, over=[("eyes", WHITE)], badge=("eye", WHITE))),

    "juggernaut": dict(mob="zombie", features=[
        helm(SLATE, brow=4, rivets=GOLD), eyes((255, 200, 80)), coat(SLATE), shoulders(SLATE, depth=3),
        emblem("anvil", GOLD, at=(1, 3)), gloves(SLATE), boots(SLATE, sole=BLACK),
        pants(SLATE, belt=GOLD), speckle([LEG], [GOLD], seed=7, density=0.08, sheet="inner"),
    ], egg=dict(skin=None, cloth=SLATE, pants=SLATE, over=[("helm", SLATE)], badge=("anvil", GOLD))),

    "plague-bearer": dict(mob="husk", features=[
        eyes(SICK), face_pixels([(0, 2), (3, 1), (7, 3), (2, 6), (6, 7)], SICK),
        vest(OLIVE, rows=(2, 12)), speckle([BODY, ARM], [SICK, (200, 230, 90)], seed=3, density=0.14),
        emblem("bio", SICK, at=(1, 4)), pants((150, 130, 90), belt=MUD),
        speckle([LEG], [MUD], seed=11, density=0.2, sheet="inner"),
    ], egg=dict(skin=None, cloth=OLIVE, pants=(150, 130, 90), over=[("spots", SICK), ("eyes", SICK)], badge=("bio", SICK))),

    "siren": dict(mob="drowned", features=[
        eyes(CYAN, glow=WHITE), crown(FOREST), paint(HAT, "top", FOREST, cols=range(2, 6), rows=range(2, 6)),
        scales([BODY], (20, 90, 100), TEAL), scales([ARM], (20, 90, 100), TEAL), emblem("wave", CYAN, at=(1, 3)),
        boots(TEAL, height=3, sole=(20, 90, 100)), pants((20, 90, 100)),
    ], egg=dict(skin=None, cloth=TEAL, pants=(20, 90, 100), over=[("band", FOREST), ("eyes", CYAN)], badge=("wave", CYAN))),

    "arsonist": dict(mob="skeleton", features=[
        eyes(ORANGE, glow=EMBER), coat(SOOT), sleeves(SOOT), speckle([BODY, ARM], [ORANGE, EMBER, RED], seed=5, density=0.12),
        emblem("flame", ORANGE, EMBER, at=(1, 3)), boots(SOOT, sole=ORANGE), pants(SOOT),
        speckle([LEG], [ORANGE, EMBER], seed=9, density=0.1, sheet="inner"),
    ], egg=dict(skin=(120, 110, 100), cloth=SOOT, pants=SOOT, over=[("eyes", ORANGE), ("embers", EMBER)], badge=("flame", ORANGE))),

    "bandit": dict(mob="zombie", features=[
        mask(RED, top=4, dots=WHITE), vest(SOOT), stripes(BODY, SOOT, (90, 90, 96), rows=(0, 12), every=2),
        emblem("bag", LEATHER, GOLD, at=(1, 3)), gloves(DARK_LEATHER), boots(DARK_LEATHER, sole=BLACK),
        pants(NAVY, belt=DARK_LEATHER),
    ], egg=dict(skin=None, cloth=SOOT, pants=NAVY, over=[("mask", RED)], badge=("bag", GOLD))),

    "wtf": dict(mob="zombie", features=[
        rainbow([HAT]), face_pixels([(1, 4), (2, 4)], PINK), face_pixels([(5, 4), (6, 4)], (60, 220, 80)),
        rainbow([BODY], start=2), rainbow([ARM], start=4), emblem("question", WHITE, at=(1, 3)),
        rainbow([LEG], sheet="inner", start=1), boots((230, 60, 60), height=3), paint(LEG, "left", (60, 130, 240), rows=range(9, 12)),
    ], egg=dict(skin=None, cloth=(240, 150, 40), pants=(150, 70, 220), over=[("cap", (230, 60, 60))], badge=("question", WHITE))),

    # eggs only - a creeper has no armour layer to dress
    "vengeful": dict(mob="zombie", features=None,
                     egg=dict(skin=(150, 60, 40), cloth=BLOOD, pants=SOOT, over=[("eyes", RED)], badge=("fist", RED))),
    "charged-creeper": dict(mob="creeper", features=None,
                            egg=dict(skin=(90, 170, 230), cloth=None, pants=None, over=[], badge=("bolt", (240, 240, 120)))),
    "silent-creeper": dict(mob="creeper", features=None,
                           egg=dict(skin=(120, 130, 120), cloth=None, pants=None, over=[], badge=("mute", WHITE))),
    "boomer": dict(mob="creeper", features=None,
                   egg=dict(skin=(230, 120, 40), cloth=None, pants=None, over=[], badge=("bomb", BLACK))),
    "chaos-creeper": dict(mob="creeper", features=None,
                          egg=dict(skin=(200, 80, 220), cloth=None, pants=None, over=[], badge=("question", WHITE))),
}

MOB_TEXTURES = {"zombie": "entity/zombie/zombie.png", "husk": "entity/zombie/husk.png",
                "drowned": "entity/zombie/drowned.png", "skeleton": "entity/skeleton/skeleton.png",
                "creeper": "entity/creeper/creeper.png"}
MOB_SKINS = {}
EGG_ITEMS = ("zombie", "husk", "drowned", "skeleton", "creeper")


def load_mobs(z):
    for mob, path in MOB_TEXTURES.items():
        img = T.texture(z, path) if z is not None else None
        MOB_SKINS[mob] = img if img is not None else blank(64, 64)


def skins():
    """{variant: Sheets} for every design that has a costume."""
    out = {}
    for vid, spec in VARIANTS.items():
        if not spec["features"]:
            continue
        s = Sheets()
        for feature in spec["features"]:
            feature(s)
        out[vid] = s
    return out


# ---------------------------------------------------------------- eggs

def hue_sat_lum(px):
    r, g, b = px[0] / 255, px[1] / 255, px[2] / 255
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        h = 0
    elif mx == r:
        h = (60 * ((g - b) / d)) % 360
    elif mx == g:
        h = 60 * ((b - r) / d) + 120
    else:
        h = 60 * ((r - g) / d) + 240
    s = 0 if mx == 0 else d / mx
    return h, s, lum(px)


def egg_class(mob, px):
    """Which of a portrait's three areas a pixel belongs to: skin, cloth (shirt), pants."""
    h, s, l = hue_sat_lum(px)
    if mob == "zombie":
        if 150 <= h < 200 and s > 0.5:
            return "cloth"
        if 200 <= h < 300 and s > 0.4:
            return "pants"
        if 60 <= h < 150:
            return "skin"
    elif mob == "husk":
        if l < 50 and s > 0.4:
            return "pants"
        if s < 0.3 and l < 130:
            return "cloth"
        if 25 <= h < 55:
            return "skin"
    elif mob == "drowned":
        if 10 <= h < 40 and s > 0.3:
            return "pants"
        if 60 <= h < 120 and s > 0.6:
            return "cloth"
        if 120 <= h < 200:
            return "skin"
    elif mob == "skeleton":
        if s < 0.15 and l > 100:
            return "skin"
    elif mob == "creeper":
        if 80 <= h < 150 and l > 45:
            return "skin"
    return None


def egg_portrait(z, mob):
    img = T.texture(z, f"item/{mob}_spawn_egg.png") if z is not None else None
    return img if img is not None else blank(16, 16)


def recolour_classes(img, mob, targets):
    """Every pixel of a class repainted in the target colour at its own brightness relative to the
    class's average, so the portrait's shading survives the new colour."""
    w, h, rows = img
    out = blank(w, h)
    sums, counts = {}, {}
    for y in range(h):
        for x in range(w):
            px = get(img, x, y)
            if px[3] == 0:
                continue
            cls = egg_class(mob, px)
            if cls:
                sums[cls] = sums.get(cls, 0) + lum(px)
                counts[cls] = counts.get(cls, 0) + 1
    for y in range(h):
        for x in range(w):
            px = get(img, x, y)
            if px[3] == 0:
                continue
            cls = egg_class(mob, px)
            target = targets.get(cls) if cls else None
            if target is None:
                out[2][y][x * 4:x * 4 + 4] = bytes(px)
                continue
            ref = sums[cls] / counts[cls]
            f = lum(px) / ref if ref else 1.0
            f = 0.55 + 0.45 * f      # flatten a little: a black costume still shows its shape
            c = tuple(clamp(t * f) for t in target)
            put(out, x, y, c)
    return out


def egg_pixels_of(img, mob, cls):
    w, h, _ = img
    return [(x, y) for y in range(h) for x in range(w)
            if get(img, x, y)[3] and egg_class(mob, get(img, x, y)) == cls]


def egg_overlay(img, base, mob, kind, c):
    """The costume's loudest piece, drawn on the 16x16 portrait: the portrait's skin pixels by row."""
    skin = egg_pixels_of(base, mob, "skin")
    if not skin:
        return
    top = min(y for _, y in skin)
    rows = {}
    for x, y in skin:
        rows.setdefault(y, []).append(x)
    eye_row = top + 5
    eyes_at = [(min(rows.get(eye_row, [5])) + 2, eye_row), (max(rows.get(eye_row, [10])) - 2, eye_row)]
    if kind in ("hood", "cap", "helm", "hair"):
        depth = {"hood": 3, "cap": 3, "helm": 3, "hair": 2}[kind]
        for y in range(top, top + depth):
            for x in rows.get(y, []):
                put(img, x, y, shade(c, 1.0 if y > top else 1.12))
        if kind in ("hood", "helm"):
            for y in range(top + depth, top + 8):
                xs = rows.get(y, [])
                if xs:
                    put(img, min(xs), y, c)
                    put(img, max(xs), y, c)
    elif kind == "band":
        y = top + 3
        for x in rows.get(y, []):
            put(img, x, y, c)
    elif kind == "mask":
        for y in range(top + 6, top + 9):
            for x in rows.get(y, []):
                put(img, x, y, c)
    elif kind == "eyes":
        for x, y in eyes_at:
            put(img, x, y, c)
    elif kind == "seam":
        for y in range(top, top + 8):
            xs = rows.get(y, [])
            if xs:
                put(img, (min(xs) + max(xs)) // 2, y, c)
    elif kind in ("spots", "embers"):
        rnd = noise(17)
        for x, y in skin:
            if rnd() < 0.16:
                put(img, x, y, c)


def egg_badge(img, glyph, c):
    """The emblem in the lower right corner, on a dark rounded plate."""
    x0, y0 = 9, 9
    for y in range(7):
        for x in range(7):
            if (x, y) in ((0, 0), (6, 0), (0, 6), (6, 6)):
                continue
            put(img, x0 + x, y0 + y, (24, 22, 28))
    rows = GLYPHS[glyph]
    gw, gh = max(len(r.rstrip(".")) for r in rows), len([r for r in rows if set(r) - {"."}])
    draw_glyph(img, x0 + (7 - min(6, gw)) // 2, y0 + (7 - min(6, gh)) // 2, glyph, c)


def eggs(z):
    out = {}
    for vid, spec in VARIANTS.items():
        mob = spec["mob"]
        base = egg_portrait(z, mob)
        e = spec["egg"]
        img = recolour_classes(base, mob, {"skin": e.get("skin"), "cloth": e.get("cloth"), "pants": e.get("pants")})
        for kind, c in e.get("over", []):
            egg_overlay(img, base, mob, kind, c)
        if e.get("badge"):
            egg_badge(img, *e["badge"])
        out[vid] = img
    return out


# ---------------------------------------------------------------- the doll (preview only)

def doll(mob, sheets, scale=1):
    """A front view of the dressed mob: the base skin's front faces, the leggings, the outer layer,
    the hat. 24x36 at scale 1."""
    w, h = 24, 36
    out = blank(w, h)
    base = MOB_SKINS[mob]
    thin = mob == "skeleton"

    def blit(src, r, dx, dy, mirror=False):
        x0, y0, fw, fh = r
        for y in range(fh):
            for x in range(fw):
                px = get(src, x0 + (fw - 1 - x if mirror else x), y0 + y)
                if px[3]:
                    put(out, dx + x, dy + y, px[:3])

    # the mob itself
    blit(base, HEAD["front"], 8, 0)
    blit(base, BODY["front"], 8, 8)
    if thin:
        blit(base, (44, 20, 2, 12), 6, 8)
        blit(base, (44, 20, 2, 12), 16, 8, mirror=True)
        blit(base, (4, 20, 2, 12), 9, 20)
        blit(base, (4, 20, 2, 12), 13, 20, mirror=True)
    else:
        blit(base, ARM["front"], 4, 8)
        blit(base, ARM["front"], 16, 8, mirror=True)
        blit(base, LEG["front"], 8, 20)
        blit(base, LEG["front"], 12, 20, mirror=True)
    if sheets is not None:
        blit(sheets.inner, LEG["front"], 8, 20)
        blit(sheets.inner, LEG["front"], 12, 20, mirror=True)
        blit(sheets.inner, BODY["front"], 8, 8)
        blit(sheets.outer, BODY["front"], 8, 8)
        blit(sheets.outer, ARM["front"], 4, 8)
        blit(sheets.outer, ARM["front"], 16, 8, mirror=True)
        blit(sheets.outer, LEG["front"], 8, 20)
        blit(sheets.outer, LEG["front"], 12, 20, mirror=True)
        blit(sheets.outer, HEAD["front"], 8, 0)
        blit(sheets.outer, HAT["front"], 8, 0)
    if scale == 1:
        return out
    big = blank(w * scale, h * scale)
    for y in range(h):
        for x in range(w):
            px = get(out, x, y)
            if px[3]:
                rect(big, x * scale, y * scale, scale, scale, px[:3])
    return big


def textures(z=None):
    """Everything drawn, by name - what serverui/previews.py draws from too:
    egg_<id> (16x16), doll_<id> (24x36) and doll_<mob> for the bare mobs."""
    z = z or T.jar()
    load_mobs(z)
    out = {}
    sheets = skins()
    for vid, img in eggs(z).items():
        out[f"egg_{vid}"] = img
    for vid, s in sheets.items():
        out[f"doll_{vid}"] = doll(VARIANTS[vid]["mob"], s)
    for mob in ("zombie", "husk", "drowned", "skeleton"):
        out[f"doll_{mob}"] = doll(mob, None)
    return out


def preview(z, sheets, egg_images, scale=3):
    """Every design: its egg at 4x, the dressed mob at 3x, on dark - preview.png."""
    ids = list(VARIANTS)
    cols = 6
    cell_w, cell_h = 64 + 4 + 24 * scale + 12, 36 * scale + 12
    rows_n = (len(ids) + cols - 1) // cols
    w, h = cols * cell_w + 8, rows_n * cell_h + 8
    img = blank(w, h)
    rect(img, 0, 0, w, h, (28, 28, 34))
    for n, vid in enumerate(ids):
        cx, cy = 8 + (n % cols) * cell_w, 8 + (n // cols) * cell_h
        egg = egg_images[vid]
        for y in range(16):
            for x in range(16):
                px = get(egg, x, y)
                if px[3]:
                    rect(img, cx + x * 4, cy + y * 4, 4, 4, px[:3])
        s = sheets.get(vid)
        d = doll(VARIANTS[vid]["mob"], s, scale)
        for y in range(d[1]):
            for x in range(d[0]):
                px = get(d, x, y)
                if px[3]:
                    put(img, cx + 68 + x, cy + y, px[:3])
    return T.png_encode(*img)


# ---------------------------------------------------------------- pack files

def vanilla_definition(z, item):
    if z is not None:
        return json.loads(z.read(f"assets/minecraft/items/{item}.json"))["model"]
    return {"type": "minecraft:model", "model": f"minecraft:item/{item}"}


def egg_definition(z, mob):
    """One egg's item definition: the variant's picture when custom_model_data strings[0] names a
    design, the running client's own definition otherwise."""
    return {"model": {
        "type": "minecraft:select",
        "property": "minecraft:custom_model_data", "index": 0,
        "cases": [{"when": vid, "model": {"type": "minecraft:model", "model": f"{NS}:item/egg/{vid}"}}
                  for vid in VARIANTS],
        "fallback": vanilla_definition(z, f"{mob}_spawn_egg"),
    }}


def equipment_definition(vid):
    return {"layers": {layer: [{"texture": f"{NS}:{vid}"}]
                       for layer in ("humanoid", "humanoid_baby", "humanoid_leggings")}}


def build(version=None):
    version = version or VERSION
    z = T.jar()
    load_mobs(z)
    sheets = skins()
    egg_images = eggs(z)
    files = {}
    for vid, img in egg_images.items():
        files[f"assets/{NS}/textures/item/egg/{vid}.png"] = T.png_encode(*img)
        files[f"assets/{NS}/models/item/egg/{vid}.json"] = (json.dumps(
            {"parent": "minecraft:item/generated", "textures": {"layer0": f"{NS}:item/egg/{vid}"}}, indent=2) + "\n").encode()
    for mob in EGG_ITEMS:
        files[f"assets/minecraft/items/{mob}_spawn_egg.json"] = (json.dumps(egg_definition(z, mob), indent=2) + "\n").encode()
    for vid, s in sheets.items():
        files[f"assets/{NS}/equipment/{vid}.json"] = (json.dumps(equipment_definition(vid), indent=2) + "\n").encode()
        files[f"assets/{NS}/textures/entity/equipment/humanoid/{vid}.png"] = T.png_encode(*s.outer)
        files[f"assets/{NS}/textures/entity/equipment/humanoid_baby/{vid}.png"] = T.png_encode(*s.outer)
        files[f"assets/{NS}/textures/entity/equipment/humanoid_leggings/{vid}.png"] = T.png_encode(*s.inner)

    (HERE / "preview.png").write_bytes(preview(z, sheets, egg_images))

    icon_egg = egg_images["vampire"]

    def px(x, y):
        sx, sy = (x - 8) // 3, (y - 8) // 3
        if 0 <= sx < 16 and 0 <= sy < 16:
            p = get(icon_egg, sx, sy)
            return p if p[3] else None
        return None

    out, from_jar = T.ship(HERE, NAME, version, "designed mobs and their eggs", files,
                           T.icon((60, 30, 40, 255), px))
    return out, from_jar


def main():
    """Build and return the shipped zip - the contract ../build.py drives."""
    import hashlib
    out, from_jar = build()
    print(f"  {out.name}: {out.stat().st_size} bytes, sha1 {hashlib.sha1(out.read_bytes()).hexdigest()}"
          + ("" if from_jar else "  (client jar not found - vanilla fallbacks assumed)"))
    return out


if __name__ == "__main__":
    main()
