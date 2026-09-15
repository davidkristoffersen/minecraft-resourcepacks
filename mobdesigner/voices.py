#!/usr/bin/env python3
"""
The Mob Designer's voices - every line of every designed mob, synthesised from nothing.

Why synthesise at all
---------------------
A `sounds.json` event can point at vanilla sound *events* (`type: event`) and nothing is
shipped; that is what this pack did first, and it is exactly as good as it sounds - a zombie
at pitch 0.5 is a zombie at pitch 0.5. A pool also picks ONE entry, so a vanilla-event voice
can never be layered either. The only way a designed mob gets a voice of its own is an audio
file, so this module is a small synthesiser: oscillators, envelopes, biquad filters, a
Schroeder reverb and the usual box of effects, all pure Python (no numpy, no samples, nothing
of Mojang's), and one recipe per design per line - 19 designs x {ambient, hurt, death}.

Mono, and why it matters
------------------------
26.2 hands the decoded buffer's format straight to OpenAL (`OpenAlUtil.audioFormatToOpenAl`,
read from the client jar - no downmix anywhere), and OpenAL does not position a stereo buffer.
A stereo voice therefore plays flat, in the middle of your head, wherever the mob is. So every
file here is **mono**, which needs a real Vorbis encoder: `oggenc` (vorbis-tools) is used when
it is installed, then ffmpeg with libvorbis. Homebrew's plain ffmpeg has neither - its built-in
`vorbis` encoder is experimental AND stereo-only - so it is the last resort and the sound is
then flat. No encoder at all: the pack ships without voices and the plugin plays the mob's own
vanilla sound for everyone, which is the same fallback a player without the pack gets.

Everything is deterministic (a seeded LCG, fixed encoder flags), so the same source gives the
same zip sha1.
"""

import math
import shutil
import struct
import subprocess
import tempfile
import pathlib

RATE = 22050
TAU = math.pi * 2

# vowels as their first three formants (Hz) - a saw through these reads as a voice, and which
# vowel it is doing is most of a creature's character
VOWELS = {
    "a": (730, 1090, 2440),     # father
    "e": (530, 1840, 2480),     # bed
    "i": (270, 2290, 3010),     # see
    "o": (570, 840, 2410),      # law
    "u": (300, 870, 2240),      # boot
    "r": (490, 1350, 1690),     # bird - the growly one
}


# ---------------------------------------------------------------- the box

def n(seconds):
    return max(1, int(RATE * seconds))


def rng(seed):
    """The same pseudo-random stream on every build."""
    state = (seed * 2654435761 + 12345) & 0x7FFFFFFF

    def nxt():
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return state / 0x7FFFFFFF
    return nxt


def const(x):
    return x if callable(x) else (lambda t: x)


def ramp(a, b, curve=1.0):
    """A value gliding a -> b over the signal's own length (t is 0..1 here)."""
    return lambda u: a + (b - a) * (u ** curve)


def wobble(rate, depth, seed=1, smooth=0.02):
    """A slow random wander round 1.0 - vocal jitter, a flickering flame, a failing machine."""
    rnd = rng(seed)
    step = 1.0 / max(1e-6, rate)
    pts = [rnd() * 2 - 1 for _ in range(4096)]

    def fn(t):
        x = t / step
        i = int(x)
        f = x - i
        a = pts[i % 4096]
        b = pts[(i + 1) % 4096]
        return 1.0 + depth * (a + (b - a) * (f * f * (3 - 2 * f)))
    return fn


def osc(seconds, freq, wave="sine", duty=0.5, phase=0.0):
    """One oscillator. `freq` is a number or a function of t in seconds - phase is accumulated,
    so a glide is continuous however hard the frequency moves."""
    count = n(seconds)
    out = [0.0] * count
    step = 1.0 / RATE
    p = phase
    fixed = not callable(freq)
    f = freq if fixed else 0.0
    if wave == "sine":
        shape = lambda x: math.sin(TAU * x)
    elif wave == "saw":
        shape = lambda x: 2.0 * x - 1.0
    elif wave == "square":
        shape = lambda x: 1.0 if x < duty else -1.0
    elif wave == "tri":
        shape = lambda x: 4.0 * abs(x - 0.5) - 1.0
    else:                                     # "pulse" - a glottal spike, the source of a voice
        shape = lambda x: (1.0 - 2.0 * x / duty) if x < duty else -1.0
    for i in range(count):
        if not fixed:
            f = freq(i * step)
        p += f * step
        if p > 1e6:
            p -= 1e6
        out[i] = shape(p % 1.0)
    return out


def noise(seconds, seed=1, colour="white"):
    count = n(seconds)
    rnd = rng(seed)
    out = [rnd() * 2 - 1 for _ in range(count)]
    if colour == "pink":                      # one-pole stack, close enough to -3 dB/octave
        b0 = b1 = b2 = 0.0
        for i, w in enumerate(out):
            b0 = 0.99765 * b0 + w * 0.0990460
            b1 = 0.96300 * b1 + w * 0.2965164
            b2 = 0.57000 * b2 + w * 1.0526913
            out[i] = (b0 + b1 + b2 + w * 0.1848) * 0.2
    return out


def env(sig, points):
    """Multiply by a shape given as [(fraction of length, level), ...]."""
    count = len(sig)
    out = [0.0] * count
    seg = 0
    for i in range(count):
        u = i / max(1, count - 1)
        while seg < len(points) - 2 and u > points[seg + 1][0]:
            seg += 1
        (u0, l0), (u1, l1) = points[seg], points[seg + 1]
        k = 0.0 if u1 <= u0 else min(1.0, max(0.0, (u - u0) / (u1 - u0)))
        out[i] = sig[i] * (l0 + (l1 - l0) * k)
    return out


def perc(sig, attack=0.004, curve=4.0):
    """A struck envelope: up in `attack` seconds, then an exponential fall."""
    count = len(sig)
    rise = max(1, n(attack))
    out = [0.0] * count
    for i in range(count):
        a = i / rise if i < rise else 1.0
        d = math.exp(-curve * (i / count))
        out[i] = sig[i] * a * d
    return out


def biquad(sig, kind, freq, q=1.0, steps=32):
    """RBJ biquad, coefficients recomputed every `steps` samples so a sweeping cutoff costs
    almost nothing. Stable anywhere in the band, unlike the cheap state-variable one."""
    ffn, qfn = const(freq), const(q)
    out = [0.0] * len(sig)
    x1 = x2 = y1 = y2 = 0.0
    b0 = b1 = b2 = a1 = a2 = 0.0
    step = 1.0 / RATE
    for i, x in enumerate(sig):
        if i % steps == 0:
            f = min(RATE * 0.45, max(20.0, ffn(i * step)))
            qq = max(0.3, qfn(i * step))
            w0 = TAU * f / RATE
            c, s = math.cos(w0), math.sin(w0)
            alpha = s / (2.0 * qq)
            a0 = 1.0 + alpha
            if kind == "lp":
                b0, b1, b2 = (1 - c) / 2, 1 - c, (1 - c) / 2
            elif kind == "hp":
                b0, b1, b2 = (1 + c) / 2, -(1 + c), (1 + c) / 2
            else:                              # "bp", unity peak
                b0, b1, b2 = alpha, 0.0, -alpha
            b0, b1, b2 = b0 / a0, b1 / a0, b2 / a0
            a1, a2 = (-2 * c) / a0, (1 - alpha) / a0
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, x
        y2, y1 = y1, y
        out[i] = y
    return out


