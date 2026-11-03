"""Genera las ilustraciones de portada de las noticias sin imagen.

Una escena por deporte y momento del día (mañana, atardecer y noche), en
static/img/portadas/<deporte>-<momento>.svg. Se ejecuta a mano si se cambian:

    python scripts/generar_portadas.py
"""

import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "portadas"
W, H, HORIZON = 640, 360, 226

PALETTES = {
    "manana": {
        "sky": ("#6fc3e6", "#bfe8f5", "#fdf1dc"),
        "sun": "#ffd166",
        "glow": "#fff3c4",
        "sun_xy": (482, 88),
        "sun_r": 30,
        "far": "#9cc8d0",
        "near": "#5f9fa3",
        "water": ("#3aa5a1", "#23817e", "#15605e"),
        "ink": "#0c2035",
        "foam": "#effcff",
        "stars": False,
        "clouds": "#ffffff",
        "birds": True,
    },
    "atardecer": {
        "sky": ("#3a1f4b", "#c2455a", "#f6a35b"),
        "sun": "#ffd27f",
        "glow": "#ffb26b",
        "sun_xy": (318, 206),
        "sun_r": 38,
        "far": "#8b3f60",
        "near": "#5a2a4e",
        "water": ("#7d3e63", "#55305b", "#302245"),
        "ink": "#1a0d21",
        "foam": "#ffd7a6",
        "stars": False,
        "clouds": "#f7b08a",
        "birds": True,
    },
    "noche": {
        "sky": ("#071729", "#102e4b", "#1e4868"),
        "sun": "#f5f0d6",
        "glow": "#9fb9d8",
        "sun_xy": (500, 78),
        "sun_r": 24,
        "far": "#1c3953",
        "near": "#122a40",
        "water": ("#1c5374", "#13405c", "#0b2d43"),
        "ink": "#030d18",
        "foam": "#a6deea",
        "stars": True,
        "clouds": None,
        "birds": False,
    },
}

ACCENTS = {
    "dragon-boat": ("#c8102e", "#e8a33d", "#8c0b21"),
    "traineras": ("#0b5394", "#ffd166", "#073a68"),
    "piraguismo": ("#e07b0b", "#fff3d6", "#a95b06"),
    "remo-olimpico": ("#f4f1ea", "#2e7d32", "#c9c3b5"),
    "vaa": ("#00838f", "#ffe08a", "#005d66"),
}


def wave(y, amp, length, color, opacity=1, phase=0):
    d = f"M-40 {y}"
    x = -40 + phase
    while x < W + 40:
        d += f" q{length / 4:.1f} {-amp} {length / 2:.1f} 0 t{length / 2:.1f} 0"
        x += length
    return f'<path d="{d} V{H} H-40 Z" fill="{color}" opacity="{opacity}"/>'


def foam_lines(y, color, rng, count=7):
    lines = []
    for _ in range(count):
        x = rng.randint(10, W - 60)
        yy = y + rng.randint(0, 50)
        lines.append(
            f'<path d="M{x} {yy} q8 -4 16 0 t16 0" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" opacity=".45"/>'
        )
    return "".join(lines)


