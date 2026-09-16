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
      custom_model_data float 1           -> which camera: 0 the plain one, 1 the flash camera
      custom_model_data flag 0 set        -> that camera with its flash lit (8 ticks after a shot)
      custom_model_data float 0 >= 1      -> that camera loaded with film (a paper tab peeks out)
      custom_model_data float 0 == 0      -> that camera empty (dark slot, red light)
      no custom_model_data                -> the vanilla recovery compass, unchanged
      (a camera made before the variants has no float 1 and still draws as the plain camera:
       the kind dispatch falls back to it, and only a compass with no float 0 either reaches
       the vanilla definition)

  assets/minecraft/items/spyglass.json
      the same three states for the zoom camera, vanilla spyglass as the fallback. The zoom
      camera IS a spyglass because the client's zoom cannot be asked for: Player.isScoping()
      is "using an item AND that item is minecraft:spyglass" (read from the 26.2 client), so
      no component and no pack can make anything else zoom.

  assets/minecraft/items/filled_map.json
      custom_model_data flag 0 set        -> a polaroid: white card, the picture area tinted by
                                             the item's average colour (until 26.3 removed the
                                             photo's average colour, so every photo's thumbnail
                                             carries its own light)
      otherwise                           -> the vanilla filled map, unchanged

  assets/minecraft/items/map.json
      custom_model_data flag 0 set        -> film: the same card before a picture is on it, a dark
                                             undeveloped window with a sheen and the camera's stripe
      otherwise                           -> the vanilla empty map, unchanged

The plugin writes exactly those components: floats [film count], flags [flashing] on the
camera, flags [true] on a photo, flags [true] on film (an empty map underneath). Real recovery compasses and real maps
carry no custom_model_data and hit the fallback, which is read from the installed client
jar at build time so it is always the running version's own definition.

In the hand the camera is a real object, not a flat sprite
------------------------------------------------------
A `generated` item model is the 16x16 drawing extruded a pixel deep, which is fine in the
inventory and reads as a card edge-on when the camera is raised to the face. The camera is
therefore a `select` on `display_context`, exactly as vanilla's own spyglass is: the flat
sprite in the gui, on the ground, in a frame and on a shelf, and a little three-dimensional
camera - a body, a lens barrel, the flash unit - in either hand and on a head.

Its geometry sits on the spyglass's own axis (the model's +Y points where you look, -Y is
the end at your eye), because the raise-to-the-face animation the plugin borrows is the
spyglass's: `ItemUseAnimation.SPYGLASS`, which is what makes the arm lift at all. So the
lens points away from you and the viewfinder end is against your eye, and the display
transforms are vanilla's spyglass ones. The faces are cut out of that camera's own 16x16
drawing - the front of the drawing is the lens end, its body rows wrap the sides - so all
nine states (three cameras x empty, loaded, flashing) follow the sprites with no second
set of art to keep in step.

Held in hand, a filled map is drawn by the client as the big map picture regardless of
its model - that is decided by the item type - so a photo still fills the screen when
you hold it and shows its picture in an item frame; the polaroid is what you see in the
inventory, in the hotbar and on the ground.

Aiming raises it, and in first person only the pack can do that
---------------------------------------------------------------
Holding right-click puts the camera at the player's face - but only for everybody else.
Read from the 26.2 client: AvatarRenderer maps ItemUseAnimation.SPYGLASS to
HumanoidModel.ArmPose.SPYGLASS for any item, so third person raises the arm on its own;
ItemInHandRenderer's own use-animation switch has NO spyglass case (NONE, EAT, DRINK,
BLOCK, BOW, TRIDENT, BRUSH, BUNDLE, SPEAR only), because the real spyglass's first-person
look is not an animation at all - Player.isScoping() is hard-coded to minecraft:spyglass
and simply hides the hands while the scope overlay covers the screen. So a camera that is
a recovery compass stays in its ordinary held pose in first person however it is aimed.

