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
font_download.py — Fonts aus kostenlosen, öffentlichen Quellen laden.

Provider (alle ohne API-Key, ausschließlich frei lizenzierte Fonts):

  Google Fonts   — via google-webfonts-helper (gwfh.mranftl.com),
                   ~1800 Familien, OFL/Apache
  Fontsource     — api.fontsource.org (freie Read-only-API),
                   2000+ Open-Source-Fonts (Google + weitere)
  Fontshare      — api.fontshare.com (Indian Type Foundry),
                   ~100 professionelle Fonts, frei für privat & kommerziell
  Font Squirrel  — fontsquirrel.com/api, handverlesen, kommerziell frei

Bewusst NICHT enthalten: Quellen ohne API bzw. mit gemischten
„free for personal use“-Lizenzen (DaFont u. ä.) sowie Anbieter ohne
öffentliche Download-API (z. B. Adobe Fonts — deren Desktop-Fonts werden
lizenzbedingt ausschließlich über die Creative-Cloud-App synchronisiert).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile

GWFH_BASE = "https://gwfh.mranftl.com/api/fonts"
FSOURCE_LIST = "https://api.fontsource.org/v1/fonts"
FSOURCE_META = "https://api.fontsource.org/v1/fonts/{}"
FSOURCE_DL = "https://api.fontsource.org/v1/download/{}"
FSHARE_LIST = "https://api.fontshare.com/v2/fonts?offset={}&limit=100"
FSHARE_DL = "https://api.fontshare.com/v2/fonts/download/{}"
FSQ_LIST = "https://www.fontsquirrel.com/api/fontlist/all"
FSQ_KIT = "https://www.fontsquirrel.com/fontfacekit/{}"

PROVIDERS = ("Google Fonts", "Fontsource", "Fontshare", "Font Squirrel")
FONT_EXTS = (".ttf", ".otf", ".ttc", ".otc")

# Browser-ähnlicher User-Agent: einige Quellen (u. a. Font Squirrel)
# liefern sonst eine HTML-Blockseite statt JSON → "Expecting value"-Fehler.
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36 FontManager/2.1"),
    "Accept": "application/json, */*;q=0.8",
    "Accept-Language": "de,en;q=0.8",
}
_list_cache: dict[str, list[dict]] = {}


class DownloadError(RuntimeError):
    pass


def _http_get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        raise DownloadError(f"Netzwerkfehler: {exc}") from exc


def _get_json(url: str, timeout: int = 40):
    raw = _http_get(url, timeout)
    text = raw.decode("utf-8-sig", errors="replace").strip()
    if not text or text[0] in "<\ufeff<":
        raise DownloadError(
            "Die Quelle hat kein JSON geliefert (vermutlich Blockseite "
            "oder vorübergehend nicht erreichbar) — bitte später erneut "
            "versuchen.")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise DownloadError(
            "Antwort der Quelle konnte nicht gelesen werden "
            f"({exc}).") from exc


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", text.lower()).strip("-") or "font"


# ---------------------------------------------------------------- Listen

def list_fonts(provider: str) -> list[dict]:
    """[{name, id, category, provider}] — pro Sitzung gecacht."""
    if provider in _list_cache:
        return _list_cache[provider]

    items: list[dict] = []
    if provider == "Google Fonts":
        for f in _get_json(GWFH_BASE):
            items.append({"name": f.get("family", "?"),
                          "id": f.get("id", ""),
                          "category": f.get("category", ""),
                          "provider": provider})
    elif provider == "Fontsource":
        for f in _get_json(FSOURCE_LIST):
            items.append({"name": f.get("family", "?"),
                          "id": f.get("id", ""),
                          "category": f.get("category", ""),
                          "provider": provider})
    elif provider == "Fontshare":
        offset = 0
        while True:
            data = _get_json(FSHARE_LIST.format(offset))
            fonts = data.get("fonts", data if isinstance(data, list) else [])
            for f in fonts:
                items.append({"name": f.get("name", "?"),
                              "id": f.get("slug", ""),
                              "category": (f.get("category") or {}).get(
                                  "name", "") if isinstance(
                                  f.get("category"), dict)
                              else str(f.get("category") or ""),
                              "provider": provider})
            if len(fonts) < 100 or offset > 2000:
                break
            offset += 100
    elif provider == "Font Squirrel":
        for f in _get_json(FSQ_LIST):
            items.append({"name": f.get("family_name", "?"),
                          "id": f.get("family_urlname", ""),
                          "category": f.get("classification", ""),
                          "provider": provider})
    else:
        raise DownloadError(f"Unbekannter Provider: {provider}")

    items = [i for i in items if i["id"]]
    _list_cache[provider] = items
    return items


