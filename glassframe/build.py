#!/usr/bin/env python3
"""
Build GlassFrame: glass that joins up, with no mods.

Why a frame around the rim is not possible
------------------------------------------
Vanilla draws a face unless the neighbour occludes it. Stone and glass both
occlude, so a resource pack can never ask "is my neighbour glass?" - which is
why nearly every connected-glass pack ships an assets/minecraft/optifine/ctm
folder and does nothing at all without OptiFine or Continuity.

You can pick, per quad, WHICH neighbour the test looks at: a face may carry a
`cullface` pointing elsewhere than it faces (vanilla does this itself in 52
model faces, chorus_plant being the known one). That lets a 1px border strip on
the north face be erased by the block to the WEST, so a wall's front reads as
one sheet with a frame only on its rim.

It still does not work, and test_culling.py proves why. A strip needs two
conditions at once - "my side is visible" AND "the surface does not continue
this way" - and a quad can test one. Whichever condition you keep, the strip
turns up as a seam in some other orientation: the frame that outlines a wall is
the same geometry that streaks a floor, one axis over. Checked across a floor
and both wall orientations, all 24 strips are a seam in at least one of them and
none survives all three.

So the only glass vanilla can draw with no seams anywhere is glass with no
border anywhere. That is what BORDERLESS builds, and why every pack that
actually looks clean on a vanilla client is a borderless one.

Why the rim cannot also hide under glass
----------------------------------------
A rim strip is culled by the block BESIDE it, so it vanishes when two slabs are
pushed together. Hiding it under another glass block as well needs a second
test - no glass above AND no glass beside - and that cannot be built.

The visible geometry is a union of quads, and each quad is gated by exactly one
"this neighbour does not occlude me" test. A union is an OR. The rim wants an
AND of two such tests, and no arrangement of quads expresses one: adding more
quads only ever adds more ways for something to appear. Even hiding a quad
behind an opaque one buys a term of the form "this neighbour DOES occlude",
never a second negative - and glass is transparent, so there is nothing to hide
behind anyway.

The consequence: a stack of glass slabs outlines every layer, not just the top.
Culling the rim by the block above instead of the one beside inverts the
problem - only the top layer is outlined, but every block in it draws its own
box, which is the grid this pack exists to remove. Drawing the outline only
where it belongs needs to know both neighbours at once, which on a vanilla
client only a plugin can do, by placing display entities along the edge.

The builds
----------
rim         the default. Clear glass everywhere, with the border kept on the
            two flat sides only, so a glass floor or roof is outlined at its
            edge while every upright side stays perfectly clear. Both of those
            strips run sideways, which is what keeps them off the hidden faces
            between two floor blocks. The cost is a tall wall: its up and down
            sides are hidden between stacked blocks, yet their strips face out
            of the wall and nothing there can cull them, so a wall more than one
            block high keeps faint level lines.
borderless  no border at all, anywhere. The only build with zero seams in every
            orientation, and the only one a solid glass cube renders nothing
            inside.
frame       border strips on all six sides, culled by the neighbour they run
            towards. Clean on a wall seen head on, streaked everywhere else.
            Kept as the evidence for the paragraph above.
cleanfloor  frame, minus the strips along the upright edges.

rim and borderless also rebuild the five vanilla pane templates without their
#edge pieces - the top rail and the end cap drawn from block/glass_pane_top.
The cap is culled by a solid neighbour but never by another pane, so it is
exactly the dark line between two connected panes.

The models sample the vanilla glass sprite rather than replacing it, so another
texture pack layered on top still shows through. The one exception is glass.png
itself, reissued with its opaque flecks at half alpha - see "the specks" below.
"""

import json
import pathlib
import sys
import shutil
import zipfile

PACK_FORMAT = 88          # 26.2, from the client's version.json
NAME = "GlassFrame"
VERSION = "2.8.3"         # bumped with ../bump.py, never by hand

HERE = pathlib.Path(__file__).parent
SRC = HERE / "src"
DIST = HERE / "dist"

COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "light_gray", "cyan", "purple", "blue", "brown", "green",
           "red", "black"]