def sky(p, rng):
    top, mid, bottom = p["sky"]
    parts = [
        '<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{top}"/><stop offset=".6" stop-color="{mid}"/>'
        f'<stop offset="1" stop-color="{bottom}"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" fill="url(#s)"/>',
    ]
    if p["stars"]:
        for _ in range(34):
            x, y, r = rng.randint(4, W - 4), rng.randint(4, 170), rng.choice((0.8, 1, 1.2, 1.6))
            parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" opacity="{rng.choice((0.5, 0.7, 0.9))}"/>')
    sx, sy = p["sun_xy"]
    r = p["sun_r"]
    parts.append(f'<circle cx="{sx}" cy="{sy}" r="{r * 2.6:.0f}" fill="{p["glow"]}" opacity=".22"/>')
    parts.append(f'<circle cx="{sx}" cy="{sy}" r="{r * 1.6:.0f}" fill="{p["glow"]}" opacity=".3"/>')
    parts.append(f'<circle cx="{sx}" cy="{sy}" r="{r}" fill="{p["sun"]}"/>')
    if p["stars"]:  # Cráteres de la luna
        parts.append(f'<circle cx="{sx - 7}" cy="{sy - 5}" r="5" fill="#000" opacity=".07"/>')
        parts.append(f'<circle cx="{sx + 8}" cy="{sy + 7}" r="3.5" fill="#000" opacity=".07"/>')
    if p["clouds"]:
        for cx, cy, s in ((120, 70, 1.0), (560, 150, 0.7), (300, 40, 0.55)):
            parts.append(
                f'<g fill="{p["clouds"]}" opacity=".75" transform="translate({cx} {cy}) scale({s})">'
                '<ellipse cx="0" cy="0" rx="46" ry="13"/><ellipse cx="-16" cy="-9" rx="20" ry="14"/>'
                '<ellipse cx="12" cy="-12" rx="24" ry="17"/></g>'
            )
    if p["birds"]:
        for bx, by, s in ((200, 92, 1), (226, 104, 0.8), (250, 86, 0.7)):
            parts.append(
                f'<path d="M{bx} {by} q{6 * s:.1f} {-6 * s:.1f} {12 * s:.1f} 0 q{6 * s:.1f} {-6 * s:.1f} {12 * s:.1f} 0" '
                f'fill="none" stroke="{p["ink"]}" stroke-width="2" stroke-linecap="round" opacity=".55"/>'
            )
    return "".join(parts)


# ---------- Paisajes ----------


def land_dragon(p):
    far = (
        f'<path d="M-10 {HORIZON} L-10 170 Q30 120 70 160 Q110 96 160 150 Q200 128 236 166 L250 {HORIZON} Z" fill="{p["far"]}"/>'
        f'<path d="M380 {HORIZON} Q420 150 470 176 Q520 110 580 162 Q620 140 660 170 L660 {HORIZON} Z" fill="{p["far"]}"/>'
    )
    # Colina con pagoda
    near = f'<path d="M-10 {HORIZON} L-10 196 Q60 168 140 200 Q170 212 190 {HORIZON} Z" fill="{p["near"]}"/>'
    pagoda = f'<g fill="{p["near"]}" transform="translate(70 120)">'
    for i, (w, h) in enumerate(((44, 14), (36, 12), (28, 11), (20, 10))):
        y = 62 - i * 17
        pagoda += (
            f'<rect x="{-w / 2 + 6}" y="{y - h + 4}" width="{w - 12}" height="{h}" />'
            f'<path d="M{-w / 2 - 6} {y - h + 5} Q0 {y - h - 6} {w / 2 + 6} {y - h + 5} L{w / 2 - 4} {y - h + 9} L{-w / 2 + 4} {y - h + 9} Z"/>'
        )
    pagoda += '<rect x="-1.5" y="-14" width="3" height="12"/></g>'
    return far + pagoda + near


