#!/usr/bin/env python3
"""
Build ServerUI: pixel icons for the server's menus, needing no mods.

What it does
------------
The dialog API gives a button a label and nothing else - no icon slot. Our menus
therefore start every label with a glyph (⚡ Actions, 🧩 Plugins, ▶ Try it) and
the vanilla client draws those from Unifont: a thin, monochrome, 16-pixel
fallback that reads as "some symbol" rather than as an icon.

A resource pack may add glyphs to the DEFAULT font, and the first provider that
knows a code point wins. So this pack registers an 8x8 pixel drawing at every
emoji and symbol code point the menus use, in front of the vanilla providers.
Every label keeps working exactly as before; a player with the pack sees an
icon where a player without it sees the Unifont symbol. Nothing is gated and no
Java changes.

Colour
------
Bitmap glyphs are multiplied by the text colour, like every letter. The icons
are therefore drawn in white and greys (four shades) and take the colour of the
label they sit in: the ⚙ in an AQUA settings label is aqua, the ⚠ in a RED
warning is red, a GOLD ★ is gold. That is the same rule the menus already use
for their glyph vocabulary, so one drawing serves every colour, and a label
that wants a fixed-colour icon simply colours that one character WHITE.

Geometry
--------
Cells are 8x8, `height` 8 and `ascent` 7, which is precisely the vanilla
letter grid: capitals fill rows 0-6, row 7 is the descender line. Icons stay in
rows 0-6 so they align with the text beside them, and every drawing is
left-aligned in its cell (the client trims trailing empty columns to find the
advance width, never leading ones). The client adds one pixel of spacing after
each glyph on its own.

Bars
----
A second sheet, `bars.png`, holds 21 progress bars at the private-use code
points U+E000..U+E014: a 22x8 frame whose interior fills from the left in
twenty steps (0 % to 100 % in 5 % steps), drawn in the same greys so the
label colour tints it. These are NOT a fallback-safe override - a client
without the pack draws a missing-glyph box for a private-use character - so
the server only emits them for a player whose client reported this pack
loaded (ServerMenus checks the Look Packs status per player and prints
▰▰▰▱▱ otherwise). One glyph is one bar: TPS on the admin main, a Haunt
category's weight, a player's health, the tier ladder.

Previews
--------
`previews.py` draws one "without | with" picture per look pack (GlassFrame, the
three theme layers, this pack's own icons) and registers each as a glyph at
U+E100.. - a dialog body can show a picture only as text, and a font glyph is
the one text that is a picture. Gated the same way as the bars: the server emits
the glyph only for a client that reported this pack loaded. `preview-packs.png`
next to this script shows them all.

Building
--------
`python3 build.py` reads the vanilla `font/default.json` from the installed
client jar (so the references to the vanilla providers are exactly the current
ones - nothing of Mojang's is vendored), writes `src/`, `ServerUI-<v>.zip`,
`preview.png` (the icon sheet at 6x on dark, for checking the art by eye) and
`preview-bars.png` (the bars the same way).
"""

import binascii
import json
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import shutil
import struct
import zipfile
import zlib

NAME = "ServerUI"
VERSION = "1.16.0"         # bumped with ../bump.py, never by hand
HERE = pathlib.Path(__file__).parent
SRC = HERE / "src"
DIST = HERE / "dist"
sys.path.insert(0, str(HERE.parent))
import themelib as _themelib  # noqa: E402  - the client jar of the version the servers run (MC_VERSION overrides)
CLIENT_JAR = _themelib.CLIENT_JAR
PACK_FORMAT_FALLBACK = 88

CELL = 8
PER_ROW = 16
# shade letters: '#' white, '+' light, '-' mid, '=' dark, '.' transparent
SHADES = {"#": 255, "+": 200, "-": 140, "=": 85}

# progress bars: 22 wide (1px frame + 20px interior), 21 fill states, private use area
BAR_W = 22
BAR_STATES = 20
BAR_BASE = 0xE000