def formants(sig, vowel, q=9.0, tilt=(1.0, 0.7, 0.35)):
    """Three bandpasses = a vowel. `vowel` is a key of VOWELS, a triple, or a function of t
    returning a triple (so a voice can move its mouth)."""
    if isinstance(vowel, str):
        f1, f2, f3 = VOWELS[vowel]
    elif callable(vowel):
        f1 = lambda t: vowel(t)[0]
        f2 = lambda t: vowel(t)[1]
        f3 = lambda t: vowel(t)[2]
    else:
        f1, f2, f3 = vowel
    a = biquad(sig, "bp", f1, q)
    b = biquad(sig, "bp", f2, q * 1.1)
    c = biquad(sig, "bp", f3, q * 1.3)
    return [a[i] * tilt[0] + b[i] * tilt[1] + c[i] * tilt[2] for i in range(len(sig))]


def mouth(seq, seconds):
    """Glide between vowels: mouth(["o", "a", "e"], 2.0) -> a function of t for `formants`."""
    table = [VOWELS[v] if isinstance(v, str) else v for v in seq]

    def fn(t):
        u = min(0.9999, max(0.0, t / seconds)) * (len(table) - 1)
        i = int(u)
        k = u - i
        k = k * k * (3 - 2 * k)
        a, b = table[i], table[min(i + 1, len(table) - 1)]
        return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k)
    return fn


def drive(sig, amount=3.0, out_gain=None):
    g = out_gain if out_gain is not None else 1.0 / math.tanh(amount)
    return [math.tanh(x * amount) * g for x in sig]


def crush(sig, bits=6, hold=3):
    levels = float(2 ** bits)
    out = [0.0] * len(sig)
    held = 0.0
    for i, x in enumerate(sig):
        if i % hold == 0:
            held = round(max(-1.0, min(1.0, x)) * levels) / levels
        out[i] = held
    return out


def ringmod(sig, freq, mix=1.0):
    m = osc(len(sig) / RATE, freq)
    m = m[:len(sig)] + [0.0] * max(0, len(sig) - len(m))
    return [sig[i] * (1 - mix + mix * m[i]) for i in range(len(sig))]


def tremolo(sig, rate, depth=0.5, wave="sine"):
    m = osc(len(sig) / RATE, rate, wave)
    return [sig[i] * (1 - depth + depth * (m[i] * 0.5 + 0.5)) for i in range(len(sig))]


def delay(sig, time=0.12, feedback=0.35, mix=0.35, tail=0.5):
    out = list(sig) + [0.0] * n(tail)
    size = max(1, n(time))
    buf = [0.0] * size
    idx = 0
    for i, x in enumerate(out):
        y = buf[idx]
        buf[idx] = x + y * feedback
        idx = (idx + 1) % size
        out[i] = x + y * mix
    return out


def reverb(sig, room=0.84, damp=0.35, mix=0.3, tail=1.0):
    """Four combs and two allpasses - a small Schroeder room. Enough to put a mob in a cave."""
    out = list(sig) + [0.0] * n(tail)
    wet = [0.0] * len(out)
    for size in (558, 638, 711, 778):
        buf = [0.0] * size
        idx = 0
        store = 0.0
        for i, x in enumerate(out):
            y = buf[idx]
            store = y * (1 - damp) + store * damp
            buf[idx] = x + store * room
            idx += 1
            if idx == size:
                idx = 0
            wet[i] += y * 0.25
    for size in (278, 170):
        buf = [0.0] * size
        idx = 0
        for i, x in enumerate(wet):
            y = buf[idx]
            buf[idx] = x + y * 0.5
            wet[i] = y - x
            idx += 1
            if idx == size:
                idx = 0
    return [out[i] * (1 - mix) + wet[i] * mix for i in range(len(out))]


def reverse(sig):
    return sig[::-1]


def stutter(sig, grain=0.035, holds=2):
    """Repeat each grain - a signal skipping like a bad connection."""
    size = max(1, n(grain))
    out = []
    for start in range(0, len(sig), size):
        piece = sig[start:start + size]
        for _ in range(holds):
            out.extend(piece)
    return out[:len(sig)]


def mix(*layers, length=None):
    """mix(a, (b, 0.4), (c, 0.6, 1.2)) - signal, gain, start in seconds."""
    parts = []
    for layer in layers:
        if isinstance(layer, tuple):
            sig, g = layer[0], layer[1]
            at = n(layer[2]) if len(layer) > 2 else 0
        else:
            sig, g, at = layer, 1.0, 0
        parts.append((sig, g, at))
    size = length if length is not None else max(at + len(sig) for sig, _, at in parts)
    out = [0.0] * size
    for sig, g, at in parts:
        for i, x in enumerate(sig):
            j = at + i
            if 0 <= j < size:
                out[j] += x * g
    return out


def seq(*sigs):
    out = []
    for s in sigs:
        out.extend(s)
    return out


def gain(sig, g):
    return [x * g for x in sig]


def fade(sig, fin=0.004, fout=0.03):
    a, b = max(1, n(fin)), max(1, n(fout))
    out = list(sig)
    for i in range(min(a, len(out))):
        out[i] *= i / a
    for i in range(min(b, len(out))):
        out[len(out) - 1 - i] *= i / b
    return out


def normalise(sig, peak=0.9):
    top = max((abs(x) for x in sig), default=0.0)
    if top < 1e-9:
        return sig
    k = peak / top
    return [x * k for x in sig]


def finish(sig, peak=0.9, fin=0.004, fout=0.04):
    return normalise(fade(sig, fin, fout), peak)


# ---------------------------------------------------------------- instruments built from the box

def voiced(seconds, f0, vowel, q=9.0, dist=2.0, jitter=0.012, seed=1, wave="saw", duty=0.12):
    """A throat: a glottal source at f0 through a vowel, then a little distortion. Everything
    that talks, growls, chants or screams in this pack comes out of this one function."""
    jit = wobble(28, jitter, seed)
    base = const(f0)
    src = osc(seconds, lambda t: base(t) * jit(t), wave, duty=duty)
    return drive(formants(src, vowel, q), dist)


def whispered(seconds, vowel, q=16.0, seed=1):
    """The same mouth with no voice behind it - breath shaped into a vowel."""
    return formants(noise(seconds, seed), vowel, q, tilt=(1.0, 0.9, 0.6))