The pack puts the raise back: `minecraft:condition` on `minecraft:using_item` picks a
second copy of the same model, `<name>_aiming`, whose first-person display transform lifts
the camera under the crosshair and turns its lens forward (see AIM_POSE for the numbers and
why they are those). Everything else about the two models is identical, so there is still
only one set of art, and a player without the pack sees exactly what they saw before.

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
VERSION = "1.7.1"         # bumped with ../bump.py, never by hand

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
    # the picture area of a polaroid (greys, which the map_color tint used to multiply - 26.3 removed it)
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

# The flash camera: the same body with a real flash unit on top, always bright.
FLASH_CAMERA = list(CAMERA)
FLASH_CAMERA[0] = "........kwwwwk.."
FLASH_CAMERA[1] = "..kkkk..kFFFFFk."
FLASH_CAMERA[2] = ".kvvvvk.kFFFFFk."

# The zoom camera: the same body with a fat telephoto barrel, the shutter button moved up
# out of its way. It is a spyglass underneath - that is the only item the client zooms with.
ZOOM_CAMERA = [
    "................",
    "..kkkk...kkkkk..",
    ".kvvvvk.kfffffk.",
    "kkkkkkkkkkkkkkkk",
    "kWWwwwwwwwwwrRsk",
    "kW1wkkkkkkkkkwsk",
    "kw2kLLLLLLLLLksk",
    "kw3kLLBlllLLLksk",
    "kw4kLLlbllLLLkgk",
    "kw5kLLlllLLLLksk",
    "kwwkLLLLLLLLLksk",
    "kswkkkkkkkkkkwsk",
    "ksvvvvvvvvvvvvsk",
    "kkkkkkkkkkkkkkkk",
    "....pppppppp....",
    "....PPPPPPPP....",
]

# Where the flash's rays go when a shot has just been taken: over the flash unit, or either
# side of the flash camera's housing, which already fills that row.
RAYS = ".........y.y.y.."
# The three cameras wear three shells. The body is one drawing for all of them, so the plain
# camera's cream, the flash camera's warm yellow and the zoom camera's cold blue are a palette
# override on the body characters alone - which tells them apart in the inventory AND on every
# face of the little three-dimensional camera, where the flash unit and the long barrel were
# the only difference and neither of them is on the side you look at while aiming.
SHELL = {
    "camera": {},
    "flashcam": {"w": (247, 231, 176, 255), "W": (255, 246, 214, 255), "s": (222, 198, 138, 255)},
    "zoomcam": {"w": (198, 222, 240, 255), "W": (228, 242, 255, 255), "s": (160, 190, 214, 255)},
}

RAYS_FLASHCAM = "......y.kwwwwk.y"

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

# Film: the card before anything is on it - the window an undeveloped dark slate with one
# sheen line, the camera's stripe where a photo carries its scribble.
FILM = [
    "..PPPPPPPPPPPP..",
    "..PppppppppppP..",
    "..PpvvvvvvvvpP..",
    "..PpvvvvvvvfpP..",
    "..PpvvvvvvfvpP..",
    "..PpvvvvvfvvpP..",
    "..PpvvvvfvvvpP..",
    "..PpvvvfvvvvpP..",
    "..PpvvvvvvvvpP..",
    "..PpvvvvvvvvpP..",
    "..PppppppppppP..",
    "..PppppppppppP..",
    "..Ppp12345pppP..",
    "..PppppppppppP..",
    "..PppppppppppP..",
    "..PPPPPPPPPPPP..",
]

# The polaroid, layer 1: the picture, greys from light at the top to darker at the bottom,
# tinted by map_color on the client until 26.3 removed it. A brighter square top right reads as the sky's light.
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


def sprite(rows, shell=None):
    """(16, 16, rgba rows) from a table, `shell` overriding palette entries for this camera."""
    out = []
    for row in rows:
        assert len(row) == 16, row
        line = bytearray()
        for ch in row:
            px = (shell or {}).get(ch, PALETTE[ch])
            line += bytes(px) if px else b"\x00\x00\x00\x00"
        out.append(line)
    assert len(out) == 16
    return 16, 16, out


