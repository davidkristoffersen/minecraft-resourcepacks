#!/usr/bin/env python3
"""
ThemeCalm - the main server's palette.

Deliberately quiet: a warm gold hotbar frame, a slightly warmer sun, and a soft
amethyst chime for every menu click. Nothing that a friend would notice as "a
pack", just a server that feels a shade warmer than vanilla. Derived from the
vanilla textures in the installed client jar at build time; the click is a remap
of vanilla sound events, no audio shipped.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import themelib as T  # noqa: E402

NAME = "ThemeCalm"
VERSION = "1.0.3"      # bumped with ../bump.py, never by hand

GOLD = (1.0, 0.84, 0.45)


def derive(z):
    """Every file this layer ships, from the open client jar (None = no textures, sound only).
    Shared with ServerUI, which draws the before/after preview from the same bytes."""
    files = {}
    img = T.texture(z, "gui/sprites/hud/hotbar_selection.png")
    if img is not None:
        files["assets/minecraft/textures/gui/sprites/hud/hotbar_selection.png"] = T.png_encode(*T.recolour(img, *GOLD))
    img = T.texture(z, "environment/celestial/sun.png")
    if img is not None:
        files["assets/minecraft/textures/environment/celestial/sun.png"] = T.png_encode(*T.multiply(img, 1.0, 0.93, 0.78))
    files["assets/minecraft/sounds.json"] = T.sounds({"ui.button.click": ("block.amethyst_block.chime", 0.35, 1.0)}).encode()
    return files


def build(version=None):
    version = version or VERSION
    z = T.jar()
    files = derive(z)

    def px(x, y):
        d = ((x - 32) ** 2 + (y - 30) ** 2) ** 0.5
        if d < 12:
            return (255, 224, 140, 255)
        if y > 46:
            return (120, 96, 60, 255)
        return None
    out, from_jar = T.ship(HERE, NAME, version, "warm frame, warmer sun, soft chime", files, T.icon((70, 52, 40, 255), px))
    return out, len(files), from_jar


def main():
    import hashlib
    out, count, from_jar = build()
    print(f"  {out.name}: {count} files, {out.stat().st_size} bytes, sha1 {hashlib.sha1(out.read_bytes()).hexdigest()}"
          + ("" if from_jar else "  (client jar not found - textures skipped)"))
    return out


if __name__ == "__main__":
    main()
