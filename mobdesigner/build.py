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

Beyond the costume (1.1.0)
--------------------------
`EXTRAS` gives designs the rest of what a vanilla client can draw or play per entity:

  wings     a `wings` layer in the costume's chest asset - the elytra model in our texture
            (`textures/entity/equipment/wings/<variant>.png`, the vanilla silhouette recoloured);
            the client draws it for any humanoid whose chest item's asset has that layer
  weapon    a hand item with `custom_model_data` strings[0] = <model>: `items/<base item>.json`
            selects our sprite (`item/weapon/<model>`, a handheld 16x16 like every vanilla sword)
            and falls back to the client's own definition, so a client without the pack sees the
            base item - a stick, an iron sword
  hat       the same for the item display riding a mob without a head layer (creepers): a cube
            model (`item/hat/<model>`) over a vanilla block item
  aura      `ITEM` particles resolve the item's model definition (26.2 BreakingItemParticle goes
            through ItemModelResolver), so an aura is a sprite: `item/aura/<model>`, a 16x16 that
            tiles one 8x8 motif 2x2 because an item particle shows a random quarter of the icon
  voice     `sounds.json` events `voice.<variant>.{ambient,hurt,death}`, every one of them a
            **mono OGG synthesised by `voices.py`** - no vanilla sound is referenced any more.
            A pool picks one entry, so a voice built out of `type: event` references could only
            ever be one vanilla sound at a chosen pitch, which is exactly what it sounded like.
            The plugin silences the mob and plays these per viewer, the mob's own vanilla sound
            to anyone without the pack - sounds are per-player packets, the one perfectly
            gateable custom asset. Needs a Vorbis encoder that can write mono: `oggenc` from
            `brew install vorbis-tools`, or an ffmpeg built with libvorbis. Without one the pack
            ships with no sounds at all and everybody hears the vanilla mob.

The Hexer is a repaint of the Illusioner (`textures/entity/illager/illusioner.png`): that mob
never spawns naturally, so a whole-type repaint leaks onto nothing - a free custom mob.

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
sys.path.insert(0, str(HERE))
import themelib as T  # noqa: E402
import voices  # noqa: E402

VOICES = voices.VOICES     # which designs have a voice - the preview marks them

NAME = "MobDesigner"
VERSION = "1.4.2"         # bumped with ../bump.py, never by hand
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
    # an Illusioner repainted whole (it never spawns naturally, so the repaint leaks onto nothing):
    # no armour layer on an illager, the texture IS the costume; its egg is the pillager's portrait
    "hexer": dict(mob="pillager", features=None,
                  egg=dict(skin=(150, 170, 140), cloth=(22, 46, 30), pants=(22, 46, 30), over=[("eyes", (120, 255, 80))],
                           badge=("hex", (150, 120, 40)))),
}


# ---------------------------------------------------------------- extras: wings, weapons, hats, auras, voices

WEAPON_PALETTE = {"#": (60, 40, 28), "+": (110, 78, 46), "=": (150, 110, 70), "*": (200, 60, 220), "o": (240, 180, 255),
                  "%": (120, 124, 130), "&": (180, 186, 192), "!": (70, 30, 30), "@": (200, 40, 40), "^": (40, 24, 16),
                  "g": (222, 180, 60)}

# 16x16 handheld sprites, drawn point-up along the diagonal like every vanilla sword
WEAPONS = {
    "warlock_staff": [
        "..............oo", ".............o*o", "............**oo", "...........g**..", "..........g+g...", ".........+#.....",
        "........+#......", ".......+#.......", "......+#........", ".....+#.........", "....+#..........", "...+#...........",
        "..+#............", ".+#.............", "##..............", "#...............",
    ],
    "brute_cudgel": [
        "................", "...........^^^..", "..........^===^.", ".........^=%==^.", "........^==%==^.", "........^=====^.",
        ".........^===^..", "........+#^^^...", ".......+#.......", "......+#........", ".....+#.........", "....+#..........",
        "...+#...........", "..+#............", ".+#.............", "##..............",
    ],
    "bandit_knife": [
        "................", "................", "...........&&&..", "..........&%&...", ".........&%&....", "........&%&.....",
        ".......&%&......", "......&%&.......", ".....&%&........", "....!%&.........", "...!@!..........", "..!#!...........",
        ".!#!............", "##..............", "#...............", "................",
    ],
}

