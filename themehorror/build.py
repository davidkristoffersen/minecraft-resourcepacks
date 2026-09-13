#!/usr/bin/env python3
"""
ThemeHorror - the layer Haunt wears while its director is armed.

Blood moon (every phase), heavier rain, a vignette that closes in, every menu click a
chest lid falling shut - and blood hearts that drip, painted on the STATE sprites only
(absorbing, blinking, frozen), so they show during a Haunt moment (the `absorbing` cue
ServerMenus plays on the victim) and never fight another theme over the everyday hearts. All of it derived from
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
VERSION = "1.1.0"      # bumped with ../bump.py, never by hand

MOONS = ["new_moon", "waxing_crescent", "first_quarter", "waxing_gibbous",
         "full_moon", "waning_gibbous", "third_quarter", "waning_crescent"]
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
BLOOD = (0.72, 0.06, 0.06)


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


def moons(z, files):
    for phase in MOONS:
        img = T.texture(z, f"environment/celestial/moon/{phase}.png")
        if img is None:
            continue
        # the disc turns blood red: red held, green and blue almost gone; the black sky stays black
        img = T.map_pixels(img, lambda r, g, b, a: (r * 0.95 + 25 if max(r, g, b) > 30 else r, g * 0.18, b * 0.15, a))
        files[f"assets/minecraft/textures/environment/celestial/moon/{phase}.png"] = T.png_encode(*img)


def weather(z, files):
    img = T.texture(z, "environment/rain.png")
    if img is not None:
        files["assets/minecraft/textures/environment/rain.png"] = T.png_encode(*T.multiply(img, 0.5, 0.45, 0.5))


def vignette(z, files):
    # the vanilla vignette is an opaque grey darkness map, white at the corners: push it
    # inwards and lift the floor so the whole screen sits in a little gloom
    img = T.texture(z, "misc/vignette.png")
    if img is None:
        img = T.radial(256, 256, lambda d: (d * 210, d * 210, d * 210, 255))
    img = T.map_pixels(img, lambda r, g, b, a: (r * 1.7 + 24, g * 1.7 + 24, b * 1.7 + 24, a))
    files["assets/minecraft/textures/misc/vignette.png"] = T.png_encode(*img)
    files["assets/minecraft/textures/misc/vignette.png.mcmeta"] = b'{\n  "texture": {\n    "blur": true\n  }\n}\n'


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
    moons(z, files)
    weather(z, files)
    vignette(z, files)
    files["assets/minecraft/sounds.json"] = T.sounds({"ui.button.click": ("block.chest.close", 0.55, 0.9)}).encode()
    return files


def build(version=None):
    version = version or VERSION
    z = T.jar()
    files = derive(z)
    out, from_jar = T.ship(HERE, NAME, version, "blood moon, dripping hearts, closing dark", files, pack_icon())
    return out, len(files), from_jar


def main():
    import hashlib
    out, count, from_jar = build()
    print(f"  {out.name}: {count} files, {out.stat().st_size} bytes, sha1 {hashlib.sha1(out.read_bytes()).hexdigest()}"
          + ("" if from_jar else "  (client jar not found - textures skipped)"))
    return out


if __name__ == "__main__":
    main()
