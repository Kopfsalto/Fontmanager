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
font_meta.py — Metadaten-Analyse einzelner Fontdateien.

Liest mit fontTools direkt aus der Fontdatei:
  - Klassifikation (Serif, Sans Serif, Slab Serif, Script, Dekorativ,
    Symbol, Monospace, Barcode) aus OS/2.sFamilyClass, PANOSE,
    post.isFixedPitch und Namens-Heuristik
  - Schriftsysteme (Latein, Arabisch, Kyrillisch, CJK, …) aus den
    OS/2 ulUnicodeRange-Bits
  - Hersteller aus der name-Tabelle (ID 8 „Manufacturer“, Fallback
    ID 9 „Designer“) und der 4-Zeichen-Vendor-ID (achVendID)

Hinweis: Die Qualität hängt an den Metadaten der Fontdatei selbst.
Schlecht getaggte (Gratis-)Fonts landen in „Unbekannt“.

Ergebnisse werden in %LOCALAPPDATA%\\FontManager\\metacache.json
gecacht (Schlüssel: Hash aus Pfad+mtime+Größe, siehe font_core).
"""

from __future__ import annotations

import json
import os

UNKNOWN = "Unbekannt"

# ---------------------------------------------------- Vendor-ID → Hersteller

VENDOR_IDS = {
    "ADBE": "Adobe", "APPL": "Apple", "B&H": "Bigelow & Holmes",
    "BITS": "Bitstream", "CANO": "Canon", "DYNA": "DynaComware",
    "FJ": "Fujitsu", "GOOG": "Google", "H&P": "Hanson & Partner",
    "HP": "Hewlett-Packard", "IBM": "IBM", "ITC": "ITC",
    "ITF": "Indian Type Foundry", "LINO": "Linotype",
    "MACR": "Macromedia", "MONO": "Monotype", "MS": "Microsoft",
    "MSFT": "Microsoft", "MT": "Monotype", "NEC": "NEC",
    "PARA": "ParaType", "RICO": "Ricoh", "TIRO": "Tiro Typeworks",
    "TMT": "TypeMyType", "UA": "UnAuthorized Type", "URW": "URW",
    "Y&Y": "Y&Y",
}

# ------------------------------------------- ulUnicodeRange-Bit → Schriftsystem

_UNICODE_RANGE_BITS = {
    0: "Latein", 1: "Latein", 2: "Latein", 3: "Latein",
    7: "Griechisch", 9: "Kyrillisch", 10: "Armenisch",
    11: "Hebräisch", 13: "Arabisch", 15: "Devanagari",
    16: "Bengalisch", 17: "Gurmukhi", 18: "Gujarati", 19: "Oriya",
    20: "Tamil", 21: "Telugu", 22: "Kannada", 23: "Malayalam",
    24: "Thai", 25: "Lao", 26: "Georgisch",
    28: "Koreanisch (Hangul)", 38: "Symbole", 45: "Symbole",
    46: "Symbole", 47: "Symbole",
    49: "Japanisch (Kana)", 50: "Japanisch (Kana)",
    51: "Chinesisch/CJK", 52: "Koreanisch (Hangul)",
    56: "Koreanisch (Hangul)", 59: "Chinesisch/CJK",
    70: "Tibetisch", 71: "Syrisch", 74: "Singhalesisch",
    75: "Birmanisch", 76: "Äthiopisch", 78: "Khmer", 80: "Braille",
}

_BARCODE_TOKENS = ("barcode", "barcod", "code39", "code 39", "code128",
                   "code 128", "ean13", "ean-13", "ean8", "ean 13",
                   "upc", "interleaved", "datamatrix", "qrcode", "qr code",
                   "postnet", "codabar", "39smart", "3 of 9", "3of9")

_FAMILY_CLASS = {
    1: "Serif", 2: "Serif", 3: "Serif", 4: "Serif",
    5: "Slab Serif", 7: "Serif",
    8: "Sans Serif", 9: "Dekorativ", 10: "Script", 12: "Symbol",
}


def _scripts_from_ranges(os2) -> list[str]:
    found: list[str] = []
    ranges = [getattr(os2, f"ulUnicodeRange{i}", 0) or 0 for i in (1, 2, 3, 4)]
    for bit, label in _UNICODE_RANGE_BITS.items():
        word, pos = divmod(bit, 32)
        if ranges[word] & (1 << pos) and label not in found:
            found.append(label)
    return found


def _classify(os2, post, name_blob: str) -> str:
    if any(tok in name_blob for tok in _BARCODE_TOKENS):
        return "Barcode"

    panose = getattr(os2, "panose", None) if os2 is not None else None
    p = [getattr(panose, a, 0) for a in
         ("bFamilyType", "bSerifStyle", "bWeight", "bProportion")] \
        if panose is not None else [0, 0, 0, 0]

    if (post is not None and getattr(post, "isFixedPitch", 0)) or p[3] == 9:
        return "Monospace"

    fam = (getattr(os2, "sFamilyClass", 0) or 0) >> 8 if os2 is not None else 0
    if fam in _FAMILY_CLASS:
        return _FAMILY_CLASS[fam]

    if p[0] == 2:                       # Text & Display
        return "Sans Serif" if 11 <= p[1] <= 15 else "Serif"
    if p[0] == 3:
        return "Script"
    if p[0] == 4:
        return "Dekorativ"
    if p[0] == 5:
        return "Symbol"

    for token, label in (("sans", "Sans Serif"), ("script", "Script"),
                         ("hand", "Script"), ("serif", "Serif"),
                         ("symbol", "Symbol"), ("dingbat", "Symbol"),
                         ("icon", "Symbol"), ("mono", "Monospace")):
        if token in name_blob:
            return label
    return UNKNOWN


def _foundry(font, os2) -> str:
    try:
        name = font["name"]
        manufacturer = name.getDebugName(8)
        if manufacturer and manufacturer.strip():
            return manufacturer.strip()[:60]
    except Exception:
        name = None
    vend = (getattr(os2, "achVendID", "") or "").strip() if os2 is not None \
        else ""
    if vend and vend.upper() in VENDOR_IDS:
        return VENDOR_IDS[vend.upper()]
    try:
        designer = name.getDebugName(9) if name is not None else None
        if designer and designer.strip():
            return designer.strip()[:60]
    except Exception:
        pass
    if vend:
        return f"Vendor-ID: {vend}"
    return UNKNOWN


def analyze_font(path: str, display_name: str = "") -> dict:
    """Liefert {"c": Klassifikation, "s": [Schriftsysteme],
    "f": Hersteller, "b": defekt?}. Wirft nie."""
    ext = os.path.splitext(path)[1].lower()
    result = {"c": UNKNOWN, "s": [], "f": UNKNOWN, "b": False}
    name_blob = f"{display_name} {os.path.basename(path)}".lower()
    try:
        from fontTools.ttLib import TTFont
        kwargs = {"lazy": True, "fontNumber": 0} if ext in (".ttc", ".otc") \
            else {"lazy": True}
        with TTFont(path, **kwargs) as font:
            os2 = font["OS/2"] if "OS/2" in font else None
            post = font["post"] if "post" in font else None
            result["c"] = _classify(os2, post, name_blob)
            result["s"] = _scripts_from_ranges(os2) if os2 is not None else []
            result["f"] = _foundry(font, os2)
    except Exception:
        # .fon/.fnt kann fontTools nicht lesen — das ist normal, kein Defekt
        result["b"] = ext not in (".fon", ".fnt")
        result["c"] = _classify(None, None, name_blob)
    return result


def registry_font_name(path: str) -> str:
    """Voller Anzeigename für den Registry-Wert bei der Installation,
    z. B. "Foo Sans Bold" bzw. bei .ttc "Foo & Foo UI". Leerer String
    bei Fehler (Aufrufer nutzt dann den Dateinamen)."""
    try:
        from fontTools.ttLib import TTFont, TTCollection

        def full_name(font) -> str:
            n = font["name"]
            v = n.getDebugName(4)
            if not v:
                fam = n.getDebugName(1) or ""
                sub = n.getDebugName(2) or ""
                v = f"{fam} {sub}".strip()
                if v.lower().endswith(" regular"):
                    v = v[:-8].strip()
            return (v or "").strip()

        ext = os.path.splitext(path)[1].lower()
        names: list[str] = []
        if ext in (".ttc", ".otc"):
            coll = TTCollection(path, lazy=True)
            try:
                names = [full_name(f) for f in coll.fonts]
            finally:
                coll.close()
        else:
            with TTFont(path, lazy=True) as f:
                names = [full_name(f)]
        names = list(dict.fromkeys(n for n in names if n))
        return " & ".join(names)
    except Exception:
        return ""


# ---------------------------------------------------------------- Cache

def load_meta_cache(cache_path: str) -> dict:
    try:
        with open(cache_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_meta_cache(cache_path: str, cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
        os.replace(tmp, cache_path)
    except OSError:
        pass