def breath(seconds, low, high, seed=1, q=1.4, shape=None):
    """One lungful: noise through a bandpass that sweeps low -> high."""
    sig = biquad(noise(seconds, seed, "pink"), "bp", ramp_t(low, high, seconds), q)
    return env(sig, shape or [(0, 0), (0.35, 1), (0.7, 0.85), (1, 0)])


def ramp_t(a, b, seconds, curve=1.0):
    """a -> b over `seconds` (the version taking t in seconds, for oscillators and filters)."""
    return lambda t: a + (b - a) * min(1.0, max(0.0, t / seconds)) ** curve


def bell(seconds, freq, ratio=1.41, index=6.0, curve=5.0):
    """FM bell - an inharmonic partial makes it metal rather than a flute."""
    mod = osc(seconds, freq * ratio)
    dec = [math.exp(-curve * i / len(mod)) for i in range(len(mod))]
    car = osc(seconds, freq)
    out = [0.0] * len(car)
    p = 0.0
    for i in range(len(car)):
        p += (freq + freq * index * dec[i] * mod[i]) / RATE
        out[i] = math.sin(TAU * (p % 1.0)) * dec[i]
    return out


def thump(seconds, top, bottom, curve=6.0):
    return perc(osc(seconds, ramp_t(top, bottom, seconds * 0.5, 0.4)), 0.002, curve)


def click(seconds, freq, q=6.0, seed=1, curve=30.0):
    return perc(biquad(noise(seconds, seed), "bp", freq, q), 0.0005, curve)


def grains(seconds, count, make, seed=1, spread=1.0, start=0.0):
    """Scatter `count` little sounds over the length - crackle, chitter, sparks, arcs."""
    rnd = rng(seed)
    layers = []
    for i in range(count):
        at = start + (seconds - start) * (rnd() ** spread)
        layers.append((make(i, rnd), 1.0, at))
    return mix(*layers, length=n(seconds))


# ---------------------------------------------------------------- the nineteen voices
#
# One function per line. They are written to be *heard*, not to be efficient: every one of them
# is a few of the instruments above stacked, because a single oscillator through a single filter
# is exactly the thin, obviously-fake sound this pack is here to stop making.

def vampire_ambient():
    inhale = breath(1.1, 260, 1900, seed=11, q=1.1)
    drone = osc(2.2, lambda t: 880 * (1 - 0.16 * min(1.0, t / 2.2)) * (1 + 0.02 * math.sin(TAU * 5.2 * t)))
    thin = osc(2.2, lambda t: 1320 * (1 - 0.16 * min(1.0, t / 2.2)))
    air = mix((drone, 0.5), (thin, 0.22))
    air = env(biquad(air, "lp", 2600, 1.0), [(0, 0), (0.25, 0.6), (0.6, 0.9), (1, 0)])
    sub = env(osc(2.2, 55), [(0, 0), (0.4, 0.35), (1, 0)])
    return finish(reverb(mix((inhale, 0.75), (air, 1.0, 0.6), (sub, 0.6)), mix=0.26, tail=0.7), 0.85)


def vampire_hurt():
    screech = voiced(0.42, ramp_t(920, 380, 0.42, 1.6), "i", q=13, dist=4.0, jitter=0.03, seed=12)
    hiss = env(biquad(noise(0.5, 13), "hp", 3000, 0.8), [(0, 1), (1, 0)])
    return finish(mix(perc(screech, 0.006, 3.5), (hiss, 0.5)), 0.95)


def vampire_death():
    scream = voiced(1.1, ramp_t(760, 120, 1.1, 1.8), mouth(["i", "a", "o"], 1.1), q=10, dist=3.0, jitter=0.04, seed=14)
    scream = env(scream, [(0, 0), (0.05, 1), (0.6, 0.7), (1, 0)])
    wings = tremolo(biquad(noise(0.9, 15, "pink"), "bp", 700, 1.2), 17, 0.9)
    wings = env(wings, [(0, 0), (0.2, 1), (1, 0)])
    return finish(reverb(mix(scream, (wings, 0.55, 0.85)), mix=0.3, tail=0.8), 0.9)


def stalker_ambient():
    beat = mix((thump(0.35, 62, 26), 1.0, 0.0), (thump(0.3, 54, 24), 0.7, 0.19),
               (thump(0.35, 62, 26), 1.0, 1.05), (thump(0.3, 54, 24), 0.7, 1.24), length=n(2.6))
    close = breath(1.5, 380, 700, seed=21, q=0.9, shape=[(0, 0), (0.3, 1), (0.55, 0.4), (0.8, 0.8), (1, 0)])
    rumble = env(osc(2.6, lambda t: 33 + 2 * math.sin(TAU * 0.4 * t)), [(0, 0), (0.3, 1), (0.8, 1), (1, 0)])
    return finish(mix((beat, 0.9), (close, 0.5, 0.55), (rumble, 0.5)), 0.8)


def stalker_hurt():
    gasp = breath(0.4, 420, 2600, seed=22, q=1.6, shape=[(0, 0), (0.15, 1), (1, 0)])
    throat = perc(voiced(0.25, ramp_t(150, 105, 0.25), "r", q=8, dist=2.0, seed=23), 0.01, 5)
    return finish(mix(gasp, (throat, 0.5)), 0.9)


def stalker_death():
    sigh = mix((whispered(1.6, mouth(["a", "u"], 1.6), q=9, seed=24), 1.0),
               (voiced(1.6, ramp_t(96, 58, 1.6), mouth(["a", "u"], 1.6), q=7, dist=1.6, seed=25), 0.35))
    sigh = env(biquad(sigh, "lp", ramp_t(3000, 320, 1.6, 0.7), 0.9), [(0, 0), (0.12, 1), (0.6, 0.6), (1, 0)])
    static = env(biquad(noise(0.7, 26), "hp", 1800, 0.7), [(0, 0), (0.3, 0.5), (1, 0)])
    return finish(mix(sigh, (static, 0.35, 1.0)), 0.85)


def warlock_ambient():
    m = mouth(["o", "o", "a", "e", "a"], 2.6)
    low = voiced(2.6, lambda t: 98 * (1 + 0.004 * math.sin(TAU * 0.8 * t)), m, q=8, dist=2.2, seed=31)
    third = voiced(2.6, lambda t: 116.5 * (1 + 0.005 * math.sin(TAU * 0.6 * t)), m, q=8, dist=2.0, seed=32)
    fifth = voiced(2.6, lambda t: 147.0 * (1 + 0.004 * math.sin(TAU * 1.1 * t)), m, q=8, dist=2.0, seed=33)
    choir = mix(low, (third, 0.7), (fifth, 0.5))
    choir = tremolo(env(choir, [(0, 0), (0.18, 1), (0.75, 0.9), (1, 0)]), 3.1, 0.22)
    return finish(reverb(choir, room=0.88, mix=0.4, tail=1.2), 0.88)


