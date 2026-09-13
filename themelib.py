"""
Shared code for the theme layers (themelab/, themecalm/, themehorror/): small packs that
retint a handful of vanilla textures and remap the button click sound, so each server can
wear its own palette with the same plugin code, and Haunt can push the horror layer while
the director is armed and pop it afterwards.

A theme is a *layer*: it ships only the files it changes, everything else stays vanilla,
and several layers stack in one ResourcePackRequest with the other look packs. Every
texture is derived at build time from the installed client jar (nothing of Mojang's is
vendored in this repo), through the same 8-bit PNG decoder GlassFrame uses.

A pack folder's build.py does: NAME, VERSION, and main() -> themelib.ship(...).
"""

import binascii
import json
import pathlib
import shutil
import struct
import zipfile
import zlib

CLIENT_JAR = pathlib.Path.home() / "Library/Application Support/minecraft/versions/26.2/26.2.jar"
PACK_FORMAT_FALLBACK = 88


# ---------------------------------------------------------------- PNG

def png_decode(data):
    """Any 8-bit PNG in, (w, h, RGBA rows) out - true colour, greyscale and palette alike."""
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
            else:
                idx = line[x]
                row[x * 4:x * 4 + 3] = palette[idx * 3:idx * 3 + 3]
                row[x * 4 + 3] = transparency[idx] if transparency and idx < len(transparency) else 255
        rows.append(row)
    return w, h, rows


def png_encode(w, h, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", binascii.crc32(tag + body) & 0xffffffff)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- the client jar

def jar():
    return zipfile.ZipFile(CLIENT_JAR) if CLIENT_JAR.exists() else None


def texture(z, path):
    """Decode assets/minecraft/textures/<path> from the jar, or None without a jar."""
    if z is None:
        return None
    return png_decode(z.read(f"assets/minecraft/textures/{path}"))


def pack_format(z):
    if z is None:
        return PACK_FORMAT_FALLBACK
    try:
        return int(json.loads(z.read("version.json"))["pack_version"]["resource_major"])
    except Exception:
        return PACK_FORMAT_FALLBACK


# ---------------------------------------------------------------- pixel ops
# every op takes (w, h, rows) and returns a new (w, h, rows); rows are RGBA bytearrays

def clamp(v):
    return 0 if v < 0 else 255 if v > 255 else int(v)


def map_pixels(img, fn):
    """fn(r, g, b, a) -> (r, g, b, a) on every pixel."""
    w, h, rows = img
    out = []
    for row in rows:
        new = bytearray(len(row))
        for x in range(w):
            r, g, b, a = row[x * 4:x * 4 + 4]
            new[x * 4:x * 4 + 4] = bytes(clamp(v) for v in fn(r, g, b, a))
        out.append(new)
    return w, h, out


def multiply(img, mr, mg, mb, ma=1.0):
    return map_pixels(img, lambda r, g, b, a: (r * mr, g * mg, b * mb, a * ma))


def recolour(img, cr, cg, cb, keep_dark=True):
    """Repaint by brightness: the brightest channel becomes the intensity, painted in (cr, cg, cb)
    fractions - a red heart turns teal but keeps its shading. Transparent pixels stay clear;
    near-black outline pixels stay black when keep_dark."""
    def fn(r, g, b, a):
        if a == 0:
            return (0, 0, 0, 0)
        i = max(r, g, b)
        if keep_dark and i < 40:
            return (r, g, b, a)
        return (i * cr, i * cg, i * cb, a)
    return map_pixels(img, fn)


def set_pixel(img, x, y, rgba):
    w, h, rows = img
    if 0 <= x < w and 0 <= y < h:
        rows[y][x * 4:x * 4 + 4] = bytes(rgba)
    return img


def pixel(img, x, y):
    w, h, rows = img
    return tuple(rows[y][x * 4:x * 4 + 4])


def solid(w, h, rgba):
    return w, h, [bytearray(bytes(rgba) * w) for _ in range(h)]


def radial(w, h, fn):
    """A w x h image where fn(d) -> rgba for the distance d (0 centre .. 1 corner)."""
    rows = []
    cx, cy = (w - 1) / 2, (h - 1) / 2
    corner = (cx * cx + cy * cy) ** 0.5
    for y in range(h):
        row = bytearray(w * 4)
        for x in range(w):
            d = (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / corner
            row[x * 4:x * 4 + 4] = bytes(clamp(v) for v in fn(d))
        rows.append(row)
    return w, h, rows


# ---------------------------------------------------------------- pack icon

def icon(back, fn):
    """64x64 pack icon: a flat ground colour, then fn(x, y) -> rgba or None drawn over it."""
    w = h = 64
    rows = [bytearray(bytes(back) * w) for _ in range(h)]
    for y in range(h):
        for x in range(w):
            px = fn(x, y)
            if px is not None:
                rows[y][x * 4:x * 4 + 4] = bytes(px)
    # a 2px frame in a lighter shade of the ground, so the icon reads as a tile in the pack list
    frame = bytes(clamp(c * 1.6 + 20) if i < 3 else 255 for i, c in enumerate(back))
    for y in range(h):
        for x in range(w):
            if x < 2 or y < 2 or x >= w - 2 or y >= h - 2:
                rows[y][x * 4:x * 4 + 4] = frame
    return png_encode(w, h, rows)


# ---------------------------------------------------------------- shipping

def sounds(mapping):
    """sounds.json remapping vanilla sound *events* to other vanilla events - no files shipped.
    mapping: {"ui.button.click": ("block.chest.close", volume, pitch)}"""
    out = {}
    for event, (target, volume, pitch) in mapping.items():
        out[event] = {"replace": True, "sounds": [{"name": target, "type": "event", "volume": volume, "pitch": pitch}]}
    return json.dumps(out, indent=2) + "\n"


def ship(here, name, version, description, files, icon_png):
    """Write src/ and <name>-<version>.zip next to build.py (older zips removed), fixed
    timestamps so the same art gives the same sha1. files: {"assets/...": bytes}."""
    src = here / "src"
    if src.exists():
        shutil.rmtree(src)
    z = jar()
    fmt = pack_format(z)
    files = dict(files)
    files["pack.mcmeta"] = (json.dumps({"pack": {
        "description": f"{name} {version}§7 - {description}",
        "pack_format": fmt, "min_format": fmt, "max_format": 2147483647,
    }}, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    files["pack.png"] = icon_png
    for rel, data in files.items():
        path = src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for old in here.glob(f"{name}-*.zip"):
        old.unlink()
    out = here / f"{name}-{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(src).as_posix(), (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, path.read_bytes())
    return out, z is not None