# ---------------------------------------------------------------- Download

def _extract_fonts_from_zip(raw: bytes, dest: str) -> list[str]:
    files: list[str] = []
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tf:
        tf.write(raw)
        tmp_zip = tf.name
    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            for info in zf.infolist():
                base = os.path.basename(info.filename)
                if not base or os.path.splitext(base)[1].lower() \
                        not in FONT_EXTS:
                    continue
                target = os.path.join(dest, base)
                with zf.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                files.append(target)
    except zipfile.BadZipFile as exc:
        raise DownloadError("Antwort war kein gültiges ZIP.") from exc
    finally:
        try:
            os.remove(tmp_zip)
        except OSError:
            pass
    return files


def _ttf_urls_from_json_blob(url: str) -> list[str]:
    """Fallback: alle .ttf/.otf-URLs aus einer JSON-Antwort fischen."""
    raw = _http_get(url).decode("utf-8-sig", errors="replace")
    return re.findall(r"https?://[^\"'\s]+?\.(?:ttf|otf)", raw)


def download_family(item: dict, dest_root: str) -> list[str]:
    """Lädt eine Fontfamilie nach dest_root/<provider>/<familie>/."""
    provider, fid = item["provider"], item["id"]
    dest = os.path.join(dest_root, _slug(provider), _slug(item["name"]))
    os.makedirs(dest, exist_ok=True)

    if provider == "Google Fonts":
        url = f"{GWFH_BASE}/{urllib.parse.quote(fid)}?download=zip&formats=ttf"
        return _extract_fonts_from_zip(_http_get(url, 120), dest)

    if provider == "Fontsource":
        try:
            return _extract_fonts_from_zip(
                _http_get(FSOURCE_DL.format(urllib.parse.quote(fid)), 120),
                dest)
        except DownloadError:
            files = []
            for u in _ttf_urls_from_json_blob(
                    FSOURCE_META.format(urllib.parse.quote(fid)))[:12]:
                target = os.path.join(dest, os.path.basename(
                    urllib.parse.urlparse(u).path))
                with open(target, "wb") as out:
                    out.write(_http_get(u, 60))
                files.append(target)
            if not files:
                raise
            return files

    if provider == "Fontshare":
        url = FSHARE_DL.format(urllib.parse.quote(fid))
        return _extract_fonts_from_zip(_http_get(url, 120), dest)

    if provider == "Font Squirrel":
        url = FSQ_KIT.format(urllib.parse.quote(fid))
        return _extract_fonts_from_zip(_http_get(url, 120), dest)

    raise DownloadError(f"Unbekannter Provider: {provider}")


# ---------------------------------------------------------------- Vorschau

def preview_font(item: dict, cache_dir: str) -> str | None:
    """Lädt EINE kleine Fontdatei der Familie für die Live-Vorschau im
    Download-Dialog (gecacht). None, wenn die Quelle keine günstige
    Einzeldatei anbietet — dann rendert der Dialog einen Platzhalter."""
    provider, fid = item["provider"], item["id"]
    os.makedirs(cache_dir, exist_ok=True)
    cached = os.path.join(cache_dir,
                          f"{_slug(provider)}-{_slug(fid)}.ttf")
    if os.path.isfile(cached) and os.path.getsize(cached) > 0:
        return cached

    urls: list[str] = []
    try:
        if provider == "Google Fonts":
            urls = _ttf_urls_from_json_blob(
                f"{GWFH_BASE}/{urllib.parse.quote(fid)}")
        elif provider == "Fontsource":
            urls = _ttf_urls_from_json_blob(
                FSOURCE_META.format(urllib.parse.quote(fid)))
        else:
            return None   # Fontshare/Squirrel: nur ZIP-Downloads
        if not urls:
            return None
        # "regular/400" bevorzugen, sonst erste URL
        urls.sort(key=lambda u: (("regular" not in u and "400" not in u),
                                 len(u)))
        data = _http_get(urls[0], 40)
        with open(cached, "wb") as out:
            out.write(data)
        return cached
    except DownloadError:
        return None