def land_traineras(p):
    far = f'<path d="M180 {HORIZON} Q260 186 330 196 Q400 176 470 194 Q540 180 660 198 L660 {HORIZON} Z" fill="{p["far"]}"/>'
    cliff = f'<path d="M-10 {HORIZON} L-10 150 L40 146 Q80 150 96 176 Q112 200 150 {HORIZON} Z" fill="{p["near"]}"/>'
    light = p["sun"] if p["stars"] else "#ffffff"
    lighthouse = (
        f'<g transform="translate(46 98)"><path d="M-8 50 L-5 6 L5 6 L8 50 Z" fill="{light}"/>'
        f'<rect x="-5" y="18" width="10" height="7" fill="{p["near"]}"/><rect x="-5" y="34" width="10" height="7" fill="{p["near"]}"/>'
        f'<rect x="-7" y="0" width="14" height="7" fill="{p["near"]}"/><path d="M-5 0 L0 -7 L5 0 Z" fill="{p["near"]}"/>'
    )
    if p["stars"]:
        lighthouse += f'<path d="M4 3 L90 -16 L90 20 Z" fill="{p["sun"]}" opacity=".18"/>'
    lighthouse += "</g>"
    town = f'<g fill="{p["near"]}">'
    x = 470
    for w, h in ((22, 26), (18, 34), (26, 22), (20, 30), (24, 38), (18, 24), (26, 30), (22, 20)):
        y = HORIZON - h
        town += f'<rect x="{x}" y="{y}" width="{w}" height="{h + 2}"/><path d="M{x - 2} {y + 1} L{x + w / 2} {y - 9} L{x + w + 2} {y + 1} Z"/>'
        x += w
    town += f'<rect x="{470 + 44}" y="{HORIZON - 64}" width="10" height="30"/><path d="M{470 + 42} {HORIZON - 63} L{470 + 49} {HORIZON - 78} L{470 + 56} {HORIZON - 63} Z"/></g>'
    return far + cliff + lighthouse + town


def pine(x, base, h, color):
    return (
        f'<path d="M{x} {base - h} L{x + h * 0.28:.1f} {base - h * 0.45:.1f} L{x + h * 0.16:.1f} {base - h * 0.45:.1f} '
        f"L{x + h * 0.34:.1f} {base} L{x - h * 0.34:.1f} {base} L{x - h * 0.16:.1f} {base - h * 0.45:.1f} "
        f'L{x - h * 0.28:.1f} {base - h * 0.45:.1f} Z" fill="{color}"/>'
    )


def land_piraguismo(p):
    far = f'<path d="M-10 {HORIZON} L-10 160 L60 110 L120 150 L190 92 L270 160 L340 118 L420 170 L500 104 L580 150 L660 120 L660 {HORIZON} Z" fill="{p["far"]}"/>'
    if not p["stars"]:
        far += '<path d="M190 92 L172 108 L182 106 L190 114 L198 104 L208 108 Z M500 104 L484 118 L494 116 L500 122 L508 114 L516 118 Z" fill="#fff" opacity=".7"/>'
    banks = f'<path d="M-10 {HORIZON} L-10 196 Q80 188 160 {HORIZON} Z M460 {HORIZON} Q560 186 660 194 L660 {HORIZON} Z" fill="{p["near"]}"/>'
    trees = "".join(
        pine(x, HORIZON + 2, h, p["near"])
        for x, h in ((14, 70), (44, 54), (78, 64), (112, 44), (512, 50), (552, 72), (590, 58), (626, 76))
    )
    return far + banks + trees


def land_remo(p):
    city = f'<g fill="{p["far"]}">'
    x = 330
    rng = random.Random(7)
    while x < 660:
        w, h = rng.randint(16, 30), rng.randint(26, 74)
        city += f'<rect x="{x}" y="{HORIZON - h}" width="{w}" height="{h}"/>'
        x += w + rng.randint(0, 4)
    city += "</g>"
    if p["stars"]:
        rng = random.Random(3)
        for _ in range(26):
            city += f'<rect x="{rng.randint(334, 650)}" y="{rng.randint(HORIZON - 60, HORIZON - 8)}" width="3" height="4" fill="{p["sun"]}" opacity=".8"/>'
    hills = f'<path d="M-10 {HORIZON} L-10 182 Q90 160 200 186 Q260 196 320 {HORIZON} Z" fill="{p["far"]}"/>'
    bridge = (
        f'<g fill="none" stroke="{p["near"]}" stroke-width="7"><path d="M-10 172 H660"/></g>'
        f'<g fill="{p["near"]}">'
        + "".join(
            f'<path d="M{x} 172 h12 v{HORIZON - 172} h-12 Z"/><path d="M{x + 12} 176 Q{x + 66} 214 {x + 120} 176" fill="none" stroke="{p["near"]}" stroke-width="5"/>'
            for x in range(-40, 660, 120)
        )
        + "</g>"
    )
    return hills + city + bridge