# 8x8 motifs for the aura particles, tiled 2x2
AURAS = {
    "blood_drop": (["...#....", "...#....", "..###...", ".#####..", ".##+##..", ".#####..", "..###...", "........"], (190, 16, 30), (240, 90, 100)),
    "spore": (["..####..", ".#....#.", "#.#..#.#", "#......#", "#.####.#", "#..##..#", ".#....#.", "..####.."], (140, 200, 40), (220, 240, 120)),
    "ember": (["....#...", "...##...", "..#+#...", ".##+##..", ".#+++#..", "..###...", "...#....", "........"], (240, 110, 20), (255, 230, 120)),
    "rune": (["...##...", "..#..#..", ".#.##.#.", "#..##..#", "#..##..#", ".#.##.#.", "..#..#..", "...##..."], (150, 80, 220), (230, 190, 255)),
    "wisp": (["........", "...##...", "..#..#..", ".#....#.", ".#....#.", "..#..#..", "...##...", "........"], (20, 18, 24), (70, 66, 80)),
    "note": (["......#.", ".....##.", "....#.#.", "....#...", "....#...", "..###...", ".####...", "..##...."], (40, 210, 220), (200, 255, 255)),
    "spark": (["...#....", "..##....", ".####...", "...#....", "..#.....", ".#......", "........", "........"], (120, 200, 255), (255, 255, 200)),
    "fuse": (["..#.....", ".#.#....", "..#.#...", "....#...", "...###..", "..#####.", "..#####.", "...###.."], (250, 140, 40), (40, 36, 40)),
}

# the cube hats: (side texture rows, top texture rows), 16x16 each, '.' = base colour shade
HATS = {
    "bomb": dict(base=(38, 36, 44), side=[
        "................", "................", "....+++++.......", "...+#####+......", "..+#######+.....", "..+#######+.....",
        ".+#########+....", ".+#########+....", ".+#########+....", ".+#########+....", "..+#######+.....", "..+#######+.....",
        "...+#####+......", "....+++++.......", "................", "................",
    ], top=[
        "................", "................", "................", "................", "................", "................",
        ".......gg.......", "......g..g......", ".......g........", ".......g........", ".......g........", "......ggg.......",
        ".....g###g......", ".....g###g......", "......ggg.......", "................",
    ], palette={"#": (20, 18, 24), "+": (70, 66, 78), "g": (250, 140, 40)}),
    "die": dict(base=(236, 232, 226), pips=(30, 28, 34)),
}

# what each design carries besides its costume: wings=(membrane, vein, glow or None),
# weapon=(base item, model), hat=(base item, model), aura=(base item, model)
EXTRAS = {
    "vampire": dict(wings=((44, 16, 28), (110, 20, 30), None), aura=("redstone", "blood_drop")),
    "arsonist": dict(wings=((30, 26, 30), (60, 50, 50), (255, 150, 40)), aura=("blaze_powder", "ember")),
    # a robed caster with nothing hanging off his shoulders looked unfinished: the wings layer is
    # the only cloth a mob can wear behind it, and in amethyst it reads as the cape the staff and
    # the rune aura were already implying
    "warlock": dict(weapon=("stick", "warlock_staff"), aura=("amethyst_shard", "rune"),
                    wings=((58, 38, 92), (128, 96, 190), None)),
    "brute": dict(weapon=("stick", "brute_cudgel")),
    "bandit": dict(weapon=("iron_sword", "bandit_knife")),
    "plague-bearer": dict(aura=("slime_ball", "spore")),
    "stalker": dict(aura=("coal", "wisp")),
    # the only design that lives in water, and the elytra silhouette read as trailing fins the
    # moment it was prismarine - faintly lit, because everything else of hers is
    "siren": dict(aura=("prismarine_shard", "note"), wings=((32, 96, 104), (18, 56, 64), (150, 240, 230))),
    # no hat for the charged creeper: the hat mechanism is a CUBE (it is an item display of a
    # block model), which is why a bomb and a die work and why a lightning rod does not - drawn as
    # a cube it reads as a block of dirt sitting on a creeper. Left with its spark aura instead.
    "charged-creeper": dict(aura=("glowstone_dust", "spark")),
    "boomer": dict(hat=("tnt", "bomb"), aura=("gunpowder", "fuse")),
    "chaos-creeper": dict(hat=("target", "die")),
}

