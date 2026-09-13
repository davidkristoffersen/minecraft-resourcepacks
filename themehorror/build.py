#!/usr/bin/env python3
"""
ThemeHorror - the layer Haunt wears while its director is armed.

A companion layer that stays loaded and paints only STATES the server puts a player in,
so Haunt can switch the look on and off per player without a pack reload anyone could
see: blood hearts that drip on the absorbing / blinking / frozen heart sprites (the cues
Haunt plays on a victim), the Hunger effect's rotten drumsticks as raw bleeding meat (the
`hunger` cue), the Nausea effect's screen overlay as veins of blood (the `nausea` cue), and
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
VERSION = "2.1.0"      # bumped with ../bump.py, never by hand

DRIP = (120, 8, 8, 255)


# The hearts this layer paints are the STATE sprites, not the everyday ones: absorbing hearts
# (ServerMenus' `absorbing` cue, which Haunt plays on a victim for every event), the blinking
# frames (a fake hurt), the frozen hearts (the freeze events). So blood shows during a Haunt
# moment and the everyday hearts stay whatever the everyday theme made them - two layers never
# fight over full.png. The absorbing sprites are gold and the frozen ones ice blue in vanilla,
# so they are repainted by brightness rather than tinted.
HEART_STATES = ["absorbing_full", "absorbing_half", "absorbing_full_blinking", "absorbing_half_blinking",
                "full_blinking", "half_blinking",
                "frozen_full", "frozen_half", "frozen_full_blinking", "frozen_half_blinking"]
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


def nausea(z, files):
    """The Nausea effect's overlay (`nausea` cue): vanilla ships a grey mask, white at the
    edges and black in the middle, that the client tints and fades in. Ours keeps that shape
    in dark red and lays veins over it, reaching in from the edges - so whatever the client
    tints it with, the edges of the screen crawl."""
    img = T.texture(z, "misc/nausea.png")
    if img is None:
        return
    w, h, rows = img
    import math, random
    rnd = random.Random(1408)
    veins = [bytearray(w) for _ in range(h)]
    for k in range(48):
        angle = rnd.uniform(0, 2 * math.pi)
        # start just outside the picture, wander inwards, thinning as it goes
        x, y = w / 2 + math.cos(angle) * w * 0.75, h / 2 + math.sin(angle) * h * 0.75
        length = rnd.randint(70, 140)
        for step in range(length):
            angle += rnd.uniform(-0.35, 0.35)
            dist = max(1.0, math.hypot(x - w / 2, y - h / 2))
            x -= (x - w / 2) / dist * 1.4 - math.cos(angle) * 0.6   # inwards, with a wobble
            y -= (y - h / 2) / dist * 1.4 - math.sin(angle) * 0.6
            thick = max(1, int(3 * (1 - step / length)))
            for dy in range(-thick, thick + 1):
                for dx in range(-thick, thick + 1):
                    X, Y = int(x) + dx, int(y) + dy
                    if 0 <= X < w and 0 <= Y < h and dx * dx + dy * dy <= thick * thick:
                        veins[Y][X] = max(veins[Y][X], int(255 * (1 - step / length)))
    out = []
    for y in range(h):
        row = bytearray(w * 4)
        for x in range(w):
            m = rows[y][x * 4]                      # the vanilla mask: 255 at the edges, 0 in the middle
            v = veins[y][x] * m // 255              # veins fade out where the mask does
            r = T.clamp(m * 0.55 + v * 0.45)
            row[x * 4:x * 4 + 4] = bytes((r, T.clamp(m * 0.04), T.clamp(m * 0.03), 255))
        out.append(row)
    files["assets/minecraft/textures/misc/nausea.png"] = T.png_encode(w, h, out)


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
    nausea(z, files)
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