def warlock_hurt():
    bark = voiced(0.4, ramp_t(120, 210, 0.4, 0.5), mouth(["o", "a"], 0.4), q=9, dist=3.5, seed=34)
    bark = env(bark, [(0, 0), (0.06, 1), (0.5, 0.8), (1, 0)])
    return finish(reverb(ringmod(bark, 73, 0.45), mix=0.25, tail=0.4), 0.92)


def warlock_death():
    m = mouth(["a", "o", "u"], 2.0)
    fall = mix(voiced(2.0, ramp_t(98, 62, 2.0, 1.4), m, q=8, dist=2.2, seed=35),
               (voiced(2.0, ramp_t(116.5, 69, 2.0, 1.4), m, q=8, dist=2.0, seed=36), 0.7),
               (voiced(2.0, ramp_t(147, 87, 2.0, 1.4), m, q=8, dist=2.0, seed=37), 0.45))
    fall = env(biquad(fall, "lp", ramp_t(3200, 420, 2.0, 0.8), 0.9), [(0, 0), (0.06, 1), (0.55, 0.75), (1, 0)])
    return finish(reverb(fall, room=0.9, mix=0.45, tail=1.6), 0.9)


def siren_ambient():
    notes = [(440, 0.0), (587.33, 0.45), (659.25, 0.85), (523.25, 1.35), (392, 1.8), (440, 2.15)]

    def melody(t):
        f = notes[0][0]
        for freq, at in notes:
            if t >= at:
                f = freq
        return f * (1 + 0.018 * math.sin(TAU * 5.4 * t))
    glide = biquad([melody(i / RATE) for i in range(n(2.7))], "lp", 9, 0.7)   # portamento
    lead = osc(2.7, lambda t: glide[min(len(glide) - 1, int(t * RATE))])
    second = osc(2.7, lambda t: 2 * glide[min(len(glide) - 1, int(t * RATE))])
    shimmer = osc(2.7, lambda t: 4 * glide[min(len(glide) - 1, int(t * RATE))])
    song = mix(lead, (second, 0.3), (shimmer, 0.08))
    song = env(biquad(song, "lp", 3200, 0.8), [(0, 0), (0.1, 1), (0.85, 0.9), (1, 0)])
    return finish(reverb(song, room=0.86, mix=0.34, tail=1.0), 0.88)


def siren_hurt():
    a = osc(0.55, ramp_t(660, 520, 0.55))
    b = osc(0.55, ramp_t(466, 500, 0.55))                 # a tritone, going sour
    crack = drive(mix(a, (b, 0.9)), 2.6)
    crack = perc(tremolo(crack, 24, 0.5), 0.008, 4)
    return finish(reverb(crack, mix=0.25, tail=0.4), 0.93)


def siren_death():
    smear = osc(1.7, ramp_t(660, 120, 1.7, 1.7))
    smear = env(biquad(mix(smear, (osc(1.7, ramp_t(1320, 240, 1.7, 1.7)), 0.3)), "lp",
                       ramp_t(3200, 260, 1.7, 0.9), 1.1), [(0, 1), (0.7, 0.7), (1, 0)])
    bubbles = grains(1.6, 14, lambda i, r: perc(osc(0.09, ramp_t(240 + r() * 500, 900 + r() * 700, 0.09)), 0.004, 8), seed=41)
    return finish(reverb(mix(smear, (bubbles, 0.4, 0.2)), mix=0.3, tail=0.8), 0.9)


def brute_ambient():
    low = voiced(1.8, lambda t: 55 * (1 + 0.03 * math.sin(TAU * 1.7 * t)), mouth(["a", "r", "a"], 1.8),
                 q=7, dist=3.6, jitter=0.03, seed=51)
    sub = osc(1.8, 41)
    growl = tremolo(mix(low, (sub, 0.45)), 7.5, 0.3)
    return finish(env(growl, [(0, 0), (0.15, 1), (0.7, 0.9), (1, 0)]), 0.92)


def brute_hurt():
    bark = voiced(0.38, ramp_t(105, 58, 0.38, 1.4), "a", q=7, dist=5.0, jitter=0.04, seed=52)
    return finish(mix(perc(bark, 0.006, 4.5), (thump(0.25, 90, 45), 0.5)), 0.97)


def brute_death():
    roar = voiced(1.5, ramp_t(86, 32, 1.5, 1.5), mouth(["a", "o", "r"], 1.5), q=7, dist=4.2, jitter=0.05, seed=53)
    roar = env(roar, [(0, 0), (0.05, 1), (0.6, 0.8), (1, 0)])
    fall = thump(0.7, 80, 30, curve=5)
    return finish(reverb(mix(roar, (fall, 0.9, 1.35)), mix=0.26, tail=0.8), 0.95)


def arsonist_ambient():
    crackle = grains(2.0, 34, lambda i, r: click(0.05, 1600 + r() * 2600, q=3.0, seed=60 + i, curve=26), seed=61)
    jet = env(biquad(noise(2.0, 62, "pink"), "lp", lambda t: 900 + 500 * math.sin(TAU * 0.7 * t), 1.0),
              [(0, 0), (0.2, 1), (0.8, 0.9), (1, 0)])
    tss = env(biquad(noise(2.0, 63), "hp", 5200, 0.7), [(0, 0), (0.5, 0.5), (1, 0)])
    return finish(mix((jet, 0.8), (crackle, 0.75), (tss, 0.3)), 0.88)


def arsonist_hurt():
    steam = biquad(noise(0.55, 64), "bp", ramp_t(900, 3200, 0.55, 0.6), 4.0)
    steam = env(steam, [(0, 0), (0.08, 1), (1, 0)])
    yelp = perc(voiced(0.35, ramp_t(280, 420, 0.35), "e", q=10, dist=3.0, seed=65), 0.008, 5)
    return finish(mix((steam, 1.0), (yelp, 0.5)), 0.95)


def arsonist_death():
    whoomph = perc(biquad(noise(0.9, 66, "pink"), "lp", ramp_t(2200, 180, 0.9, 0.6), 1.0), 0.01, 3.5)
    sub = thump(0.8, 120, 38)
    dying = grains(1.7, 22, lambda i, r: click(0.05, 1200 + r() * 2200, q=3.0, seed=70 + i, curve=26), seed=67, spread=0.45, start=0.25)
    return finish(reverb(mix((whoomph, 1.0), (sub, 0.7), (dying, 0.5)), mix=0.25, tail=0.7), 0.95)


def plague_ambient():
    gurgle = ringmod(biquad(noise(2.2, 71, "pink"), "lp", lambda t: 420 + 300 * math.sin(TAU * 1.3 * t), 2.2), 34, 0.8)
    gurgle = env(gurgle, [(0, 0), (0.2, 1), (0.8, 0.9), (1, 0)])
    throat = voiced(2.2, lambda t: 72 * (1 + 0.05 * math.sin(TAU * 2.1 * t)), mouth(["u", "o", "u"], 2.2),
                    q=6, dist=2.4, jitter=0.05, seed=72)
    bubbles = grains(2.2, 11, lambda i, r: perc(osc(0.1, ramp_t(120 + r() * 200, 400 + r() * 400, 0.1)), 0.005, 9), seed=73)
    return finish(mix((gurgle, 0.9), (throat, 0.55), (bubbles, 0.3)), 0.88)