def palm(x, base, h, lean, color):
    tx, ty = x + lean, base - h
    trunk = (
        f'<path d="M{x - 4} {base} Q{x + lean * 0.2:.1f} {base - h * 0.6:.1f} {tx - 2} {ty} L{tx + 2} {ty} '
        f'Q{x + lean * 0.2 + 5:.1f} {base - h * 0.6:.1f} {x + 4} {base} Z" fill="{color}"/>'
    )
    fronds = ""
    for dx, dy in ((-36, 10), (-30, 24), (36, 12), (28, 26), (-8, -16), (12, -14)):
        mx, my = tx + dx * 0.5, ty + dy * 0.5 - 9
        fronds += (
            f'<path d="M{tx} {ty} Q{mx:.1f} {my - 5:.1f} {tx + dx} {ty + dy} '
            f'Q{mx:.1f} {my + 6:.1f} {tx} {ty} Z" fill="{color}"/>'
        )
    return trunk + fronds


def land_vaa(p):
    far = f'<path d="M300 {HORIZON} L380 160 Q400 150 420 160 L520 {HORIZON} Z" fill="{p["far"]}"/>'
    island = f'<path d="M420 {HORIZON} Q470 196 560 198 Q620 200 660 210 L660 {HORIZON} Z" fill="{p["near"]}"/>'
    palms = palm(520, 204, 70, -10, p["near"]) + palm(556, 206, 54, 12, p["near"]) + palm(600, 210, 62, -6, p["near"])
    islet = f'<path d="M-10 {HORIZON} L-10 206 Q50 196 110 {HORIZON} Z" fill="{p["near"]}"/>' + palm(
        36, 206, 48, 8, p["near"]
    )
    return far + island + palms + islet


LANDS = {
    "dragon-boat": land_dragon,
    "traineras": land_traineras,
    "piraguismo": land_piraguismo,
    "remo-olimpico": land_remo,
    "vaa": land_vaa,
}


# ---------- Embarcaciones ----------


def person_line(x1, y1, x2, y2, ink, width=9):
    return f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{ink}" stroke-width="{width}" stroke-linecap="round"/>'


def head(x, y, ink, r=6.2):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{ink}"/>'


def blade(x, y, ink, angle=-20, rx=3.2, ry=8):
    return f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{ink}" transform="rotate({angle} {x} {y})"/>'


def boat_dragon(p, accent):
    hull, trim, dark = accent
    ink = p["ink"]
    out = [
        # Cola
        f'<path d="M166 268 C146 260 136 244 140 226 C142 216 152 214 157 221 C150 232 154 250 176 264 Z" fill="{hull}"/>',
        f'<path d="M140 226 C142 216 152 214 157 221 C152 220 147 222 145 228 Z" fill="{trim}"/>',
        # Timonel de pie con el remo de gobierno
        person_line(178, 266, 178, 236, ink, 8),
        head(178, 227, ink, 6.5),
        f'<path d="M184 242 L128 304" stroke="{ink}" stroke-width="3.2" stroke-linecap="round"/>',
        blade(130, 300, ink, 42, 3.4, 9),
    ]
    for i in range(9):
        x = 206 + i * 28
        lean = 7 if i % 2 else 5
        out.append(person_line(x, 266, x + lean, 248, ink))
        out.append(head(x + lean + 3, 240, ink))
        tip = x - (10 if i % 2 else 2)
        out.append(f'<path d="M{x + 15} 243 L{tip} 296" stroke="{ink}" stroke-width="2.6" stroke-linecap="round"/>')
        out.append(blade(tip + 1, 292, ink, 18 if i % 2 else 12))
    # Tamborilero mirando a los palistas
    out += [
        person_line(468, 266, 466, 248, ink),
        head(465, 239, ink),
        f'<path d="M462 247 L448 232" stroke="{ink}" stroke-width="2.6" stroke-linecap="round"/>',
        f'<ellipse cx="452" cy="258" rx="9" ry="7" fill="{trim}" stroke="{dark}" stroke-width="2.5"/>',
    ]
    # Casco, escamas y cabeza de dragón
    out += [
        f'<path d="M156 266 L492 266 Q486 281 462 286 L180 286 Q160 281 156 266 Z" fill="{hull}"/>',
        f'<rect x="166" y="268" width="318" height="3.5" rx="1.7" fill="{trim}"/>',
        "".join(f'<circle cx="{x}" cy="278" r="3.6" fill="{dark}"/>' for x in range(184, 470, 13)),
        f'<path d="M478 268 C496 262 500 246 494 232 C490 222 498 213 509 215 L530 221 L523 227 L534 231 L521 236 C512 238 508 247 512 258 C514 266 506 272 488 272 Z" fill="{hull}"/>',
        f'<path d="M494 232 C488 240 490 252 498 262 L492 263 C484 254 483 242 488 232 Z" fill="{trim}"/>',
        f'<path d="M505 214 L498 200 L512 210 Z" fill="{trim}"/>',
        f'<circle cx="512" cy="221" r="2.4" fill="{trim}"/>',
    ]
    return "".join(out)


