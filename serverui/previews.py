"""
Pack previews as font glyphs: one picture per look pack, drawn into the default font at
a private-use code point, so the Look Packs screen can show "without | with" in a dialog
body - the only way a dialog gets a picture. Each preview is a W x H image; the glyph has
`ascent` 7 so it hangs down from its own line, and the menu follows it with enough blank
lines for the layout to reserve the height (a dialog sizes a body by its line count).

Left panel: the vanilla look. Right panel: the same thing with the pack. Textures come
from the installed client jar and from the packs' own build code (each theme's derive(),
GlassFrame's speck fading), never from vendored files. Code points are the PREVIEWS table
below - ServerMenus' LookPacksMenu carries the same table; change both together.
"""

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import themelib as T  # noqa: E402

W, H = 256, 72                 # the picture; a dialog body is 300 wide
ASCENT = 7                     # hangs down from the first line: the menu pads 8 blank lines under it
PREVIEWS = [("GlassFrame", 0xE100), ("ServerUI", 0xE101), ("ThemeCalm", 0xE102),
            ("ThemeLab", 0xE103), ("ThemeHorror", 0xE104)]

HUD_BACK = (36, 40, 50, 255)
SKY_BACK = (118, 168, 226, 255)
DIVIDER = (90, 96, 110, 255)