def camera_state(state, body=None, rays=RAYS, shell=None):
    """One camera in one of its three states, derived from that camera's one drawing: no film
    (red light, no paper tab), loaded, and the moment after a shot (window and lens alight)."""
    rows = list(body or CAMERA)
    if state == "empty":
        rows = [r.replace("g", "o") for r in rows]
        rows[14] = rows[15] = "................"
    elif state == "flash":
        rows[0] = rays
        # window and lens alight in one pass - chained replaces would whiten the glint twice over
        alight = str.maketrans("flb", "FbB")
        rows = [r.translate(alight) for r in rows]
    return sprite(rows, shell)


def textures():
    """Every texture the pack ships, by name - also what serverui/previews.py draws from."""
    out = {}
    for prefix, body, rays in (("camera", CAMERA, RAYS), ("flashcam", FLASH_CAMERA, RAYS_FLASHCAM),
                               ("zoomcam", ZOOM_CAMERA, RAYS)):
        for state in ("empty", "loaded", "flash"):
            out[f"{prefix}_{state}"] = camera_state(state, body, rays, SHELL[prefix])
    out["polaroid"] = sprite(POLAROID_CARD)
    out["polaroid_picture"] = sprite(POLAROID_PICTURE)
    for bucket, rgb in POLAROID_TINTS.items():
        out[f"polaroid_picture_{bucket}"] = tinted(out["polaroid_picture"], rgb)
    out["film"] = sprite(FILM)
    return out


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


def by_film(prefix, lit, fallback):
    """One camera's three states: the flash while it is lit, otherwise empty or loaded by the
    film count. `fallback` is what a stack with no film count at all draws as."""
    if lit:
        return handed(f"{prefix}_flash")
    return {
        "type": "minecraft:range_dispatch",
        "property": "minecraft:custom_model_data", "index": 0,
        "entries": [
            {"threshold": 0.0, "model": handed(f"{prefix}_empty")},
            {"threshold": 1.0, "model": handed(f"{prefix}_loaded")},
        ],
        "fallback": fallback,
    }


def camera_definition(z):
    """The recovery compass: which camera (float 1), then its state. The kind dispatch falls back
    to the plain camera, so a camera crafted before the variants still draws as one; only a stack
    with no film count either - a real recovery compass - reaches the vanilla definition.

    Kind 2, the zoom camera, is here as well as in the spyglass definition: an empty zoom camera
    is turned into a compass by the plugin, because a spyglass raises itself from the item and
    nothing server-side can stop a camera with no film from scoping while it is one."""
    vanilla = vanilla_definition(z, "recovery_compass")

    def by_kind(lit):
        return {
            "type": "minecraft:range_dispatch",
            "property": "minecraft:custom_model_data", "index": 1,
            "entries": [
                {"threshold": 0.0, "model": by_film("camera", lit, vanilla)},
                {"threshold": 1.0, "model": by_film("flashcam", lit, vanilla)},
                {"threshold": 2.0, "model": by_film("zoomcam", lit, vanilla)},
            ],
            "fallback": by_film("camera", lit, vanilla),
        }

    return {"model": {
        "type": "minecraft:condition",
        "property": "minecraft:custom_model_data", "index": 0,
        "on_true": by_kind(True),
        "on_false": by_kind(False),
    }}


def zoom_definition(z):
    """The spyglass: the zoom camera, vanilla spyglass for a real one."""
    vanilla = vanilla_definition(z, "spyglass")
    return {"model": {
        "type": "minecraft:condition",
        "property": "minecraft:custom_model_data", "index": 0,
        "on_true": by_film("zoomcam", True, vanilla),
        "on_false": by_film("zoomcam", False, vanilla),
    }}


