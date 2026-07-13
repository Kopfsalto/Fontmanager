# -*- coding: utf-8 -*-
#
# FontManager — Schriftverwaltung für Windows 11
# Copyright (C) 2026 Kopfsalto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
"""
gen_icon.py — erzeugt FontManager.ico (Multi-Resolution) + Vorschau-PNG.

Design: abgerundetes Quadrat mit Crimson-Verlauf, großes weißes „Aa“
mit dezentem Schatten, unten drei kleine „Kachel“-Punkte als Anspielung
auf die Grid-Ansicht des Tools. Bleibt auch bei 16 px lesbar.

Aufruf:  python gen_icon.py
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 1024
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48),
             (64, 64), (128, 128), (256, 256)]

CRIMSON_TOP = (225, 45, 90)      # heller Verlauf oben
CRIMSON_MID = (197, 7, 61)       # #C5073D
CRIMSON_BOT = (122, 6, 40)       # dunkler Verlauf unten


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold
        else r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def _rounded_gradient(size: int, radius: int) -> Image.Image:
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        if t < 0.5:
            f = t / 0.5
            c = tuple(int(a + (b - a) * f)
                      for a, b in zip(CRIMSON_TOP, CRIMSON_MID))
        else:
            f = (t - 0.5) / 0.5
            c = tuple(int(a + (b - a) * f)
                      for a, b in zip(CRIMSON_MID, CRIMSON_BOT))
        grad.putpixel((0, y), c)
    grad = grad.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)

    # leichter Glanz oben
    gloss = Image.new("L", (size, size), 0)
    ImageDraw.Draw(gloss).ellipse(
        (-size * 0.25, -size * 0.55, size * 1.25, size * 0.45), fill=46)
    gloss = Image.composite(gloss, Image.new("L", (size, size), 0), mask)
    white = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    out = Image.composite(white, out, gloss.point(lambda v: v))
    out.putalpha(mask)
    return out


def build_icon() -> Image.Image:
    img = _rounded_gradient(SIZE, radius=SIZE // 5)
    draw = ImageDraw.Draw(img)

    # „Aa“ mit Schatten
    f_big = _font(int(SIZE * 0.60))
    f_small = _font(int(SIZE * 0.42))
    text_y = int(SIZE * 0.42)
    a_x = int(SIZE * 0.16)

    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    off = SIZE // 64
    sd.text((a_x + off, text_y + off), "A", font=f_big,
            fill=(0, 0, 0, 110), anchor="lm")
    bbox = sd.textbbox((a_x, text_y), "A", font=f_big, anchor="lm")
    a2_x = bbox[2] + int(SIZE * 0.02)
    sd.text((a2_x + off, text_y + int(SIZE * 0.075) + off), "a",
            font=f_small, fill=(0, 0, 0, 110), anchor="lm")
    shadow = shadow.filter(ImageFilter.GaussianBlur(SIZE // 90))
    img.alpha_composite(shadow)

    draw.text((a_x, text_y), "A", font=f_big,
              fill=(255, 255, 255, 255), anchor="lm")
    draw.text((a2_x, text_y + int(SIZE * 0.075)), "a", font=f_small,
              fill=(255, 250, 245, 255), anchor="lm")

    # drei Kachel-Punkte unten (Grid-Motiv), Mitte „fehlt“ = gelöscht
    dot_r = SIZE // 26
    dot_y = int(SIZE * 0.80)
    for i, x_f in enumerate((0.30, 0.50, 0.70)):
        cx = int(SIZE * x_f)
        if i == 1:
            draw.ellipse((cx - dot_r, dot_y - dot_r, cx + dot_r,
                          dot_y + dot_r),
                         outline=(255, 255, 255, 200), width=SIZE // 110)
        else:
            draw.ellipse((cx - dot_r, dot_y - dot_r, cx + dot_r,
                          dot_y + dot_r), fill=(255, 255, 255, 230))
    return img


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    img = build_icon()
    img.save(os.path.join(here, "FontManager_Logo.png"))
    # Für kleine Größen mit LANCZOS herunterskalieren (schärfer als
    # die ICO-interne Skalierung)
    frames = [img.resize(s, Image.LANCZOS) for s in ICO_SIZES]
    frames[-1].save(os.path.join(here, "FontManager.ico"),
                    format="ICO", sizes=ICO_SIZES,
                    append_images=frames[:-1])
    print("FontManager.ico und FontManager_Logo.png erzeugt.")


if __name__ == "__main__":
    main()
