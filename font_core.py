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
font_core.py — Kernlogik des Font-Managers (ohne GUI).

Enthält:
  - Win32-Anbindung via ctypes (RemoveFontResourceW, AddFontResourceW,
    WM_FONTCHANGE-Broadcast, Datei-Besitzer-Ermittlung, MoveFileEx)
  - Registry-Enumeration (HKLM + HKCU ...\\Fonts)
  - Dreistufige Schutzprüfung (Whitelist, .fon, TrustedInstaller in
    C:\\Windows\\Fonts) — wird UNMITTELBAR vor jedem Löschvorgang
    erneut ausgeführt (Defense in Depth, nie nur UI-Filterung)
  - 30-Tage-Papierkorb mit JSON-Manifest und Wiederherstellung
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

if sys.platform == "win32":
    import winreg

from win11_default_fonts import WIN11_DEFAULT_FONT_FILES

# ---------------------------------------------------------------- Konstanten

FONTS_REG_PATH = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
FONTS_REG_PATH_WOW = r"SOFTWARE\Wow6432Node\Microsoft\Windows NT\CurrentVersion\Fonts"
SYSTEM_FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
USER_FONT_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"
)

APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FontManager")
TRASH_DIR = os.path.join(APP_DATA_DIR, "Papierkorb")
THUMB_CACHE_DIR = os.path.join(APP_DATA_DIR, "ThumbCache")
MANIFEST_PATH = os.path.join(TRASH_DIR, "manifest.json")
DEACTIVATED_PATH = os.path.join(APP_DATA_DIR, "deaktiviert.json")
META_CACHE_PATH = os.path.join(APP_DATA_DIR, "metacache.json")
TAGS_PATH = os.path.join(APP_DATA_DIR, "tags.json")
SETTINGS_PATH = os.path.join(APP_DATA_DIR, "settings.json")
REG_BACKUP_DIR = os.path.join(APP_DATA_DIR, "RegistryBackup")
DOWNLOAD_DIR = os.path.join(APP_DATA_DIR, "Downloads")
TRASH_RETENTION_DAYS = 30

TRUSTED_INSTALLER_SID = (
    "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
)

WM_FONTCHANGE = 0x001D
HWND_BROADCAST = 0xFFFF
SMTO_ABORTIFHUNG = 0x0002
MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
MOVEFILE_REPLACE_EXISTING = 0x1

FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".fon", ".fnt", ".otc"}