# item definitions the extras override, base item -> [(string, model path)]
# ---------------------------------------------------------------- costume icons
#
# The carrier pieces are leather armour, so in a chest window they draw as leather armour - which
# tells you nothing about which costume you are holding, and on 26.3 draws as the missing model
# anyway while Paper's trim registry is broken. Each carrier already gets `custom_model_data`
# strings[0] = the design id, so the pack can select on it exactly as the eggs do: one 16x16 per
# design per slot, cut from that design's own costume sheet and blown up to fill the icon.
#
# Which faces: the head's front for a helmet, the body's front for a chestplate, the leg's front
# doubled for leggings (a 4-wide face on a 16-wide icon), the boot rows of the leg for boots.
# every armour item, for the 26.3 trim workaround below
ARMOUR_PIECES = [f"{m}_{s}" for m in ("chainmail", "iron", "golden", "diamond", "netherite", "copper")
                 for s in ("helmet", "chestplate", "leggings", "boots")] + ["turtle_helmet"]

# Where each slot sits in the front view `doll()` draws (24 wide, 36 tall at scale 1, no
# headroom): the head at y 0-8, the body and arms at 8-20, the legs at 20-32. The icon is that
# band of the **dressed** figure, so a hood looks like a hood on a head and a coat like a coat on
# a body - which is what the mob looks like when you spawn it. Cutting the faces straight off the
# costume sheet instead gave flat coloured rectangles that were hard to tell apart.
COSTUME_CROPS = {
    "helmet": (4, 0, 16, 9),
    "chestplate": (2, 8, 20, 12),
    # the two legs touch in the front view, so ANY tight crop of them is one flat colour - the
    # trousers only read as trousers with the silhouette round them, so these two keep the hips
    # and the empty air either side rather than filling the icon with a swatch
    "leggings": (6, 18, 12, 14),
    "boots": (6, 22, 12, 10),
}

# Whether a design puts anything on a slot is a question about its own sheets, not about the
# picture: the bands above touch (a coat hangs over the top of the legs), so comparing crops
# called every slot changed. These are the faces the armour layer draws for each slot.
COSTUME_PAINTS = {
    "helmet": ("outer", (HEAD, HAT)),
    "chestplate": ("outer", (BODY, ARM)),
    "leggings": ("inner", (LEG, BODY)),
    "boots": ("outer", (LEG,)),
}


def paints(sheets, slot):
    """Does this design paint anything on that slot's faces?"""
    which, boxes = COSTUME_PAINTS[slot]
    src = sheets.outer if which == "outer" else sheets.inner
    for box in boxes:
        for u, v, w, h in box.values():
            for y in range(v, v + h):
                for x in range(u, u + w):
                    if get(src, x, y)[3]:
                        return True
    return False