def _load(pack):
    spec = importlib.util.spec_from_file_location(f"pv_{pack}", HERE.parent / pack / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canvas(back):
    return [bytearray(bytes(back) * W) for _ in range(H)]


def blit(rows, img, ox, oy, scale=1):
    w, h, src = img
    for y in range(h):
        for x in range(w):
            px = src[y][x * 4:x * 4 + 4]
            if px[3] == 0:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    X, Y = ox + x * scale + dx, oy + y * scale + dy
                    if 0 <= X < W and 0 <= Y < H:
                        if px[3] == 255:
                            rows[Y][X * 4:X * 4 + 4] = px
                        else:  # blend onto what is there
                            a = px[3] / 255
                            for c in range(3):
                                rows[Y][X * 4 + c] = int(px[c] * a + rows[Y][X * 4 + c] * (1 - a))


def divider(rows):
    for y in range(H):
        rows[y][(W // 2) * 4:(W // 2) * 4 + 4] = bytes(DIVIDER)


def panel(rows, side, back):
    x0 = 0 if side == 0 else W // 2 + 1
    x1 = W // 2 if side == 0 else W
    for y in range(H):
        for x in range(x0, x1):
            rows[y][x * 4:x * 4 + 4] = bytes(back)


def crop(img, x0, y0, w, h):
    sw, sh, rows = img
    return w, h, [bytearray(rows[y0 + y][x0 * 4:(x0 + w) * 4]) for y in range(h)]


def decoded(files, path):
    data = files.get(path)
    return T.png_decode(data) if data else None


def hearts_row(z, files, count=3, kind="full"):
    """count hearts on their containers, from vanilla or from a layer's files; kind picks the state sprite."""
    container = decoded(files, "assets/minecraft/textures/gui/sprites/hud/heart/container.png") or T.texture(z, "gui/sprites/hud/heart/container.png")
    full = decoded(files, f"assets/minecraft/textures/gui/sprites/hud/heart/{kind}.png") or T.texture(z, f"gui/sprites/hud/heart/{kind}.png")
    return container, full, count


def draw_hearts(rows, z, files, x, y, scale=2, kind="full"):
    container, full, count = hearts_row(z, files, kind=kind)
    for i in range(count):
        blit(rows, container, x + i * 8 * scale, y, scale)
        blit(rows, full, x + i * 8 * scale, y, scale)


def draw_hud(rows, z, files, side, heart="full"):
    """Three hearts, a slice of the experience bar and the hotbar frame - the HUD a layer retints."""
    x0 = (0 if side == 0 else W // 2 + 1) + 6
    draw_hearts(rows, z, files, x0, 6, kind=heart)
    bar_bg = T.texture(z, "gui/sprites/hud/experience_bar_background.png")
    bar = decoded(files, "assets/minecraft/textures/gui/sprites/hud/experience_bar_progress.png") or T.texture(z, "gui/sprites/hud/experience_bar_progress.png")
    if bar_bg and bar:
        blit(rows, crop(bar_bg, 0, 0, 26, 5), x0, 28, 2)
        blit(rows, crop(bar, 0, 0, 18, 5), x0, 28, 2)
    frame = decoded(files, "assets/minecraft/textures/gui/sprites/hud/hotbar_selection.png") or T.texture(z, "gui/sprites/hud/hotbar_selection.png")
    if frame:
        slot = T.texture(z, "gui/sprites/hud/hotbar.png")
        if slot:
            blit(rows, crop(slot, 0, 0, 22, 22), x0 + 66, 12, 2)
        blit(rows, frame, x0 + 65, 11, 2)


def preview_theme(z, pack, draw_extra=None, heart="full"):
    """heart: which heart sprite the 'with' panel shows - a layer that paints the state sprites
    (ThemeHorror, absorbing hearts during a cue) previews that state."""
    module = _load(pack)
    files = module.derive(z)
    rows = canvas(HUD_BACK)
    draw_hud(rows, z, {}, 0)
    draw_hud(rows, z, files, 1, heart=heart)
    if draw_extra:
        draw_extra(rows, z, {}, 0)
        draw_extra(rows, z, files, 1)
    divider(rows)
    return W, H, rows


def sun(rows, z, files, side):
    img = decoded(files, "assets/minecraft/textures/environment/celestial/sun.png") or T.texture(z, "environment/celestial/sun.png")
    if img:
        blit(rows, img, (0 if side == 0 else W // 2 + 1) + 14, 40, 1)  # under the hearts, beside the frame


def moon(rows, z, files, side):
    img = decoded(files, "assets/minecraft/textures/environment/celestial/moon/full_moon.png") or T.texture(z, "environment/celestial/moon/full_moon.png")
    if img:
        blit(rows, img, (0 if side == 0 else W // 2 + 1) + 14, 40, 1)


def preview_glassframe(z):
    """Vanilla glass tiles against sky: a grid of borders on the left, one clear sheet on the right."""
    gf = _load("glassframe")
    rows = canvas(SKY_BACK)
    glass = T.texture(z, "block/glass.png")
    if glass:
        # with the pack: the model samples the 14 texels inside the border and the flecks fade to SPECK_ALPHA
        inner = crop(glass, 1, 1, 14, 14)
        w, h, src = inner
        sheet_rows = []
        for y in range(16):
            sy = min(13, y * 14 // 16)
            row = bytearray()
            for x in range(16):
                sx = min(13, x * 14 // 16)
                px = bytearray(src[sy][sx * 4:sx * 4 + 4])
                if px[3] > gf.SPECK_ALPHA:
                    px[3] = gf.SPECK_ALPHA
                row += px
            sheet_rows.append(row)
        sheet = (16, 16, sheet_rows)
        for side, tex in ((0, glass), (1, sheet)):
            x0 = (0 if side == 0 else W // 2 + 1) + 8
            for ty in range(2):
                for tx in range(3):
                    blit(rows, tex, x0 + tx * 32 + 8, 4 + ty * 32, 2)
    divider(rows)
    return W, H, rows


def preview_serverui(sheet_png):
    """Our own icons: the first three rows of the sheet at 2x, one panel - without the pack there
    is nothing to draw the 'before' with (it would be Unifont, which we do not have)."""
    rows = canvas(HUD_BACK)
    w, h, src = T.png_decode(sheet_png)
    strip = crop((w, h, src), 0, 0, w, min(h, 24))
    blit(rows, strip, (W - w * 2) // 2, (H - min(h, 24) * 2) // 2, 2)
    return W, H, rows


def previews(sheet_png):
    """{name: (w, h, rows)} for every entry in PREVIEWS that can be drawn."""
    z = T.jar()
    out = {}
    if z is not None:
        out["GlassFrame"] = preview_glassframe(z)
        out["ThemeCalm"] = preview_theme(z, "themecalm", sun)
        out["ThemeLab"] = preview_theme(z, "themelab")
        out["ThemeHorror"] = preview_theme(z, "themehorror", moon, heart="absorbing_full")
    out["ServerUI"] = preview_serverui(sheet_png)
    return out


def contact_sheet(images, scale=2):
    """Every preview stacked, for looking at them - written next to build.py as preview-packs.png."""
    names = [n for n, _ in PREVIEWS if n in images]
    pad = 4
    w = (W + 2 * pad) * scale
    h = (len(names) * (H + pad) + pad) * scale
    bg = bytes((20, 20, 24, 255))
    rows = [bytearray(bg * w) for _ in range(h)]
    for n, name in enumerate(names):
        _, _, src = images[name]
        oy = (pad + n * (H + pad)) * scale
        for y in range(H):
            for x in range(W):
                px = src[y][x * 4:x * 4 + 4]
                for dy in range(scale):
                    row = rows[oy + y * scale + dy]
                    for dx in range(scale):
                        i = ((pad + x) * scale + dx) * 4
                        row[i:i + 4] = px
    return T.png_encode(w, h, rows)
