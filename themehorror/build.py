#!/usr/bin/env python3
"""
ThemeHorror - the layer Haunt wears while its director is armed.

A companion layer that stays loaded and paints only STATES the server puts a player in,
so Haunt can switch the look on and off per player without a pack reload anyone could
see: blood hearts that drip on the absorbing / blinking / frozen heart sprites (the cues
Haunt plays on a victim), and the NEW MOON repainted as a blood moon - the `bloodmoon`
cue shifts a player's sky to that phase while the director is armed. A natural new-moon
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
VERSION = "2.0.0"      # bumped with ../bump.py, never by hand

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
    moons(z, files)
    return files


def build(version=None):
    version = version or VERSION
    z = T.jar()
    files = derive(z)
    out, from_jar = T.ship(HERE, NAME, version, "blood hearts and a blood moon, on cue", files, pack_icon())
    return out, len(files), from_jar


def main():
    import hashlib
    out, count, from_jar = build()
    print(f"  {out.name}: {count} files, {out.stat().st_size} bytes, sha1 {hashlib.sha1(out.read_bytes()).hexdigest()}"
          + ("" if from_jar else "  (client jar not found - textures skipped)"))
    return out


if __name__ == "__main__":
    main()