def plague_hurt():
    cough = perc(voiced(0.3, ramp_t(140, 80, 0.3, 1.5), "a", q=7, dist=4.5, jitter=0.05, seed=74), 0.004, 6)
    wet = perc(biquad(noise(0.45, 75, "pink"), "lp", 1400, 1.6), 0.006, 5)
    return finish(mix(cough, (wet, 0.6), (perc(voiced(0.22, 110, "r", dist=3.5, seed=76), 0.01, 7), 0.5, 0.26)), 0.95)


def plague_death():
    exhale = env(biquad(noise(1.5, 77, "pink"), "lp", ramp_t(1600, 300, 1.5), 1.2), [(0, 0), (0.15, 1), (1, 0)])
    voice = env(voiced(1.2, ramp_t(78, 44, 1.2), mouth(["a", "u"], 1.2), q=6, dist=2.6, jitter=0.06, seed=78),
                [(0, 1), (0.6, 0.6), (1, 0)])
    splat = perc(biquad(noise(0.35, 79, "pink"), "lp", 700, 1.4), 0.003, 9)
    return finish(mix((exhale, 0.9), (voice, 0.8), (splat, 0.8, 1.45)), 0.9)


def blinker_ambient():
    shimmer = mix(bell(1.2, 620, 1.37, 5.0, 4.0), (bell(1.2, 930, 1.41, 4.0, 4.5), 0.6))
    warp = reverse(env(shimmer, [(0, 0), (0.8, 1), (1, 1)]))
    glitch = stutter(biquad(noise(0.5, 81), "bp", ramp_t(2600, 500, 0.5), 5.0), 0.012, 2)
    glitch = env(glitch, [(0, 0), (0.5, 1), (1, 0)])
    return finish(mix((warp, 0.9), (glitch, 0.35, 1.15), (perc(osc(0.12, 1400), 0.001, 20), 0.5, 1.2)), 0.9)


def blinker_hurt():
    zap = crush(osc(0.3, ramp_t(2200, 180, 0.3, 2.2)), 5, 2)
    return finish(mix(perc(zap, 0.002, 6), (click(0.2, 3000, seed=82), 0.5)), 0.95)


def blinker_death():
    collapse = mix(osc(1.0, ramp_t(1200, 42, 1.0, 2.4)),
                   (biquad(noise(1.0, 83), "bp", ramp_t(2400, 90, 1.0, 2.2), 6.0), 0.7))
    collapse = env(collapse, [(0, 1), (0.75, 0.7), (0.95, 0.1), (1, 0)])
    return finish(mix(collapse, (perc(osc(0.1, 2600), 0.001, 25), 0.35, 1.08)), 0.9)


def juggernaut_ambient():
    slip, hunt = wobble(3.2, 0.06, 91), wobble(1.1, 0.04, 92)
    grind = drive(osc(2.2, lambda t: 47 * slip(t), "saw"), 6.0)
    grind = tremolo(biquad(grind, "lp", 1400, 1.2), 11, 0.55, "square")
    servo = env(biquad(osc(2.2, lambda t: 430 * hunt(t), "saw"), "bp", 1500, 6.0),
                [(0, 0), (0.25, 1), (0.8, 0.8), (1, 0)])
    scrape = env(tremolo(biquad(noise(2.2, 93), "bp", 1900, 4.0), 23, 0.8), [(0, 0), (0.3, 1), (1, 0)])
    return finish(mix((grind, 1.0), (servo, 0.28), (scrape, 0.3)), 0.9)


def juggernaut_hurt():
    body = noise(0.6, 94)
    ring = mix(biquad(body, "bp", 520, 34), (biquad(body, "bp", 1310, 30), 0.7), (biquad(body, "bp", 2470, 26), 0.4))
    return finish(mix(perc(ring, 0.001, 3.2), (thump(0.3, 140, 60), 0.6)), 0.97)


def juggernaut_death():
    sag = lambda t: max(0.12, 1.0 - 0.85 * (t / 2.0) ** 0.8)
    slip = wobble(3.0, 0.08, 95)
    grind = drive(osc(2.0, lambda t: 47 * sag(t) * slip(t), "saw"), 5.5)
    grind = tremolo(biquad(grind, "lp", ramp_t(1500, 300, 2.0), 1.2), lambda t: 1.5 + 10 * sag(t), 0.6, "square")
    servo = env(biquad(osc(2.0, lambda t: 430 * sag(t), "saw"), "bp", ramp_t(1500, 300, 2.0), 6.0),
                [(0, 1), (0.8, 0.5), (1, 0)])
    drop = thump(0.9, 110, 28, curve=4.5)
    return finish(reverb(mix((grind, 1.0), (servo, 0.3), (drop, 0.9, 1.85)), mix=0.2, tail=0.7), 0.95)


def chaos_ambient():
    rnd = rng(101)
    scale = [262, 311, 370, 415, 466, 554, 622, 740, 831, 988, 1245]
    blips = []
    at = 0.0
    while at < 1.7:
        f = scale[int(rnd() * len(scale))] * (1 + 0.5 * int(rnd() * 2))
        blips.append((perc(bell(0.3, f, 1.31 + rnd() * 0.4, 4 + rnd() * 5, 6), 0.002, 5), 0.6 + rnd() * 0.4, at))
        at += 0.07 + rnd() * 0.16
    return finish(delay(mix(*blips, length=n(1.8)), 0.09, 0.3, 0.3, 0.4), 0.9)


def chaos_hurt():
    glitch = crush(biquad(noise(0.3, 102), "bp", ramp_t(600, 3000, 0.3), 4.0), 4, 4)
    rnd = rng(103)
    blips = [(perc(bell(0.16, 500 + rnd() * 1600, 1.4, 6, 8), 0.001, 6), 0.8, 0.02 + i * 0.055) for i in range(4)]
    return finish(mix((perc(glitch, 0.002, 5), 0.8), *blips), 0.95)


def chaos_death():
    whistle = osc(1.2, lambda t: (300 + 1700 * (t / 1.2) ** 1.5) * (1 + 0.02 * math.sin(TAU * 9 * t)))
    whistle = env(whistle, [(0, 0), (0.1, 0.8), (0.9, 1), (1, 0)])
    rnd = rng(104)
    sparks = [(perc(bell(0.25, 700 + rnd() * 2200, 1.37, 7, 7), 0.001, 6), 0.7, 0.75 + rnd() * 0.9) for _ in range(12)]
    return finish(reverb(mix((whistle, 0.7), *sparks, length=n(1.9)), mix=0.25, tail=0.6), 0.92)