def boat_traineras(p, accent):
    hull, trim, dark = accent
    ink = p["ink"]
    out = [
        person_line(146, 266, 146, 236, ink, 8),
        head(146, 227, ink, 6.5),
        f'<ellipse cx="146" cy="221.5" rx="8.5" ry="2.6" fill="{ink}"/>',  # txapela
        f'<path d="M150 244 L170 254" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>',
    ]
    for i in range(11):
        x = 178 + i * 29
        far_side = i % 2 == 1
        opacity = ' opacity=".65"' if far_side else ""
        out.append(f"<g{opacity}>")
        out.append(person_line(x, 266, x + 5, 249, ink))
        out.append(head(x + 7, 241, ink))
        out.append(f'<path d="M{x - 6} 252 L{x - 38} 302" stroke="{ink}" stroke-width="2.8" stroke-linecap="round"/>')
        out.append(blade(x - 37, 299, ink, 32, 3.4, 9))
        out.append("</g>")
    out += [
        f'<path d="M126 268 L506 265 Q528 262 542 248 Q540 270 520 280 L154 285 Q130 282 126 268 Z" fill="{hull}"/>',
        f'<path d="M132 270 L510 267 Q526 264 536 256" fill="none" stroke="{trim}" stroke-width="3.2"/>',
        f'<path d="M156 279 L500 276" stroke="{dark}" stroke-width="2" opacity=".6"/>',
    ]
    return "".join(out)


def kayak(p, accent, cx, wy, scale=1.0):
    hull, trim, dark = accent
    ink = p["ink"]
    return (
        f'<g transform="translate({cx} {wy}) scale({scale})">'
        f'<path d="M-30 -60 L32 4" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>'
        + blade(-30, -60, ink, 40, 4, 11)
        + blade(32, 4, ink, 40, 4, 11)
        + person_line(-2, -6, 4, -32, ink, 10)
        + f'<path d="M3 -28 L-18 -42 M5 -26 L16 -12" stroke="{ink}" stroke-width="4" stroke-linecap="round"/>'
        + head(7, -41, ink, 7)
        + f'<path d="M-118 -2 Q-40 -14 0 -12 Q60 -12 122 -4 Q60 10 0 10 Q-60 10 -118 -2 Z" fill="{hull}"/>'
        f'<path d="M-104 -4 Q-40 -12 0 -10 Q60 -10 112 -5" fill="none" stroke="{trim}" stroke-width="2.6"/>'
        f'<ellipse cx="-2" cy="-10" rx="16" ry="3.4" fill="{dark}"/></g>'
    )


def boat_piraguismo(p, accent):
    return kayak(p, accent, 470, 262, 0.62) + kayak(p, accent, 290, 284, 1.0)