# Every icon is at most 7 columns wide and 7 rows tall (rows 0-6); row 7 is the
# descender line and stays empty so icons sit on the same baseline as letters.
# Order and grouping mirror CLAUDE.md's glyph vocabulary, then hubs, then the
# rest - the sheet is only a texture, the order never matters to the client.
ART = {
    # ---- vocabulary
    "▶": ["##.....",
          "####...",
          "######.",
          "#######",
          "######.",
          "####...",
          "##....."],
    "◀": [".....##",
          "...####",
          ".######",
          "#######",
          ".######",
          "...####",
          ".....##"],
    "▸": [".......",
          "##.....",
          "###....",
          "####...",
          "###....",
          "##.....",
          "......."],
    "✔": ["......#",
          ".....##",
          "....##.",
          "#..##..",
          "##.##..",
          ".###...",
          "..#...."],
    "✎": [".....##",
          "....#=#",
          "...#=#.",
          "..#=#..",
          ".#=#...",
          ".##....",
          "#-....."],
    "⚙": [".#.#.#.",
          ".#####.",
          "##...##",
          ".#...#.",
          "##...##",
          ".#####.",
          ".#.#.#."],
    "❓": [".#####.",
          "##...##",
          ".....##",
          "....##.",
          "...##..",
          ".......",
          "...##.."],
    "⚠": ["...#...",
          "..#.#..",
          "..#.#..",
          ".#.#.#.",
          ".#...#.",
          "#..#..#",
          "#######"],
    "★": ["...#...",
          "..###..",
          "#######",
          ".#####.",
          "..###..",
          ".##.##.",
          ".#...#."],
    "●": ["..###..",
          ".#####.",
          "#######",
          "#######",
          "#######",
          ".#####.",
          "..###.."],
    "○": ["..###..",
          ".#...#.",
          "#.....#",
          "#.....#",
          "#.....#",
          ".#...#.",
          "..###.."],
    "■": [".......",
          ".#####.",
          ".#####.",
          ".#####.",
          ".#####.",
          ".#####.",
          "......."],
    "▢": ["#######",
          "#.....#",
          "#.....#",
          "#.....#",
          "#.....#",
          "#.....#",
          "#######"],
    "•": [".......",
          ".......",
          "..##...",
          ".####..",
          ".####..",
          "..##...",
          "......."],
    "⟳": ["..###.#",
          ".#...##",
          "#...###",
          "#......",
          "#.....#",
          ".#...#.",
          "..###.."],
    "⟲": ["#.###..",
          "##...#.",
          "###...#",
          "......#",
          "#.....#",
          ".#...#.",
          "..###.."],
    "✖": ["#.....#",
          "##...##",
          ".##.##.",
          "..###..",
          ".##.##.",
          "##...##",
          "#.....#"],
    "✘": [".......",
          "##...##",
          ".##.##.",
          "..###..",
          ".##.##.",
          "##...##",
          "......."],
    "→": [".......",
          "...#...",
          "...##..",
          "#######",
          "...##..",
          "...#...",
          "......."],
    "✦": ["...#...",
          "...#...",
          "..###..",
          "#######",
          "..###..",
          "...#...",
          "...#..."],
    "✨": [".#.....",
          "###..#.",
          ".#..###",
          ".....#.",
          "..#....",
          ".###...",
          "..#...."],
    "＋": [".......",
          "...#...",
          "...#...",
          ".#####.",
          "...#...",
          "...#...",
          "......."],
    "ℹ": [".#####.",
          "#..#..#",
          "#.....#",
          "#..#..#",
          "#..#..#",
          "#..#..#",
          ".#####."],
    "⬆": ["...#...",
          "..###..",
          ".#####.",
          "#######",
          "..###..",
          "..###..",
          "..###.."],
    "⬇": ["..###..",
          "..###..",
          "..###..",
          "#######",
          ".#####.",
          "..###..",
          "...#..."],
    # ---- admin hubs
    "🧩": ["..##...",
           "..##...",
           "######.",
           "######.",
           "#######",
           "#######",
           "##..##."],
    "🎨": [".......",
           ".#####.",
           "#=#=###",
           "#######",
           "#=###.#",
           "###..##",
           ".#####."],
    "🌍": ["..###..",
           ".#=####",
           "#===###",
           "##=##=#",
           "###==##",
           ".####=.",
           "..###.."],
    "⚡": ["...###.",
           "..###..",
           ".###...",
           ".#####.",
           "...##..",
           "..##...",
           ".#....."],
    "🖥": ["#######",
           "#.....#",
           "#.....#",
           "#.....#",
           "#######",
           "...#...",
           ".#####."],
    "☠": [".#####.",
          "#######",
          "#=###=#",
          "#######",
          ".#####.",
          "..#.#..",
          "..###.."],
    "👁": [".......",
           "..###..",
           ".#+++#.",
           "##+=+##",
           ".#+++#.",
           "..###..",
           "......."],
    "🎒": ["..###..",
           ".#...#.",
           "#######",
           "#.....#",
           "#.###.#",
           "#.....#",
           ".#####."],
    "📦": ["#######",
          "#--=--#",
          "#######",
          "#-=+=-#",
          "#--+--#",
          "#-=+=-#",
          "#######"],
    "🧰": ["..###..",
           "..#.#..",
           "#######",
           "#.....#",
           "#######",
           "#.....#",
           "#######"],
    # ---- actions and settings
    "☀": ["#..#..#",
          ".#####.",
          ".#####.",
          "#######",
          ".#####.",
          ".#####.",
          "#..#..#"],
    "🌙": ["...###.",
           "..##...",
           ".##....",
           ".##....",
           ".##....",
           "..##...",
           "...###."],
    "🌤": ["#.#.#..",
           ".###...",
           "#####..",
           ".###.##",
           "#.#####",
           "..#####",
           "...###."],
    "🌧": ["..###..",
           ".######",
           "#######",
           ".#####.",
           ".#.#.#.",
           "#.#.#..",
           ".#.#.#."],
    "⛈": ["..###..",
          ".######",
          "#######",
          ".#####.",
          "...##..",
          "..###..",
          "...##.."],
    "🧪": [".#####.",
           "..#.#..",
           "..#.#..",
           "..#.#..",
           ".#+++#.",
           ".#+++#.",
           "..###.."],
    "💾": ["######.",
           "#.##.##",
           "#.##..#",
           "#.....#",
           "#.###.#",
           "#.###.#",
           "#######"],
    "👥": [".##....",
           ".##.##.",
           "....##.",
           ".###...",
           "####.##",
           "####.##",
           "####.##"],
    "👤": ["..###..",
           "..###..",
           "..###..",
           ".......",
           ".#####.",
           "#######",
           "#######"],
    "📜": [".######",
           "##....#",
           "#.###.#",
           "#.....#",
           "#.###.#",
           "#....##",
           "######."],
    "📖": [".......",
           "###.###",
           "#++#++#",
           "#++#++#",
           "#++#++#",
           "###.###",
           "......."],
    "🌐": ["..###..",
           ".#.#.#.",
           "#######",
           "#.#.#.#",
           "#######",
           ".#.#.#.",
           "..###.."],
    "🎲": [".#####.",
           "#=###=#",
           "#######",
           "###=###",
           "#######",
           "#=###=#",
           ".#####."],
    "🗑": ["..###..",
           "#######",
           ".#####.",
           ".#.#.#.",
           ".#.#.#.",
           ".#.#.#.",
           ".#####."],
    "⚖": ["...#...",
          "#######",
          ".#.#.#.",
          "#..#..#",
          "###.###",
          "...#...",
          "..###.."],
    "◎": ["..###..",
          ".#...#.",
          "#.###.#",
          "#.#.#.#",
          "#.###.#",
          ".#...#.",
          "..###.."],
    "⌖": ["...#...",
          "...#...",
          "..###..",
          "##.#.##",
          "..###..",
          "...#...",
          "...#..."],
    "♪": ["...##..",
          "...#.#.",
          "...#..#",
          "...#...",
          ".###...",
          "#####..",
          ".###..."],
    "⏹": [".......",
          ".#####.",
          ".#####.",
          ".#####.",
          ".#####.",
          ".#####.",
          "......."],
    "📣": [".....#.",
           "...###.",
           ".#####.",
           "######.",
           ".#####.",
           "...###.",
           "..#..#."],
    "🔊": ["...#..#",
           "..##...",
           "####.#.",
           "####..#",
           "####.#.",
           "..##...",
           "...#..#"],
    "❤": [".##.##.",
          "#######",
          "#######",
          "#######",
          ".#####.",
          "..###..",
          "...#..."],
    # ---- creatures (Haunt, MobSeats, Mob Designer)
    "🐴": [".#.....",
           "###....",
           "#####..",
           ".#####.",
           "..###.#",
           "..##...",
           "..##..."],
    "🐕": [".##....",
           ".###...",
           ".####..",
           "..#####",
           "..#####",
           "..#..#.",
           "..#..#."],
    "🐈": ["#...#..",
           "#####..",
           "#=#=#.#",
           "#####.#",
           ".####.#",
           ".######",
           ".#..#.."],
    "🦜": ["..###..",
           ".#=###.",
           "=#####.",
           "..####.",
           "..####.",
           "..###..",
           "..#...."],
    "🐾": [".#.#.#.",
           ".#.#.#.",
           ".......",
           ".#####.",
           "#######",
           "#######",
           ".#####."],
    "🧟": [".#####.",
           ".#=#=#.",
           ".#####.",
           ".##.##.",
           "#######",
           "#..#..#",
           "#..#..#"],
    "👻": ["..###..",
           ".#####.",
           ".#=#=#.",
           ".#####.",
           ".#####.",
           ".#####.",
           ".#.#.#."],
    "🍖": ["..###..",
           ".#####.",
           ".#####.",
           "..###..",
           "...##..",
           "...=#..",
           "....##."],
    # ---- Haunt categories
    "🌫": [".......",
           ".######",
           ".......",
           "######.",
           ".......",
           ".######",
           "......."],
    "🧬": ["######.",
           "#....#.",
           ".#..#..",
           "..##...",
           ".#..#..",
           "#....#.",
           "######."],
    "🫀": [".##.##.",
           "#######",
           "#######",
           "#######",
           ".#####.",
           "..###..",
           "...#..."],
    # ---- the odd Toolbox / shortcut glyphs that reach a menu label
    "🏆": ["#######",
           "#.###.#",
           "#.###.#",
           ".#####.",
           "..###..",
           "...#...",
           ".#####."],
    "🗺": ["#######",
           "#.....#",
           "#.##..#",
           "#...#.#",
           "#..##.#",
           "#.....#",
           "#######"],
    "🎥": [".##.##.",
           ".##.##.",
           "#####.#",
           "######.",
           "#####.#",
           ".#..#..",
           ".#..#.."],
    "📷": ["..##...",
           "#######",
           "#.###.#",
           "#.#=#.#",
           "#.###.#",
           "#######",
           "......."],
    "🔥": ["...#...",
           "..##...",
           "..###..",
           ".####..",
           ".#####.",
           ".#####.",
           "..###.."],
    "💬": [".######",
           "#.....#",
           "#.....#",
           "#.....#",
           ".#####.",
           ".##....",
           ".#....."],
    "💎": [".......",
           ".#####.",
           "#+#+#+#",
           "#######",
           ".#####.",
           "..###..",
           "...#..."],
    "🔔": ["...#...",
           "..###..",
           ".#####.",
           ".#####.",
           ".#####.",
           "#######",
           "...#..."],
    "🔮": ["..###..",
           ".#+###.",
           "#++####",
           "#+#####",
           ".#####.",
           "..###..",
           ".#####."],
    "🧊": [".#####.",
           "#+....#",
           "#+....#",
           "#+....#",
           "#+....#",
           "#++++++",
           ".#####."],
    "🍞": ["..####.",
           ".######",
           "#######",
           "######.",
           "#####..",
           "#####..",
           "......."],
    # 1.10.0: the six labels that still fell back to Unifont
    "📡": ["#....#.",      # a dish, its stand, and a wave going out to the right
           "##..#..",
           "###.#..",
           ".###...",
           "..#..#.",
           "..#.#..",
           ".###..."],
    "🎭": [".#####.",      # a theatre mask
           "#######",
           "#.###.#",
           "#######",
           "##.#.##",
           ".##.##.",
           "..###.."],
    "🥚": ["..###..",      # an egg with a speckle
           ".#####.",
           "##+####",
           "##+####",
           "#######",
           ".#####.",
           "..###.."],
    "📊": ["...#...",      # a bar chart on its baseline
           "...#...",
           "...#...",
           "...#.#.",
           ".#.#.#.",
           ".#.#.#.",
           "#######"],
    "🎮": [".......",      # a gamepad: two grips, a pad left, buttons right
           ".##.##.",
           "#######",
           "#.#####",
           "###.#.#",
           "#######",
           ".##.##."],
    "🎞": ["#######",      # a strip of film
           "#.#.#.#",
           "#######",
           "#.....#",
           "#######",
           "#.#.#.#",
           "#######"],
    "🔧": [".##.##.",          # a wrench: the plugins written here
          ".#####.",
          "..###..",
          "...##..",
          "..##...",
          ".##....",
          "##....."],
    "🖼": ["#######",          # a framed picture: the pattern gallery
          "#.....#",
          "#.+...#",
          "#.....#",
          "#..#..#",
          "#.###.#",
          "#######"],
    "▣": ["#######",      # a framed square: GlassRim's outlines
          "#.....#",
          "#.###.#",
          "#.###.#",
          "#.###.#",
          "#.....#",
          "#######"],
    "🔍": [".####..",      # a magnifying glass
           "#....#.",
           "#....#.",
           "#....#.",
           ".####..",
           "....##.",
           ".....##"],
}
# glyphs that share a drawing
ALIASES = {"↻": "⟳", "❔": "❓", "✅": "✔", "🎵": "♪"}