def boomer_ambient():
    hiss = env(biquad(noise(2.0, 111), "bp", ramp_t(2600, 4200, 2.0), 1.6), [(0, 0), (0.1, 0.8), (1, 1)])
    hiss = tremolo(hiss, 31, 0.35)
    ticks = []                                 # the fuse counting down, and hurrying
    at, step = 0.05, 0.30
    while at < 1.95:
        ticks.append((click(0.05, 2600, q=5.0, seed=112 + int(at * 100), curve=30), 0.9, at))
        at += step
        step = max(0.06, step * 0.86)
    return finish(mix((hiss, 0.7), *ticks, length=n(2.0)), 0.88)


def boomer_hurt():
    return finish(mix(env(biquad(noise(0.35, 113), "bp", ramp_t(1400, 4000, 0.35), 2.2), [(0, 0), (0.1, 1), (1, 0)]),
                      (click(0.12, 3200, seed=114), 0.4)), 0.93)


def boomer_death():
    blast = perc(drive(biquad(noise(1.1, 115, "pink"), "lp", ramp_t(3000, 120, 1.1, 0.5), 1.0), 3.0), 0.002, 3.0)
    sub = thump(1.0, 95, 24, curve=3.5)
    return finish(reverb(mix((blast, 1.0), (sub, 0.95)), room=0.88, mix=0.3, tail=0.9), 0.98)


def charged_ambient():
    hum = mix(osc(2.0, 50, "saw"), (osc(2.0, 100), 0.5))
    hum = env(biquad(hum, "bp", 420, 3.0), [(0, 0), (0.2, 1), (0.8, 1), (1, 0)])
    arcs = grains(2.0, 26, lambda i, r: click(0.04, 2400 + r() * 3400, q=8.0, seed=120 + i, curve=34), seed=121)
    ring = env(osc(2.0, lambda t: 1180 * (1 + 0.01 * math.sin(TAU * 3 * t))), [(0, 0), (0.4, 0.35), (1, 0)])
    return finish(mix((hum, 0.85), (arcs, 0.7), (ring, 0.22)), 0.9)


def charged_hurt():
    zap = ringmod(biquad(noise(0.3, 122), "bp", ramp_t(3200, 700, 0.3, 1.6), 5.0), 160, 0.7)
    return finish(mix(perc(zap, 0.001, 5), (perc(osc(0.2, ramp_t(1400, 300, 0.2)), 0.002, 7), 0.4)), 0.95)


def charged_death():
    crack = perc(biquad(noise(1.4, 123, "pink"), "lp", ramp_t(5000, 140, 1.4, 0.45), 1.0), 0.001, 3.2)
    sub = thump(1.0, 130, 30, curve=4)
    arcs = grains(1.8, 16, lambda i, r: click(0.05, 1800 + r() * 3000, q=7.0, seed=130 + i, curve=30), seed=124, spread=0.5, start=0.35)
    return finish(reverb(mix((crack, 1.0), (sub, 0.8), (arcs, 0.55)), room=0.9, mix=0.32, tail=1.0), 0.97)


def swift_ambient():
    puffs = []
    at = 0.0
    for i in range(6):
        up = i % 2 == 0
        puffs.append((breath(0.16, 700 if up else 1500, 1500 if up else 600, seed=131 + i, q=1.8), 0.9, at))
        at += 0.21
    return finish(mix(*puffs, length=n(1.4)), 0.85)


def swift_hurt():
    yelp = voiced(0.28, lambda t: 380 + 340 * math.sin(math.pi * min(1.0, t / 0.28)), "e", q=10, dist=3.5, seed=137)
    return finish(perc(yelp, 0.005, 5), 0.95)


def swift_death():
    gasp = env(voiced(0.6, ramp_t(240, 430, 0.6), mouth(["a", "e"], 0.6), q=9, dist=3.0, seed=138),
               [(0, 0), (0.08, 1), (0.85, 0.9), (0.9, 0), (1, 0)])
    out = breath(0.45, 900, 380, seed=139, q=1.5)
    return finish(mix(gasp, (out, 0.5, 0.62)), 0.92)


def baby_ambient():
    rnd = rng(141)
    bursts = []
    at = 0.05
    for i in range(3):
        d = 0.28 + rnd() * 0.12
        g = voiced(d, lambda t, b=380 + rnd() * 90: b * (1 + 0.06 * math.sin(TAU * 13 * t)),
                   mouth(["i", "e", "i"], d), q=11, dist=2.6, jitter=0.03, seed=142 + i)
        bursts.append((tremolo(env(g, [(0, 0), (0.1, 1), (0.8, 0.8), (1, 0)]), 13, 0.7), 0.9, at))
        at += d + 0.12
    return finish(mix(*bursts, length=n(1.6)), 0.88)


def baby_hurt():
    squeal = voiced(0.3, ramp_t(820, 1350, 0.3, 0.6), "i", q=12, dist=4.0, seed=145)
    return finish(perc(squeal, 0.004, 5), 0.95)


def baby_death():
    wail = voiced(0.95, ramp_t(780, 210, 0.95, 1.5), mouth(["e", "a", "o"], 0.95), q=10, dist=3.0, jitter=0.03, seed=146)
    wail = tremolo(env(wail, [(0, 0), (0.06, 1), (0.7, 0.8), (1, 0)]), 6.5, 0.3)
    return finish(wail, 0.93)


def bandit_ambient():
    rnd = rng(151)
    syllables = []
    at = 0.08
    vowels = ["o", "a", "r", "u", "e", "a", "o"]
    for i in range(6):
        d = 0.14 + rnd() * 0.12
        base = 108 + rnd() * 26
        s = voiced(d, ramp_t(base, base * (0.82 + rnd() * 0.2), d), vowels[i % len(vowels)],
                   q=8, dist=2.4, jitter=0.02, seed=152 + i)
        syllables.append((env(s, [(0, 0), (0.15, 1), (0.7, 0.8), (1, 0)]), 0.8 + rnd() * 0.3, at))
        at += d + 0.04 + rnd() * 0.12
    muttered = biquad(mix(*syllables, length=n(2.0)), "lp", 1900, 0.9)
    return finish(muttered, 0.88)


def bandit_hurt():
    grunt = voiced(0.3, ramp_t(132, 86, 0.3, 1.3), "o", q=7, dist=3.4, jitter=0.03, seed=158)
    return finish(perc(grunt, 0.006, 4.5), 0.95)


def bandit_death():
    curse = voiced(1.3, ramp_t(120, 58, 1.3, 1.4), mouth(["a", "r", "o", "u"], 1.3), q=7, dist=3.2, jitter=0.04, seed=159)
    curse = env(curse, [(0, 0), (0.06, 1), (0.55, 0.7), (1, 0)])
    return finish(reverb(biquad(curse, "lp", ramp_t(2200, 500, 1.3), 0.9), mix=0.22, tail=0.6), 0.92)


