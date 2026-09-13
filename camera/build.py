#!/usr/bin/env python3
"""
Build Camera: the look of the Camera plugin's camera and its photos, needing no mods.

What it does
------------
The plugin's camera is a recovery compass and its photos are filled maps - vanilla
items, chosen because a player WITHOUT this pack must still see something sensible,
and an `item_model` pointing at a model that only exists in a pack renders as the
purple-and-black missing model for them. So the pack does not add item models of its
own; it overrides the two vanilla item model definitions and puts the vanilla one
back as the fallback:

  assets/minecraft/items/recovery_compass.json
      custom_model_data flag 0 set        -> the camera with its flash lit (8 ticks after a shot)
      custom_model_data float 0 >= 1      -> the camera loaded with film (a paper tab peeks out)
      custom_model_data float 0 == 0      -> the empty camera (dark slot, red light)
      no custom_model_data                -> the vanilla recovery compass, unchanged

  assets/minecraft/items/filled_map.json
      custom_model_data flag 0 set        -> a polaroid: white card, the picture area tinted by
                                             the item's map_color (the plugin sets it to the
                                             photo's average colour, so every photo's thumbnail
                                             carries its own light)
      otherwise                           -> the vanilla filled map, unchanged

The plugin writes exactly those components: floats [film count], flags [flashing] on the
camera, flags [true] plus map_color on a photo. Real recovery compasses and real maps
carry no custom_model_data and hit the fallback, which is read from the installed client
jar at build time so it is always the running version's own definition.

Held in hand, a filled map is drawn by the client as the big map picture regardless of
its model - that is decided by the item type - so a photo still fills the screen when
you hold it and shows its picture in an item frame; the polaroid is what you see in the
inventory, in the hotbar and on the ground.

Art
---
16x16 sprites in the tables below, one character per pixel, `PALETTE` giving each
character its colour. The camera is one drawing (`CAMERA`) with the LED, the paper tab
and the flash derived per state, so the three never drift apart. `preview.png` next to
this script shows all the sprites at 8x - look at it after every change.

Building
--------
`python3 build.py` writes `src/`, `Camera-<v>.zip`, `preview.png`. Shared code in
`../themelib.py`.
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import themelib as T  # noqa: E402

NAME = "Camera"
VERSION = "1.0.0"         # bumped with ../bump.py, never by hand

PALETTE = {
    ".": None,
    "k": (40, 36, 44, 255),        # outline
    "w": (245, 240, 228, 255),     # body, cream
    "W": (255, 255, 250, 255),     # body highlight
    "s": (214, 206, 190, 255),     # body shade
    "v": (60, 64, 80, 255),        # viewfinder glass, film slot
    "f": (200, 214, 232, 255),     # flash window
    "F": (255, 250, 205, 255),     # flash window, lit
    "y": (255, 230, 120, 255),     # flash rays
    "L": (96, 98, 108, 255),       # lens ring
    "l": (26, 26, 34, 255),        # lens glass
    "b": (110, 170, 235, 255),     # lens glint, blue
    "B": (230, 245, 255, 255),     # lens glint, white
    "r": (225, 70, 80, 255),       # shutter button
    "R": (250, 140, 150, 255),     # shutter button highlight
    "g": (90, 220, 110, 255),      # LED, film loaded
    "o": (220, 60, 60, 255),       # LED, no film
    "1": (230, 80, 80, 255),       # the stripe: red
    "2": (240, 160, 60, 255),      #             orange
    "3": (240, 220, 80, 255),      #             yellow
    "4": (90, 200, 110, 255),      #             green
    "5": (80, 140, 230, 255),      #             blue
    "p": (255, 255, 255, 255),     # photo paper
    "P": (216, 216, 222, 255),     # photo paper shade / card edge
    "c": (160, 160, 170, 255),     # the scribble on a photo's border
    # the picture area of a polaroid: greys the map_color tint multiplies
    "9": (255, 255, 255, 255),
    "8": (236, 236, 236, 255),
    "7": (216, 216, 216, 255),
    "6": (196, 196, 196, 255),
    "A": (176, 176, 176, 255),
    "C": (156, 156, 156, 255),
}

# The camera, loaded with film. Rows 14-15 are the paper tab; the LED at row 7 col 13.
CAMERA = [
    "................",
    "..kkkk...kkkkk..",
    ".kvvvvk.kfffffk.",
    "kkkkkkkkkkkkkkkk",
    "kWWwwwwwwwwwwwsk",
    "kW1wwwkkkkkwrRsk",
    "kw2wwkLLLLLkwwsk",
    "kw3wwkLBllLkwgsk",
    "kw4wwkLlblLkwwsk",
    "kw5wwkLlllLkwwsk",
    "kwwwwkLLLLLkwwsk",
    "kswwwwkkkkkwwwsk",
    "ksvvvvvvvvvvvvsk",
    "kkkkkkkkkkkkkkkk",
    "....pppppppp....",
    "....PPPPPPPP....",
]

# The polaroid, layer 0: the card. The window (rows 2-9, cols 4-11) is clear so layer 1 shows.
POLAROID_CARD = [
    "..PPPPPPPPPPPP..",
    "..PppppppppppP..",
    "..Pp........pP..",
    "..Pp........pP..",
    "..Pp........pP..",
    "..Pp........pP..",
    "..Pp........pP..",
    "..Pp........pP..",
    "..Pp........pP..",
    "..Pp........pP..",
    "..PppppppppppP..",
    "..PppppppppppP..",
    "..PppcccccpppP..",
    "..PppppppppppP..",
    "..PppppppppppP..",
    "..PPPPPPPPPPPP..",
]

# The polaroid, layer 1: the picture, greys from light at the top to darker at the bottom,
# tinted by map_color on the client. A brighter square top right reads as the sky's light.
POLAROID_PICTURE = [
    "................",
    "................",
    "....99999999....",
    "....88888998....",
    "....88888998....",
    "....77777777....",
    "....66666666....",
    "....AAAAAAAA....",
    "....CCCCCCCC....",
    "....CCCCCCCC....",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
]


def sprite(rows):
    """(16, 16, rgba rows) from a table."""
    out = []
    for row in rows:
        assert len(row) == 16, row
        line = bytearray()
        for ch in row:
            px = PALETTE[ch]
            line += bytes(px) if px else b"\x00\x00\x00\x00"
        out.append(line)
    assert len(out) == 16
    return 16, 16, out


def camera_state(state):
    """The camera in one of its three states, derived from the one drawing."""
    rows = list(CAMERA)
    if state == "empty":
        rows[7] = rows[7].replace("g", "o")
        rows[14] = rows[15] = "................"
    elif state == "flash":
        rows[0] = ".........y.y.y.."
        rows[1] = "..kkkk..ykkkkky."
        rows[2] = rows[2].replace("f", "F")
        rows[7] = rows[7].replace("LBllL", "LBBBL")
        rows[8] = rows[8].replace("LlblL", "LBWBL")
        rows[9] = rows[9].replace("LlllL", "LBBBL")
    return sprite(rows)


def textures():
    """Every texture the pack ships, by name - also what serverui/previews.py draws from."""
    return {
        "camera_empty": camera_state("empty"),
        "camera_loaded": camera_state("loaded"),
        "camera_flash": camera_state("flash"),
        "polaroid": sprite(POLAROID_CARD),
        "polaroid_picture": sprite(POLAROID_PICTURE),
    }


def tinted(img, rgb):
    """What the client shows for a tinted layer: the greys multiplied by the colour."""
    r, g, b = rgb
    return T.multiply(img, r / 255, g / 255, b / 255)


def model(name):
    return {"type": "minecraft:model", "model": f"camera:item/{name}"}


def vanilla_definition(z, item):
    """The running client's own definition of an item, as the fallback. Without the jar a plain
    model reference stands in - a real recovery compass would then lose its needle for anyone
    with the pack, so a shipped build always comes from a machine with the client installed."""
    if z is not None:
        return json.loads(z.read(f"assets/minecraft/items/{item}.json"))["model"]
    return {"type": "minecraft:model", "model": f"minecraft:item/{item}"}


def camera_definition(z):
    return {"model": {
        "type": "minecraft:condition",
        "property": "minecraft:custom_model_data", "index": 0,
        "on_true": model("camera_flash"),
        "on_false": {
            "type": "minecraft:range_dispatch",
            "property": "minecraft:custom_model_data", "index": 0,
            "entries": [
                {"threshold": 0.0, "model": model("camera_empty")},
                {"threshold": 1.0, "model": model("camera_loaded")},
            ],
            "fallback": vanilla_definition(z, "recovery_compass"),
        },
    }}


def polaroid_definition(z):
    return {"model": {
        "type": "minecraft:condition",
        "property": "minecraft:custom_model_data", "index": 0,
        "on_true": {
            "type": "minecraft:model", "model": "camera:item/polaroid",
            "tints": [
                {"type": "minecraft:constant", "value": -1},
                {"type": "minecraft:map_color", "default": 0x8FB4DC},
            ],
        },
        "on_false": vanilla_definition(z, "filled_map"),
    }}


def item_model(*layers):
    return {"parent": "minecraft:item/generated",
            "textures": {f"layer{i}": f"camera:item/{name}" for i, name in enumerate(layers)}}


def preview(scale=8):
    """Every sprite in a row at 8x on a dark ground, the polaroid also tinted as a photo
    of a sunny day would be - written next to this script as preview.png."""
    tex = textures()
    shown = [tex["camera_empty"], tex["camera_loaded"], tex["camera_flash"], tex["polaroid"],
             tex["polaroid_picture"], tinted(tex["polaroid_picture"], (120, 170, 220))]
    pad = 8
    w = (len(shown) * (16 + pad) + pad) * scale
    h = (16 + 2 * pad) * scale
    rows = [bytearray(bytes((46, 50, 62, 255)) * w) for _ in range(h)]

    def blit(img, ox, oy):
        _, _, src = img
        for y in range(16):
            for x in range(16):
                px = src[y][x * 4:x * 4 + 4]
                if px[3] == 0:
                    continue
                for dy in range(scale):
                    row = rows[oy + y * scale + dy]
                    for dx in range(scale):
                        i = (ox + x * scale + dx) * 4
                        row[i:i + 4] = px

    for n, img in enumerate(shown):
        ox = (pad + n * (16 + pad)) * scale
        blit(img, ox, pad * scale)
        if n == 3:  # the card with its picture on top, as the client composes the two layers
            blit(shown[5], ox, pad * scale)
    return T.png_encode(w, h, rows)


def build(version=None):
    version = version or VERSION
    z = T.jar()
    tex = textures()
    files = {}
    for name, img in tex.items():
        files[f"assets/camera/textures/item/{name}.png"] = T.png_encode(*img)
    for name in ("camera_empty", "camera_loaded", "camera_flash"):
        files[f"assets/camera/models/item/{name}.json"] = (json.dumps(item_model(name), indent=2) + "\n").encode()
    files["assets/camera/models/item/polaroid.json"] = (
        json.dumps(item_model("polaroid", "polaroid_picture"), indent=2) + "\n").encode()
    files["assets/minecraft/items/recovery_compass.json"] = (json.dumps(camera_definition(z), indent=2) + "\n").encode()
    files["assets/minecraft/items/filled_map.json"] = (json.dumps(polaroid_definition(z), indent=2) + "\n").encode()

    cam = tex["camera_loaded"]

    def px(x, y):
        sx, sy = (x - 8) // 3, (y - 8) // 3
        if 0 <= sx < 16 and 0 <= sy < 16:
            p = T.pixel(cam, sx, sy)
            return p if p[3] else None
        return None

    (HERE / "preview.png").write_bytes(preview())
    out, from_jar = T.ship(HERE, NAME, version, "a camera and its polaroids", files,
                           T.icon((70, 82, 110, 255), px))
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
