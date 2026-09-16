#!/usr/bin/env python3
"""
ThemeLab - the test server's palette.

Teal hearts, a cyan experience bar and hotbar frame, and a short digital blip for
every menu click: the HUD says "lab" the moment you join. Derived from the vanilla
textures in the installed client jar at build time; the click is a remap of vanilla
sound events, no audio shipped. Enabled on the test server only (look-packs config).
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import themelib as T  # noqa: E402

NAME = "ThemeLab"
VERSION = "1.0.3"      # bumped with ../bump.py, never by hand

TEAL = (0.18, 0.86, 0.90)
CYAN = (0.30, 0.92, 1.0)


def derive(z):
    """Every file this layer ships, from the open client jar (None = no textures, sound only).
    Shared with ServerUI, which draws the before/after preview from the same bytes."""
    files = {}
    for kind in ("full", "half"):
        img = T.texture(z, f"gui/sprites/hud/heart/{kind}.png")
        if img is not None:
            files[f"assets/minecraft/textures/gui/sprites/hud/heart/{kind}.png"] = T.png_encode(*T.recolour(img, *TEAL))
    img = T.texture(z, "gui/sprites/hud/experience_bar_progress.png")
    if img is not None:
        files["assets/minecraft/textures/gui/sprites/hud/experience_bar_progress.png"] = T.png_encode(*T.recolour(img, *CYAN))
    img = T.texture(z, "gui/sprites/hud/hotbar_selection.png")
    if img is not None:
        # only the light frame pixels take the colour; the dark shadow pixels stay
        files["assets/minecraft/textures/gui/sprites/hud/hotbar_selection.png"] = T.png_encode(*T.recolour(img, *CYAN))
    files["assets/minecraft/sounds.json"] = T.sounds({"ui.button.click": ("block.note_block.bit", 0.45, 1.3)}).encode()
    return files


def build(version=None):
    version = version or VERSION
    z = T.jar()
    files = derive(z)

    def px(x, y):
        # a flask: neck, then a round body with a bubble
        if 27 <= x < 37 and 10 <= y < 24:
            return (40, 200, 215, 255)
        d = ((x - 32) ** 2 + (y - 38) ** 2) ** 0.5
        if d < 16:
            return (30, 190, 205, 255) if d > 6 or (x - 27) ** 2 + (y - 34) ** 2 > 9 else (220, 250, 255, 255)
        return None
    out, from_jar = T.ship(HERE, NAME, version, "teal HUD, digital clicks", files, T.icon((14, 30, 38, 255), px))
    return out, len(files), from_jar


def main():
    import hashlib
    out, count, from_jar = build()
    print(f"  {out.name}: {count} files, {out.stat().st_size} bytes, sha1 {hashlib.sha1(out.read_bytes()).hexdigest()}"
          + ("" if from_jar else "  (client jar not found - textures skipped)"))
    return out


if __name__ == "__main__":
    main()