SIDES = {
    "north": {"axis": "z", "at": 0,  "into": +1},
    "south": {"axis": "z", "at": 16, "into": -1},
    "west":  {"axis": "x", "at": 0,  "into": +1},
    "east":  {"axis": "x", "at": 16, "into": -1},
    "up":    {"axis": "y", "at": 16, "into": -1},
    "down":  {"axis": "y", "at": 0,  "into": +1},
}

IN_PLANE = {
    "north": [("x", "west", "east"), ("y", "down", "up")],
    "south": [("x", "west", "east"), ("y", "down", "up")],
    "west":  [("z", "north", "south"), ("y", "down", "up")],
    "east":  [("z", "north", "south"), ("y", "down", "up")],
    "up":    [("x", "west", "east"), ("z", "north", "south")],
    "down":  [("x", "west", "east"), ("z", "north", "south")],
}

AXES = ["x", "y", "z"]
CORNER_OFFSET = 0.1


def _point(axis_values):
    return [axis_values[a] for a in AXES]


def _element(side, spans, depth, uv, cullface):
    cfg = SIDES[side]
    coord = cfg["at"] + cfg["into"] * depth
    low, high = dict(spans), dict(spans)
    for axis in spans:
        low[axis], high[axis] = spans[axis]
    low[cfg["axis"]] = high[cfg["axis"]] = coord
    return {
        "from": _point(low),
        "to": _point(high),
        "faces": {side: {"uv": uv, "texture": "#glass", "cullface": cullface}},
    }


def side_elements(side, mode):
    (a1, a1_low, a1_high), (a2, a2_low, a2_high) = IN_PLANE[side]
    # A face with no border at all: the whole side, sampling only the inside of
    # the texture so the ring never appears. Culled by its own side, exactly as
    # vanilla glass is, so two sheets facing each other still merge.
    plain = [_element(side, {a1: (0, 16), a2: (0, 16)}, 0, [1, 1, 15, 15], side)]
    if mode == "borderless":
        return plain
    if mode in ("rim", "rimtop"):
        # Border kept on the two flat sides only, so a glass floor or roof is
        # outlined while every upright side stays clear. Both of these strips
        # run sideways, which is what keeps them off the hidden faces between
        # two floor blocks. The cost is a wall: its up and down sides are hidden
        # between stacked blocks, yet their strips face out of the wall and no
        # neighbour there can cull them, so a tall wall keeps faint level lines.
        if side not in ("up", "down"):
            return plain
        # rimtop outlines the top only. A floating slab seen from above
        # otherwise shows its underside rim through the glass as a second line
        # a block below the first - the doubled outline. The cost is a glass
        # roof seen from below, which then has no outline at all.
        if mode == "rimtop" and side == "down":
            return plain
    out = [
        _element(side, {a1: (1, 15), a2: (1, 15)}, 0, [1, 1, 15, 15], side),
        _element(side, {a1: (0, 1), a2: (0, 16)}, 0, [0, 0, 1, 16], a1_low),
        _element(side, {a1: (15, 16), a2: (0, 16)}, 0, [15, 0, 16, 16], a1_high),
    ]
    if mode in ("frame", "rim", "rimtop") or side in ("up", "down"):
        out += [
            _element(side, {a1: (0, 16), a2: (0, 1)}, CORNER_OFFSET, [0, 15, 16, 16], a2_low),
            _element(side, {a1: (0, 16), a2: (15, 16)}, CORNER_OFFSET, [0, 0, 16, 1], a2_high),
        ]
    return out


def block_model(texture, mode):
    elements = []
    for side in SIDES:
        elements.extend(side_elements(side, mode))
    return {
        "parent": "minecraft:block/block",
        "textures": {
            "particle": texture,
            # vanilla glass carries force_translucent in 26.2; without it the
            # block lands in the wrong render pass
            "glass": {"force_translucent": True, "sprite": texture},
        },
        "elements": elements,
    }


# The five vanilla pane templates, rebuilt with only their #pane faces. What is
# dropped are the #edge pieces: the top and bottom rail and the end cap, drawn
# from block/glass_pane_top. The cap is culled by a solid neighbour but not by
# another pane, so it is exactly the dark line between two connected panes.
# UVs stay inside the sprite (1..15) so the border ring never shows either.
def texel(unit):
    """Where a point on a block face lands in the texture, once the border ring is
    skipped: 16 units of surface across 14 texels. Panes are mapped at the same rate,
    so a fleck is the same size on a pane as on a block - sampling a pane's 7-unit arm
    across 7 texels instead drew them 14% smaller, which is most of why panes looked
    fainter than blocks even at identical alpha."""
    return round(1 + unit * 14 / 16, 4)