def pacifist_ambient():
    notes = [(392, 0.0, 0.55), (523.25, 0.6, 0.5), (587.33, 1.15, 0.5), (440, 1.7, 0.65)]
    hums = []
    for f, at, d in notes:
        lead = osc(d, lambda t, f=f: f * (1 + 0.012 * math.sin(TAU * 4.6 * t)))
        warm = osc(d, lambda t, f=f: 2 * f * (1 + 0.012 * math.sin(TAU * 4.6 * t)))
        h = env(biquad(mix(lead, (warm, 0.18)), "lp", 1800, 0.9), [(0, 0), (0.25, 1), (0.75, 0.9), (1, 0)])
        hums.append((h, 0.9, at))
    return finish(reverb(mix(*hums, length=n(2.4)), mix=0.24, tail=0.7), 0.82)


def pacifist_hurt():
    oh = voiced(0.35, ramp_t(280, 205, 0.35, 1.2), "o", q=9, dist=1.6, seed=161)
    return finish(env(oh, [(0, 0), (0.1, 1), (0.6, 0.7), (1, 0)]), 0.88)


def pacifist_death():
    a = osc(1.4, lambda t: 392 * (1 - 0.16 * min(1.0, t / 1.4)) * (1 + 0.012 * math.sin(TAU * 4.2 * t)))
    b = osc(1.4, lambda t: 466 * (1 - 0.16 * min(1.0, t / 1.4)))
    sad = env(biquad(mix(a, (b, 0.55)), "lp", ramp_t(1900, 700, 1.4), 0.9), [(0, 0), (0.12, 1), (0.6, 0.7), (1, 0)])
    return finish(reverb(sad, mix=0.3, tail=0.8), 0.85)


def spider_ambient():
    chitter = grains(1.6, 46, lambda i, r: click(0.012, 2400 + r() * 2600, q=9.0, seed=170 + i, curve=45), seed=171)
    rattle = grains(1.6, 13, lambda i, r: click(0.09, 900 + r() * 700, q=16.0, seed=190 + i, curve=16), seed=172)
    return finish(mix((chitter, 0.9), (rattle, 0.7)), 0.88)


def spider_hurt():
    clat = mix(*[(click(0.1, 1400 - i * 150, q=14.0, seed=175 + i, curve=20), 0.9, i * 0.035) for i in range(6)],
               length=n(0.45))
    return finish(mix(clat, (click(0.15, 2800, q=6.0, seed=181), 0.4)), 0.95)


def spider_death():
    falls = []
    at, step = 0.0, 0.055
    for i in range(11):
        falls.append((click(0.13, 1500 * (0.93 ** i), q=15.0, seed=182 + i, curve=18), 0.9, at))
        step *= 1.12
        at += step
    last = grains(0.5, 12, lambda i, r: click(0.012, 1800 + r() * 1800, q=9.0, seed=200 + i, curve=45), seed=183)
    return finish(mix(mix(*falls, length=n(1.5)), (last, 0.5)), 0.92)


def wtf_ambient():
    def crazy(t):
        return 300 + 500 * math.sin(TAU * 0.9 * t) + 220 * math.sin(TAU * 2.7 * t + 1)
    yell = voiced(1.3, crazy, mouth(["a", "i", "o", "e", "a"], 1.3), q=11, dist=3.2, jitter=0.03, seed=191)
    yell = ringmod(env(yell, [(0, 0), (0.05, 1), (0.85, 0.9), (1, 0)]), 61, 0.35)
    boing = osc(0.6, lambda t: 260 * (1 + 0.55 * math.sin(TAU * 7 * t) * math.exp(-4 * t)))
    return finish(mix((yell, 1.0), (perc(boing, 0.005, 4), 0.6, 1.32)), 0.95)


def wtf_hurt():
    squeak = crush(voiced(0.26, ramp_t(500, 1500, 0.26, 0.5), "i", q=12, dist=3.0, seed=192), 5, 2)
    return finish(perc(squeak, 0.003, 6), 0.95)


def wtf_death():
    slide = osc(1.0, ramp_t(1500, 190, 1.0, 1.8))
    slide = mix(env(slide, [(0, 0), (0.05, 1), (0.9, 0.8), (1, 0)]),
                (env(biquad(noise(1.0, 193), "bp", ramp_t(1500, 190, 1.0, 1.8), 6.0), [(0, 0.6), (1, 0)]), 0.4))
    splat = perc(biquad(noise(0.3, 194, "pink"), "lp", 600, 1.3), 0.002, 9)
    horn = env(tremolo(drive(osc(0.45, 196, "saw"), 3.0), 19, 0.6), [(0, 0), (0.08, 1), (1, 0)])
    return finish(mix((slide, 0.9), (splat, 0.8, 0.98), (horn, 0.5, 1.15)), 0.95)


def hexer_ambient():
    m = mouth(["u", "e", "a", "i", "o", "u"], 1.9)
    whisper = mix(whispered(1.9, m, q=18, seed=201), (whispered(1.9, m, q=14, seed=202), 0.6))
    whisper = reverse(env(whisper, [(0, 0), (0.75, 1), (1, 0.2)]))
    drone = mix(osc(2.4, 130.8, "saw"), (osc(2.4, 131.6, "saw"), 0.9))
    drone = env(biquad(drone, "bp", 520, 2.4), [(0, 0), (0.3, 0.5), (0.8, 0.5), (1, 0)])
    return finish(reverb(mix((whisper, 1.0), (drone, 0.45)), room=0.9, mix=0.42, tail=1.3), 0.88)


def hexer_hurt():
    yelp = voiced(0.45, ramp_t(240, 150, 0.45, 1.4), mouth(["e", "a"], 0.45), q=10, dist=3.0, seed=203)
    return finish(reverb(stutter(perc(yelp, 0.005, 4), 0.028, 2), mix=0.25, tail=0.5), 0.93)


def hexer_death():
    m = mouth(["a", "o", "u"], 1.4)
    collapse = reverse(env(mix(whispered(1.4, m, q=15, seed=204),
                               (voiced(1.4, ramp_t(150, 96, 1.4), m, q=8, dist=2.2, seed=205), 0.5)),
                           [(0, 0), (0.85, 1), (1, 0)]))
    toll = mix(bell(1.8, 165, 1.43, 7.0, 2.6), (bell(1.8, 330, 1.41, 4.0, 3.2), 0.35))
    return finish(reverb(mix((collapse, 0.9), (toll, 0.7, 1.15)), room=0.92, mix=0.45, tail=1.6), 0.92)