def boat_remo(p, accent):
    hull, trim, dark = accent
    ink = p["ink"]
    out = []
    for i in range(4):
        x = 230 + i * 70
        out.append(person_line(x, 268, x - 8, 250, ink))
        out.append(head(x - 11, 241, ink))
        out.append(f'<path d="M{x - 12} 254 L{x + 2} 266" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>')
        out.append(f'<path d="M{x - 14} 254 L{x - 52} 300" stroke="{ink}" stroke-width="2.4" stroke-linecap="round"/>')
        out.append(blade(x - 51, 297, trim, 38, 3.6, 9))
        out.append(f'<path d="M{x - 6} 268 L{x + 4} 260 L{x + 14} 268" fill="none" stroke="{dark}" stroke-width="2"/>')
    out.append(f'<path d="M136 270 L504 268 Q514 269 522 271 Q506 276 136 276 Q128 273 136 270 Z" fill="{hull}"/>')
    out.append(f'<path d="M150 272 L500 270.5" stroke="{trim}" stroke-width="1.6"/>')
    return "".join(out)


def boat_vaa(p, accent):
    hull, trim, dark = accent
    ink = p["ink"]
    out = [
        f'<path d="M262 256 Q330 250 404 256 Q330 262 262 256 Z" fill="{dark}" opacity=".85"/>',
        f'<path d="M252 268 Q256 252 276 255 M366 268 Q370 252 390 255" fill="none" stroke="{dark}" stroke-width="4" stroke-linecap="round"/>',
    ]
    for i in range(6):
        x = 196 + i * 50
        out.append(person_line(x, 266, x + 8, 247, ink))
        out.append(head(x + 11, 239, ink))
        out.append(f'<path d="M{x + 18} 236 L{x + 6} 296" stroke="{ink}" stroke-width="2.6" stroke-linecap="round"/>')
        out.append(f'<path d="M{x + 13} 236 H{x + 23}" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>')
        out.append(blade(x + 7, 292, ink, 12, 3.4, 9))
    out += [
        f'<path d="M154 268 L474 268 Q500 264 514 252 Q510 276 486 284 L174 285 Q154 280 154 268 Z" fill="{hull}"/>',
        f'<path d="M162 271 L480 271 Q500 268 508 260" fill="none" stroke="{trim}" stroke-width="3"/>',
    ]
    return "".join(out)


BOATS = {
    "dragon-boat": boat_dragon,
    "traineras": boat_traineras,
    "piraguismo": boat_piraguismo,
    "remo-olimpico": boat_remo,
    "vaa": boat_vaa,
}


def scene(sport, moment):
    p = PALETTES[moment]
    rng = random.Random(f"{sport}-{moment}")
    sx = p["sun_xy"][0]
    reflection = "".join(
        f'<rect x="{sx - w / 2:.0f}" y="{y}" width="{w}" height="2.4" rx="1.2" fill="{p["glow"]}" opacity=".35"/>'
        for y, w in ((232, 64), (239, 46), (246, 30))
    )
    water = (
        f'<rect y="{HORIZON}" width="{W}" height="{H - HORIZON}" fill="{p["water"][0]}"/>'
        + reflection
        + wave(252, 5, 90, p["water"][1], 0.9, 20)
    )
    front = wave(293, 7, 120, p["water"][2]) + foam_lines(300, p["foam"], rng) + wave(330, 6, 150, p["ink"], 0.25, 40)
    body = sky(p, rng) + LANDS[sport](p) + water + BOATS[sport](p, ACCENTS[sport]) + front
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">{body}</svg>\n'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for sport in BOATS:
        for moment in PALETTES:
            (OUT / f"{sport}-{moment}.svg").write_text(scene(sport, moment), encoding="utf-8")
    print(f"{len(BOATS) * len(PALETTES)} ilustraciones en {OUT}")


if __name__ == "__main__":
    main()