# The polaroid's picture area, tinted per **bucket**: the plugin works out which one a finished
# photo falls into from its own average colour and writes it as custom_model_data strings[0], so a
# shelf of photos is not a shelf of identical white cards. Six is deliberate - the item model is
# chosen from components and nothing can carry a whole photo's colour, so this is a handful of
# recognisable kinds (a night shot, a sunset, sky, forest, desert, stone), not a per-photo tint.
# It replaces the map_color tint 26.3 removed, and keeps working without any component at all:
# a photo with no bucket falls back to the plain grey card.
POLAROID_TINTS = {
    "night": (58, 66, 96),
    "dawn": (214, 138, 92),
    "sky": (126, 172, 222),
    "green": (114, 170, 104),
    "sand": (216, 196, 150),
    "stone": (156, 156, 162),
}


def polaroid_definition(z):
    """The polaroid, and the client's own filled_map for a real one.

    **No `minecraft:map_color` tint any more.** 26.3 removed the `map_color` item component and
    the tint source that read it, and an item definition naming a tint source the client does not
    know **fails to parse as a whole** - so on a 26.3 client every filled_map, ours and vanilla's,
    fell back to the missing-model cube. (Vanilla's own `items/filled_map.json` dropped the tint
    in the same release; `vanilla_definition` picks that up by itself, as long as the pack is
    built against a 26.3 client - `MC_VERSION=26.3` until the main server has run once.)

    The picture layer is therefore drawn at full colour instead of being multiplied by the photo's
    average. A polaroid in the inventory is the same for every photo now; the picture itself, in
    the hand and in a frame, is unaffected - that is the map, not the item model."""
    return {"model": {
        "type": "minecraft:condition",
        "property": "minecraft:custom_model_data", "index": 0,
        "on_true": {
            "type": "minecraft:select",
            "property": "minecraft:custom_model_data", "index": 0,
            "cases": [{"when": bucket, "model": model(f"polaroid_{bucket}")} for bucket in POLAROID_TINTS],
            "fallback": model("polaroid"),
        },
        "on_false": vanilla_definition(z, "filled_map"),
    }}


def film_definition(z):
    return {"model": {
        "type": "minecraft:condition",
        "property": "minecraft:custom_model_data", "index": 0,
        "on_true": model("film"),
        "on_false": vanilla_definition(z, "map"),
    }}


# The lens of each camera in its own 16x16 drawing: [x0, y0, x1, y1], used as the uv of the
# barrel. The zoom camera's telephoto is wider and its barrel longer.
LENS_UV = {"camera": [5, 5, 12, 12], "flashcam": [5, 5, 12, 12], "zoomcam": [3, 5, 14, 12]}
BODY_UV = [1, 4, 2, 13]         # one opaque column of the body, stretched: a plain camera side
BACK_UV = [1, 4, 5, 13]         # the body's left edge with its stripe: the back, the end at your eye
EYE_UV = [2, 2, 6, 3]           # the viewfinder itself, on the little eyepiece that end carries
FLASH_UV = [8, 1, 14, 4]        # the flash window: the little unit on top of the flash camera