def _png_encode(w, h, rows):
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", binascii.crc32(tag + body) & 0xffffffff))
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def glyphs():
    """The full table, aliases resolved and every drawing checked and left-aligned."""
    table = dict(ART)
    for alias, target in ALIASES.items():
        table[alias] = ART[target]
    out = {}
    for ch, rows in table.items():
        if len(ch) != 1:
            raise ValueError(f"{ch!r} is not a single code point")
        if len(rows) > CELL:
            raise ValueError(f"{ch}: {len(rows)} rows, cell is {CELL}")
        for r in rows:
            if len(r) > CELL or set(r) - set(SHADES) - {"."}:
                raise ValueError(f"{ch}: bad row {r!r}")
        # left-align: leading empty columns would become padding the client keeps
        lead = min((len(r) - len(r.lstrip(".")) for r in rows if r.strip(".")), default=0)
        rows = [r[lead:] for r in rows]
        if not any(r.strip(".") for r in rows):
            raise ValueError(f"{ch}: empty drawing")
        out[ch] = rows
    return out


def sheet(table):
    """One RGBA texture, PER_ROW cells per line; returns (png bytes, chars rows)."""
    chars = list(table)
    lines = (len(chars) + PER_ROW - 1) // PER_ROW
    w, h = PER_ROW * CELL, lines * CELL
    rows = [bytearray(w * 4) for _ in range(h)]
    char_rows = []
    for line in range(lines):
        slice_ = chars[line * PER_ROW:(line + 1) * PER_ROW]
        for col, ch in enumerate(slice_):
            for y, art in enumerate(table[ch]):
                for x, px in enumerate(art):
                    if px == ".":
                        continue
                    v = SHADES[px]
                    i = ((col * CELL) + x) * 4
                    rows[line * CELL + y][i:i + 4] = bytes((v, v, v, 255))
        # code point 0 pads the line: the client skips it
        char_rows.append("".join(slice_) + chr(0) * (PER_ROW - len(slice_)))
    return _png_encode(w, h, rows), char_rows


