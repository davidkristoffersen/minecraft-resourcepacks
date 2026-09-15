#!/usr/bin/env python3
"""
ThemeHorror - the layer Haunt wears while its director is armed.

A companion layer that stays loaded and paints only STATES the server puts a player in,
so Haunt can switch the look on and off per player without a pack reload anyone could
see: blood hearts that drip on the absorbing / blinking heart sprites (the cues Haunt
plays on a victim), the Hunger effect's rotten drumsticks as raw bleeding meat (the
`hunger` cue), blood veins over the whole screen as a glyph of the pack's own font (the `veins` cue sends
it as a title - drawn by the server, never by a state), and
the NEW MOON repainted as a blood moon - the `bloodmoon` cue shifts a player's sky to that
phase while the director is armed. A natural new-moon
night shows the blood moon to everyone with the pack, one night in eight. Nothing
everyday is touched, so it never fights another theme over a file. All of it derived from
the vanilla textures in the installed client jar at build time; the sound is a
remap of vanilla sound events, no audio shipped. Pushed and popped by the Haunt
plugin through ServerMenus' `/lookpacks ThemeHorror on|off`.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import themelib as T  # noqa: E402

NAME = "ThemeHorror"
VERSION = "2.3.3"      # bumped with ../bump.py, never by hand

DRIP = (120, 8, 8, 255)


# The hearts this layer paints are the STATE sprites, not the everyday ones: absorbing hearts
# (ServerMenus' `absorbing` cue, which Haunt plays on a victim for every event) and the blinking
# frames (a fake hurt). So blood shows during a Haunt
# moment and the everyday hearts stay whatever the everyday theme made them - two layers never
# fight over full.png. The absorbing sprites are gold and the frozen ones ice blue in vanilla,
# so they are repainted by brightness rather than tinted. (The absorbing sprites are gold in vanilla.)
HEART_STATES = ["absorbing_full", "absorbing_half", "absorbing_full_blinking", "absorbing_half_blinking",
                "full_blinking", "half_blinking"]
# NOT the frozen hearts or the frost border: a real freeze (powder snow, Toolbox's freeze trick) is a
# vanilla state players reach without Haunt, and a layer cannot tell it from the frozen cue
BLOOD = (0.52, 0.03, 0.03)   # dark enough to read as blood next to a vanilla heart, not just 'red'


def hearts(z, files):
    for kind in HEART_STATES:
        try:
            img = T.texture(z, f"gui/sprites/hud/heart/{kind}.png")
        except KeyError:
            continue
        if img is None:
            continue
        img = T.recolour(img, *BLOOD)
        # a drop under the heart's point, where the sprite has a spare bottom row
        if T.pixel(img, 4, 7)[3] > 0 and T.pixel(img, 4, 8)[3] == 0:
            T.set_pixel(img, 4, 8, DRIP)
        files[f"assets/minecraft/textures/gui/sprites/hud/heart/{kind}.png"] = T.png_encode(*img)


def food(z, files):
    """The Hunger effect's drumsticks (`hunger` cue): the meat repainted blood red with a drop
    running off it, the bone left pale. The everyday drumsticks are not touched."""
    for kind in ("food_full_hunger", "food_half_hunger", "food_empty_hunger"):
        img = T.texture(z, f"gui/sprites/hud/{kind}.png")
        if img is None:
            continue
        w, h, rows = img
        out = []
        for y in range(h):
            row = bytearray(rows[y])
            for x in range(w):
                r, g, b, a = row[x * 4:x * 4 + 4]
                if a == 0 or x >= 6:        # the bone sits in the lower-right corner
                    continue
                i = max(r, g, b)
                if kind == "food_empty_hunger":
                    i = i // 2              # the empty outline: dried blood
                row[x * 4:x * 4 + 3] = bytes(T.clamp(v) for v in (i * BLOOD[0] + 40, i * BLOOD[1], i * BLOOD[2]))
            out.append(row)
        img = (w, h, out)
        if kind != "food_empty_hunger":
            # a drop under the meat, in the clear column beside the bone
            if T.pixel(img, 2, 4)[3] > 0 and T.pixel(img, 2, 5)[3] == 0:
                T.set_pixel(img, 2, 5, DRIP)
                T.set_pixel(img, 2, 6, (90, 4, 4, 200))
        files[f"assets/minecraft/textures/gui/sprites/hud/{kind}.png"] = T.png_encode(*img)


# 512x256: themelib.font_picture cuts it into two 256x256 cells (the client's glyph-texture limit),
# U+E000 U+E001, one continuous drawing. Declared 150 units tall each, so 150 wide: 300x150 units,
# x4 as a title = 1200x600 GUI px.
VEINS_W, VEINS_H = 512, 256
VEINS_HEIGHT, VEINS_ASCENT = 150, 65   # a title draws at (-w/2, -10) scaled 4x around the screen centre: ascent = h/2 - 10 centres it


def veins(z, files):
    """Blood veins over the whole screen, drawn by the SERVER, not by a state: ServerMenus' `veins` cue
    sends a title whose text is two glyphs of this pack's own font (`themehorror:veins`, U+E000-E001), so the
    picture exists exactly while the cue runs and nothing vanilla ever shows it. (The frozen border was
    tried first and rolled back: a real freeze - powder snow, Toolbox's freeze trick - wore the veins too,
    and a layer cannot tell the cue from the real thing.) The veins run evenly over the picture rather
    than ringing its edge: a title scales with the GUI scale, so a small GUI sees the whole glyph and a
    large one only its middle - even art reads the same either way."""
    import math, random
    w, h = VEINS_W, VEINS_H
    rnd = random.Random(1408)
    cover = [bytearray(w) for _ in range(h)]
    for k in range(110):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        angle = rnd.uniform(0, 2 * math.pi)
        length = rnd.randint(80, 220)
        for step in range(length):
            angle += rnd.uniform(-0.3, 0.3)
            x += math.cos(angle) * 1.2
            y += math.sin(angle) * 1.2
            if not (0 <= x < w and 0 <= y < h):
                break
            t = step / length
            thick = 1 + int(2.2 * math.sin(t * math.pi))       # thin at both ends, fuller in the middle
            for dy in range(-thick, thick + 1):
                for dx in range(-thick, thick + 1):
                    X, Y = int(x) + dx, int(y) + dy
                    if 0 <= X < w and 0 <= Y < h and dx * dx + dy * dy <= thick * thick:
                        edge = 1 - (dx * dx + dy * dy) / (thick * thick + 1)
                        cover[Y][X] = max(cover[Y][X], int(255 * (0.55 + 0.45 * edge) * math.sin(t * math.pi) ** 0.5))
            if rnd.random() < 0.02:  # a branch: another, shorter vein from here
                bx, by, ba = x, y, angle + rnd.choice((-1, 1)) * rnd.uniform(0.6, 1.2)
                for s2 in range(rnd.randint(20, 60)):
                    ba += rnd.uniform(-0.3, 0.3)
                    bx += math.cos(ba) * 1.2
                    by += math.sin(ba) * 1.2
                    X, Y = int(bx), int(by)
                    if 0 <= X < w and 0 <= Y < h:
                        cover[Y][X] = max(cover[Y][X], 150)
    out = []
    for y in range(h):
        row = bytearray(w * 4)
        for x in range(w):
            c = cover[y][x]
            if c == 0:
                continue
            a = min(200, c * 200 // 255)
            row[x * 4:x * 4 + 4] = bytes((int(110 + 90 * c / 255), int(6 + 8 * c / 255), int(6 + 6 * c / 255), a))
        out.append(row)
    # two 256x256 cells, U+E000 U+E001 - ServerMenus' Cues.VEINS sends exactly that string
    chars = T.font_picture(files, "themehorror", "veins", (w, h, out), VEINS_HEIGHT, VEINS_ASCENT, first=0xE000)
    assert chars == "\ue000\ue001", chars


def moons(z, files):
    """Only the new moon: the full moon disc, blood red, stands in the phase the bloodmoon cue
    parks a player's sky on. Every other phase stays vanilla."""
    img = T.texture(z, "environment/celestial/moon/full_moon.png")
    if img is None:
        return
    img = T.map_pixels(img, lambda r, g, b, a: (r * 0.95 + 25 if max(r, g, b) > 30 else r, g * 0.18, b * 0.15, a))
    files["assets/minecraft/textures/environment/celestial/moon/new_moon.png"] = T.png_encode(*img)


def pack_icon():
    # a red moon low over a black horizon
    def px(x, y):
        d = ((x - 40) ** 2 + (y - 26) ** 2) ** 0.5
        if d < 13:
            return (170 if d > 10 else 205, 16, 16, 255)
        if y > 48:
            return (8, 6, 6, 255)
        return None
    return T.icon((16, 8, 12, 255), px)


def derive(z):
    """Every file this layer ships, from the open client jar (None = no textures, sound only).
    Shared with ServerUI, which draws the before/after preview from the same bytes."""
    files = {}
    hearts(z, files)
    food(z, files)
    veins(z, files)
    moons(z, files)
    return files


def build(version=None):
    version = version or VERSION
    z = T.jar()
    files = derive(z)
    out, from_jar = T.ship(HERE, NAME, version, "blood hearts, rotten food, veins and a blood moon, on cue", files, pack_icon())
    return out, len(files), from_jar


def main():
    import hashlib
    out, count, from_jar = build()
    print(f"  {out.name}: {count} files, {out.stat().st_size} bytes, sha1 {hashlib.sha1(out.read_bytes()).hexdigest()}"
          + ("" if from_jar else "  (client jar not found - textures skipped)"))
    return out


if __name__ == "__main__":
    main()