def crop_to_icon(img, box):
    """A rectangle of a doll, scaled by whole pixels to fill a 16x16 item sprite and centred."""
    x0, y0, w, h = box
    scale = max(1, min(16 // w, 16 // h))
    out = blank(16, 16)
    ox = (16 - w * scale) // 2
    oy = (16 - h * scale) // 2
    for y in range(h):
        for x in range(w):
            c = get(img, x0 + x, y0 + y)
            if not c[3]:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    put(out, ox + x * scale + dx, oy + y * scale + dy, c[:3])
    return out


def costume_icons(vid, sheets):
    """{slot: icon} for the slots this design actually changes.

    A slot this design paints nothing on is left out entirely - the carrier then draws as the
    client's own leather piece, which says "this design puts nothing on your legs" instead of
    showing a square that looks broken. The figure is also drawn bare as a second guard, so a
    band that somehow comes out identical is dropped too."""
    mob = VARIANTS[vid]["mob"]
    bare = doll(mob, None, vid=vid, props=False)
    worn = doll(mob, sheets, vid=vid, props=False)
    out = {}
    for slot, box in COSTUME_CROPS.items():
        if not paints(sheets, slot):
            continue
        dressed = crop_to_icon(worn, box)
        if crop_to_icon(bare, box)[2] != dressed[2]:
            out[slot] = dressed
    return out


def extra_overrides():
    out = {}
    for vid, extra in EXTRAS.items():
        for kind in ("weapon", "hat", "aura"):
            if kind in extra:
                base, model = extra[kind]
                out.setdefault(base, []).append((model, f"{NS}:item/{kind}/{model}"))
    return out


def sprite16(rows, palette, base=None):
    img = blank(16, 16)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "." and base is None:
                continue
            c = palette.get(ch, base)
            if c is not None:
                put(img, x, y, c)
    return img


def aura_texture(model):
    rows, dark, light = AURAS[model]
    img = blank(16, 16)
    for ty in range(2):
        for tx in range(2):
            for y, row in enumerate(rows):
                for x, ch in enumerate(row):
                    if ch == "#":
                        put(img, tx * 8 + x, ty * 8 + y, dark)
                    elif ch == "+":
                        put(img, tx * 8 + x, ty * 8 + y, light)
    return img


def die_face(n, base, pip):
    img = blank(16, 16)
    for y in range(16):
        for x in range(16):
            edge = x in (0, 15) or y in (0, 15)
            put(img, x, y, shade(base, 0.8 if edge else (1.0 if (x + y) % 2 else 0.96)))
    spots = {1: [(7, 7)], 2: [(3, 3), (11, 11)], 3: [(3, 3), (7, 7), (11, 11)], 4: [(3, 3), (11, 3), (3, 11), (11, 11)],
             5: [(3, 3), (11, 3), (7, 7), (3, 11), (11, 11)], 6: [(3, 2), (11, 2), (3, 7), (11, 7), (3, 12), (11, 12)]}[n]
    for sx, sy in spots:
        for dy in range(2):
            for dx in range(2):
                put(img, sx + dx, sy + dy, pip)
    return img


def hat_textures(model):
    """{texture name: image} for a cube hat."""
    spec = HATS[model]
    if model == "die":
        return {f"die_{n}": die_face(n, spec["base"], spec["pips"]) for n in range(1, 7)}
    pal = dict(spec["palette"])
    return {f"{model}_side": sprite16(spec["side"], pal), f"{model}_top": sprite16(spec["top"], pal)}


def hat_model(model):
    if model == "die":
        faces = {"down": 1, "up": 6, "north": 2, "south": 5, "west": 3, "east": 4}
        return {"parent": "minecraft:block/cube", "textures": {"particle": f"{NS}:item/hat/die_1",
                **{face: f"{NS}:item/hat/die_{n}" for face, n in faces.items()}}}
    tex = {"particle": f"{NS}:item/hat/{model}_side", "up": f"{NS}:item/hat/{model}_top", "down": f"{NS}:item/hat/{model}_side"}
    for face in ("north", "south", "west", "east"):
        tex[face] = f"{NS}:item/hat/{model}_side"
    return {"parent": "minecraft:block/cube", "textures": tex}


WING_REGION = (22, 0, 24, 22)   # the elytra's wing on the 64x32 sheet: both wings share it (the left is mirrored)


def wing_texture(z, membrane, vein, glow):
    """The vanilla elytra silhouette in our colours: a pixel's brightness relative to the wing's
    average decides membrane (light) or vein (dark); glow speckles the membrane."""
    out = blank(64, 32)
    src = T.texture(z, "entity/equipment/wings/elytra.png") if z is not None else None
    if src is None:
        return out
    x0, y0, w, h = WING_REGION
    pixels = [(x, y, get(src, x, y)) for y in range(y0, y0 + h) for x in range(x0, x0 + w) if get(src, x, y)[3]]
    if not pixels:
        return out
    avg = sum(lum(p) for _, _, p in pixels) / len(pixels)
    rnd = noise(29)
    for x, y, p in pixels:
        f = lum(p) / avg
        c = membrane if f >= 0.97 else vein
        c = shade(c, 0.85 + 0.3 * min(1.3, f) / 1.3)
        if glow and f >= 0.97 and rnd() < 0.12:
            c = glow
        put(out, x, y, c)
    return out


def hexer_texture(z):
    """The Illusioner repainted: its blue robe and hood in hexer green-black, the eyes lit."""
    src = T.texture(z, "entity/illager/illusioner.png") if z is not None else None
    if src is None:
        return blank(64, 64)
    w, h, _ = src
    out = blank(w, h)
    robe, trim = (22, 46, 30), (150, 120, 40)
    for y in range(h):
        for x in range(w):
            p = get(src, x, y)
            if p[3] == 0:
                continue
            hh, s, l = hue_sat_lum(p)
            if 190 <= hh < 230 and s > 0.45:          # the blues of the robe and hood
                f = 0.5 + 0.5 * (l / 90.0)
                c = tuple(clamp(t * f) for t in robe)
                if l > 120:                          # the light blue trim
                    c = trim
                put(out, x, y, c)
            elif s < 0.15 and l > 120:                # the grey face - a little greener, paler
                put(out, x, y, (clamp(p[0] * 0.92), clamp(p[1] * 1.02), clamp(p[2] * 0.9)))
            else:
                put(out, x, y, p[:3])
    # eyes: the head's front face is at (8, 8), 8x10; the illager eye row is its row 6
    for x, c in ((9, (20, 20, 20)), (10, (120, 255, 80)), (13, (120, 255, 80)), (14, (20, 20, 20))):
        put(out, x, 14, c)
    return out


# ---------------------------------------------------------------- voices

def voice_files(files):
    """Every design's three lines as mono OGG, plus sounds.json and the subtitles.

    The sounds themselves are `voices.py`: a small synthesiser and one recipe per line. Nothing
    vanilla is referenced any more - a pool picks one entry, so a voice made of vanilla events
    could never be more than one vanilla event, which is what it sounded like."""
    sounds, events, lang, encoder = voices.render(NS)
    if encoder is None:
        print("  ! no Vorbis encoder (install vorbis-tools) - shipping without voices")
        return
    files.update(sounds)
    files[f"assets/{NS}/sounds.json"] = (json.dumps(events, indent=2) + "\n").encode()
    files[f"assets/{NS}/lang/en_us.json"] = (json.dumps(lang, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    print(f"  voices: {len(sounds)} lines through {encoder}, {sum(len(v) for v in sounds.values()) // 1024} KB")


MOB_TEXTURES = {"zombie": "entity/zombie/zombie.png", "husk": "entity/zombie/husk.png",
                "drowned": "entity/zombie/drowned.png", "skeleton": "entity/skeleton/skeleton.png",
                "creeper": "entity/creeper/creeper.png", "pillager": "entity/illager/illusioner.png"}
MOB_SKINS = {}
EGG_ITEMS = ("zombie", "husk", "drowned", "skeleton", "creeper", "pillager")


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
    elif mob == "pillager":
        if s < 0.2 and 100 <= l < 200:
            return "skin"
        if 160 <= h < 200 and s > 0.2:
            return "cloth"
        if (330 <= h or h < 20) and s > 0.3:
            return "pants"
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

def doll(mob, sheets, scale=1, vid=None, headroom=0, props=True):
    """A front view of the dressed mob: the base skin's front faces, the leggings, the outer layer,
    the hat - plus the design's extras: wings behind the shoulders, the weapon in the right hand, a
    cube hat over a creeper, the aura motif floating beside it. 24x(36+headroom) at scale 1; the
    body starts `headroom` rows down so a hat has room."""
    w, h = 24, 36 + headroom
    out = blank(w, h)
    base = hexer_texture(T.jar()) if vid == "hexer" else MOB_SKINS[mob]   # the Hexer IS its repaint
    thin = mob == "skeleton"
    extra = EXTRAS.get(vid, {}) if vid else {}
    z0 = headroom

    def blit(src, r, dx, dy, mirror=False):
        x0, y0, fw, fh = r
        for y in range(fh):
            for x in range(fw):
                px = get(src, x0 + (fw - 1 - x if mirror else x), y0 + y)
                if px[3]:
                    put(out, dx + x, dy + y, px[:3])

    # wings first - they hang behind the shoulders (the elytra's back face, x 36..46, 10x20)
    if "wings" in extra:
        # ElytraModel: texOffs(22,0), box 10x20x1 - the face you see from behind is the BACK one,
        # at (u + d + w + d, v + d) = (34, 1); the front face at (23,1) is the hidden inner side
        wings = wing_texture(T.jar(), *extra["wings"])
        blit(wings, (34, 1, 10, 20), -2, z0 + 6)
        blit(wings, (34, 1, 10, 20), 16, z0 + 6, mirror=True)
    # the mob itself
    if mob == "creeper":
        blit(base, (8, 8, 8, 8), 8, z0 + 8)            # head
        blit(base, (20, 20, 4, 12), 10, z0 + 16)       # body
        blit(base, (4, 20, 4, 6), 7, z0 + 28)          # legs
        blit(base, (4, 20, 4, 6), 13, z0 + 28, mirror=True)
    elif mob == "pillager":
        # IllagerModel.createBodyLayer, read from resources-camera/mob-models.json: head 8x10 at
        # texOffs 0,0; body 8x12 at 16,20; the ROBE a second body cube 8x20 at 0,38 (front face
        # 6,44) hanging over body and legs - the piece that carries the illager's colour; arms
        # 4x12 at 40,46; legs 4x12 at 0,22
        blit(base, (8, 8, 8, 10), 8, z0)
        blit(base, (22, 26, 8, 12), 8, z0 + 10)
        blit(base, (4, 26, 4, 12), 8, z0 + 22)
        blit(base, (4, 26, 4, 12), 12, z0 + 22, mirror=True)
        blit(base, (44, 50, 4, 12), 4, z0 + 10)
        blit(base, (44, 50, 4, 12), 16, z0 + 10, mirror=True)
        blit(base, (6, 44, 8, 20), 8, z0 + 10)
    else:
        blit(base, HEAD["front"], 8, z0)
        blit(base, BODY["front"], 8, z0 + 8)
        if thin:
            blit(base, (44, 20, 2, 12), 6, z0 + 8)
            blit(base, (44, 20, 2, 12), 16, z0 + 8, mirror=True)
            blit(base, (4, 20, 2, 12), 9, z0 + 20)
            blit(base, (4, 20, 2, 12), 13, z0 + 20, mirror=True)
        else:
            blit(base, ARM["front"], 4, z0 + 8)
            blit(base, ARM["front"], 16, z0 + 8, mirror=True)
            blit(base, LEG["front"], 8, z0 + 20)
            blit(base, LEG["front"], 12, z0 + 20, mirror=True)
    if sheets is not None:
        blit(sheets.inner, LEG["front"], 8, z0 + 20)
        blit(sheets.inner, LEG["front"], 12, z0 + 20, mirror=True)
        blit(sheets.inner, BODY["front"], 8, z0 + 8)
        blit(sheets.outer, BODY["front"], 8, z0 + 8)
        blit(sheets.outer, ARM["front"], 4, z0 + 8)
        blit(sheets.outer, ARM["front"], 16, z0 + 8, mirror=True)
        blit(sheets.outer, LEG["front"], 8, z0 + 20)
        blit(sheets.outer, LEG["front"], 12, z0 + 20, mirror=True)
        blit(sheets.outer, HEAD["front"], 8, z0)
        blit(sheets.outer, HAT["front"], 8, z0)
    # the weapon in the right hand (the viewer's left), point up
    if props and "weapon" in extra:
        blit(sprite16(WEAPONS[extra["weapon"][1]], WEAPON_PALETTE), (0, 0, 16, 16), -3, z0 + 10)
    # a cube hat floats over a creeper: the side texture at half size
    if props and "hat" in extra and headroom >= 8:
        hats = hat_textures(extra["hat"][1])
        side = hats.get(f"{extra['hat'][1]}_side") or hats.get("die_5")
        for y in range(8):
            for x in range(8):
                px = get(side, x * 2, y * 2)
                if px[3]:
                    put(out, 8 + x, z0 - 1 + y, px[:3])
        top = hats.get(f"{extra['hat'][1]}_top")
        if top is not None:                      # the fuse sticking out of the top
            for y in range(4):
                for x in range(8):
                    px = get(top, x * 2, y * 2 + 6)
                    if px[3]:
                        put(out, 8 + x, z0 - 5 + y, px[:3])
    # aura motifs beside it
    if props and "aura" in extra:
        motif = aura_texture(extra["aura"][1])
        for dx, dy in ((0, z0 + 22), (17, z0 + 4)):
            blit(motif, (0, 0, 8, 8), dx, dy)
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
        out[f"doll_{vid}"] = doll(VARIANTS[vid]["mob"], s, vid=vid)
    for vid in VARIANTS:
        if vid not in sheets:
            out[f"doll_{vid}"] = doll(VARIANTS[vid]["mob"], None, vid=vid)
    for mob in ("zombie", "husk", "drowned", "skeleton", "creeper", "pillager"):
        out[f"doll_{mob}"] = doll(mob, None)
    for model, rows in WEAPONS.items():
        out[f"weapon_{model}"] = sprite16(rows, WEAPON_PALETTE)
    for model in AURAS:
        out[f"aura_{model}"] = aura_texture(model)
    for model in HATS:
        out.update({f"hat_{name}": img for name, img in hat_textures(model).items()})
    out["hexer_sheet"] = hexer_texture(z)
    for vid, extra in EXTRAS.items():
        if "wings" in extra:
            out[f"wings_{vid}"] = wing_texture(z, *extra["wings"])
    return out


def preview(z, sheets, egg_images, scale=3):
    """Every design: its egg at 4x, the dressed mob at 3x, on dark - preview.png."""
    ids = list(VARIANTS)
    cols = 6
    headroom = 8
    cell_w, cell_h = 64 + 4 + 24 * scale + 12, (36 + headroom) * scale + 12
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
        d = doll(VARIANTS[vid]["mob"], s, scale, vid=vid, headroom=headroom)
        for y in range(d[1]):
            for x in range(d[0]):
                px = get(d, x, y)
                if px[3]:
                    put(img, cx + 68 + x, cy + y, px[:3])
        if vid in VOICES:   # a little speaker mark under the egg: this one has a voice
            for x, y in ((0, 2), (1, 1), (1, 2), (1, 3), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (4, 1), (4, 3), (5, 2)):
                rect(img, cx + 2 + x * 2, cy + 66 + y * 2, 2, 2, (200, 200, 210))
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
    layers = {layer: [{"texture": f"{NS}:{vid}"}] for layer in ("humanoid", "humanoid_baby", "humanoid_leggings")}
    if "wings" in EXTRAS.get(vid, {}):
        layers["wings"] = [{"texture": f"{NS}:{vid}"}]   # textures/entity/equipment/wings/<vid>.png
    return {"layers": layers}


def override_definition(z, base, cases):
    """A vanilla item's definition with our models selected by custom_model_data strings[0]."""
    return {"model": {
        "type": "minecraft:select",
        "property": "minecraft:custom_model_data", "index": 0,
        "cases": [{"when": string, "model": {"type": "minecraft:model", "model": model}} for string, model in cases],
        "fallback": vanilla_definition(z, base),
    }}


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
    # the costume carriers: one icon per design per slot, and the four leather definitions that
    # select them - so a costume in a chest window looks like the costume, not like leather armour
    drawn = {slot: [] for slot in COSTUME_CROPS}
    for vid, s in sheets.items():
        for slot, icon in costume_icons(vid, s).items():
            drawn[slot].append(vid)
            files[f"assets/{NS}/textures/item/costume/{slot}/{vid}.png"] = T.png_encode(*icon)
            files[f"assets/{NS}/models/item/costume/{slot}/{vid}.json"] = (json.dumps(
                {"parent": "minecraft:item/generated",
                 "textures": {"layer0": f"{NS}:item/costume/{slot}/{vid}"}}, indent=2) + "\n").encode()
    for slot in COSTUME_CROPS:
        files[f"assets/minecraft/items/leather_{slot}.json"] = (json.dumps(override_definition(
            z, f"leather_{slot}", [(vid, f"{NS}:item/costume/{slot}/{vid}") for vid in drawn[slot]]), indent=2) + "\n").encode()
    # Every other armour piece, copied from the client jar verbatim. On 26.3 the client bakes a
    # trim permutation it has no texture for (`item/<piece>/minecraft/sentry/minecraft/_fallback`,
    # `_fallback` appears in neither jar nor registry) and every armour icon comes out as the
    # missing model - a Paper 26.3 alpha fault, not ours. Re-supplying the definition from a pack
    # is what fixed leather, which this pack already overrode, so the same is done for the rest.
    # Harmless when Paper fixes it: these are the client's own bytes.
    for piece in ARMOUR_PIECES:
        if z is not None and f"assets/minecraft/items/{piece}.json" in z.namelist():
            files[f"assets/minecraft/items/{piece}.json"] = (json.dumps(
                {"model": vanilla_definition(z, piece)}, indent=2) + "\n").encode()
    for vid, s in sheets.items():
        files[f"assets/{NS}/equipment/{vid}.json"] = (json.dumps(equipment_definition(vid), indent=2) + "\n").encode()
        files[f"assets/{NS}/textures/entity/equipment/humanoid/{vid}.png"] = T.png_encode(*s.outer)
        files[f"assets/{NS}/textures/entity/equipment/humanoid_baby/{vid}.png"] = T.png_encode(*s.outer)
        files[f"assets/{NS}/textures/entity/equipment/humanoid_leggings/{vid}.png"] = T.png_encode(*s.inner)
    # the extras: wings, weapons, hats, auras - and the item definitions that select them
    for vid, extra in EXTRAS.items():
        if "wings" in extra:
            files[f"assets/{NS}/textures/entity/equipment/wings/{vid}.png"] = T.png_encode(*wing_texture(z, *extra["wings"]))
    for model, rows in WEAPONS.items():
        files[f"assets/{NS}/textures/item/weapon/{model}.png"] = T.png_encode(*sprite16(rows, WEAPON_PALETTE))
        files[f"assets/{NS}/models/item/weapon/{model}.json"] = (json.dumps(
            {"parent": "minecraft:item/handheld", "textures": {"layer0": f"{NS}:item/weapon/{model}"}}, indent=2) + "\n").encode()
    for model in HATS:
        for name, img in hat_textures(model).items():
            files[f"assets/{NS}/textures/item/hat/{name}.png"] = T.png_encode(*img)
        files[f"assets/{NS}/models/item/hat/{model}.json"] = (json.dumps(hat_model(model), indent=2) + "\n").encode()
    for model in AURAS:
        files[f"assets/{NS}/textures/item/aura/{model}.png"] = T.png_encode(*aura_texture(model))
        files[f"assets/{NS}/models/item/aura/{model}.json"] = (json.dumps(
            {"parent": "minecraft:item/generated", "textures": {"layer0": f"{NS}:item/aura/{model}"}}, indent=2) + "\n").encode()
    for base, cases in extra_overrides().items():
        files[f"assets/minecraft/items/{base}.json"] = (json.dumps(override_definition(z, base, cases), indent=2) + "\n").encode()
    # the Hexer: the Illusioner's own texture, repainted
    files["assets/minecraft/textures/entity/illager/illusioner.png"] = T.png_encode(*hexer_texture(z))
    voice_files(files)

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