def bar_drawing(k):
    """One bar with k of BAR_STATES interior columns filled: frame in mid grey, fill white, rest dim."""
    frame = "-" * BAR_W
    inner = "-" + "#" * k + "=" * (BAR_STATES - k) + "-"
    return [frame] + [inner] * 6 + [frame]


def bars():
    """The bar sheet: one glyph per line so every cell is BAR_W wide; returns (png bytes, chars rows)."""
    drawings = [bar_drawing(k) for k in range(BAR_STATES + 1)]
    h = len(drawings) * CELL
    rows = [bytearray(BAR_W * 4) for _ in range(h)]
    for n, art in enumerate(drawings):
        for y, line in enumerate(art):
            for x, px in enumerate(line):
                if px == ".":
                    continue
                v = SHADES[px]
                rows[n * CELL + y][x * 4:x * 4 + 4] = bytes((v, v, v, 255))
    chars = [chr(BAR_BASE + k) for k in range(BAR_STATES + 1)]
    return _png_encode(BAR_W, h, rows), chars


def preview_bars(scale=6):
    """Every bar state at `scale` on dark, one under the other."""
    drawings = [bar_drawing(k) for k in range(BAR_STATES + 1)]
    pad = 2
    w = (BAR_W + 2 * pad) * scale
    h = len(drawings) * (CELL + pad) * scale + pad * scale
    bg = bytes((32, 34, 40, 255))
    rows = [bytearray(bg * w) for _ in range(h)]
    for n, art in enumerate(drawings):
        cy = (n * (CELL + pad) + pad) * scale
        for y, line in enumerate(art):
            for x, px in enumerate(line):
                if px == ".":
                    continue
                v = SHADES[px]
                for dy in range(scale):
                    row = rows[cy + y * scale + dy]
                    for dx in range(scale):
                        i = ((x + pad) * scale + dx) * 4
                        row[i:i + 4] = bytes((v, v, v, 255))
    return _png_encode(w, h, rows)