# id -> the three lines, the subtitle stem and how loud this design is
VOICES = {
    "vampire": dict(subtitle="Vampire", verbs=("hisses", "shrieks", "dies"), volume=0.9,
                    ambient=vampire_ambient, hurt=vampire_hurt, death=vampire_death),
    "stalker": dict(subtitle="Stalker", verbs=("breathes", "gasps", "fades"), volume=1.0,
                    ambient=stalker_ambient, hurt=stalker_hurt, death=stalker_death),
    "warlock": dict(subtitle="Warlock", verbs=("chants", "snarls", "unravels"), volume=0.9,
                    ambient=warlock_ambient, hurt=warlock_hurt, death=warlock_death),
    "siren": dict(subtitle="Siren", verbs=("sings", "cracks", "drowns"), volume=0.85,
                  ambient=siren_ambient, hurt=siren_hurt, death=siren_death),
    "brute": dict(subtitle="Brute", verbs=("growls", "barks", "roars"), volume=1.0,
                  ambient=brute_ambient, hurt=brute_hurt, death=brute_death),
    "arsonist": dict(subtitle="Arsonist", verbs=("crackles", "steams", "goes out"), volume=0.9,
                     ambient=arsonist_ambient, hurt=arsonist_hurt, death=arsonist_death),
    "plague-bearer": dict(subtitle="Plague-bearer", verbs=("gurgles", "retches", "bursts"), volume=0.9,
                          ambient=plague_ambient, hurt=plague_hurt, death=plague_death),
    "blinker": dict(subtitle="Blinker", verbs=("warps", "glitches", "collapses"), volume=0.85,
                    ambient=blinker_ambient, hurt=blinker_hurt, death=blinker_death),
    "juggernaut": dict(subtitle="Juggernaut", verbs=("grinds", "clangs", "winds down"), volume=1.0,
                       ambient=juggernaut_ambient, hurt=juggernaut_hurt, death=juggernaut_death),
    "chaos-creeper": dict(subtitle="Chaos", verbs=("jangles", "glitches", "scatters"), volume=0.85,
                          ambient=chaos_ambient, hurt=chaos_hurt, death=chaos_death),
    "boomer": dict(subtitle="Boomer", verbs=("fizzes", "spits", "detonates"), volume=1.0,
                   ambient=boomer_ambient, hurt=boomer_hurt, death=boomer_death),
    "charged-creeper": dict(subtitle="Charged", verbs=("hums", "zaps", "cracks"), volume=0.95,
                            ambient=charged_ambient, hurt=charged_hurt, death=charged_death),
    "swift": dict(subtitle="Swift", verbs=("pants", "yelps", "gasps"), volume=0.85,
                  ambient=swift_ambient, hurt=swift_hurt, death=swift_death),
    "baby-army": dict(subtitle="Baby", verbs=("giggles", "squeals", "wails"), volume=0.85,
                      ambient=baby_ambient, hurt=baby_hurt, death=baby_death),
    "bandit": dict(subtitle="Bandit", verbs=("mutters", "grunts", "curses"), volume=0.9,
                   ambient=bandit_ambient, hurt=bandit_hurt, death=bandit_death),
    "pacifist": dict(subtitle="Friendly one", verbs=("hums", "startles", "sighs"), volume=0.8,
                     ambient=pacifist_ambient, hurt=pacifist_hurt, death=pacifist_death),
    "spider-rider": dict(subtitle="Rider", verbs=("chitters", "clatters", "falls apart"), volume=0.9,
                         ambient=spider_ambient, hurt=spider_hurt, death=spider_death),
    "wtf": dict(subtitle="Something", verbs=("makes a noise", "squeaks", "deflates"), volume=0.9,
                ambient=wtf_ambient, hurt=wtf_hurt, death=wtf_death),
    "hexer": dict(subtitle="Hexer", verbs=("whispers", "stutters", "unmakes itself"), volume=0.9,
                  ambient=hexer_ambient, hurt=hexer_hurt, death=hexer_death),
}


# ---------------------------------------------------------------- shipping

KINDS = ("ambient", "hurt", "death")


def wav_bytes(sig, rate=RATE):
    pcm = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, x)) * 32000)) for x in sig)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(pcm)) + pcm)


def encoder():
    """(name, argv builder) for the best Vorbis encoder installed, or None.

    Mono matters - see the module docstring - so `oggenc` and ffmpeg's libvorbis come first and
    ffmpeg's own experimental encoder (stereo only, so the voice would play flat) comes last."""
    oggenc = shutil.which("oggenc")
    if oggenc:
        # --serial fixes the Ogg page serial, which is random by default: without it every build
        # writes different bytes and publish-packs.py would patch-bump the pack for nothing.
        return "oggenc", lambda src, dst: [oggenc, "-Q", "-q", "4", "--serial", "1", "-o", dst, src]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    base = [ffmpeg, "-loglevel", "error", "-y", "-i"]
    tail = ["-fflags", "+bitexact", "-flags", "+bitexact", "-map_metadata", "-1"]
    try:
        have = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    except OSError:
        return None
    if "libvorbis" in have:
        return "ffmpeg/libvorbis", lambda src, dst: base + [src, "-c:a", "libvorbis", "-q:a", "4", *tail, dst]
    return "ffmpeg/vorbis (stereo - plays flat)", lambda src, dst: base + [
        src, "-c:a", "vorbis", "-strict", "experimental", "-ac", "2", "-b:a", "96k", *tail, dst]


def encode(sig, argv):
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "in.wav"
        dst = pathlib.Path(tmp) / "out.ogg"
        src.write_bytes(wav_bytes(sig))
        result = subprocess.run(argv(str(src), str(dst)), capture_output=True)
        if result.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
            return None
        return dst.read_bytes()


def render(ns):
    """{path: bytes} for the pack, the `sounds.json` events and the subtitle strings.

    Every event is one file and nothing else: a design with a voice sounds like itself or, for a
    client without the pack, like its plain vanilla mob - never like a vanilla sound pretending."""
    files, events, lang = {}, {}, {}
    enc = encoder()
    if enc is None:
        return files, events, lang, None
    name, argv = enc
    for vid, voice in VOICES.items():
        for i, kind in enumerate(KINDS):
            data = encode(voice[kind](), argv)
            if data is None:
                continue
            files[f"assets/{ns}/sounds/voice/{vid}/{kind}.ogg"] = data
            key = f"voice.{vid}.{kind}"
            events[key] = {
                "sounds": [{"name": f"{ns}:voice/{vid}/{kind}",
                            "volume": voice.get("volume", 0.9),
                            "attenuation_distance": 20}],
                "subtitle": f"subtitles.{ns}.{key}",
            }
            lang[f"subtitles.{ns}.{key}"] = f"{voice['subtitle']} {voice['verbs'][i]}"
    return files, events, lang, name


def audition(path):
    """Every line end to end as one playable file - the only way to judge 57 sounds at once."""
    gap = [0.0] * n(0.35)
    whole = []
    for vid, voice in VOICES.items():
        for kind in KINDS:
            whole.extend(voice[kind]())
            whole.extend(gap)
        whole.extend(gap)
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wav = path.with_suffix(".wav")
    wav.write_bytes(wav_bytes(whole))
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and path.suffix != ".wav":
        result = subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", str(wav),
                                 "-c:a", "libmp3lame", "-q:a", "4", str(path)], capture_output=True)
        if result.returncode == 0:
            wav.unlink()
            return path
    return wav


if __name__ == "__main__":
    print("encoder:", (encoder() or ("none - the pack would ship without voices", None))[0])
    out = audition(pathlib.Path(__file__).parent / "dist" / "voices-audition.mp3")
    print("wrote", out)