# ---------------------------------------------------------------- Win32 API

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Startet den aktuellen Prozess mit UAC-Prompt neu. True bei Erfolg."""
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, params
    else:
        exe, args = sys.executable, f'"{os.path.abspath(sys.argv[0])}" {params}'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
    return rc > 32


def remove_font_resource(path: str) -> None:
    """Hängt eine Schrift aus der GDI-Fonttabelle aus.

    RemoveFontResourceW dekrementiert einen Referenzzähler; deshalb in
    Schleife aufrufen, bis 0 zurückkommt (max. 10 Durchläufe als Kappe).
    """
    gdi32 = ctypes.windll.gdi32
    for _ in range(10):
        if not gdi32.RemoveFontResourceW(path):
            break


def add_font_resource(path: str) -> None:
    ctypes.windll.gdi32.AddFontResourceW(path)


def broadcast_font_change() -> None:
    """Informiert alle Fenster über die geänderte Fonttabelle.

    SendMessageTimeout statt SendMessage, damit ein hängendes Fenster
    das Tool nicht blockiert.
    """
    res = wt.DWORD(0)
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_FONTCHANGE, 0, 0,
        SMTO_ABORTIFHUNG, 1000, ctypes.byref(res),
    )


def schedule_move_on_reboot(src: str, dst: str | None) -> bool:
    """Verschiebt (oder löscht bei dst=None) eine gesperrte Datei beim
    nächsten Neustart. Benötigt Adminrechte."""
    return bool(
        ctypes.windll.kernel32.MoveFileExW(src, dst, MOVEFILE_DELAY_UNTIL_REBOOT)
    )


def get_file_owner_sid(path: str) -> str | None:
    """Liefert die Besitzer-SID einer Datei als String (oder None)."""
    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32

    SE_FILE_OBJECT = 1
    OWNER_SECURITY_INFORMATION = 0x00000001

    p_sid = ctypes.c_void_p()
    p_sd = ctypes.c_void_p()
    rc = advapi32.GetNamedSecurityInfoW(
        path, SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION,
        ctypes.byref(p_sid), None, None, None, ctypes.byref(p_sd),
    )
    if rc != 0:
        return None
    try:
        str_sid = ctypes.c_wchar_p()
        if not advapi32.ConvertSidToStringSidW(p_sid, ctypes.byref(str_sid)):
            return None
        try:
            return str_sid.value
        finally:
            kernel32.LocalFree(str_sid)
    finally:
        kernel32.LocalFree(p_sd)


# ---------------------------------------------------------------- Datenmodell

@dataclass
class RegistryRef:
    hive_name: str          # "HKLM" oder "HKCU"
    value_name: str         # z. B. "Foo Sans (TrueType)"
    value_data: str         # Registry-Wert (Dateiname oder absoluter Pfad)


@dataclass
class FontEntry:
    display_name: str               # abgeleitet aus Registry-Wertname(n)
    file_path: str                  # aufgelöster absoluter Pfad
    file_name: str
    size_bytes: int
    mtime: float
    scope: str                      # "Alle Benutzer" oder "Nur ich"
    protected: bool
    protect_reason: str
    file_exists: bool
    registry_refs: list[RegistryRef] = field(default_factory=list)
    checked: bool = False           # Checkbox-Zustand in der GUI
    deactivated: bool = False       # Registry entfernt, Datei bleibt erhalten
    classification: str = ""        # Serif, Sans Serif, Monospace, …
    scripts: list[str] = field(default_factory=list)   # Latein, Arabisch, …
    foundry: str = ""               # Hersteller/Foundry
    tags: list[str] = field(default_factory=list)       # eigene Tags
    broken: bool = False            # von fontTools nicht lesbar (defekt)


# ---------------------------------------------------------------- Schutz

def check_protected(file_path: str) -> tuple[bool, str]:
    """Dreistufige Schutzprüfung. Wird bei der Enumeration UND unmittelbar
    vor jedem Löschvorgang aufgerufen."""
    base = os.path.basename(file_path).lower()
    ext = os.path.splitext(base)[1]

    # Regel 1: offizielle Windows-11-Whitelist (inkl. Sprachpakete)
    if base in WIN11_DEFAULT_FONT_FILES:
        return True, "Windows-11-Standardschrift (Whitelist)"

    # Regel 2: Raster-/Systemfonts (.fon/.fnt) grundsätzlich schützen
    if ext in (".fon", ".fnt"):
        return True, "System-Rasterschrift (.fon)"

    # Regel 3: Datei in C:\Windows\Fonts UND Besitzer TrustedInstaller
    try:
        in_sysdir = os.path.normcase(os.path.dirname(os.path.abspath(file_path))) \
            == os.path.normcase(SYSTEM_FONT_DIR)
    except Exception:
        in_sysdir = False
    if in_sysdir and os.path.exists(file_path):
        owner = get_file_owner_sid(file_path)
        if owner == TRUSTED_INSTALLER_SID:
            return True, "Systemdatei (Besitzer: TrustedInstaller)"

    return False, ""


# ---------------------------------------------------------------- Enumeration

def _resolve_font_path(value_data: str) -> str:
    """HKLM-Werte enthalten oft nur den Dateinamen (relativ zu
    C:\\Windows\\Fonts), HKCU-Werte meist absolute Pfade."""
    value_data = os.path.expandvars(value_data.strip())
    if os.path.isabs(value_data):
        return value_data
    return os.path.join(SYSTEM_FONT_DIR, value_data)


def _iter_registry_values(root, hive_name: str):
    try:
        key = winreg.OpenKey(root, FONTS_REG_PATH, 0, winreg.KEY_READ)
    except OSError:
        return
    with key:
        i = 0
        while True:
            try:
                name, data, vtype = winreg.EnumValue(key, i)
            except OSError:
                break
            i += 1
            if vtype == winreg.REG_SZ and isinstance(data, str) and data.strip():
                yield RegistryRef(hive_name, name, data)


def enumerate_fonts() -> list[FontEntry]:
    """Liest HKLM- und HKCU-Fonts-Registry und gruppiert nach Zieldatei
    (mehrere Registry-Werte können auf dieselbe .ttc zeigen)."""
    by_path: dict[str, FontEntry] = {}

    sources = [
        (winreg.HKEY_LOCAL_MACHINE, "HKLM", "Alle Benutzer"),
        (winreg.HKEY_CURRENT_USER, "HKCU", "Nur ich"),
    ]
    for root, hive_name, scope in sources:
        for ref in _iter_registry_values(root, hive_name):
            path = _resolve_font_path(ref.value_data)
            key = os.path.normcase(path)
            entry = by_path.get(key)
            if entry is None:
                exists = os.path.isfile(path)
                size = mtime = 0
                if exists:
                    try:
                        st = os.stat(path)
                        size, mtime = st.st_size, st.st_mtime
                    except OSError:
                        exists = False
                prot, reason = check_protected(path)
                display = ref.value_name
                for suffix in (" (TrueType)", " (OpenType)", " (VGA res)",
                               " (All res)"):
                    if display.endswith(suffix):
                        display = display[: -len(suffix)]
                        break
                entry = FontEntry(
                    display_name=display,
                    file_path=path,
                    file_name=os.path.basename(path),
                    size_bytes=size,
                    mtime=mtime,
                    scope=scope,
                    protected=prot,
                    protect_reason=reason,
                    file_exists=exists,
                )
                by_path[key] = entry
            entry.registry_refs.append(ref)

    # Deaktivierte Fonts (Registry entfernt, Datei vorhanden) ergänzen
    for item in _load_deactivated().get("items", []):
        path = item.get("file_path", "")
        key = os.path.normcase(path)
        if not path or key in by_path:
            continue  # wieder aktiv (z. B. neu installiert) → Manifest-Leiche
        exists = os.path.isfile(path)
        size = mtime = 0
        if exists:
            try:
                st = os.stat(path)
                size, mtime = st.st_size, st.st_mtime
            except OSError:
                exists = False
        prot, reason = check_protected(path)
        refs = [RegistryRef(r["hive"], r["name"], r["data"])
                for r in item.get("registry", [])]
        scope = "Alle Benutzer" if any(r.hive_name == "HKLM" for r in refs) \
            else "Nur ich"
        by_path[key] = FontEntry(
            display_name=item.get("display_name", os.path.basename(path)),
            file_path=path, file_name=os.path.basename(path),
            size_bytes=size, mtime=mtime, scope=scope,
            protected=prot, protect_reason=reason, file_exists=exists,
            registry_refs=refs, deactivated=True,
        )

    return sorted(by_path.values(), key=lambda e: e.display_name.lower())


# ---------------------------------------------------------------- Papierkorb

def _load_manifest() -> dict:
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"items": []}


def _save_manifest(manifest: dict) -> None:
    os.makedirs(TRASH_DIR, exist_ok=True)
    tmp = MANIFEST_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, MANIFEST_PATH)


def list_trash_items() -> list[dict]:
    return _load_manifest().get("items", [])


def purge_expired_trash(retention_days: int = TRASH_RETENTION_DAYS) -> int:
    """Löscht Papierkorb-Einträge, die älter als retention_days sind,
    endgültig. Rückgabe: Anzahl entfernter Einträge."""
    manifest = _load_manifest()
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    keep, purged = [], 0
    for item in manifest.get("items", []):
        try:
            deleted_at = datetime.fromisoformat(item["deleted_at"])
        except (KeyError, ValueError):
            deleted_at = datetime.now(timezone.utc)
        if deleted_at < cutoff:
            try:
                if os.path.isfile(item.get("trash_path", "")):
                    os.remove(item["trash_path"])
                purged += 1
            except OSError:
                keep.append(item)  # beim nächsten Start erneut versuchen
        else:
            keep.append(item)
    if purged:
        manifest["items"] = keep
        _save_manifest(manifest)
    return purged


# ---------------------------------------------------------------- Deaktivieren

def _load_deactivated() -> dict:
    try:
        with open(DEACTIVATED_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"items": []}


def _save_deactivated(data: dict) -> None:
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    tmp = DEACTIVATED_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, DEACTIVATED_PATH)


def _remove_deactivated_by_paths(paths: set[str]) -> None:
    norm = {os.path.normcase(p) for p in paths}
    data = _load_deactivated()
    kept = [it for it in data.get("items", [])
            if os.path.normcase(it.get("file_path", "")) not in norm]
    if len(kept) != len(data.get("items", [])):
        data["items"] = kept
        _save_deactivated(data)


def deactivate_fonts(entries: list[FontEntry],
                     progress_cb=None) -> "UninstallResult":
    """Deaktiviert Fonts: GDI aushängen + Registry-Werte entfernen,
    Datei bleibt unangetastet. Schutzprüfung wie beim Löschen
    (Defense in Depth) — Windows-Standardschriften sind auch von der
    Deaktivierung ausgeschlossen."""
    result = UninstallResult()
    data = _load_deactivated()
    known = {os.path.normcase(it.get("file_path", ""))
             for it in data.get("items", [])}

    for i, entry in enumerate(entries):
        if progress_cb:
            progress_cb(i, len(entries), entry.display_name)

        prot, _ = check_protected(entry.file_path)
        if prot or entry.protected:
            result.skipped_protected.append(entry.display_name)
            continue
        if entry.deactivated:
            continue

        try:
            if entry.file_exists:
                remove_font_resource(entry.file_path)
            reg_errors = _delete_registry_refs(entry)
            if reg_errors:
                result.errors.append((entry.display_name,
                                      "; ".join(reg_errors)))
                continue
            if os.path.normcase(entry.file_path) not in known:
                data["items"].append({
                    "id": uuid.uuid4().hex,
                    "display_name": entry.display_name,
                    "file_path": entry.file_path,
                    "deactivated_at":
                        datetime.now(timezone.utc).isoformat(),
                    "registry": [
                        {"hive": r.hive_name, "name": r.value_name,
                         "data": r.value_data}
                        for r in entry.registry_refs
                    ],
                })
            result.ok.append(entry.display_name)
        except Exception as exc:  # noqa: BLE001
            result.errors.append((entry.display_name, str(exc)))

    _save_deactivated(data)
    broadcast_font_change()
    return result


def reactivate_fonts(entries: list[FontEntry],
                     progress_cb=None) -> "UninstallResult":
    """Macht die Deaktivierung rückgängig: Registry-Werte wieder
    anlegen + AddFontResourceW."""
    result = UninstallResult()
    paths_done: set[str] = set()

    for i, entry in enumerate(entries):
        if progress_cb:
            progress_cb(i, len(entries), entry.display_name)
        if not entry.deactivated:
            continue
        try:
            for ref in entry.registry_refs:
                root = winreg.HKEY_LOCAL_MACHINE if ref.hive_name == "HKLM" \
                    else winreg.HKEY_CURRENT_USER
                with winreg.OpenKey(root, FONTS_REG_PATH, 0,
                                    winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, ref.value_name, 0,
                                      winreg.REG_SZ, ref.value_data)
            if entry.file_exists:
                add_font_resource(entry.file_path)
            paths_done.add(entry.file_path)
            result.ok.append(entry.display_name)
        except Exception as exc:  # noqa: BLE001
            result.errors.append((entry.display_name, str(exc)))

    _remove_deactivated_by_paths(paths_done)
    if result.ok:
        broadcast_font_change()
    return result


# ---------------------------------------------------------------- Deinstallation

@dataclass
class UninstallResult:
    ok: list[str] = field(default_factory=list)
    skipped_protected: list[str] = field(default_factory=list)
    pending_reboot: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)


def _delete_registry_refs(entry: FontEntry) -> list[str]:
    """Entfernt alle Registry-Werte, die auf die Datei zeigen (inkl.
    best-effort Wow6432Node-Spiegel). Rückgabe: Fehlermeldungen."""
    errors = []
    for ref in entry.registry_refs:
        root = winreg.HKEY_LOCAL_MACHINE if ref.hive_name == "HKLM" \
            else winreg.HKEY_CURRENT_USER
        for reg_path in ((FONTS_REG_PATH, FONTS_REG_PATH_WOW)
                         if ref.hive_name == "HKLM" else (FONTS_REG_PATH,)):
            try:
                with winreg.OpenKey(root, reg_path, 0,
                                    winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, ref.value_name)
            except FileNotFoundError:
                pass  # Wert existiert dort nicht (z. B. kein Wow-Spiegel)
            except OSError as exc:
                if reg_path == FONTS_REG_PATH:
                    errors.append(
                        f"{ref.hive_name}\\...\\Fonts → "
                        f"'{ref.value_name}': {exc}"
                    )
    return errors


def _move_to_trash(entry: FontEntry) -> tuple[str | None, bool]:
    """Verschiebt die Datei in den Papierkorb-Ordner.
    Rückgabe: (Zielpfad oder None, pending_reboot)."""
    day_dir = os.path.join(TRASH_DIR, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(day_dir, exist_ok=True)
    dst = os.path.join(day_dir, entry.file_name)
    n = 1
    while os.path.exists(dst):
        stem, ext = os.path.splitext(entry.file_name)
        dst = os.path.join(day_dir, f"{stem}_{n}{ext}")
        n += 1

    for attempt in range(3):
        try:
            os.replace(entry.file_path, dst)
            return dst, False
        except PermissionError:
            time.sleep(0.25 * (attempt + 1))
        except OSError:
            break

    # Datei ist gesperrt (in Benutzung) → beim nächsten Neustart verschieben
    if schedule_move_on_reboot(entry.file_path, dst):
        return dst, True
    return None, False


def uninstall_fonts(entries: list[FontEntry],
                    progress_cb=None) -> UninstallResult:
    """Deinstalliert die übergebenen Fonts in den Papierkorb.

    Sicherheitsgarantie: check_protected() wird hier für JEDEN Eintrag
    erneut ausgeführt — unabhängig davon, was die GUI übergeben hat.
    """
    result = UninstallResult()
    manifest = _load_manifest()
    deleted_paths: set[str] = set()

    for i, entry in enumerate(entries):
        if progress_cb:
            progress_cb(i, len(entries), entry.display_name)

        # Defense in Depth: Schutz unmittelbar vor dem Löschen neu prüfen
        prot, reason = check_protected(entry.file_path)
        if prot or entry.protected:
            result.skipped_protected.append(entry.display_name)
            continue

        try:
            # 1) Aus der GDI-Fonttabelle aushängen
            if entry.file_exists:
                remove_font_resource(entry.file_path)

            # 2) Registry-Einträge entfernen
            reg_errors = _delete_registry_refs(entry)
            if reg_errors:
                result.errors.append((entry.display_name, "; ".join(reg_errors)))
                continue

            # 3) Datei in den Papierkorb verschieben
            trash_path, pending = None, False
            if entry.file_exists:
                trash_path, pending = _move_to_trash(entry)
                if trash_path is None:
                    result.errors.append(
                        (entry.display_name,
                         "Datei konnte nicht verschoben werden (gesperrt)")
                    )
                    continue

            manifest["items"].append({
                "id": uuid.uuid4().hex,
                "display_name": entry.display_name,
                "original_path": entry.file_path,
                "trash_path": trash_path,
                "pending_reboot": pending,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "registry": [
                    {"hive": r.hive_name, "name": r.value_name,
                     "data": r.value_data}
                    for r in entry.registry_refs
                ],
            })
            (result.pending_reboot if pending else result.ok).append(
                entry.display_name
            )
            deleted_paths.add(entry.file_path)
        except Exception as exc:  # noqa: BLE001 — pro Font isolieren
            result.errors.append((entry.display_name, str(exc)))

    _save_manifest(manifest)
    if deleted_paths:
        _remove_deactivated_by_paths(deleted_paths)
    broadcast_font_change()
    return result


def restore_trash_items(item_ids: set[str]) -> tuple[int, list[str]]:
    """Stellt Papierkorb-Einträge wieder her (Datei + Registry + GDI)."""
    manifest = _load_manifest()
    restored, errors, keep = 0, [], []
    for item in manifest.get("items", []):
        if item["id"] not in item_ids:
            keep.append(item)
            continue
        try:
            src, dst = item.get("trash_path"), item["original_path"]
            if src and os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.replace(src, dst)
            for ref in item.get("registry", []):
                root = winreg.HKEY_LOCAL_MACHINE if ref["hive"] == "HKLM" \
                    else winreg.HKEY_CURRENT_USER
                with winreg.OpenKey(root, FONTS_REG_PATH, 0,
                                    winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, ref["name"], 0, winreg.REG_SZ,
                                      ref["data"])
            if os.path.isfile(dst):
                add_font_resource(dst)
            restored += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{item.get('display_name', '?')}: {exc}")
            keep.append(item)
    manifest["items"] = keep
    _save_manifest(manifest)
    if restored:
        broadcast_font_change()
    return restored, errors


def empty_trash() -> tuple[int, list[str]]:
    """Leert den Papierkorb endgültig (auf ausdrücklichen Nutzerwunsch)."""
    manifest = _load_manifest()
    removed, errors, keep = 0, [], []
    for item in manifest.get("items", []):
        try:
            tp = item.get("trash_path")
            if tp and os.path.isfile(tp):
                os.remove(tp)
            removed += 1
        except OSError as exc:
            errors.append(f"{item.get('display_name', '?')}: {exc}")
            keep.append(item)
    manifest["items"] = keep
    _save_manifest(manifest)
    return removed, errors


# ---------------------------------------------------------------- Export

def export_fonts(entries: list[FontEntry], dest_zip: str,
                 progress_cb=None) -> UninstallResult:
    """Exportiert Fontdateien als ZIP (Ordner fonts/ + manifest.json),
    damit sie auf einem anderen System per Bulk-Import installiert
    werden können. Geschützte Windows-Standardschriften werden
    übersprungen — die sind auf jedem Windows ohnehin vorhanden."""
    import zipfile

    result = UninstallResult()
    manifest: list[dict] = []
    used_names: set[str] = set()

    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, e in enumerate(entries):
            if progress_cb:
                progress_cb(i, len(entries), e.display_name)
            prot, _ = check_protected(e.file_path)
            if prot or e.protected:
                result.skipped_protected.append(e.display_name)
                continue
            if not e.file_exists or not os.path.isfile(e.file_path):
                result.errors.append((e.display_name, "Datei fehlt"))
                continue
            arc = e.file_name
            n = 1
            while arc.lower() in used_names:
                stem, ext = os.path.splitext(e.file_name)
                arc = f"{stem}_{n}{ext}"
                n += 1
            used_names.add(arc.lower())
            try:
                zf.write(e.file_path, arcname=f"fonts/{arc}")
                manifest.append({
                    "file": arc,
                    "display_name": e.display_name,
                    "original_path": e.file_path,
                    "deactivated": e.deactivated,
                })
                result.ok.append(e.display_name)
            except OSError as exc:
                result.errors.append((e.display_name, str(exc)))
        zf.writestr("manifest.json",
                    json.dumps({"exported_at":
                                datetime.now(timezone.utc).isoformat(),
                                "items": manifest},
                               ensure_ascii=False, indent=2))
    return result


# ---------------------------------------------------------------- Installation

INSTALLABLE_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}


def _collect_install_files(paths: list[str]) -> tuple[list[str], list[str]]:
    """Löst ZIP-Archive (z. B. eigene Exporte) in ein Temp-Verzeichnis
    auf und liefert (fontdateien, temp_verzeichnisse)."""
    import tempfile
    import zipfile

    files: list[str] = []
    temps: list[str] = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext == ".zip":
            try:
                tmp = tempfile.mkdtemp(prefix="fontimport_",
                                       dir=APP_DATA_DIR if
                                       os.path.isdir(APP_DATA_DIR) else None)
                temps.append(tmp)
                with zipfile.ZipFile(p) as zf:
                    zf.extractall(tmp)
                for root, _dirs, names in os.walk(tmp):
                    for name in names:
                        if os.path.splitext(name)[1].lower() \
                                in INSTALLABLE_EXTENSIONS:
                            files.append(os.path.join(root, name))
            except (OSError, zipfile.BadZipFile):
                files.append(p)  # als Fehler im Hauptlauf melden
        else:
            files.append(p)
    return files, temps


def install_fonts(paths: list[str], per_user: bool = True,
                  progress_cb=None) -> UninstallResult:
    """Installiert Fontdateien (Bulk). per_user=True → nur aktueller
    Benutzer (HKCU, kein Admin nötig); False → alle Benutzer
    (C:\\Windows\\Fonts + HKLM, Admin erforderlich)."""
    import shutil
    from font_meta import registry_font_name

    result = UninstallResult()
    files, temps = _collect_install_files(paths)

    if per_user:
        dest_dir, root = USER_FONT_DIR, winreg.HKEY_CURRENT_USER
    else:
        dest_dir, root = SYSTEM_FONT_DIR, winreg.HKEY_LOCAL_MACHINE
        if not is_admin():
            for f in files:
                result.errors.append(
                    (os.path.basename(f),
                     "Installation für alle Benutzer erfordert Adminrechte"))
            return result
    os.makedirs(dest_dir, exist_ok=True)

    try:
        for i, src in enumerate(files):
            base = os.path.basename(src)
            if progress_cb:
                progress_cb(i, len(files), base)
            ext = os.path.splitext(base)[1].lower()
            if ext not in INSTALLABLE_EXTENSIONS:
                result.errors.append((base, "Kein unterstütztes Fontformat"))
                continue
            if not os.path.isfile(src):
                result.errors.append((base, "Datei nicht gefunden/lesbar"))
                continue

            target = os.path.join(dest_dir, base)
            if os.path.isfile(target):
                result.skipped_protected.append(base)   # bereits vorhanden
                continue

            try:
                name = registry_font_name(src) or os.path.splitext(base)[0]
                suffix = " (OpenType)" if ext in (".otf", ".otc") \
                    else " (TrueType)"
                value_name = name + suffix
                value_data = target if per_user else base

                shutil.copy2(src, target)
                with winreg.OpenKey(root, FONTS_REG_PATH, 0,
                                    winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ,
                                      value_data)
                add_font_resource(target)
                result.ok.append(name)
            except Exception as exc:  # noqa: BLE001
                try:
                    if os.path.isfile(target):
                        os.remove(target)   # halbe Installation aufräumen
                except OSError:
                    pass
                result.errors.append((base, str(exc)))
    finally:
        import shutil as _sh
        for tmp in temps:
            _sh.rmtree(tmp, ignore_errors=True)

    if result.ok:
        broadcast_font_change()
    return result


# ---------------------------------------------------------------- Settings

DEFAULT_SETTINGS = {"welcome_shown": False, "trash_days": 30,
                    "sample_text": ""}


def load_settings() -> dict:
    data = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            data.update(loaded)
    except (OSError, ValueError):
        pass
    return data


def save_settings(settings: dict) -> None:
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_PATH)


# ---------------------------------------------------------------- Tags

def load_tags() -> dict:
    """{normcase(pfad): [tag, …]}"""
    try:
        with open(TAGS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_tags(tags: dict) -> None:
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    tmp = TAGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in tags.items() if v}, fh,
                  ensure_ascii=False, indent=1)
    os.replace(tmp, TAGS_PATH)


# ---------------------------------------------------------------- Registry-Backup

def backup_font_registry() -> list[str]:
    """Exportiert die Fonts-Registry-Keys (HKLM + HKCU) als .reg-Dateien
    nach %LOCALAPPDATA%\\FontManager\\RegistryBackup. Unabhängiges
    Sicherheitsnetz zusätzlich zum Papierkorb."""
    import subprocess
    os.makedirs(REG_BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    created = []
    for hive in ("HKLM", "HKCU"):
        dest = os.path.join(REG_BACKUP_DIR, f"Fonts_{hive}_{ts}.reg")
        try:
            subprocess.run(["reg", "export", f"{hive}\\{FONTS_REG_PATH}",
                            dest, "/y"],
                           creationflags=flags, capture_output=True,
                           timeout=60)
            if os.path.isfile(dest):
                created.append(dest)
        except (OSError, Exception):  # noqa: BLE001
            pass
    return created


def has_registry_backup() -> bool:
    try:
        return any(f.lower().endswith(".reg")
                   for f in os.listdir(REG_BACKUP_DIR))
    except OSError:
        return False


# ---------------------------------------------------------------- Temporäre Aktivierung

_temp_active: set[str] = set()


def temp_activate(paths: list[str], progress_cb=None) -> UninstallResult:
    """Aktiviert Fontdateien nur für die laufende Windows-Sitzung
    (AddFontResourceW ohne Registry-Eintrag). Nach Abmeldung/Neustart
    automatisch wieder weg — ideal, um Photoshop dauerhaft schlank zu
    halten und Fonts nur bei Bedarf zu laden."""
    result = UninstallResult()
    for i, p in enumerate(paths):
        base = os.path.basename(p)
        if progress_cb:
            progress_cb(i, len(paths), base)
        ext = os.path.splitext(p)[1].lower()
        if ext not in INSTALLABLE_EXTENSIONS or not os.path.isfile(p):
            result.errors.append((base, "Keine gültige Fontdatei"))
            continue
        if ctypes.windll.gdi32.AddFontResourceW(p):
            _temp_active.add(p)
            result.ok.append(base)
        else:
            result.errors.append((base, "AddFontResource fehlgeschlagen"))
    if result.ok:
        broadcast_font_change()
    return result


def temp_active_paths() -> list[str]:
    return sorted(_temp_active)


def temp_deactivate_all() -> int:
    n = 0
    for p in list(_temp_active):
        remove_font_resource(p)
        _temp_active.discard(p)
        n += 1
    if n:
        broadcast_font_change()
    return n


# ---------------------------------------------------------------- Datei-Hash

def file_hash(path: str) -> str:
    """SHA-1 des Dateiinhalts (für die Duplikat-Erkennung)."""
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- Sonstiges

def thumb_cache_key(entry: FontEntry) -> str:
    raw = f"{entry.file_path}|{entry.mtime}|{entry.size_bytes}"
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()


def format_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return f"{num:.1f} GB"