def preview(table, scale=6):
    """The sheet at `scale` on dark, one cell of padding, for looking at the art."""
    chars = list(table)
    lines = (len(chars) + PER_ROW - 1) // PER_ROW
    pad = 2
    cw = (CELL + pad) * scale
    w, h = PER_ROW * cw, lines * cw
    bg = bytes((32, 34, 40, 255))
    rows = [bytearray(bg * w) for _ in range(h)]
    for n, ch in enumerate(chars):
        cx, cy = (n % PER_ROW) * cw, (n // PER_ROW) * cw
        for y, art in enumerate(table[ch]):
            for x, px in enumerate(art):
                if px == ".":
                    continue
                v = SHADES[px]
                for dy in range(scale):
                    row = rows[cy + (y + 1) * scale + dy]
                    for dx in range(scale):
                        i = (cx + (x + 1) * scale + dx) * 4
                        row[i:i + 4] = bytes((v, v, v, 255))
    return _png_encode(w, h, rows)


def pack_icon(table):
    """pack.png, 64x64: one menu button as the client draws it - grey face, light top edge,
    dark bottom edge - carrying a yellow ⚡ at 3x and two white bars where the label goes.
    A picture of exactly what the pack changes."""
    size = 64
    rows = [bytearray(bytes((30, 32, 40, 255)) * size) for _ in range(size)]

    def fill(x0, y0, x1, y1, colour):
        for y in range(y0, y1):
            for x in range(x0, x1):
                rows[y][x * 4:x * 4 + 4] = bytes((*colour, 255))

    bx0, by0, bx1, by1 = 4, 17, 60, 47          # the button: 56 x 30
    fill(bx0, by0, bx1, by1, (108, 108, 108))    # face
    fill(bx0, by0, bx1, by0 + 2, (160, 160, 160))  # light top edge
    fill(bx0, by0, bx0 + 2, by1, (160, 160, 160))  # light left edge
    fill(bx0, by1 - 3, bx1, by1, (46, 46, 46))     # dark bottom edge
    fill(bx1 - 3, by0, bx1, by1, (46, 46, 46))     # dark right edge
    fill(0, by1, size, by1 + 2, (0, 0, 0))         # drop shadow under the button

    scale = 3
    gx, gy = bx0 + 6, by0 + 5
    for y, art in enumerate(table["⚡"]):
        for x, px in enumerate(art):
            if px == ".":
                continue
            v = SHADES[px] / 255
            colour = (int(255 * v), int(255 * v), int(85 * v))
            fill(gx + x * scale, gy + y * scale, gx + (x + 1) * scale, gy + (y + 1) * scale, colour)
    fill(gx + 27, by0 + 8, bx1 - 7, by0 + 13, (240, 240, 240))  # label bars
    fill(gx + 27, by0 + 17, bx1 - 14, by0 + 22, (240, 240, 240))
    return _png_encode(size, size, rows)


# ---------------------------------------------------------------- chest grid frames (font serverui:gui)
#
# A container title is a Component, and in 26.2 the client draws the labels BEFORE the slots
# (AbstractContainerScreen.extractRenderState: extractLabels, then extractSlots), so a glyph in the
# title is a full background the items sit on. The generic container is 176 x (114 + 18 rows) GUI
# px, the title starts at (8, 6), a bitmap glyph's top sits at y + 7 - ascent, so ascent 13 puts it
# on the container's top edge and a negative space of 8 puts it on the left edge; a glyph advances
# by its width + 1, so 177 back returns the cursor and 169 back lands the title text at x = 8 again.
# Two pictures per row count: the neutral panel (sent WHITE) and the accent (sent in the screen's
# colour - a font glyph is tinted by its text colour, so one drawing serves every domain).
# The space provider carries negative advances -1, -2, -4 ... -128 at U+F801..F808 to compose any
# step. All of it lives in its own font serverui:gui, never in default.json.
GUI_W = 176
GUI_BASE, GUI_ACCENT, GUI_SPACE = 0xE200, 0xE210, 0xF800
GUI_ASCENT = 13
# The hub header banner (1.9.0): two wings that fade outward from the middle, U+E220 (left) and
# U+E221 (right), and the icon sheet once more at 3x under the SAME characters - so the server
# writes the hub's own icon between the wings with no code-point table to keep in step
# ("🧩" in font serverui:gui is the big icon). Sent in the hub's colour; a body row 300 wide.
BANNER_W, BANNER_H = 132, 24
BANNER_LEFT, BANNER_RIGHT = 0xE220, 0xE221
BANNER_ASCENT = 10           # the glyph is 24 px in a 9 px line: 3 px above the line top (inside the text
                             # widget's 4 px padding), 11 px below its 17 px element (into the 10 px layout
                             # spacing + the next element's padding) - no blank lines needed, DialogScreen 26.2
BIG_SCALE = 3
BIG_ASCENT = 9                # the 3x art (rows 0-20 of 24) centred on the wings' rule: one px lower than the wings' top


def gui_height(rows):
    return 114 + 18 * rows


def gui_slots(rows):
    """Every slot square (x, y) of a generic container with that many rows: the grid, then the
    player's inventory and hotbar below - the client draws its items over our picture."""
    out = [(7 + 18 * c, 17 + 18 * r) for r in range(rows) for c in range(9)]
    out += [(7 + 18 * c, 30 + 18 * rows + 18 * r) for r in range(3) for c in range(9)]
    out += [(7 + 18 * c, 88 + 18 * rows) for c in range(9)]
    return out


def _fill(rows_, x0, y0, w, h, rgba):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            rows_[y][x * 4:x * 4 + 4] = bytes(rgba)


def gui_pictures(rows):
    """(neutral, accent) RGBA images for a grid of `rows` rows, each (w, h, rows)."""
    w, h = GUI_W, gui_height(rows)
    neutral = [bytearray(w * 4) for _ in range(h)]
    accent = [bytearray(w * 4) for _ in range(h)]
    # the panel: a dark plate with a one-pixel rim, rounded corners left clear like vanilla's
    _fill(neutral, 0, 0, w, h, (44, 46, 52, 255))
    _fill(neutral, 0, 0, w, 1, (18, 18, 22, 255)); _fill(neutral, 0, h - 1, w, 1, (18, 18, 22, 255))
    _fill(neutral, 0, 0, 1, h, (18, 18, 22, 255)); _fill(neutral, w - 1, 0, 1, h, (18, 18, 22, 255))
    _fill(neutral, 1, 1, w - 2, 1, (70, 72, 80, 255)); _fill(neutral, 1, 1, 1, h - 2, (70, 72, 80, 255))
    for (cx, cy) in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        neutral[cy][cx * 4:cx * 4 + 4] = bytes(4)
    # the title band
    _fill(neutral, 2, 2, w - 4, 15, (56, 58, 66, 255))
    # slots: an inset square, dark with the lit edge at the bottom right like vanilla's
    for (sx, sy) in gui_slots(rows):
        _fill(neutral, sx, sy, 18, 18, (28, 29, 34, 255))
        _fill(neutral, sx, sy, 18, 1, (16, 16, 20, 255)); _fill(neutral, sx, sy, 1, 18, (16, 16, 20, 255))
        _fill(neutral, sx + 1, sy + 17, 17, 1, (74, 76, 86, 255)); _fill(neutral, sx + 17, sy + 1, 1, 17, (74, 76, 86, 255))
        _fill(neutral, sx + 1, sy + 1, 16, 16, (34, 35, 41, 255))
    # the accent, tinted by the screen's colour: a wash over the title band that fades to the right,
    # a line under it, a frame round the grid rows (not the player's own inventory)
    for x in range(2, w - 2):
        a = int(150 * (1 - (x - 2) / (w - 4)) ** 1.4) + 20
        for y in range(2, 17):
            accent[y][x * 4:x * 4 + 4] = bytes((255, 255, 255, a))
    _fill(accent, 2, 16, w - 4, 1, (255, 255, 255, 230))
    gy0, gy1 = 17, 17 + 18 * rows
    _fill(accent, 6, gy0 - 1, w - 12, 1, (255, 255, 255, 120)); _fill(accent, 6, gy1, w - 12, 1, (255, 255, 255, 120))
    _fill(accent, 6, gy0 - 1, 1, gy1 - gy0 + 2, (255, 255, 255, 120)); _fill(accent, w - 7, gy0 - 1, 1, gy1 - gy0 + 2, (255, 255, 255, 120))
    return (w, h, neutral), (w, h, accent)


def banner_wings():
    """(left, right) RGBA wings, each (w, h, rows): a double rule that is bright at the icon and fades
    outward, white so the hub colour tints it. The bright end is the inner one, so the fade never
    reaches a glyph's edge on the side the client measures the advance from (a trailing transparent
    column would shorten the left wing)."""
    w, h = BANNER_W, BANNER_H
    left = [bytearray(w * 4) for _ in range(h)]
    mid = h // 2
    for x in range(w):
        t = x / (w - 1)                       # 0 at the outer end, 1 at the icon
        a = int(255 * t ** 1.6)
        if a == 0:
            continue
        left[mid - 1][x * 4:x * 4 + 4] = bytes((255, 255, 255, a))
        left[mid][x * 4:x * 4 + 4] = bytes((255, 255, 255, a))
        soft = int(a * 0.45)
        if soft:
            left[mid + 2][x * 4:x * 4 + 4] = bytes((255, 255, 255, soft))
    # a small diamond where the rule meets the icon
    for dy, span in ((-3, 1), (-2, 2), (-1, 3), (0, 3), (1, 3), (2, 2), (3, 1)):
        for dx in range(-span + 1, span):
            x = w - 4 + dx
            if 0 <= x < w:
                left[mid + dy][x * 4:x * 4 + 4] = bytes((255, 255, 255, 255))
    right = [bytearray(b"".join(bytes(r[i * 4:i * 4 + 4]) for i in reversed(range(w)))) for r in left]
    return (w, h, left), (w, h, right)


def banner_composite(icon_rows, tint):
    """The banner as the client shows it, for the preview: left wing, the icon at 3x, right wing,
    everything tinted (r, g, b) - 300 px wide like the body row it sits in."""
    (w, h, left), (_, _, right) = banner_wings()
    icon_w = max(len(r) for r in icon_rows) * BIG_SCALE
    gap = 3
    total = w + gap + icon_w + gap + w
    out = [bytearray(total * 4) for _ in range(h)]
    def put(img_rows, ox):
        for y in range(h):
            for x in range(len(img_rows[y]) // 4):
                a = img_rows[y][x * 4 + 3]
                if a:
                    out[y][(ox + x) * 4:(ox + x) * 4 + 4] = bytes((*tint, a))
    put(left, 0)
    put(right, w + gap + icon_w + gap)
    oy = (h - CELL * BIG_SCALE) // 2 + 1
    for y, art in enumerate(icon_rows):
        for x, px in enumerate(art):
            if px == ".":
                continue
            v = SHADES[px] / 255
            for dy in range(BIG_SCALE):
                for dx in range(BIG_SCALE):
                    X = w + gap + x * BIG_SCALE + dx
                    out[oy + y * BIG_SCALE + dy][X * 4:X * 4 + 4] = bytes((int(tint[0] * v), int(tint[1] * v), int(tint[2] * v), 255))
    return total, h, out


def gui_font(tex_dir, font_dir=None, icon_chars=None):
    """Write the frames, the banner wings and serverui:gui; returns the provider list (for the record).
    `icon_chars` = the icon sheet's char rows: the same sheet joins this font at 3x for the banners."""
    # negative advances -1, -2, -4 … -128 at U+F801..F808 and positive +1 … +128 at U+F809..F810
    spaces = {chr(GUI_SPACE + k): -(1 << (k - 1)) for k in range(1, 9)}
    spaces.update({chr(GUI_SPACE + 8 + k): (1 << (k - 1)) for k in range(1, 9)})
    providers = [{"type": "space", "advances": spaces}]
    for rows in range(1, 7):
        neutral, accent = gui_pictures(rows)
        for kind, img, cp in (("", neutral, GUI_BASE + rows), ("_accent", accent, GUI_ACCENT + rows)):
            file = f"grid_{rows}{kind}.png"
            (tex_dir / file).write_bytes(_png_encode(*img))
            providers.append({"type": "bitmap", "file": f"serverui:font/{file}", "height": img[1], "ascent": GUI_ASCENT, "chars": [chr(cp)]})
    left, right = banner_wings()
    for file, img, cp in (("banner_left.png", left, BANNER_LEFT), ("banner_right.png", right, BANNER_RIGHT)):
        (tex_dir / file).write_bytes(_png_encode(*img))
        providers.append({"type": "bitmap", "file": f"serverui:font/{file}", "height": img[1], "ascent": BANNER_ASCENT, "chars": [chr(cp)]})
    if icon_chars:
        # the icons at 3x: same picture file, same characters, height 24 - the client scales the cells
        providers.append({"type": "bitmap", "file": "serverui:font/icons.png",
                          "height": CELL * BIG_SCALE, "ascent": BIG_ASCENT, "chars": icon_chars})
    # the font is serverui:gui -> assets/serverui/font/gui.json, beside the textures, not under minecraft/
    own_font_dir = tex_dir.parent.parent / "font"
    own_font_dir.mkdir(parents=True, exist_ok=True)
    (own_font_dir / "gui.json").write_text(json.dumps({"providers": providers}, ensure_ascii=True) + "\n", encoding="utf-8")
    return providers


def gui_composite(rows, tint):
    """Neutral under accent tinted (r, g, b) - what the client shows, for the preview."""
    (w, h, neutral), (_, _, accent) = gui_pictures(rows)
    out = [bytearray(r) for r in neutral]
    for y in range(h):
        for x in range(w):
            a = accent[y][x * 4 + 3]
            if a == 0:
                continue
            f = a / 255
            for c in range(3):
                out[y][x * 4 + c] = int(out[y][x * 4 + c] * (1 - f) + tint[c] * f)
    return w, h, out


def vanilla_item_model(item):
    """The client's own definition of an item, as the fallback - so a real arrow is untouched."""
    if CLIENT_JAR.exists():
        with zipfile.ZipFile(CLIENT_JAR) as jar:
            return json.loads(jar.read(f"assets/minecraft/items/{item}.json"))["model"]
    return {"type": "minecraft:model", "model": f"minecraft:item/{item}"}


def vanilla_default_font():
    """The client's own font/default.json providers, so ours go in front of exactly
    what the running version ships. Falls back to the 26.x shape when the jar is
    not installed."""
    if CLIENT_JAR.exists():
        with zipfile.ZipFile(CLIENT_JAR) as jar:
            data = json.loads(jar.read("assets/minecraft/font/default.json"))
            fmt = json.loads(jar.read("version.json"))["pack_version"]["resource_major"]
        return data["providers"], fmt, True
    return [
        {"type": "reference", "id": "minecraft:include/space"},
        {"type": "reference", "id": "minecraft:include/default", "filter": {"uniform": False}},
        {"type": "reference", "id": "minecraft:include/unifont"},
    ], PACK_FORMAT_FALLBACK, False


# ---------------------------------------------------------------- chest-window control icons
#
# A chest window has no buttons, so every control in one is an item, and every control was an
# ARROW: back a page, forward a page, Done, search, pin. Five different things wearing the same
# picture, which you can only tell apart by reading the name. These are real pictures instead,
# put on the arrow through `custom_model_data` strings[0] and selected by
# `assets/minecraft/items/arrow.json` with the client's own arrow as the fallback - so a real
# arrow is untouched and anyone without the pack sees exactly what they see today.
#
# 16x16, drawn like the ART table: '#' the body, '+' the highlight, '-' the shade, '.' clear.
UI_ICONS = {
    "prev": ("""
................
................
.......##.......
......###.......
.....####.......
....#####+++++..
...######+++++..
..#######+++++..
..#######+++++..
...######+++++..
....#####+++++..
.....####.......
......###.......
.......##.......
................
................""", (236, 236, 242), (150, 150, 158)),
    "next": ("""
................
................
.......##.......
.......###......
.......####.....
..+++++#####....
..+++++######...
..+++++#######..
..+++++#######..
..+++++######...
..+++++#####....
.......####.....
.......###......
.......##.......
................
................""", (236, 236, 242), (150, 150, 158)),
    "done": ("""
................
................
.............##.
............##..
...........##...
..##......##....
..###....##.....
...###..##......
....######......
.....####.......
......##........
................
................
................
................
................""", (120, 230, 120), (60, 150, 60)),
    "pin": (None, (210, 210, 218), (150, 150, 158)),
    "pinned": (None, (255, 206, 60), (170, 120, 20)),
    "search": ("""
................
....######......
...##----##.....
..##------##....
..#--++++--#....
..#--++++--#....
..#--++++--#....
..##------##....
...##----##.....
....######-#....
.........-##....
..........-##...
...........-##..
............-##.
.............-#.
................""", (220, 226, 236), (110, 116, 130)),
    "pin": ("""
................
.......##.......
.......##.......
......#--#......
.....##--##.....
..####----####..
..#----------#..
...##------##...
....#------#....
....##----##....
...##--##--##...
..##--#..#--##..
..##-#....#-##..
...#.......#....
................
................""", (200, 200, 208), (120, 120, 128)),
    "pinned": ("""
................
.......##.......
.......##.......
......####......
.....######.....
..############..
..############..
...##########...
....########....
....########....
...###.##.###...
..###...#..###..
..##.......##...
...#........#...
................
................""", (255, 214, 70), (190, 150, 30)),
}


def star_icon(filled, body, shade):
    """A five-pointed star, rasterised rather than drawn by hand - a star is all diagonals and a
    hand-drawn one at 16 px comes out as a spider. `filled` is the pinned state (solid gold), the
    other is the outline (pin it)."""
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 7.4 if i % 2 == 0 else 3.1
        pts.append((8 + r * math.cos(a), 8 + r * math.sin(a)))

    def inside(px, py):
        hit = False
        j = len(pts) - 1
        for i, (xi, yi) in enumerate(pts):
            xj, yj = pts[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                hit = not hit
            j = i
        return hit

    img = (16, 16, [bytearray(16 * 4) for _ in range(16)])
    solid = [[inside(x + 0.5, y + 0.5) for x in range(16)] for y in range(16)]
    for y in range(16):
        for x in range(16):
            if not solid[y][x]:
                continue
            edge = any(not (0 <= x + dx < 16 and 0 <= y + dy < 16 and solid[y + dy][x + dx])
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            c = shade if edge else body
            if not filled and not edge:
                continue
            img[2][y][x * 4:x * 4 + 4] = bytes((c[0], c[1], c[2], 255))
    return img


def ui_icon(rows, body, shade):
    img = (16, 16, [bytearray(16 * 4) for _ in range(16)])
    light = tuple(min(255, c + 30) for c in body)
    for y, row in enumerate(rows.strip("\n").split("\n")):
        for x, ch in enumerate(row):
            c = body if ch == "#" else light if ch == "+" else shade if ch == "-" else None
            if c is not None:
                img[2][y][x * 4:x * 4 + 4] = bytes((c[0], c[1], c[2], 255))
    return img


def build(version=None):
    version = version or VERSION
    table = glyphs()
    if SRC.exists():
        shutil.rmtree(SRC)
    font_dir = SRC / "assets" / "minecraft" / "font"
    tex_dir = SRC / "assets" / "serverui" / "textures" / "font"
    font_dir.mkdir(parents=True)
    tex_dir.mkdir(parents=True)

    png, char_rows = sheet(table)
    (tex_dir / "icons.png").write_bytes(png)
    bars_png, bar_chars = bars()
    (tex_dir / "bars.png").write_bytes(bars_png)
    gui_font(tex_dir, font_dir, char_rows)   # serverui:gui - chest-grid frames, hub banners, its own font file
    import previews as pv
    pictures = pv.previews(png)
    preview_providers = []
    for name, key, cp in pv.panels():
        if (name, key) not in pictures:
            continue
        file = f"preview_{name.lower()}_{key}.png"
        (tex_dir / file).write_bytes(_png_encode(*pictures[(name, key)]))
        preview_providers.append({"type": "bitmap", "file": f"serverui:font/{file}",
                                  "height": pv.H, "ascent": pv.ASCENT, "chars": [chr(cp)]})

    # the chest-window controls, as real pictures on an arrow
    ui_tex = SRC / "assets" / "serverui" / "textures" / "item" / "ui"
    ui_mod = SRC / "assets" / "serverui" / "models" / "item" / "ui"
    ui_tex.mkdir(parents=True)
    ui_mod.mkdir(parents=True)
    for name, (rows, body, shade) in UI_ICONS.items():
        art = star_icon(name == "pinned", body, shade) if name in ("pin", "pinned") \
            else ui_icon(rows, body, shade)
        (ui_tex / f"{name}.png").write_bytes(_png_encode(*art))
        (ui_mod / f"{name}.json").write_text(json.dumps(
            {"parent": "minecraft:item/generated", "textures": {"layer0": f"serverui:item/ui/{name}"}},
            indent=2) + "\n", encoding="utf-8")
    items_dir = SRC / "assets" / "minecraft" / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    (items_dir / "arrow.json").write_text(json.dumps({"model": {
        "type": "minecraft:select",
        "property": "minecraft:custom_model_data", "index": 0,
        "cases": [{"when": f"ui/{name}",
                   "model": {"type": "minecraft:model", "model": f"serverui:item/ui/{name}"}}
                  for name in UI_ICONS],
        "fallback": vanilla_item_model("arrow"),
    }}, indent=2) + "\n", encoding="utf-8")

    providers, fmt, from_jar = vanilla_default_font()
    ours = [
        {"type": "bitmap", "file": "serverui:font/icons.png",
         "height": CELL, "ascent": 7, "chars": char_rows},
        {"type": "bitmap", "file": "serverui:font/bars.png",
         "height": CELL, "ascent": 7, "chars": bar_chars},
    ] + preview_providers
    (font_dir / "default.json").write_text(
        json.dumps({"providers": ours + providers}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    # 26.x reads min_format/max_format; a pack with only pack_format plus the
    # older supported_formats array shows as "incompatible or broken"
    (SRC / "pack.mcmeta").write_text(json.dumps({
        "pack": {
            "description": f"ServerUI {version}§7 - menu icons",
            "pack_format": fmt,
            "min_format": fmt,
            "max_format": 2147483647,
        }
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (SRC / "pack.png").write_bytes(pack_icon(table))

    (HERE / "preview.png").write_bytes(preview(table))
    (HERE / "preview-bars.png").write_bytes(preview_bars())
    (HERE / "preview-packs.png").write_bytes(pv.contact_sheet(pictures))
    # the shipped zip lands next to this script (that is the URL the server hands out),
    # older versions go
    for old in HERE.glob(f"{NAME}-*.zip"):
        old.unlink()
    out = HERE / f"{NAME}-{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SRC.rglob("*")):
            if path.is_file():
                # fixed timestamps: the same art always gives the same sha1
                info = zipfile.ZipInfo(path.relative_to(SRC).as_posix(), (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
    return out, len(table), from_jar and len(pictures) == len(pv.panels())


def main():
    """Build and return the shipped zip - the contract ../build.py drives."""
    import hashlib
    out, count, from_jar = build()
    print(f"  {out.name}: {count} glyphs + {BAR_STATES + 1} bars, {out.stat().st_size} bytes, "
          f"sha1 {hashlib.sha1(out.read_bytes()).hexdigest()}"
          + ("" if from_jar else "  (client jar not found - vanilla providers assumed)"))
    return out


if __name__ == "__main__":
    main()