# The aim pose: where the camera goes in FIRST person while it is being held up.
#
# The client places a held item with ItemInHandRenderer.applyItemArmTransform, which only
# translates: (+/-0.56, -0.52, -0.72) blocks - right/left, down, and away into the screen.
# A display transform is applied inside that same frame (+X right, +Y up, -Z into the
# screen) and its translation is in sixteenths, so these numbers undo that placement:
#   x   -7   most of the way in from the +0.56 to the right, so it sits under the crosshair
#            (for the off hand the client negates x itself, so both entries are identical)
#   y   +3.5 lifts it from the hip
#   z   -2   pushes it a little further out, because a camera at arm's length is a raised
#            camera and a camera against the eye is a blindfold: at these numbers it covers
#            21 degrees in the lower middle (screen y -0.25..-0.77 of the half-screen) and
#            leaves the crosshair and the whole upper view clear. Idle it is off in the
#            bottom-right corner (x +0.45..+0.80), so the move up and in reads as the raise.
# The rotation lays the model down: its +Y is the lens (the spyglass axis it is built on),
# and -90 about X turns +Y into -Z, so the lens points where you are looking and the
# viewfinder end faces you; the small yaw shows an edge of the body, so it reads as an
# object rather than a sticker. Vanilla has no such pose to copy - the real spyglass is not
# rendered in first person at all (Player.isScoping() hides the hands and draws the scope
# overlay instead), and ItemInHandRenderer's use-animation switch has no SPYGLASS case, so
# a SPYGLASS-animation item that is not minecraft:spyglass keeps its ordinary held pose.
# Third person needs nothing: AvatarRenderer maps the animation to ArmPose.SPYGLASS itself.
AIM_POSE = {"rotation": [-90, -12, 0], "translation": [-7, 3.5, -2]}