PANE_TEMPLATES = {
    "template_glass_pane_post": {
        "from": [7, 0, 7], "to": [9, 16, 9],
        "faces": {"north": (7, 9), "south": (7, 9), "west": (7, 9), "east": (7, 9)},
    },
    "template_glass_pane_side": {
        "from": [7, 0, 0], "to": [9, 16, 7],
        "faces": {"west": (0, 7), "east": (0, 7)},
    },
    "template_glass_pane_side_alt": {
        "from": [7, 0, 9], "to": [9, 16, 16],
        "faces": {"west": (9, 16), "east": (9, 16)},
    },
    "template_glass_pane_noside": {
        "from": [7, 0, 7], "to": [9, 16, 9],
        "faces": {"north": (7, 9)},
    },
    "template_glass_pane_noside_alt": {
        "from": [7, 0, 7], "to": [9, 16, 9],
        "faces": {"south": (7, 9)},
    },
}


def pane_template(spec):
    return {
        "textures": {"particle": "#pane"},
        "elements": [{
            "from": spec["from"], "to": spec["to"],
            # across = the arm's own span, down = the full height of the block
            "faces": {side: {"uv": [texel(across[0]), texel(0),
                                    texel(across[1]), texel(16)],
                             "texture": "#pane"}
                      for side, across in spec["faces"].items()},
        }],
    }


# ---------------------------------------------------------------- the specks
# Clear glass carries a few fully opaque flecks in the middle of its texture. With
# the border gone they are the only thing left on a sheet, and at alpha 255 they
# read as hard white chips against glass that is otherwise invisible. At 30% they
# still catch the light without drawing the eye. This is the only thing setting
# how strong they are: blocks and panes sample the same texture at the same rate
# (see texel()), so whatever this says, both shapes agree.
#
# This is the one texture the pack ships. Stained glass needs nothing: its interior
# is already 40-61% alpha, well under half. The vanilla texture is read from the
# installed client, so nothing is vendored into the repo that Mojang did not
# already put on this machine, and the pack still builds without it.

SPECK_ALPHA = 77         # out of 255, so 30% - blocks
PANE_SPECK_ALPHA = 128   # 50% - panes, which need more to read the same


# A pane is a far smaller piece of glass than a block face, so at equal alpha it
# simply carries fewer flecks and all but disappears. Sampling the sprite more
# densely would fix the count but shrink each fleck, so instead panes get their
# own copy of the texture with the flecks left stronger. Only clear glass needs
# it; stained panes are already 40-61% in their own textures.
PANE_TEXTURE = "glassframe_pane"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import themelib as _themelib  # noqa: E402  - the client jar of the version the servers run (MC_VERSION overrides)
CLIENT_JAR = _themelib.CLIENT_JAR


def _png_decode(data):
    """Any 8-bit PNG in, RGBA rows out. Minecraft's sprites are a mix of true colour,
    greyscale and palette forms, so normalise rather than assume."""
    import struct, zlib
    pos, idat, palette, transparency = 8, b"", None, None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ, chunk = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, colour = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"PLTE":
            palette = chunk
        elif typ == b"tRNS":
            transparency = chunk
        pos += 12 + ln
    if depth != 8:
        raise ValueError(f"expected 8 bits per channel, got {depth}")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    raw, stride, lines, prev, i = zlib.decompress(idat), w * channels, [], bytearray(w * channels), 0
    for _ in range(h):
        filt, line, i = raw[i], bytearray(raw[i + 1:i + 1 + stride]), i + 1 + stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if filt == 1:
                line[x] = (line[x] + a) & 255
            elif filt == 2:
                line[x] = (line[x] + b) & 255
            elif filt == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        lines.append(bytearray(line))
        prev = line
    rows = []
    for line in lines:
        row = bytearray(w * 4)
        for x in range(w):
            if colour == 6:
                row[x * 4:x * 4 + 4] = line[x * 4:x * 4 + 4]
            elif colour == 2:
                row[x * 4:x * 4 + 3] = line[x * 3:x * 3 + 3]
                row[x * 4 + 3] = 255
            elif colour == 4:
                grey, alpha = line[x * 2], line[x * 2 + 1]
                row[x * 4:x * 4 + 4] = bytes((grey, grey, grey, alpha))
            elif colour == 0:
                grey = line[x]
                row[x * 4:x * 4 + 4] = bytes((grey, grey, grey, 255))
            else:                                   # palette
                idx = line[x]
                row[x * 4:x * 4 + 3] = palette[idx * 3:idx * 3 + 3]
                row[x * 4 + 3] = transparency[idx] if transparency and idx < len(transparency) else 255
        rows.append(row)
    return w, h, rows