def fill_gaps(img):
    """The same drawing with its holes filled, for the three-dimensional camera.

    A sprite may be transparent wherever it likes - the icon is a picture on a background. A
    box may not: a transparent texel is a hole, and through it you see the unlit inside of the
    model (the far wall is back-face culled, so it is a window into nothing). The camera's own
    drawing is full of them - the border, the ring around the lens, the rows above the body
    where the viewfinder sits - and every one of them was a gap in the camera held to the eye.
    So each transparent texel takes the colour of the nearest opaque one, which keeps the model
    in step with the art by construction: there is still one drawing per camera state.
    """
    w, h, _ = img
    out = T.solid(w, h, (0, 0, 0, 0))
    opaque = [(x, y) for y in range(h) for x in range(w) if T.pixel(img, x, y)[3] > 0]
    for y in range(h):
        for x in range(w):
            here = T.pixel(img, x, y)
            if here[3] > 0:
                T.set_pixel(out, x, y, here)
                continue
            ox, oy = min(opaque, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
            r, g, b, _ = T.pixel(img, ox, oy)
            T.set_pixel(out, x, y, (r, g, b, 255))
    return out


def box(frm, to, faces):
    return {"from": frm, "to": to, "faces": faces}


def all_faces(uv, texture="#camera", ends=None):
    """The four sides from one uv rectangle, the two ends from another (default: the same)."""
    out = {side: {"uv": list(uv), "texture": texture} for side in ("north", "east", "south", "west")}
    out["up"] = {"uv": list(ends or uv), "texture": texture}
    out["down"] = {"uv": list(ends or uv), "texture": texture}
    return out


def in_hand_model(name, aiming=False):
    """The camera as an object: a body, a barrel with the lens at its far end, and the flash
    camera's unit beside it. Cut from that camera's own drawing, on the spyglass's axis.

    With `aiming`, the same object with a first-person pose that raises it: see AIM_POSE."""
    prefix = name.rsplit("_", 1)[0]
    lens = LENS_UV[prefix]
    long_barrel = prefix == "zoomcam"
    elements = [
        # the body: the end at -Y carries the viewfinder, so it is the one against your eye
        box([5.5, 3, 5.5], [10.5, 9, 10.5], {
            **all_faces(BODY_UV),
            "down": {"uv": list(BACK_UV), "texture": "#camera"},
        }),
        # the barrel, pointing where you look, the lens on its far face
        box([6.5, 9, 6.5], [9.5, 13.5 if long_barrel else 11.5, 9.5],
            all_faces(lens, ends=lens)),
    ]
    # the eyepiece on the back, which in the aim pose is the thing you are looking into
    elements.append(box([7, 1.5, 7], [9, 3, 9], all_faces(EYE_UV)))
    if prefix == "flashcam":
        elements.append(box([5.5, 9, 6.5], [7.5, 10.5, 8.5], all_faces(FLASH_UV)))
    return {
        "textures": {"camera": f"camera:item/{name}_solid", "particle": f"camera:item/{name}"},
        "elements": elements,
        "display": {
            "thirdperson_righthand": {"translation": [0, -2, 0]},
            "thirdperson_lefthand": {"translation": [0, -2, 0]},
            "head": {"rotation": [90, 0, 0], "translation": [0, 0, -16], "scale": [1.6, 1.6, 1.6]},
            **({"firstperson_righthand": dict(AIM_POSE),
                "firstperson_lefthand": dict(AIM_POSE)} if aiming else {}),
        },
    }


def handed(name):
    """The flat drawing where a picture is wanted, the little camera where a thing is held.
    Vanilla's spyglass splits its own contexts exactly this way."""
    return {
        "type": "minecraft:select",
        "property": "minecraft:display_context",
        "cases": [{"when": ["gui", "ground", "fixed", "on_shelf"], "model": model(name)}],
        # held: the little camera, raised to the eye while it is being aimed
        "fallback": {
            "type": "minecraft:condition",
            "property": "minecraft:using_item",
            "on_true": {"type": "minecraft:model", "model": f"camera:item/{name}_aiming"},
            "on_false": {"type": "minecraft:model", "model": f"camera:item/{name}_in_hand"},
        },
    }


def item_model(*layers):
    return {"parent": "minecraft:item/generated",
            "textures": {f"layer{i}": f"camera:item/{name}" for i, name in enumerate(layers)}}


def preview(scale=8):
    """Every sprite in a row at 8x on a dark ground, the polaroid also tinted as a photo
    of a sunny day would be - written next to this script as preview.png."""
    tex = textures()
    shown = [tex["camera_empty"], tex["camera_loaded"], tex["camera_flash"],
             tex["flashcam_loaded"], tex["flashcam_flash"], tex["zoomcam_loaded"],
             tex["polaroid"], tex["polaroid_picture"], tinted(tex["polaroid_picture"], (120, 170, 220)),
             tex["film"]]
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
        if n == 6:  # the card with its picture on top, as the client composes the two layers
            blit(shown[8], ox, pad * scale)
    return T.png_encode(w, h, rows)


def build(version=None):
    version = version or VERSION
    z = T.jar()
    tex = textures()
    files = {}
    for name, img in tex.items():
        files[f"assets/camera/textures/item/{name}.png"] = T.png_encode(*img)
    for name in tex:
        if name.startswith("polaroid"):
            continue
        files[f"assets/camera/models/item/{name}.json"] = (json.dumps(item_model(name), indent=2) + "\n").encode()
        if not name.startswith(("film", "polaroid")):
            files[f"assets/camera/textures/item/{name}_solid.png"] = T.png_encode(*fill_gaps(tex[name]))
            files[f"assets/camera/models/item/{name}_in_hand.json"] = (
                json.dumps(in_hand_model(name), indent=2) + "\n").encode()
            files[f"assets/camera/models/item/{name}_aiming.json"] = (
                json.dumps(in_hand_model(name, aiming=True), indent=2) + "\n").encode()
    files["assets/camera/models/item/polaroid.json"] = (
        json.dumps(item_model("polaroid", "polaroid_picture"), indent=2) + "\n").encode()
    for bucket in POLAROID_TINTS:
        files[f"assets/camera/models/item/polaroid_{bucket}.json"] = (
            json.dumps(item_model("polaroid", f"polaroid_picture_{bucket}"), indent=2) + "\n").encode()
    files["assets/minecraft/items/recovery_compass.json"] = (json.dumps(camera_definition(z), indent=2) + "\n").encode()
    files["assets/minecraft/items/filled_map.json"] = (json.dumps(polaroid_definition(z), indent=2) + "\n").encode()
    files["assets/minecraft/items/map.json"] = (json.dumps(film_definition(z), indent=2) + "\n").encode()
    files["assets/minecraft/items/spyglass.json"] = (json.dumps(zoom_definition(z), indent=2) + "\n").encode()

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