def _png_encode(w, h, rows):
    import struct, zlib, binascii
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", binascii.crc32(tag + body) & 0xffffffff))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def fade_specks(models_dir):
    """Write the two glass textures, flecks toned down - the block one and the pane
    one, which keeps them stronger. False if the client jar was not there to read."""
    import zipfile
    if not CLIENT_JAR.exists():
        return False
    with zipfile.ZipFile(CLIENT_JAR) as jar:
        source = jar.read("assets/minecraft/textures/block/glass.png")
    out = models_dir.parent.parent / "textures" / "block"
    out.mkdir(parents=True, exist_ok=True)
    for name, ceiling in (("glass", SPECK_ALPHA), (PANE_TEXTURE, PANE_SPECK_ALPHA)):
        w, h, rows = _png_decode(source)
        # everything opaque comes down: the flecks, and the border ring too, which
        # the models never sample but which would be the one hard edge left if
        # anything ever did
        for y in range(h):
            for x in range(w):
                if rows[y][x * 4 + 3] > ceiling:
                    rows[y][x * 4 + 3] = ceiling
        (out / f"{name}.png").write_bytes(_png_encode(w, h, rows))

    # Stained glass ships untouched, at vanilla's own 40-61%. It was thinned for a
    # while because the GlassRim bars are made of it and a display entity has no alpha
    # of its own - but a see-through bar cuts a hole in the water behind it whatever its
    # alpha is (a display is drawn before the translucent terrain pass and writes depth
    # across its whole box), and the bar's own opacity is the only thing hiding that
    # hole. Thinning them did not cause the missing water, it uncovered it.
    return True


def pack_icon():
    """pack.png, 64x64: what a window looks like with this pack and GlassRim - four glass
    blocks reading as ONE sheet: the vanilla sprite's interior tiled 2x2 at 2x, no lines
    between the blocks, and a single frame around the whole thing in the sprite's own
    border colour. Over a dusk-blue ground so the clear sheet reads as glass. Without the
    client jar, a plain pale sheet."""
    size, ground = 64, (38, 52, 74, 255)
    rows = [bytearray(bytes(ground) * size) for _ in range(size)]
    sprite = None
    if CLIENT_JAR.exists():
        import zipfile
        with zipfile.ZipFile(CLIENT_JAR) as jar:
            w, h, px = _png_decode(jar.read("assets/minecraft/textures/block/glass.png"))
        sprite = [[tuple(px[y][x * 4:x * 4 + 4]) for x in range(w)] for y in range(h)]
    for ty in range(2):
        for tx in range(2):
            for y in range(16):
                for x in range(16):
                    if sprite is not None:
                        # the outer ring is the border the pack removes; sample the inside only
                        sx, sy = 1 + (x * 14) // 16, 1 + (y * 14) // 16
                        r, g, b, a = sprite[sy][sx]
                    else:
                        r, g, b, a = (255, 255, 255, 70 if (x + y) % 5 else 160)
                    if a == 0:
                        r, g, b, a = 200, 225, 240, 40  # clear glass: a breath of pale blue
                    base = rows[0][0:4]
                    out = tuple(int(base[i] * (1 - a / 255) + (r, g, b)[i] * (a / 255)) for i in range(3))
                    for dy in range(2):
                        row = rows[(ty * 16 + y) * 2 + dy]
                        for dx in range(2):
                            i = ((tx * 16 + x) * 2 + dx) * 4
                            row[i:i + 4] = bytes((*out, 255))
    # one frame around the whole sheet - the outline GlassRim draws where the glass stops
    r, g, b, a = sprite[0][8] if sprite is not None else (255, 255, 255, 255)
    frame = bytes((r, g, b, 255))
    for y in range(size):
        for x in range(size):
            if x < 3 or y < 3 or x >= size - 3 or y >= size - 3:
                rows[y][x * 4:x * 4 + 4] = frame
    return _png_encode(size, size, rows)


# The concrete models for CLEAR glass panes, repointed at the pane texture. Vanilla
# sets "pane" on these, not on the templates, so a template cannot change it - the
# child always wins. Stained panes are left alone and keep their own colours.
PANE_MODELS = ["glass_pane_post", "glass_pane_side", "glass_pane_side_alt",
               "glass_pane_noside", "glass_pane_noside_alt"]


def build(mode="borderless", version=None):
    version = version or VERSION
    if SRC.exists():
        shutil.rmtree(SRC)
    models = SRC / "assets" / "minecraft" / "models" / "block"
    models.mkdir(parents=True)

    label = {"rim": "clear glass, outlined on floors and roofs",
             "rimtop": "clear glass, outlined on top only",
             "borderless": "no borders, blocks and panes",
             "frame": "frame on the rim (streaks - see the docstring)",
             "cleanfloor": "for flat floors seen from above"}[mode]
    # 26.x reads min_format/max_format; a pack with only pack_format plus the
    # older supported_formats array shows as "incompatible or broken"
    (SRC / "pack.mcmeta").write_text(json.dumps({
        "pack": {
            "description": f"GlassFrame {version}§7 - {label}",
            "pack_format": PACK_FORMAT,
            "min_format": PACK_FORMAT,
            "max_format": 2147483647,
        }
    }, indent=2) + "\n")

    names = {"glass": "minecraft:block/glass"}
    for colour in COLOURS:
        names[f"{colour}_stained_glass"] = f"minecraft:block/{colour}_stained_glass"
    for name, texture in names.items():
        (models / f"{name}.json").write_text(
            json.dumps(block_model(texture, mode), indent=1) + "\n")

    written = len(names)
    if mode in ("borderless", "rim", "rimtop"):
        for name, spec in PANE_TEMPLATES.items():
            (models / f"{name}.json").write_text(
                json.dumps(pane_template(spec), indent=1) + "\n")
        written += len(PANE_TEMPLATES)
        for name in PANE_MODELS:
            (models / f"{name}.json").write_text(json.dumps({
                "parent": f"minecraft:block/template_{name}",
                "textures": {"pane": {"force_translucent": True,
                                      "sprite": f"minecraft:block/{PANE_TEXTURE}"}},
            }, indent=1) + "\n")
        written += len(PANE_MODELS)

    if mode in ("borderless", "rim", "rimtop") and not fade_specks(models):
        print("  (client jar not found - shipping without the faded speck texture)")
    (SRC / "pack.png").write_bytes(pack_icon())

    DIST.mkdir(exist_ok=True)
    out = DIST / f"GlassFrame-{version}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SRC.rglob("*")):
            if path.is_file():
                # fixed timestamps: the same models always give the same sha1, so the
                # publisher can tell "rebuilt" from "changed"
                info = zipfile.ZipInfo(path.relative_to(SRC).as_posix(), (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
    return out, written


def main():
    """Build every variant. The borderless build is the one that ships: it lands next to
    this script as NAME-VERSION-borderless.zip (older versions removed), the four evidence
    builds stay in dist/. Returns the shipped zip - the contract ../build.py drives."""
    shipped = None
    for mode, name in (("rim", VERSION),
                       ("rimtop", VERSION + "-toponly"),
                       ("borderless", VERSION + "-borderless"),
                       ("cleanfloor", VERSION + "-cleanfloor"),
                       ("frame", VERSION + "-frame")):
        path, count = build(mode, name)
        print(f"  {path.name:34} {count:2} models  {path.stat().st_size:6} bytes")
        if mode == "borderless":
            shipped = HERE / path.name
            for old in HERE.glob(f"{NAME}-*.zip"):
                old.unlink()
            shutil.copy(path, shipped)
    return shipped


if __name__ == "__main__":
    main()
