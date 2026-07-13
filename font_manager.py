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
font_manager.py — FontManager v2.0 für Windows 11 (PySide6).

Funktionsumfang:
  Kachelansicht mit Lazy-Thumbnails · Filter (Status, Klassifikation,
  Schriftsystem, Hersteller, Tags) · eigener Vorschautext ·
  Massen-Löschen mit 30-Tage-Papierkorb · Deaktivieren/Reaktivieren ·
  Duplikat-Finder · Defekt-Erkennung · temporäre Aktivierung ·
  Registry-Backup · Vergleichsansicht · Tags · PDF-Musterkatalog ·
  verwaiste Registry-Einträge bereinigen · Export/Bulk-Installation ·
  Font-Download aus freien Quellen (Google Fonts, Font Squirrel)

Windows-11-Standardschriften sind dreistufig geschützt (Whitelist,
.fon-Regel, TrustedInstaller) — die Prüfung läuft zusätzlich in der
Kernlogik unmittelbar vor jeder Lösch-/Deaktivier-Aktion.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

from PySide6.QtCore import (QAbstractListModel, QModelIndex, QRect, QSize,
                            QSortFilterProxyModel, Qt, QThread, QThreadPool,
                            QRunnable, QObject, Signal, Slot, QEvent, QTimer)
from PySide6.QtGui import (QColor, QFont, QIcon, QImage, QKeySequence,
                           QPainter, QPen, QPixmap, QShortcut)
from PySide6.QtWidgets import (QApplication, QComboBox, QCompleter, QDialog,
                               QDialogButtonBox, QFileDialog, QFrame,
                               QGroupBox, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QListView,
                               QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QProgressDialog, QPushButton,
                               QRadioButton, QScrollArea, QSpinBox,
                               QStatusBar, QStyle, QStyledItemDelegate,
                               QStyleOptionViewItem, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

try:
    from qfluentwidgets import (FluentWindow, NavigationItemPosition,
                                FluentIcon as FIF, setTheme, setThemeColor,
                                Theme, PushButton, PrimaryPushButton,
                                SearchLineEdit, ComboBox as FComboBox,
                                EditableComboBox, SpinBox as FSpinBox,
                                SwitchButton, CardWidget, CommandBar,
                                Action, MSFluentWindow, StateToolTip,
                                IndeterminateProgressRing)
except ImportError as exc:                      # pragma: no cover
    raise SystemExit(
        "PySide6-Fluent-Widgets fehlt — bitte build.bat ausführen oder "
        "'pip install pyside6-fluent-widgets'.") from exc

import font_core as core
import font_meta as meta

APP_VERSION = "3.3"
DEFAULT_SAMPLE = "AaBbGg 0123 ÄÖÜß"
THUMB_W, THUMB_H = 236, 50
TILE_W, TILE_H = 260, 140

EntryRole = Qt.UserRole + 1

# ------------------------------------------------------------ Icons
# Vektorbasiert mit QPainter gezeichnet — gestochen scharf in jeder
# Größe, themefarben, keine Emoji-Abhängigkeit vom System-Font.

_icon_cache: dict = {}


def make_icon(name: str, color: str | None = None, size: int = 64) -> QIcon:
    color = color or THEME["accent"]
    key = (name, color, size)
    if key in _icon_cache:
        return _icon_cache[key]

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    pen = QPen(c, size * 0.085, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    s = size

    def pt(x, y):
        from PySide6.QtCore import QPointF
        return QPointF(x * s, y * s)

    if name == "search":
        p.drawEllipse(pt(0.42, 0.42), 0.26 * s, 0.26 * s)
        p.drawLine(pt(0.62, 0.62), pt(0.85, 0.85))
    elif name == "eye":
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(pt(0.1, 0.5))
        path.quadTo(pt(0.5, 0.14), pt(0.9, 0.5))
        path.quadTo(pt(0.5, 0.86), pt(0.1, 0.5))
        p.drawPath(path)
        p.setBrush(c)
        p.drawEllipse(pt(0.5, 0.5), 0.11 * s, 0.11 * s)
    elif name == "check":
        p.drawRoundedRect(0.14 * s, 0.14 * s, 0.72 * s, 0.72 * s,
                          0.16 * s, 0.16 * s)
        p.drawPolyline([pt(0.32, 0.52), pt(0.46, 0.66), pt(0.7, 0.36)])
    elif name == "globe":
        p.drawEllipse(pt(0.5, 0.5), 0.36 * s, 0.36 * s)
        p.drawEllipse(pt(0.5, 0.5), 0.16 * s, 0.36 * s)
        p.drawLine(pt(0.14, 0.5), pt(0.86, 0.5))
    elif name == "trash":
        p.drawLine(pt(0.2, 0.28), pt(0.8, 0.28))
        p.drawLine(pt(0.4, 0.28), pt(0.4, 0.18))
        p.drawLine(pt(0.4, 0.18), pt(0.6, 0.18))
        p.drawLine(pt(0.6, 0.18), pt(0.6, 0.28))
        p.drawRoundedRect(0.26 * s, 0.28 * s, 0.48 * s, 0.56 * s,
                          0.08 * s, 0.08 * s)
        p.drawLine(pt(0.42, 0.4), pt(0.42, 0.72))
        p.drawLine(pt(0.58, 0.4), pt(0.58, 0.72))
    elif name == "sun":
        p.drawEllipse(pt(0.5, 0.5), 0.18 * s, 0.18 * s)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                       (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
            p.drawLine(pt(0.5 + dx * 0.28, 0.5 + dy * 0.28),
                       pt(0.5 + dx * 0.38, 0.5 + dy * 0.38))
    elif name == "moon":
        from PySide6.QtGui import QPainterPath
        big = QPainterPath()
        big.addEllipse(pt(0.5, 0.5), 0.34 * s, 0.34 * s)
        cut = QPainterPath()
        cut.addEllipse(pt(0.64, 0.4), 0.3 * s, 0.3 * s)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPath(big.subtracted(cut))
    elif name == "sparkle":
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(pt(0.5, 0.08))
        path.quadTo(pt(0.56, 0.44), pt(0.92, 0.5))
        path.quadTo(pt(0.56, 0.56), pt(0.5, 0.92))
        path.quadTo(pt(0.44, 0.56), pt(0.08, 0.5))
        path.quadTo(pt(0.44, 0.44), pt(0.5, 0.08))
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPath(path)
    elif name == "camera":
        p.drawRoundedRect(0.12 * s, 0.12 * s, 0.76 * s, 0.76 * s,
                          0.2 * s, 0.2 * s)
        p.drawEllipse(pt(0.5, 0.5), 0.17 * s, 0.17 * s)
        p.setBrush(c)
        p.drawEllipse(pt(0.73, 0.27), 0.045 * s, 0.045 * s)
    elif name == "gamepad":
        p.drawRoundedRect(0.1 * s, 0.3 * s, 0.8 * s, 0.4 * s,
                          0.18 * s, 0.18 * s)
        p.drawLine(pt(0.3, 0.42), pt(0.3, 0.58))
        p.drawLine(pt(0.22, 0.5), pt(0.38, 0.5))
        p.setBrush(c)
        p.drawEllipse(pt(0.66, 0.44), 0.04 * s, 0.04 * s)
        p.drawEllipse(pt(0.76, 0.56), 0.04 * s, 0.04 * s)
    elif name == "cup":
        p.drawRoundedRect(0.18 * s, 0.3 * s, 0.44 * s, 0.44 * s,
                          0.08 * s, 0.08 * s)
        p.drawArc(int(0.58 * s), int(0.34 * s), int(0.26 * s),
                  int(0.3 * s), -90 * 16, 180 * 16)
        p.drawLine(pt(0.18, 0.86), pt(0.66, 0.86))
    elif name == "mail":
        p.drawRoundedRect(0.12 * s, 0.24 * s, 0.76 * s, 0.52 * s,
                          0.1 * s, 0.1 * s)
        p.drawPolyline([pt(0.14, 0.28), pt(0.5, 0.55), pt(0.86, 0.28)])
    elif name == "wrench":
        p.drawArc(int(0.16 * s), int(0.16 * s), int(0.34 * s),
                  int(0.34 * s), 30 * 16, 280 * 16)
        p.drawLine(pt(0.44, 0.44), pt(0.8, 0.8))
    elif name == "shield":
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(pt(0.5, 0.1))
        path.lineTo(pt(0.84, 0.24))
        path.quadTo(pt(0.84, 0.62), pt(0.5, 0.9))
        path.quadTo(pt(0.16, 0.62), pt(0.16, 0.24))
        path.closeSubpath()
        p.drawPath(path)
        p.drawPolyline([pt(0.36, 0.48), pt(0.47, 0.6), pt(0.66, 0.36)])
    elif name == "warn":
        p.drawPolygon([pt(0.5, 0.12), pt(0.9, 0.84), pt(0.1, 0.84)])
        p.drawLine(pt(0.5, 0.38), pt(0.5, 0.62))
        p.setBrush(c)
        p.drawEllipse(pt(0.5, 0.73), 0.035 * s, 0.035 * s)
    p.end()
    icon = QIcon(pm)
    _icon_cache[key] = icon
    return icon


class SuccessPopup(QWidget):
    """Erfolgs-Animation statt Emoji: Kreis zeichnet sich, Haken
    schwingt ein, Konfetti rieselt — blendet sich selbst wieder aus."""

    def __init__(self, window, text: str) -> None:
        super().__init__(window)
        import random
        from PySide6.QtCore import QVariantAnimation, QEasingCurve, QTimer
        self._text = text
        self._t = 0.0
        self.setGeometry(window.rect())
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        rng = random.Random(42)
        palette = [THEME["accent"], "#f2b705", "#2e9e5b", "#3a7bd5",
                   THEME["accent_dark"]]
        self._confetti = [(rng.random(), rng.random() * 0.6 + 0.2,
                           rng.choice(palette), rng.random() * 5 + 3)
                          for _ in range(26)]
        anim = QVariantAnimation(self)
        anim.setDuration(750)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(self._tick)
        anim.start()
        QTimer.singleShot(1800, self._close)
        self.show()
        self.raise_()

    def _tick(self, v) -> None:
        self._t = float(v)
        self.update()

    def _close(self) -> None:
        self.close()
        self.deleteLater()

    def mousePressEvent(self, event) -> None:
        event.accept()
        self._close()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cw, ch = 380, 170
        x = (self.width() - cw) // 2
        y = (self.height() - ch) // 2
        card = QRect(x, y, cw, ch)
        p.setPen(QPen(QColor(THEME["border"])))
        p.setBrush(QColor(THEME["pane"]))
        p.drawRoundedRect(card, 16, 16)

        # Konfetti fällt aus dem oberen Kartendrittel
        if self._t > 0.25:
            ct = (self._t - 0.25) / 0.75
            for fx, speed, color, r in self._confetti:
                cxp = x + 20 + fx * (cw - 40)
                cyp = y + 20 + ct * speed * (ch - 30)
                col = QColor(color)
                col.setAlphaF(max(0.0, 1.0 - ct))
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawEllipse(int(cxp), int(cyp), int(r), int(r))

        # Kreis + Haken
        green = QColor("#2e9e5b")
        ring = QRect(x + 28, y + ch // 2 - 34, 68, 68)
        p.setPen(QPen(green, 5, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(ring, 90 * 16, -int(360 * 16 * min(1.0, self._t / 0.6)))
        if self._t > 0.55:
            k = min(1.0, (self._t - 0.55) / 0.45)
            from PySide6.QtCore import QPointF
            a = QPointF(ring.left() + 18, ring.top() + 36)
            b = QPointF(ring.left() + 30, ring.top() + 48)
            c = QPointF(ring.left() + 52, ring.top() + 22)
            if k < 0.5:
                m = a + (b - a) * (k / 0.5)
                p.drawLine(a, m)
            else:
                p.drawLine(a, b)
                m = b + (c - b) * ((k - 0.5) / 0.5)
                p.drawLine(b, m)

        # Text
        p.setPen(QColor(THEME["text"]))
        f = p.font()
        f.setPointSize(11)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRect(x + 116, y, cw - 136, ch),
                   Qt.AlignVCenter | Qt.TextWordWrap, self._text)
        p.end()


# ------------------------------------------------------------ Thumbnails

class ThumbSignals(QObject):
    ready = Signal(str, QImage)


class ThumbJob(QRunnable):
    def __init__(self, entry, key, text, px, signals) -> None:
        super().__init__()
        self.entry, self.key = entry, key
        self.text, self.px, self.signals = text, px, signals
        self.setAutoDelete(True)

    def run(self) -> None:
        cache_png = os.path.join(core.THUMB_CACHE_DIR, self.key + ".png")
        img = QImage()
        if os.path.isfile(cache_png) and img.load(cache_png):
            self.signals.ready.emit(self.key, img)
            return
        try:
            from PIL import Image, ImageDraw, ImageFont
            pil_font = ImageFont.truetype(self.entry.file_path, self.px)
            pil = Image.new("RGB", (THUMB_W, THUMB_H), (255, 255, 255))
            ImageDraw.Draw(pil).text((6, THUMB_H // 2), self.text,
                                     font=pil_font, fill=(25, 25, 25),
                                     anchor="lm")
            os.makedirs(core.THUMB_CACHE_DIR, exist_ok=True)
            pil.save(cache_png, "PNG")
            img = QImage(pil.tobytes("raw", "RGB"), pil.width, pil.height,
                         pil.width * 3, QImage.Format_RGB888).copy()
        except Exception:
            img = QImage(THUMB_W, THUMB_H, QImage.Format_RGB888)
            img.fill(QColor(245, 245, 245))
            p = QPainter(img)
            p.setPen(QColor(150, 150, 150))
            p.drawText(QRect(0, 0, THUMB_W, THUMB_H), Qt.AlignCenter,
                       "Keine Vorschau möglich")
            p.end()
        self.signals.ready.emit(self.key, img)


# ------------------------------------------------------------ Hintergrund-Threads

class FuncThread(QThread):
    """Führt eine Funktion im Hintergrund aus (für kurze, aber
    blockierende Arbeiten wie reg-Export oder Dienst-Neustart)."""
    done = Signal(object)

    def __init__(self, fn) -> None:
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self.fn())
        except Exception as exc:  # noqa: BLE001
            self.done.emit(exc)


class LoaderThread(QThread):
    loaded = Signal(list)

    def run(self) -> None:
        entries = core.enumerate_fonts()
        cache = meta.load_meta_cache(core.META_CACHE_PATH)
        tags = core.load_tags()
        for e in entries:
            data = cache.get(core.thumb_cache_key(e))
            if data:
                e.classification = data.get("c", "")
                e.scripts = data.get("s", [])
                e.foundry = data.get("f", "")
                e.broken = bool(data.get("b", False))
            e.tags = list(tags.get(os.path.normcase(e.file_path), []))
        self.loaded.emit(entries)


class MetaScanThread(QThread):
    progress = Signal(int, int)
    finished_scan = Signal()

    def __init__(self, entries) -> None:
        super().__init__()
        self.entries = entries

    def run(self) -> None:
        cache = meta.load_meta_cache(core.META_CACHE_PATH)
        todo = [e for e in self.entries
                if not e.classification and e.file_exists]
        dirty = 0
        for i, e in enumerate(todo):
            if self.isInterruptionRequested():
                break
            key = core.thumb_cache_key(e)
            data = cache.get(key)
            if data is None:
                data = meta.analyze_font(e.file_path, e.display_name)
                cache[key] = data
                dirty += 1
            e.classification = data.get("c", meta.UNKNOWN)
            e.scripts = data.get("s", [])
            e.foundry = data.get("f", meta.UNKNOWN)
            e.broken = bool(data.get("b", False))
            if i % 50 == 0:
                self.progress.emit(i, len(todo))
            if dirty and dirty % 500 == 0:
                meta.save_meta_cache(core.META_CACHE_PATH, cache)
        if dirty:
            meta.save_meta_cache(core.META_CACHE_PATH, cache)
        self.finished_scan.emit()


class ActionThread(QThread):
    progress = Signal(int, int, str)
    finished_with = Signal(object)

    def __init__(self, func, entries) -> None:
        super().__init__()
        self.func, self.entries = func, entries

    def run(self) -> None:
        res = self.func(
            self.entries,
            progress_cb=lambda i, n, name: self.progress.emit(i, n, name))
        self.finished_with.emit(res)


class DupScanThread(QThread):
    """Feature 1: Duplikate — exakt gleiche Dateien (Hash) und gleiche
    Fontnamen in mehreren Dateien."""
    progress = Signal(int, int)
    done = Signal(list)   # [(art, [FontEntry, …]), …]

    def __init__(self, entries) -> None:
        super().__init__()
        self.entries = [e for e in entries
                        if e.file_exists and not e.protected]

    def run(self) -> None:
        groups = []
        # 1) exakte Duplikate: erst nach Größe gruppieren, dann hashen
        by_size: dict[int, list] = {}
        for e in self.entries:
            by_size.setdefault(e.size_bytes, []).append(e)
        candidates = [g for g in by_size.values() if len(g) > 1]
        total = sum(len(g) for g in candidates)
        i = 0
        for group in candidates:
            by_hash: dict[str, list] = {}
            for e in group:
                if self.isInterruptionRequested():
                    return
                try:
                    by_hash.setdefault(core.file_hash(e.file_path),
                                       []).append(e)
                except OSError:
                    pass
                i += 1
                if i % 25 == 0:
                    self.progress.emit(i, total)
            for same in by_hash.values():
                if len(same) > 1:
                    groups.append(("Exakte Kopie", same))
        # 2) Namens-Duplikate (gleicher Fontname, andere Datei/Version)
        exact_paths = {e.file_path for _k, g in groups for e in g}
        by_name: dict[str, list] = {}
        for e in self.entries:
            by_name.setdefault(e.display_name.strip().lower(),
                               []).append(e)
        for same in by_name.values():
            rest = [e for e in same if e.file_path not in exact_paths]
            if len(rest) > 1:
                groups.append(("Gleicher Name", rest))
        self.done.emit(groups)


class PdfCatalogThread(QThread):
    """Feature 7: PDF-Musterkatalog der übergebenen Fonts."""
    progress = Signal(int, int)
    done = Signal(str, str)   # pfad, fehler

    def __init__(self, entries, sample: str, dest: str) -> None:
        super().__init__()
        self.entries, self.sample, self.dest = entries, sample, dest

    def run(self) -> None:
        try:
            from PIL import Image, ImageDraw, ImageFont
            W, H, MARGIN, ROW = 1240, 1754, 60, 104   # A4 @150dpi
            per_page = (H - 2 * MARGIN - 40) // ROW
            label_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
                if os.name != "nt" else r"C:\Windows\Fonts\segoeui.ttf", 18)
            pages, page, draw, row = [], None, None, per_page
            for i, e in enumerate(self.entries):
                if self.isInterruptionRequested():
                    return
                if row >= per_page:
                    page = Image.new("RGB", (W, H), "white")
                    draw = ImageDraw.Draw(page)
                    draw.text((MARGIN, MARGIN - 30),
                              f"FontManager – Musterkatalog "
                              f"(Seite {len(pages) + 1})",
                              font=label_font, fill=(120, 120, 120))
                    pages.append(page)
                    row = 0
                y = MARGIN + 20 + row * ROW
                draw.text((MARGIN, y),
                          f"{e.display_name}   "
                          f"({core.format_size(e.size_bytes)})",
                          font=label_font, fill=(90, 90, 90))
                try:
                    f = ImageFont.truetype(e.file_path, 44)
                    draw.text((MARGIN, y + 26), self.sample, font=f,
                              fill=(15, 15, 15))
                except Exception:
                    draw.text((MARGIN, y + 30),
                              "(keine Vorschau möglich – Datei defekt?)",
                              font=label_font, fill=(190, 60, 60))
                row += 1
                if i % 20 == 0:
                    self.progress.emit(i, len(self.entries))
            if not pages:
                self.done.emit("", "Keine Fonts zu exportieren.")
                return
            pages[0].save(self.dest, save_all=True,
                          append_images=pages[1:], resolution=150)
            self.done.emit(self.dest, "")
        except Exception as exc:  # noqa: BLE001
            self.done.emit("", str(exc))


class DownloadPreviewThread(QThread):
    ready = Signal(int, QImage, str)   # token, bild, hinweis

    def __init__(self, item: dict, sample: str, token: int) -> None:
        super().__init__()
        self.item, self.sample, self.token = item, sample, token

    def run(self) -> None:
        import font_download as fdl
        img, note = QImage(), ""
        try:
            path = fdl.preview_font(
                self.item, os.path.join(core.DOWNLOAD_DIR, "_preview"))
            if path:
                from PIL import Image, ImageDraw, ImageFont
                f = ImageFont.truetype(path, 34)
                pil = Image.new("RGB", (620, 56), (255, 255, 255))
                ImageDraw.Draw(pil).text((6, 28), self.sample, font=f,
                                         fill=(20, 20, 20), anchor="lm")
                img = QImage(pil.tobytes("raw", "RGB"), pil.width,
                             pil.height, pil.width * 3,
                             QImage.Format_RGB888).copy()
            else:
                note = ("Für diese Quelle gibt es die Vorschau nach dem "
                        "Download.")
        except Exception as exc:  # noqa: BLE001
            note = f"Vorschau nicht möglich: {exc}"
        self.ready.emit(self.token, img, note)


class BackupThread(QThread):
    """Sicherung der Schriftenliste ohne UI-Blockade (reg export)."""
    done = Signal(list)

    def run(self) -> None:
        self.done.emit(core.backup_font_registry())


class CacheRebuildThread(QThread):
    """Font-Anzeige-Cache erneuern (net stop/start) ohne UI-Blockade."""
    done = Signal()

    def run(self) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(["net", "stop", "FontCache"], creationflags=flags)
        cache_dir = os.path.join(
            os.environ.get("WINDIR", r"C:\Windows"), "ServiceProfiles",
            "LocalService", "AppData", "Local", "FontCache")
        try:
            for f in os.listdir(cache_dir):
                if f.lower().endswith(".dat"):
                    try:
                        os.remove(os.path.join(cache_dir, f))
                    except OSError:
                        pass
        except OSError:
            pass
        subprocess.run(["net", "start", "FontCache"], creationflags=flags)
        self.done.emit()


class DownloadListThread(QThread):
    done = Signal(str, list, str)   # provider, items, fehler

    def __init__(self, provider: str) -> None:
        super().__init__()
        self.provider = provider

    def run(self) -> None:
        import font_download as fdl
        try:
            self.done.emit(self.provider, fdl.list_fonts(self.provider), "")
        except Exception as exc:  # noqa: BLE001
            self.done.emit(self.provider, [], str(exc))


class DownloadWorkThread(QThread):
    progress = Signal(int, int, str)
    done = Signal(object, bool)     # UninstallResult, installiert?

    def __init__(self, items: list[dict], install: bool) -> None:
        super().__init__()
        self.items, self.install = items, install

    def run(self) -> None:
        import font_download as fdl
        files: list[str] = []
        errors: list[tuple[str, str]] = []
        for i, item in enumerate(self.items):
            self.progress.emit(i, len(self.items),
                               f"Lade {item['name']} …")
            try:
                files += fdl.download_family(item, core.DOWNLOAD_DIR)
            except Exception as exc:  # noqa: BLE001
                errors.append((item["name"], str(exc)))
        if self.install:
            res = core.install_fonts(files, per_user=True,
                                     progress_cb=lambda i, n, s:
                                     self.progress.emit(i, n,
                                                        f"Installiere {s}"))
        else:
            res = core.temp_activate(files,
                                     progress_cb=lambda i, n, s:
                                     self.progress.emit(i, n,
                                                        f"Aktiviere {s}"))
        res.errors = errors + res.errors
        self.done.emit(res, self.install)


# ------------------------------------------------------------ Model / Proxy

class FontListModel(QAbstractListModel):
    checked_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.entries: list = []
        self.sample_text = DEFAULT_SAMPLE
        self.sample_px = 28
        self._pixmaps: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._key_to_row: dict[str, int] = {}
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(max(2, (os.cpu_count() or 4) // 2))
        self._signals = ThumbSignals()
        self._signals.ready.connect(self._on_thumb_ready)

    def _thumb_key(self, e) -> str:
        extra = hashlib.sha1(
            f"{self.sample_text}|{self.sample_px}".encode("utf-8")
        ).hexdigest()[:8]
        return f"{core.thumb_cache_key(e)}-{extra}"

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries)

    def flags(self, index):
        fl = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if not self.entries[index.row()].protected:
            fl |= Qt.ItemIsUserCheckable
        return fl

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self.entries[index.row()]
        if role == Qt.DisplayRole:
            return e.display_name
        if role == Qt.CheckStateRole:
            return Qt.Checked if e.checked else Qt.Unchecked
        if role == Qt.ToolTipRole:
            status = ("geschützt: " + e.protect_reason) if e.protected \
                else ("DEFEKT" if e.broken else
                      ("deaktiviert" if e.deactivated else "aktiv, löschbar"))
            return (f"<b>{e.display_name}</b><br>"
                    f"Datei: {e.file_path}<br>"
                    f"Größe: {core.format_size(e.size_bytes)} · {e.scope}<br>"
                    f"Status: {status}<br>"
                    f"Klassifikation: {e.classification or '–'}<br>"
                    f"Schriftsysteme: {', '.join(e.scripts) or '–'}<br>"
                    f"Hersteller: {e.foundry or '–'}<br>"
                    f"Tags: {', '.join(e.tags) or '–'}")
        if role == EntryRole:
            return e
        return None

    def setData(self, index, value, role=Qt.EditRole) -> bool:
        if role == Qt.CheckStateRole:
            e = self.entries[index.row()]
            if e.protected:
                return False
            e.checked = (Qt.CheckState(value) == Qt.Checked)
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            self.checked_changed.emit()
            return True
        return False

    def set_entries(self, entries) -> None:
        self.beginResetModel()
        self.entries = entries
        self._rebuild_keys()
        self.endResetModel()
        self.checked_changed.emit()

    def set_sample(self, text: str, px: int) -> None:
        self.sample_text = text.strip() or DEFAULT_SAMPLE
        self.sample_px = px
        self.beginResetModel()
        self._rebuild_keys()
        self.endResetModel()

    def _rebuild_keys(self) -> None:
        self._pixmaps.clear()
        self._pending.clear()
        self._key_to_row = {self._thumb_key(e): i
                            for i, e in enumerate(self.entries)}

    def pixmap_for(self, e) -> QPixmap | None:
        key = self._thumb_key(e)
        pix = self._pixmaps.get(key)
        if pix is not None:
            return pix
        if key not in self._pending and e.file_exists:
            self._pending.add(key)
            self._pool.start(ThumbJob(e, key, self.sample_text,
                                      self.sample_px, self._signals))
        return None

    @Slot(str, QImage)
    def _on_thumb_ready(self, key: str, img: QImage) -> None:
        self._pending.discard(key)
        if len(self._pixmaps) > 800:
            self._pixmaps.clear()
        self._pixmaps[key] = QPixmap.fromImage(img)
        row = self._key_to_row.get(key)
        if row is not None and row < len(self.entries):
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [Qt.DecorationRole])

    def checked_entries(self) -> list:
        return [e for e in self.entries if e.checked and not e.protected]

    def set_checked_bulk(self, entries, checked: bool) -> None:
        for e in entries:
            if not e.protected:
                e.checked = checked
        if self.entries:
            self.dataChanged.emit(self.index(0),
                                  self.index(len(self.entries) - 1),
                                  [Qt.CheckStateRole])
        self.checked_changed.emit()


class FontFilterProxy(QSortFilterProxyModel):
    SORT_KEYS = ["Name", "Dateigröße", "Änderungsdatum", "Status",
                 "Hersteller", "Klassifikation"]

    def __init__(self) -> None:
        super().__init__()
        self.search = ""
        self.status_filter = "Alle"
        self.class_filter = "Alle"
        self.script_filter = "Alle"
        self.foundry_filter = "Alle"
        self.tag_filter = "Alle"
        self.sort_key = "Name"

    def filterAcceptsRow(self, row, parent) -> bool:
        e = self.sourceModel().entries[row]
        sf = self.status_filter
        if sf == "Löschbar" and e.protected:
            return False
        if sf == "Geschützt" and not e.protected:
            return False
        if sf == "Deaktiviert" and not e.deactivated:
            return False
        if sf == "Aktiv" and (e.deactivated or e.protected):
            return False
        if sf == "Defekt" and not e.broken:
            return False
        if self.class_filter != "Alle" \
                and (e.classification or "Unbekannt") != self.class_filter:
            return False
        if self.script_filter != "Alle" \
                and self.script_filter not in e.scripts:
            return False
        if self.foundry_filter != "Alle" \
                and (e.foundry or "Unbekannt") != self.foundry_filter:
            return False
        if self.tag_filter != "Alle" and self.tag_filter not in e.tags:
            return False
        if self.search:
            hay = (f"{e.display_name} {e.file_name} {e.foundry} "
                   f"{e.classification} {' '.join(e.scripts)} "
                   f"{' '.join(e.tags)}").lower()
            if self.search not in hay:
                return False
        return True

    def lessThan(self, left, right) -> bool:
        a = self.sourceModel().entries[left.row()]
        b = self.sourceModel().entries[right.row()]
        k = self.sort_key
        if k == "Dateigröße":
            return a.size_bytes < b.size_bytes
        if k == "Änderungsdatum":
            return a.mtime < b.mtime
        if k == "Status":
            return (a.protected, a.deactivated, a.display_name.lower()) \
                < (b.protected, b.deactivated, b.display_name.lower())
        if k == "Hersteller":
            return (a.foundry.lower(), a.display_name.lower()) \
                < (b.foundry.lower(), b.display_name.lower())
        if k == "Klassifikation":
            return (a.classification.lower(), a.display_name.lower()) \
                < (b.classification.lower(), b.display_name.lower())
        return a.display_name.lower() < b.display_name.lower()


# ------------------------------------------------------------ Delegate

class TileDelegate(QStyledItemDelegate):
    PROTECT = QColor(178, 34, 52)
    BROKEN = QColor(205, 120, 0)
    DEACT = QColor(120, 120, 120)
    OK = QColor(0, 120, 60)

    def sizeHint(self, option, index) -> QSize:
        return QSize(TILE_W, TILE_H)

    def paint(self, painter, option: QStyleOptionViewItem, index) -> None:
        e = index.data(EntryRole)
        r = option.rect.adjusted(4, 4, -4, -4)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        selected = bool(option.state & QStyle.State_Selected)
        bg = QColor(THEME["tile_sel"]) if selected \
            else (QColor(236, 236, 238) if e.deactivated
                  else QColor(THEME["tile"]))
        painter.setPen(QPen(QColor(THEME["accent"]) if selected
                            else QColor(THEME["tile_border"])))
        painter.setBrush(bg)
        painter.drawRoundedRect(r, 10, 10)

        cb = QRect(r.left() + 8, r.top() + 8, 16, 16)
        if not e.protected:
            painter.setPen(QPen(QColor(120, 120, 120), 1.4))
            painter.setBrush(Qt.white)
            painter.drawRoundedRect(cb, 3, 3)
            if e.checked:
                painter.setPen(QPen(self.OK, 2.4))
                painter.drawLine(cb.left() + 3, cb.center().y() + 1,
                                 cb.center().x() - 1, cb.bottom() - 3)
                painter.drawLine(cb.center().x() - 1, cb.bottom() - 3,
                                 cb.right() - 2, cb.top() + 3)

        if e.protected:
            badge, bg_c, fg_c = "GESCHÜTZT", self.PROTECT, Qt.white
        elif e.broken:
            badge, bg_c, fg_c = "DEFEKT", self.BROKEN, Qt.white
        elif e.deactivated:
            badge, bg_c, fg_c = "DEAKTIVIERT", self.DEACT, Qt.white
        else:
            badge, bg_c, fg_c = "löschbar", QColor(228, 240, 232), self.OK
        painter.setFont(QFont(option.font.family(), 7, QFont.Bold))
        bw = painter.fontMetrics().horizontalAdvance(badge) + 12
        br = QRect(r.right() - bw - 6, r.top() + 7, bw, 16)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_c)
        painter.drawRoundedRect(br, 8, 8)
        painter.setPen(fg_c)
        painter.drawText(br, Qt.AlignCenter, badge)

        thumb = QRect(r.left() + 10, r.top() + 30, THUMB_W, THUMB_H)
        model = index.model().sourceModel()
        pix = model.pixmap_for(e)
        if pix is not None:
            if e.deactivated:
                painter.setOpacity(0.45)
            painter.drawPixmap(thumb, pix)
            painter.setOpacity(1.0)
        else:
            painter.setPen(QColor(170, 170, 170))
            painter.setFont(QFont(option.font.family(), 8))
            painter.drawText(thumb, Qt.AlignCenter,
                             "Lade Vorschau…" if e.file_exists
                             else "Datei fehlt")

        painter.setPen(QColor(30, 30, 30))
        painter.setFont(QFont(option.font.family(), 9, QFont.DemiBold))
        name_rect = QRect(r.left() + 10, thumb.bottom() + 3,
                          r.width() - 20, 15)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(
                             e.display_name, Qt.ElideRight,
                             name_rect.width()))

        painter.setPen(QColor(110, 110, 110))
        painter.setFont(QFont(option.font.family(), 8))
        info = (f"{core.format_size(e.size_bytes)}  ·  {e.scope}"
                if e.file_exists else f"Datei fehlt  ·  {e.scope}")
        info_rect = QRect(r.left() + 10, name_rect.bottom(),
                          r.width() - 20, 13)
        painter.drawText(info_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(
                             info, Qt.ElideRight, info_rect.width()))

        parts = [x for x in (e.classification, e.foundry)
                 if x and x != "Unbekannt"]
        if e.tags:
            parts.append(" ".join("#" + t for t in e.tags))
        if parts:
            painter.setPen(QColor(130, 130, 130))
            meta_rect = QRect(r.left() + 10, info_rect.bottom(),
                              r.width() - 20, 13)
            painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(
                                 "  ·  ".join(parts), Qt.ElideRight,
                                 meta_rect.width()))
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.MouseButtonRelease:
            e = index.data(EntryRole)
            if not e.protected:
                r = option.rect.adjusted(4, 4, -4, -4)
                cb = QRect(r.left() + 8, r.top() + 8, 16, 16)
                if cb.adjusted(-4, -4, 4, 4).contains(event.pos()):
                    state = Qt.Unchecked if e.checked else Qt.Checked
                    model.setData(index, state, Qt.CheckStateRole)
                    return True
        return super().editorEvent(event, model, option, index)


# ------------------------------------------------------------ Dialoge

class ExportDialog(QDialog):
    def __init__(self, checked, deletable, visible, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fonts exportieren")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "Exportiert die Fontdateien als ZIP (inkl. manifest.json).\n"
            "Auf dem Zielsystem: „Fonts installieren…“ und die ZIP wählen.\n"
            "Windows-Standardschriften werden nicht exportiert."))
        self.rb_checked = QRadioButton(f"Markierte Schriften ({checked})")
        self.rb_deletable = QRadioButton(
            f"Alle selbst installierten / löschbaren ({deletable})")
        self.rb_visible = QRadioButton(
            f"Alle aktuell angezeigten (Filter) ({visible})")
        self.rb_checked.setEnabled(checked > 0)
        (self.rb_checked if checked else self.rb_deletable).setChecked(True)
        for rb in (self.rb_checked, self.rb_deletable, self.rb_visible):
            lay.addWidget(rb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def scope(self) -> str:
        if self.rb_checked.isChecked():
            return "checked"
        return "deletable" if self.rb_deletable.isChecked() else "visible"


class TrashDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            f"Papierkorb (automatische Löschung nach "
            f"{core.TRASH_RETENTION_DAYS} Tagen)")
        self.resize(760, 420)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["Schrift", "Gelöscht am", "Ursprünglicher Pfad"])
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.table)
        btns = QHBoxLayout()
        b_restore = QPushButton("Auswahl wiederherstellen")
        b_empty = QPushButton("Papierkorb endgültig leeren…")
        btns.addWidget(b_restore)
        btns.addWidget(b_empty)
        btns.addStretch(1)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        btns.addWidget(close)
        lay.addLayout(btns)
        b_restore.clicked.connect(self._restore)
        b_empty.clicked.connect(self._empty)
        self._reload()

    def _reload(self) -> None:
        self.items = core.list_trash_items()
        self.table.setRowCount(len(self.items))
        for row, it in enumerate(self.items):
            self.table.setItem(row, 0, QTableWidgetItem(
                it.get("display_name", "?")))
            self.table.setItem(row, 1, QTableWidgetItem(
                it.get("deleted_at", "")[:19].replace("T", " ")))
            self.table.setItem(row, 2, QTableWidgetItem(
                it.get("original_path", "")))

    def _selected_ids(self) -> set:
        rows = {i.row() for i in self.table.selectionModel().selectedRows()}
        return {self.items[r]["id"] for r in rows}

    def _restore(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        restored, errors = core.restore_trash_items(ids)
        msg = f"{restored} Schrift(en) wiederhergestellt."
        if errors:
            msg += "\n\nFehler:\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "Wiederherstellen", msg)
        self._reload()

    def _empty(self) -> None:
        if not self.items:
            return
        rc = QMessageBox.question(
            self, "Papierkorb leeren",
            f"{len(self.items)} Schrift(en) werden ENDGÜLTIG gelöscht.\n\n"
            f"Fortfahren?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if rc == QMessageBox.Yes:
            removed, errors = core.empty_trash()
            msg = f"{removed} Datei(en) endgültig gelöscht."
            if errors:
                msg += "\n\nFehler:\n" + "\n".join(errors[:10])
            QMessageBox.information(self, "Papierkorb", msg)
            self._reload()


class DuplicatesDialog(QDialog):
    """Feature 1: Ergebnis des Duplikat-Scans."""

    def __init__(self, groups, model: FontListModel, parent=None) -> None:
        super().__init__(parent)
        self.groups, self.model = groups, model
        self.setWindowTitle(f"Duplikate — {len(groups)} Gruppe(n) gefunden")
        self.resize(860, 480)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Gruppe", "Art", "Schrift", "Datei", "Größe"])
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        row = 0
        for gi, (kind, entries) in enumerate(groups, 1):
            for e in sorted(entries, key=lambda x: -x.mtime):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(gi)))
                self.table.setItem(row, 1, QTableWidgetItem(kind))
                self.table.setItem(row, 2, QTableWidgetItem(e.display_name))
                self.table.setItem(row, 3, QTableWidgetItem(e.file_path))
                self.table.setItem(row, 4, QTableWidgetItem(
                    core.format_size(e.size_bytes)))
                row += 1
        lay.addWidget(self.table)
        info = QLabel("„Markieren“ setzt in jeder Gruppe alle bis auf die "
                      "neueste Datei auf die Löschliste — danach wie "
                      "gewohnt prüfen und „In den Papierkorb…“ ausführen.")
        info.setWordWrap(True)
        lay.addWidget(info)
        btns = QHBoxLayout()
        b_mark = QPushButton("Duplikate markieren (neueste behalten)")
        b_mark.clicked.connect(self._mark)
        btns.addWidget(b_mark)
        btns.addStretch(1)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        btns.addWidget(close)
        lay.addLayout(btns)

    def _mark(self) -> None:
        to_mark = []
        for _kind, entries in self.groups:
            keep = max(entries, key=lambda e: e.mtime)
            to_mark += [e for e in entries if e is not keep]
        self.model.set_checked_bulk(to_mark, True)
        QMessageBox.information(
            self, "Markiert",
            f"{len(to_mark)} Duplikat(e) markiert. Die jeweils neueste "
            f"Datei jeder Gruppe bleibt unmarkiert.")
        self.accept()


class CompareDialog(QDialog):
    """Feature 5: markierte/ausgewählte Fonts im direkten Vergleich."""

    def __init__(self, entries, sample: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Vergleich — {len(entries)} Schriften")
        self.resize(980, 640)
        lay = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        il = QVBoxLayout(inner)
        try:
            from PIL import Image, ImageDraw, ImageFont
            for e in entries:
                cap = QLabel(f"{e.display_name}  ·  "
                             f"{e.classification or '–'}  ·  "
                             f"{e.foundry or '–'}")
                cap.setStyleSheet("color:#666;")
                il.addWidget(cap)
                try:
                    f = ImageFont.truetype(e.file_path, 40)
                    img = Image.new("RGB", (920, 64), "white")
                    ImageDraw.Draw(img).text((4, 32), sample, font=f,
                                             fill=(15, 15, 15), anchor="lm")
                    qim = QImage(img.tobytes("raw", "RGB"), img.width,
                                 img.height, img.width * 3,
                                 QImage.Format_RGB888).copy()
                    pic = QLabel()
                    pic.setPixmap(QPixmap.fromImage(qim))
                    il.addWidget(pic)
                except Exception:
                    err = QLabel("(keine Vorschau möglich)")
                    err.setStyleSheet("color:#b44;")
                    il.addWidget(err)
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setStyleSheet("color:#ddd;")
                il.addWidget(line)
        except ImportError:
            il.addWidget(QLabel("Pillow nicht verfügbar."))
        il.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class DownloadDialog(QDialog):
    """Font-Download aus freien Quellen (Google Fonts, Font Squirrel)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fonts aus dem Internet laden — nur freie, "
                            "öffentliche Quellen")
        self.resize(680, 560)
        self._lists: dict[str, list[dict]] = {}
        self.installed_something = False

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.provider = QComboBox()
        import font_download as fdl
        self.provider.addItems(list(fdl.PROVIDERS))
        self.provider.currentTextChanged.connect(self._load_list)
        top.addWidget(QLabel("Quelle:"))
        top.addWidget(self.provider)
        self.ring = IndeterminateProgressRing(self)
        self.ring.setFixedSize(20, 20)
        self.ring.setStrokeWidth(3)
        self.ring.hide()
        top.addWidget(self.ring)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen…")
        self.search.textChanged.connect(self._refresh)
        top.addWidget(self.search, 1)
        lay.addLayout(top)

        self.listw = QListWidget()
        self.listw.setSelectionMode(QListWidget.ExtendedSelection)
        self.listw.currentItemChanged.connect(self._preview_selected)
        lay.addWidget(self.listw, 1)

        prev_box = QGroupBox("Live-Vorschau der zuletzt angeklickten Familie")
        pv = QVBoxLayout(prev_box)
        self.preview_label = QLabel("Familie anklicken für eine Vorschau…")
        self.preview_label.setMinimumHeight(58)
        self.preview_label.setStyleSheet(
            "background:#fff;border:1px solid #ddd;border-radius:6px;"
            "padding:2px;color:#888;")
        pv.addWidget(self.preview_label)
        lay.addWidget(prev_box)
        self._preview_token = 0

        self.rb_install = QRadioButton(
            "Herunterladen und installieren (nur für mich)")
        self.rb_temp = QRadioButton(
            "Herunterladen und NUR temporär aktivieren "
            "(bis Abmeldung/Neustart)")
        self.rb_install.setChecked(True)
        lay.addWidget(self.rb_install)
        lay.addWidget(self.rb_temp)

        note = QLabel("Google Fonts: OFL/Apache-lizenziert · Font Squirrel: "
                      "handverlesen, kommerziell frei. Die jeweilige Lizenz "
                      "liegt den Downloads bei bzw. ist beim Anbieter "
                      "einsehbar.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#777;")
        lay.addWidget(note)

        btns = QHBoxLayout()
        self.b_go = QPushButton("Ausgewählte laden")
        self.b_go.clicked.connect(self._start)
        btns.addWidget(self.b_go)
        btns.addStretch(1)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        btns.addWidget(close)
        lay.addLayout(btns)

        srow = QHBoxLayout()
        self.fetch_ring = IndeterminateProgressRing()
        self.fetch_ring.setFixedSize(18, 18)
        try:
            self.fetch_ring.setStrokeWidth(3)
        except Exception:
            pass
        self.fetch_ring.hide()
        self.status = QLabel("")
        srow.addWidget(self.fetch_ring)
        srow.addWidget(self.status, 1)
        lay.addLayout(srow)
        self._load_list(self.provider.currentText())

    def _preview_selected(self, current, _prev=None) -> None:
        if current is None:
            return
        item = current.data(Qt.UserRole)
        self._preview_token += 1
        token = self._preview_token
        self.preview_label.setText(f"Lade Vorschau: {item['name']} …")
        self.preview_label.setPixmap(QPixmap())
        parent = self.parent()
        sample = parent.model.sample_text if parent is not None \
            else DEFAULT_SAMPLE
        self.prev_thread = DownloadPreviewThread(item, sample, token)
        self.prev_thread.ready.connect(self._on_preview)
        self.prev_thread.start()

    @Slot(int, QImage, str)
    def _on_preview(self, token: int, img: QImage, note: str) -> None:
        if token != self._preview_token:
            return   # veraltete Antwort ignorieren
        if not img.isNull():
            self.preview_label.setPixmap(QPixmap.fromImage(img))
            self.preview_label.setText("")
        else:
            self.preview_label.setText(note or "Keine Vorschau verfügbar.")

    def _load_list(self, provider: str) -> None:
        if provider in self._lists:
            self._refresh()
            return
        self.status.setText(f"Lade Font-Liste von {provider} …")
        self.fetch_ring.show()
        self.listw.clear()
        self.list_thread = DownloadListThread(provider)
        self.list_thread.done.connect(self._on_list)
        self.list_thread.start()

    @Slot(str, list, str)
    def _on_list(self, provider: str, items: list, error: str) -> None:
        self.fetch_ring.hide()
        if error:
            self.status.setText(f"Fehler: {error}")
            return
        self._lists[provider] = items
        self.status.setText(f"{len(items)} Familien verfügbar.")
        self._refresh()

    def _refresh(self) -> None:
        items = self._lists.get(self.provider.currentText(), [])
        q = self.search.text().strip().lower()
        if q:
            items = [i for i in items if q in i["name"].lower()]
        self.listw.clear()
        for i in items[:500]:
            it = QListWidgetItem(
                f"{i['name']}   —   {i['category'] or '?'}")
            it.setData(Qt.UserRole, i)
            self.listw.addItem(it)
        if len(items) > 500:
            self.status.setText(f"{len(items)} Treffer — es werden die "
                                f"ersten 500 angezeigt, Suche verfeinern.")

    def _start(self) -> None:
        items = [i.data(Qt.UserRole) for i in self.listw.selectedItems()]
        if not items:
            QMessageBox.information(self, "Keine Auswahl",
                                    "Bitte mindestens eine Familie wählen.")
            return
        install = self.rb_install.isChecked()
        self.b_go.setEnabled(False)
        self.prog = QProgressDialog("Lade…", None, 0, len(items), self)
        self.prog.setWindowModality(Qt.WindowModal)
        self.prog.setCancelButton(None)
        self.prog.setMinimumDuration(0)
        self.work = DownloadWorkThread(items, install)
        self.work.progress.connect(
            lambda i, n, s: (self.prog.setMaximum(n),
                             self.prog.setValue(i),
                             self.prog.setLabelText(s)))
        self.work.done.connect(self._on_done)
        self.work.start()

    @Slot(object, bool)
    def _on_done(self, res, installed: bool) -> None:
        self.prog.close()
        self.b_go.setEnabled(True)
        if installed and res.ok:
            self.installed_something = True
        lines = [("Installiert: " if installed else "Temporär aktiviert: ")
                 + str(len(res.ok))]
        if res.skipped_protected:
            lines.append(f"Übersprungen (bereits vorhanden): "
                         f"{len(res.skipped_protected)}")
        if res.errors:
            lines.append(f"Fehler: {len(res.errors)}")
            lines += [f"  • {n}: {m}" for n, m in res.errors[:8]]
        if not installed and res.ok:
            lines.append("\nDie Fonts sind bis zur Abmeldung/zum Neustart "
                         "in allen Programmen verfügbar.")
        QMessageBox.information(self, "Ergebnis", "\n".join(lines))


class SettingsPage(QWidget):
    """Einstellungen als eigene Navigations-Seite (Fluent-Cards)."""

    def __init__(self, main) -> None:
        super().__init__()
        self.setObjectName("settingsPage")
        self.main = main
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 20, 28, 20)
        outer.setSpacing(12)
        title = QLabel("Einstellungen")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        outer.addWidget(title)

        def card(heading: str) -> QVBoxLayout:
            c = CardWidget(self)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(16, 12, 16, 14)
            h = QLabel(heading)
            h.setStyleSheet("font-weight:700;")
            cl.addWidget(h)
            outer.addWidget(c)
            return cl

        c1 = card("Design")
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Erscheinungsbild:"))
        self.theme_combo = FComboBox()
        self.theme_combo.addItems(["Hell", "Dunkel"])
        self.theme_combo.currentTextChanged.connect(self._on_theme)
        row1.addWidget(self.theme_combo)
        row1.addStretch(1)
        c1.addLayout(row1)

        c2 = card("Tutorial")
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Tutorial-Modus aktiv:"))
        self.tutorial_switch = SwitchButton()
        self.tutorial_switch.checkedChanged.connect(self._on_tutorial)
        row2.addWidget(self.tutorial_switch)
        row2.addStretch(1)
        b_tour = PushButton("Tour jetzt starten")
        b_tour.clicked.connect(self._start_tour)
        row2.addWidget(b_tour)
        c2.addLayout(row2)

        c3 = card("Papierkorb")
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Aufbewahrung gelöschter Schriften (Tage):"))
        self.days = FSpinBox()
        self.days.setRange(1, 365)
        self.days.valueChanged.connect(self._on_days)
        row3.addWidget(self.days)
        row3.addStretch(1)
        c3.addLayout(row3)

        c4 = card("Vorschau")
        row4 = QHBoxLayout()
        self.sample = QLineEdit()
        self.sample.setPlaceholderText("Beispieltext für die Kacheln…")
        row4.addWidget(self.sample, 1)
        b_apply = PushButton("Übernehmen")
        b_apply.clicked.connect(self._on_sample)
        row4.addWidget(b_apply)
        c4.addLayout(row4)

        outer.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        s = self.main.settings
        for w in (self.theme_combo, self.tutorial_switch, self.days):
            w.blockSignals(True)
        self.theme_combo.setCurrentIndex(
            1 if s.get("theme") == "dark" else 0)
        self.tutorial_switch.setChecked(
            bool(s.get("tutorial_enabled", True)))
        self.days.setValue(int(s.get("trash_days", 30) or 30))
        self.sample.setText(s.get("sample_text", ""))
        for w in (self.theme_combo, self.tutorial_switch, self.days):
            w.blockSignals(False)

    def _on_theme(self, text: str) -> None:
        self.main.set_app_theme("dark" if text == "Dunkel" else "light")

    def _on_tutorial(self, checked: bool) -> None:
        self.main.settings["tutorial_enabled"] = bool(checked)
        core.save_settings(self.main.settings)

    def _on_days(self, value: int) -> None:
        self.main.settings["trash_days"] = int(value)
        core.TRASH_RETENTION_DAYS = int(value)
        core.save_settings(self.main.settings)

    def _on_sample(self) -> None:
        text = self.sample.text().strip()
        self.main.settings["sample_text"] = text
        core.save_settings(self.main.settings)
        self.main.sample_edit.setText(text or DEFAULT_SAMPLE)
        self.main.model.set_sample(text or DEFAULT_SAMPLE,
                                   self.main.sample_px.value())

    def _start_tour(self) -> None:
        self.main.switchTo(self.main.library_page)
        self.main.start_tour()


class AboutPage(QWidget):
    """Über-Seite mit Logo, Version und Kontakt-Links."""

    def __init__(self, main) -> None:
        super().__init__()
        self.setObjectName("aboutPage")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 20)
        head = QHBoxLayout()
        icon_path = _resource_path("FontManager.ico")
        if os.path.isfile(icon_path):
            logo = QLabel()
            logo.setPixmap(QIcon(icon_path).pixmap(84, 84))
            head.addWidget(logo)
        head.addWidget(QLabel(
            f"<h2 style='margin:0'>FontManager {APP_VERSION}</h2>"
            f"<p>Font-Verwaltung für Windows 11<br>"
            f"von <b>Kopfsalto</b></p>"))
        head.addStretch(1)
        lay.addLayout(head)
        card = CardWidget(self)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 14)
        for icon_name, html in (
                ("camera", 'Instagram: <a href='
                 '"https://www.instagram.com/kopfsalto">Kopfsalto</a>'),
                ("gamepad", 'Twitch: <a href='
                 '"https://www.twitch.tv/kopfsalto1337">kopfsalto1337</a>'),
                ("cup", 'Ko-Fi: <a href="https://ko-fi.com/Kopfsalto">'
                 'Kopfsalto</a>'),
                ("mail", 'Support: <a href="mailto:mail@kopfsalto.de">'
                 'mail@kopfsalto.de</a>')):
            row = QHBoxLayout()
            ic = QLabel()
            ic.setPixmap(make_icon(icon_name).pixmap(18, 18))
            ic.setFixedWidth(26)
            lk = QLabel(html)
            lk.setOpenExternalLinks(True)
            row.addWidget(ic)
            row.addWidget(lk)
            row.addStretch(1)
            cl.addLayout(row)
        lay.addWidget(card)
        note = QLabel(
            "Font-Quellen: Google Fonts, Fontsource, Fontshare und "
            "Font Squirrel — ausschließlich frei lizenzierte Schriften. "
            "Windows-11-Standardschriften sind in diesem Tool fest "
            "geschützt. UI auf Basis von PySide6-Fluent-Widgets "
            "(GPLv3, nicht-kommerzielle Nutzung).")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch(1)


class SplashOverlay(QWidget):
    """Erststart-Animation in voller Anwendungsgröße — als Overlay IM
    Hauptfenster (kein eigenes Fenster mehr → kann keine Eingaben
    blockieren). Logo-Zoom, „Willkommen", Name + Version, Fade-out."""
    finished = Signal()

    def __init__(self, window, icon_path: str) -> None:
        super().__init__(window)
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        from PySide6.QtCore import (QPropertyAnimation, QEasingCurve,
                                    QSequentialAnimationGroup,
                                    QParallelAnimationGroup,
                                    QVariantAnimation)
        self._win = window
        self._bg_alpha = 255
        self._done_called = False
        self.setGeometry(window.rect())
        window.installEventFilter(self)

        lay = QVBoxLayout(self)
        lay.addStretch(3)
        self.logo = QLabel(alignment=Qt.AlignCenter)
        self._logo_icon = QIcon(icon_path) if os.path.isfile(icon_path) \
            else None
        lay.addWidget(self.logo)
        lay.addSpacing(14)
        self.lbl_welcome = QLabel("Willkommen", alignment=Qt.AlignCenter)
        self.lbl_welcome.setStyleSheet(
            f"font-size:40px;font-weight:800;color:{THEME['text']};"
            f"background:transparent;")
        lay.addWidget(self.lbl_welcome)
        self.lbl_name = QLabel(
            f"FontManager <span style='color:{THEME['accent']}'>"
            f"{APP_VERSION}</span> by Kopfsalto",
            alignment=Qt.AlignCenter)
        self.lbl_name.setStyleSheet(
            f"font-size:17px;color:{THEME['sub']};background:transparent;")
        lay.addWidget(self.lbl_name)
        lay.addStretch(4)

        self._effects = []
        for w in (self.logo, self.lbl_welcome, self.lbl_name):
            eff = QGraphicsOpacityEffect(w)
            eff.setOpacity(0.0)
            w.setGraphicsEffect(eff)
            self._effects.append(eff)

        def fade(eff, start_v, end_v, ms=340):
            a = QPropertyAnimation(eff, b"opacity", self)
            a.setDuration(ms)
            a.setStartValue(start_v)
            a.setEndValue(end_v)
            a.setEasingCurve(QEasingCurve.OutCubic)
            return a

        zoom = QVariantAnimation(self)
        zoom.setDuration(650)
        zoom.setStartValue(64)
        zoom.setEndValue(160)
        zoom.setEasingCurve(QEasingCurve.OutBack)
        zoom.valueChanged.connect(self._set_logo_size)

        intro = QParallelAnimationGroup(self)
        intro.addAnimation(zoom)
        intro.addAnimation(fade(self._effects[0], 0.0, 1.0, 500))

        bg_out = QVariantAnimation(self)
        bg_out.setDuration(480)
        bg_out.setStartValue(255)
        bg_out.setEndValue(0)
        bg_out.setEasingCurve(QEasingCurve.InCubic)
        bg_out.valueChanged.connect(self._set_bg_alpha)

        outro = QParallelAnimationGroup(self)
        outro.addAnimation(bg_out)
        for eff in self._effects:
            outro.addAnimation(fade(eff, 1.0, 0.0, 480))

        self._seq = QSequentialAnimationGroup(self)
        self._seq.addPause(150)
        self._seq.addAnimation(intro)
        self._seq.addPause(100)
        self._seq.addAnimation(fade(self._effects[1], 0.0, 1.0))
        self._seq.addPause(80)
        self._seq.addAnimation(fade(self._effects[2], 0.0, 1.0))
        self._seq.addPause(1050)
        self._seq.addAnimation(outro)
        self._seq.finished.connect(self._done)
        self._started = False
        self.show()   # wird zusammen mit dem Hauptfenster sichtbar

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self.raise_()
            self._seq.start()

    def _set_logo_size(self, px) -> None:
        if self._logo_icon is not None:
            self.logo.setPixmap(self._logo_icon.pixmap(int(px), int(px)))

    def _set_bg_alpha(self, a) -> None:
        self._bg_alpha = int(a)
        self.update()

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QLinearGradient, QRadialGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        top = QColor(THEME["win"]); top.setAlpha(self._bg_alpha)
        bot = QColor(THEME["stripe"]); bot.setAlpha(self._bg_alpha)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bot)
        p.fillRect(self.rect(), grad)
        glow = QColor(THEME["accent"])
        glow.setAlpha(int(38 * self._bg_alpha / 255))
        rg = QRadialGradient(self.rect().center(),
                             max(220, self.width() // 3))
        rg.setColorAt(0.0, glow)
        transparent = QColor(0, 0, 0, 0)
        rg.setColorAt(1.0, transparent)
        p.setPen(Qt.NoPen)
        p.setBrush(rg)
        p.drawRect(self.rect())
        p.end()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._win and event.type() in (QEvent.Resize,
                                                 QEvent.WindowStateChange):
            self.setGeometry(self._win.rect())
        return False

    def mousePressEvent(self, event) -> None:
        event.accept()
        self._seq.stop()
        self._done()

    def _done(self) -> None:
        if self._done_called:
            return
        self._done_called = True
        try:
            self._win.removeEventFilter(self)
        except RuntimeError:
            pass
        self.close()
        self.deleteLater()
        self.finished.emit()


class SetupDialog(QDialog):
    """Kleines Ersteinrichtungs-Setup: Design (Live-Vorschau),
    Tutorial ja/nein und die wichtigsten Einstellungen."""

    def __init__(self, settings: dict, icon_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ersteinrichtung")
        self.setModal(True)
        self.setFixedWidth(460)
        self._settings = settings
        lay = QVBoxLayout(self)

        head = QHBoxLayout()
        if os.path.isfile(icon_path):
            logo = QLabel()
            logo.setPixmap(QIcon(icon_path).pixmap(56, 56))
            head.addWidget(logo)
        head.addWidget(QLabel(
            f"<b style='font-size:16px'>Kurzes Setup</b><br>"
            f"<span style='color:{THEME['sub']}'>FontManager "
            f"{APP_VERSION} by Kopfsalto — dauert 10 Sekunden.</span>"))
        head.addStretch(1)
        lay.addLayout(head)

        gb_design = QGroupBox("Design")
        gd = QHBoxLayout(gb_design)
        self.rb_light = QRadioButton("Hell")
        self.rb_light.setIcon(make_icon("sun"))
        self.rb_dark = QRadioButton("Dunkel")
        self.rb_dark.setIcon(make_icon("moon"))
        (self.rb_dark if settings.get("theme") == "dark"
         else self.rb_light).setChecked(True)
        self.rb_light.toggled.connect(self._preview_theme)
        gd.addWidget(self.rb_light)
        gd.addWidget(self.rb_dark)
        gd.addStretch(1)
        lay.addWidget(gb_design)

        gb_tour = QGroupBox("Tutorial")
        gt = QVBoxLayout(gb_tour)
        self.rb_tour_yes = QRadioButton(
            "Ja, nach dem Setup die kurze Tour zeigen (empfohlen)")
        self.rb_tour_yes.setIcon(make_icon("sparkle"))
        self.rb_tour_no = QRadioButton("Nein, direkt loslegen")
        self.rb_tour_yes.setChecked(True)
        gt.addWidget(self.rb_tour_yes)
        gt.addWidget(self.rb_tour_no)
        lay.addWidget(gb_tour)

        gb_misc = QGroupBox("Wichtige Einstellungen")
        gm = QVBoxLayout(gb_misc)
        row = QHBoxLayout()
        row.addWidget(QLabel("Papierkorb-Aufbewahrung (Tage):"))
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(int(settings.get("trash_days", 30) or 30))
        row.addWidget(self.days)
        row.addStretch(1)
        gm.addLayout(row)
        gm.addWidget(QLabel("Beispieltext für die Vorschau-Kacheln:"))
        self.sample = QLineEdit(settings.get("sample_text", "")
                                or DEFAULT_SAMPLE)
        gm.addWidget(self.sample)
        gm.addWidget(QLabel(
            f"<span style='color:{THEME['sub']}'>Alles später änderbar "
            f"unter „Einstellungen“. Windows-11-Standardschriften sind "
            f"immer geschützt.</span>"))
        lay.addWidget(gb_misc)

        b_go = QPushButton("Los geht's  ✓")
        b_go.setDefault(True)
        b_go.setStyleSheet(
            f"QPushButton{{background:{THEME['accent']};color:#fff;"
            f"font-weight:600;border:none;padding:9px;}}"
            f"QPushButton:hover{{background:{THEME['accent_dark']};"
            f"color:#fff;}}")
        b_go.clicked.connect(self.accept)
        lay.addWidget(b_go)

    def _preview_theme(self) -> None:
        apply_theme(QApplication.instance(),
                    "light" if self.rb_light.isChecked() else "dark")

    # -- Ergebnisse
    def theme(self) -> str:
        return "light" if self.rb_light.isChecked() else "dark"

    def want_tour(self) -> bool:
        return self.rb_tour_yes.isChecked()

    def trash_days(self) -> int:
        return self.days.value()

    def sample_text(self) -> str:
        return self.sample.text().strip()


class TourOverlay(QWidget):
    """Abschaltbarer Tutorial-Modus: dunkelt das Fenster ab, hebt das
    aktuelle Ziel-Element hervor und erklärt es in einer Sprechblase."""

    def __init__(self, window, steps, on_done=None) -> None:
        super().__init__(window)
        self._win = window
        self.steps = steps          # [(lambda->widget, titel, text), …]
        self.i = 0
        self.on_done = on_done
        self.setGeometry(window.rect())
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        # Fenstergrößen-Änderungen (z. B. Maximieren) live mitverfolgen —
        # sonst bleibt ein "dunkler Streifen" der alten Größe stehen.
        window.installEventFilter(self)

        self.bubble = QFrame(self)
        self.bubble.setStyleSheet(
            f"QFrame{{background:{THEME['pane']};border:1px solid "
            f"{THEME['accent']};border-radius:12px;}}"
            f"QLabel{{border:none;background:transparent;}}")
        bl = QVBoxLayout(self.bubble)
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet(
            f"font-weight:700;color:{THEME['accent_dark']};")
        self.lbl_text = QLabel()
        self.lbl_text.setWordWrap(True)
        row = QHBoxLayout()
        self.b_skip = QPushButton("Tour beenden")
        self.b_skip.clicked.connect(self._finish)
        self.b_next = QPushButton("Weiter →")
        self.b_next.clicked.connect(self._next)
        row.addWidget(self.b_skip)
        row.addStretch(1)
        row.addWidget(self.b_next)
        bl.addWidget(self.lbl_title)
        bl.addWidget(self.lbl_text)
        bl.addLayout(row)
        self.bubble.setFixedWidth(340)

        self.show()
        self.raise_()
        self._layout_step()

    # -- Ablauf
    def _target_rect(self) -> QRect | None:
        getter = self.steps[self.i][0]
        try:
            w = getter()
        except Exception:
            w = None
        if w is None:
            return None
        from PySide6.QtCore import QPoint
        return QRect(w.mapTo(self._win, QPoint(0, 0)), w.size())

    def _reveal_target(self) -> None:
        """Klappt eine eingeklappte Ziel-Sektion auf und scrollt sie in
        einer umgebenden ScrollArea in Sicht."""
        try:
            w = self.steps[self.i][0]()
        except Exception:
            return
        if w is None:
            return
        # AUCH eingeklappte Eltern-Sektionen öffnen (Ziel kann ein
        # Kind-Widget wie das Vorschautext-Feld sein)
        node = w
        while node is not None:
            if isinstance(node, CollapsibleSection) \
                    and not node.is_expanded():
                node.expand_instant()
            node = node.parentWidget()
        QApplication.processEvents()     # Layout setzen lassen
        parent = w.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if isinstance(parent, QScrollArea):
            parent.ensureWidgetVisible(w, 24, 24)
            QApplication.processEvents()

    def _layout_step(self) -> None:
        self._reveal_target()
        _g, title, text = self.steps[self.i]
        self.lbl_title.setText(f"{title}  ({self.i + 1}/{len(self.steps)})")
        self.lbl_text.setText(text)
        self.b_next.setText("Fertig ✓" if self.i == len(self.steps) - 1
                            else "Weiter →")
        self.bubble.adjustSize()
        target = self._target_rect()
        bw, bh = self.bubble.width(), self.bubble.height()
        if target is None:
            x = (self.width() - bw) // 2
            y = (self.height() - bh) // 2
        else:
            hole = target.adjusted(-6, -6, 6, 6)
            x = min(max(8, hole.left()), self.width() - bw - 8)
            candidates = [
                (x, hole.bottom() + 14),                       # darunter
                (x, hole.top() - bh - 14),                     # darüber
                (hole.right() + 14, max(8, hole.top())),       # rechts
                (hole.left() - bw - 14, max(8, hole.top())),   # links
            ]
            x, y = candidates[0]
            for cx, cy in candidates:
                r = QRect(int(cx), int(cy), bw, bh)
                if (r.top() >= 8 and r.bottom() <= self.height() - 8
                        and r.left() >= 8
                        and r.right() <= self.width() - 8
                        and not r.intersects(hole)):
                    x, y = cx, cy
                    break
            else:
                # Notfall: unten mittig, garantiert ohne Überlappung
                x = (self.width() - bw) // 2
                y = self.height() - bh - 16
        self.bubble.move(int(x), int(y))
        self.update()

    def _next(self) -> None:
        if self.i >= len(self.steps) - 1:
            self._finish()
            return
        self.i += 1
        self._layout_step()

    def _finish(self) -> None:
        try:
            self._win.removeEventFilter(self)
        except RuntimeError:
            pass
        self.close()
        self.deleteLater()
        if self.on_done:
            self.on_done()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._win and event.type() in (QEvent.Resize,
                                                 QEvent.WindowStateChange):
            self.setGeometry(self._win.rect())
            self._layout_step()
        return False

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._finish()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Right,
                             Qt.Key_Space):
            self._next()
        else:
            super().keyPressEvent(event)

    # -- Darstellung / Eingabe
    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QPainterPath
        from PySide6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dim = QColor(0, 0, 0, 150)
        target = self._target_rect()
        if target is None:
            p.fillRect(self.rect(), dim)
        else:
            # Abdunkelung als Pfad UM das Ziel herum — das Ziel selbst
            # bleibt unangetastet sichtbar (kein Composition-Trick).
            hole = QRectF(target.adjusted(-6, -6, 6, 6))
            full = QPainterPath()
            full.addRect(QRectF(self.rect()))
            cut = QPainterPath()
            cut.addRoundedRect(hole, 10, 10)
            p.fillPath(full.subtracted(cut), dim)
            p.setPen(QPen(QColor(THEME["accent"]), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(hole, 10, 10)
        p.end()

    def mousePressEvent(self, event) -> None:
        event.accept()   # Klicks nicht zum Fenster durchlassen

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_step()


class CollapsibleSection(QWidget):
    """Aufklappbare Sidebar-Sektion mit animiertem Ein-/Ausklappen."""

    def __init__(self, title: str, expanded: bool = True,
                 on_toggle=None, icon: QIcon | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QSize
        self._title = title
        self._expanded = expanded
        self._on_toggle = on_toggle

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        self.header = QPushButton()
        self.header.setObjectName("sectionHeader")
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.clicked.connect(self.toggle)
        if icon is not None:
            self.header.setIcon(icon)
            self.header.setIconSize(QSize(17, 17))
        v.addWidget(self.header)

        self.body = QFrame()
        self.body.setObjectName("sectionBody")
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(10, 8, 10, 10)
        self.body_lay.setSpacing(6)
        v.addWidget(self.body)

        self._anim = QPropertyAnimation(self.body, b"maximumHeight", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._after_anim)
        self._apply_state(initial=True)

    def add(self, w: QWidget) -> QWidget:
        self.body_lay.addWidget(w)
        return w

    def add_layout(self, lay) -> None:
        self.body_lay.addLayout(lay)

    def is_expanded(self) -> bool:
        return self._expanded

    def expand_instant(self) -> None:
        """Sofort (ohne Animation) aufklappen — z. B. für die Tour."""
        if self._expanded:
            return
        self._expanded = True
        if self._on_toggle:
            self._on_toggle(True)
        self._apply_state(initial=True)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        if self._on_toggle:
            self._on_toggle(self._expanded)
        self._apply_state()

    def _apply_state(self, initial: bool = False) -> None:
        self.header.setText(("▾  " if self._expanded else "▸  ")
                            + self._title)
        if initial:
            self.body.setVisible(self._expanded)
            self.body.setMaximumHeight(
                16777215 if self._expanded else 0)
            return
        self._anim.stop()
        if self._expanded:
            self.body.setVisible(True)
            self.body.setMaximumHeight(0)
            self._anim.setStartValue(0)
            self._anim.setEndValue(self.body.sizeHint().height())
        else:
            self._anim.setStartValue(self.body.height())
            self._anim.setEndValue(0)
        self._anim.start()

    def _after_anim(self) -> None:
        if self._expanded:
            self.body.setMaximumHeight(16777215)
        else:
            self.body.setVisible(False)


# ------------------------------------------------------------ Hauptfenster

def _resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS",
                   os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


class MainWindow(MSFluentWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = core.load_settings()
        core.TRASH_RETENTION_DAYS = int(
            self.settings.get("trash_days", 30) or 30)
        self.setWindowTitle(f"FontManager {APP_VERSION} by Kopfsalto")
        icon_path = _resource_path("FontManager.ico")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._restore_geometry()

        self.model = FontListModel()
        self.proxy = FontFilterProxy()
        self.proxy.setSourceModel(self.model)
        self.meta_thread: MetaScanThread | None = None

        self.view = QListView()
        self.view.setModel(self.proxy)
        self.view.setItemDelegate(TileDelegate(self.view))
        self.view.setViewMode(QListView.IconMode)
        self.view.setResizeMode(QListView.Adjust)
        self.view.setUniformItemSizes(True)
        self.view.setLayoutMode(QListView.Batched)
        self.view.setBatchSize(120)
        self.view.setSpacing(6)
        self.view.setSelectionMode(QListView.ExtendedSelection)
        self.view.setMouseTracking(True)

        self.library_page = self._build_central()
        self.library_page.setObjectName("libraryPage")
        self.settings_page = SettingsPage(self)
        self.about_page = AboutPage(self)
        self.addSubInterface(self.library_page, FIF.FONT, "Bibliothek")
        self.addSubInterface(self.settings_page, FIF.SETTING,
                             "Einstellungen",
                             position=NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.about_page, FIF.INFO, "Über",
                             position=NavigationItemPosition.BOTTOM)
        self.model.checked_changed.connect(self._update_status)
        QShortcut(QKeySequence(Qt.Key_Space), self.view,
                  activated=self._toggle_selection_checked)

        purged = core.purge_expired_trash()
        if purged:
            self.show_status(
                f"Papierkorb: {purged} alte Einträge endgültig entfernt.",
                8000)

        # Feature 4: Registry-Backup beim allerersten Start
        QTimer.singleShot(1500, self._startup_backup)
        saved_sample = self.settings.get("sample_text", "").strip()
        if saved_sample:
            self.sample_edit.setText(saved_sample)
            self.model.set_sample(saved_sample, self.sample_px.value())
        if not self.settings.get("welcome_shown"):
            self._show_welcome()   # Overlay deckt das Fenster ab Frame 1 ab
        self._reload_fonts()

    def _show_welcome(self) -> None:
        # Erststart: Vollflächen-Animation im Fenster, danach das
        # kurze Setup (Design, Tutorial, wichtige Einstellungen).
        self._splash = SplashOverlay(self,
                                     _resource_path("FontManager.ico"))
        self._splash.finished.connect(self._show_setup)

    def _show_setup(self) -> None:
        dlg = SetupDialog(self.settings,
                          _resource_path("FontManager.ico"), self)
        dlg.exec()
        self.settings["welcome_shown"] = True
        self.settings["theme"] = dlg.theme()
        self.settings["trash_days"] = dlg.trash_days()
        sample = dlg.sample_text()
        if sample and sample != DEFAULT_SAMPLE:
            self.settings["sample_text"] = sample
            self.sample_edit.setText(sample)
            self.model.set_sample(sample, self.sample_px.value())
        core.save_settings(self.settings)
        core.TRASH_RETENTION_DAYS = int(self.settings["trash_days"])
        self.set_app_theme(self.settings["theme"])
        self.settings_page.refresh()
        if dlg.want_tour():
            self.start_tour()

    def start_tour(self) -> None:
        if not self.settings.get("tutorial_enabled", True):
            return
        steps = [
            (lambda: self.search, "Suchen",
             "Hier findest du jede Schrift — nach Name, Datei, Hersteller "
             "oder Tag. Die Filter darunter grenzen weiter ein."),
            (lambda: self.filter_status, "Status-Filter",
             "Zeigt z. B. nur löschbare, deaktivierte oder defekte "
             "Schriften. Geschützte Windows-Schriften erkennst du am "
             "roten Badge."),
            (lambda: self.sample_edit, "Eigener Vorschautext",
             "Tipp deinen eigenen Text ein — alle Kacheln rendern ihn "
             "in der jeweiligen Schrift."),
            (lambda: self.view, "Die Kachelansicht",
             "Jede Kachel = eine Schrift. Checkbox links oben markiert "
             "sie für Aktionen; Strg/Shift + Leertaste markiert viele "
             "auf einmal. Tooltip zeigt alle Details."),
            (lambda: self.gb_act, "Aktionen",
             "Deaktivieren (Datei bleibt, jederzeit zurückholbar) oder "
             "in den Papierkorb — dort liegen Schriften "
             f"{core.TRASH_RETENTION_DAYS} Tage als Sicherheitsnetz."),
            (lambda: self.gb_io, "Neue Fonts",
             "Aus vier freien Quellen laden (installieren oder nur "
             "temporär aktivieren), als ZIP exportieren oder per Bulk "
             "installieren."),
            (lambda: self.gb_tools, "Werkzeuge",
             "Alle Extras gesammelt: Duplikate, Aufräumen, PDF-Katalog "
             "und die Tour. Daneben „Papierkorb & Sicherung“. "
             "Einstellungen und Über findest du links in der "
             "Navigationsleiste."),
        ]
        old = getattr(self, "_tour", None)
        if old is not None:
            try:
                old._finish()
            except RuntimeError:
                pass
        self._tour = TourOverlay(self, steps)
        self._tour.setFocus()

    # ---- Fenster-Geometrie ---------------------------------------------
    def _restore_geometry(self) -> None:
        """Erststart: zentriert auf dem Bildschirm. Danach: exakt die
        zuletzt genutzte Position/Größe (inkl. Maximiert-Zustand)."""
        from PySide6.QtCore import QByteArray
        saved = self.settings.get("win_geometry", "")
        restored = False
        if saved:
            try:
                restored = self.restoreGeometry(
                    QByteArray.fromBase64(saved.encode("ascii")))
            except Exception:
                restored = False
        # Sicherstellen, dass das Fenster auf einem sichtbaren Monitor
        # liegt (z. B. nach Abstecken eines Zweitmonitors)
        if restored:
            on_screen = any(
                s.availableGeometry().intersects(self.frameGeometry())
                for s in QApplication.screens())
            if not on_screen:
                restored = False
        if not restored:
            self._center_window()

    def _center_window(self) -> None:
        scr = QApplication.primaryScreen().availableGeometry()
        w = min(1320, int(scr.width() * 0.9))
        h = min(820, int(scr.height() * 0.9))
        self.resize(w, h)
        self.move(scr.center().x() - w // 2, scr.center().y() - h // 2)
        # Finale Zentrierung nach dem ersten Anzeigen — erst dann greifen
        # Mindestgrößen des Fluent-Fensters (siehe showEvent).
        self._needs_center = True

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if getattr(self, "_needs_center", False):
            self._needs_center = False
            scr = QApplication.primaryScreen().availableGeometry()
            fg = self.frameGeometry()
            x = scr.center().x() - fg.width() // 2
            y = scr.center().y() - fg.height() // 2
            self.move(max(scr.left(), x), max(scr.top(), y))

    def _save_geometry(self) -> None:
        try:
            data = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self.settings["win_geometry"] = data
            core.save_settings(self.settings)
        except Exception:
            pass

    # ---- Aufbau -------------------------------------------------------
    def _build_central(self) -> QWidget:
        outer = QWidget()
        v = QVBoxLayout(outer)
        v.setContentsMargins(8, 4, 8, 8)
        v.addWidget(self._build_command_bar())
        if not core.is_admin():
            banner = QFrame()
            banner.setStyleSheet(
                "QFrame{background:#FFF4E5;border:1px solid #E8B96A;"
                "border-radius:6px;} QLabel{border:none;}")
            bl = QHBoxLayout(banner)
            warn = QLabel()
            warn.setPixmap(make_icon("warn", "#b3720a").pixmap(20, 20))
            bl.addWidget(warn)
            bl.addWidget(QLabel(
                "Eingeschränkter Modus: Ohne Adminrechte kannst du nur "
                "deine eigenen Schriften verwalten."))
            btn = PushButton("Als Administrator neu starten")
            btn.clicked.connect(self._restart_admin)
            bl.addWidget(btn)
            bl.addStretch(1)
            v.addWidget(banner)
        h = QHBoxLayout()
        h.addWidget(self._build_sidebar())
        h.addWidget(self.view, 1)
        v.addLayout(h, 1)
        srow = QHBoxLayout()
        self.busy_ring = IndeterminateProgressRing()
        self.busy_ring.setFixedSize(16, 16)
        try:
            self.busy_ring.setStrokeWidth(3)
        except Exception:
            pass
        self.busy_ring.hide()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        srow.addWidget(self.busy_ring)
        srow.addWidget(self.status_label, 1)
        v.addLayout(srow)
        return outer

    def _build_sidebar(self) -> QWidget:
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(2, 0, 10, 0)
        lay.setSpacing(8)
        saved = self.settings.get("sidebar", {})

        def section(title: str, key: str, default: bool,
                    icon_name: str = "check") -> CollapsibleSection:
            sec = CollapsibleSection(
                title, bool(saved.get(key, default)),
                on_toggle=lambda ex, k=key: self._remember_section(k, ex),
                icon=make_icon(icon_name))
            lay.addWidget(sec)
            return sec

        # ------------------------------------------- 1) Suche & Filter
        s1 = section("Suche && Filter", "filter", True, "search")
        self.search = SearchLineEdit()
        self.search.setPlaceholderText("Name, Datei, Hersteller, Tag…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        s1.add(self.search)

        def combo(sec: CollapsibleSection, label: str,
                  items: list) -> QComboBox:
            sec.add(QLabel(label))
            c = FComboBox()
            c.addItems(items)
            c.currentTextChanged.connect(self._apply_filter)
            sec.add(c)
            return c

        self.filter_status = combo(
            s1, "Status", ["Alle", "Löschbar", "Aktiv", "Deaktiviert",
                           "Geschützt", "Defekt"])
        self.filter_class = combo(s1, "Klassifikation", ["Alle"])
        self.filter_script = combo(s1, "Schriftsystem", ["Alle"])
        s1.add(QLabel("Hersteller"))
        self.filter_foundry = EditableComboBox()
        self.filter_foundry.addItems(["Alle"])
        try:      # EditableComboBox erbt nicht von QComboBox
            self.filter_foundry.setInsertPolicy(QComboBox.NoInsert)
            self.filter_foundry.completer().setCompletionMode(
                QCompleter.PopupCompletion)
            self.filter_foundry.completer().setFilterMode(Qt.MatchContains)
        except Exception:
            pass
        self.filter_foundry.currentTextChanged.connect(self._apply_filter)
        s1.add(self.filter_foundry)
        self.filter_tag = combo(s1, "Tag", ["Alle"])
        b_reset = PushButton("Filter zurücksetzen")
        b_reset.clicked.connect(self._reset_filters)
        s1.add(b_reset)

        # --------------------------------------- 2) Ansicht & Vorschau
        s2 = section("Ansicht && Vorschau", "view", False, "eye")
        s2.add(QLabel("Eigener Beispieltext"))
        self.sample_edit = QLineEdit(DEFAULT_SAMPLE)
        self.sample_edit.setPlaceholderText("Eigener Beispieltext…")
        self.sample_edit.returnPressed.connect(self._apply_sample)
        s2.add(self.sample_edit)
        row = QHBoxLayout()
        row.addWidget(QLabel("Größe:"))
        self.sample_px = FSpinBox()
        self.sample_px.setRange(14, 48)
        self.sample_px.setValue(28)
        row.addWidget(self.sample_px)
        b_apply = PushButton("Anwenden")
        b_apply.clicked.connect(self._apply_sample)
        row.addWidget(b_apply)
        s2.add_layout(row)
        s2.add(QLabel("Sortierung"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(FontFilterProxy.SORT_KEYS)
        self.sort_combo.currentTextChanged.connect(self._apply_sort)
        s2.add(self.sort_combo)

        # -------------------------------------- 3) Auswahl & Aktionen
        s3 = section("Auswahl && Aktionen", "actions", True, "check")
        b1 = PushButton("Alle löschbaren markieren")
        b1.setToolTip("Berücksichtigt die aktuellen Filter")
        b1.clicked.connect(self._check_all_deletable)
        b2 = PushButton("Markierung aufheben")
        b2.clicked.connect(
            lambda: self.model.set_checked_bulk(self.model.entries, False))
        b3 = PushButton("Markierte vergleichen…")
        b3.clicked.connect(self._compare_checked)
        b_tag1 = PushButton(FIF.TAG, "Tag hinzufügen…")
        b_tag1.clicked.connect(self._tag_add)
        b_tag2 = PushButton(FIF.TAG, "Tag entfernen…")
        b_tag2.clicked.connect(self._tag_remove)
        hint = QLabel("Strg/Shift auswählen, Leertaste markiert.")
        hint.setStyleSheet(f"color:{THEME['sub']};")
        for w in (b1, b2, b3, b_tag1, b_tag2, hint):
            s3.add(w)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{THEME['border']};")
        s3.add(line)
        b_deact = PushButton("Deaktivieren")
        b_deact.setToolTip("Font verschwindet aus allen Programmen; die "
                           "Datei bleibt erhalten und ist jederzeit "
                           "reaktivierbar.")
        b_deact.clicked.connect(self._deactivate_checked)
        b_react = PushButton("Reaktivieren")
        b_react.clicked.connect(self._reactivate_checked)
        b_del = PrimaryPushButton("In den Papierkorb…")
        b_del.setIcon(make_icon("trash", "#ffffff"))
        b_del.clicked.connect(self._delete_checked)
        for w in (b_deact, b_react, b_del):
            s3.add(w)

        # ------------------------------------------ 4) Import & Export
        s4 = section("Import && Export", "io", False, "globe")
        b_dl = PushButton("Aus dem Internet laden…")
        b_dl.clicked.connect(self._download_fonts)
        b_exp = PushButton("Fonts exportieren (ZIP)…")
        b_exp.clicked.connect(self._export_fonts)
        b_imp = PushButton("Fonts installieren…")
        b_imp.clicked.connect(self._install_fonts)
        b_tmp = PushButton("Fonts temporär laden…")
        b_tmp.setToolTip("Nur für diese Windows-Sitzung aktivieren — "
                         "ohne Installation, nach Neustart wieder weg.")
        b_tmp.clicked.connect(self._temp_load)
        for w in (b_dl, b_exp, b_imp, b_tmp):
            s4.add(w)

        # ------------------------------------------------ 5) Werkzeuge
        s5 = section("Werkzeuge", "tools", False, "wrench")
        for icon, text, fn in (
                (FIF.COPY, "Duplikate suchen…", self._find_duplicates),
                (FIF.BROOM, "Einträge ohne Datei aufräumen…",
                 self._cleanup_orphans),
                (FIF.DOCUMENT, "PDF-Musterkatalog erstellen…",
                 self._pdf_catalog),
                (FIF.HISTORY, "Schrift-Infos neu einlesen",
                 self._rescan_meta),
                (FIF.CLOSE, "Temporäre Fonts entladen",
                 self._temp_unload),
                (FIF.UPDATE, "Font-Anzeige-Cache erneuern (Admin)",
                 self._rebuild_font_cache),
                (FIF.EDUCATION, "Tour (Tutorial) starten",
                 self.start_tour)):
            b = PushButton(icon, text)
            b.clicked.connect(fn)
            s5.add(b)

        # ------------------------------------ 6) Papierkorb & Sicherung
        s6 = section("Papierkorb && Sicherung", "backup", False, "shield")
        for icon, text, fn in (
                (FIF.DELETE, "Papierkorb anzeigen…", self._open_trash),
                (FIF.SAVE, "Schriftenliste sichern", self._backup_now),
                (FIF.FOLDER, "Sicherungs-Ordner öffnen",
                 self._open_backup_dir)):
            b = PushButton(icon, text)
            b.clicked.connect(fn)
            s6.add(b)

        self.gb_act, self.gb_io = s3, s4   # Ziele für die Tour
        self.gb_tools = s5
        lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(300)
        scroll.setObjectName("sidebar")
        self.sidebar = scroll          # Breite skaliert in resizeEvent mit
        return scroll

    def _remember_section(self, key: str, expanded: bool) -> None:
        self.settings.setdefault("sidebar", {})[key] = expanded
        core.save_settings(self.settings)

    def _build_command_bar(self) -> CommandBar:
        bar = CommandBar(self)
        try:
            bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        except Exception:
            pass
        bar.addAction(Action(FIF.SYNC, "Neu laden",
                             triggered=self._reload_fonts))
        self.command_bar = bar
        return bar

    def _open_trash(self) -> None:
        TrashDialog(self).exec()

    def _open_backup_dir(self) -> None:
        os.makedirs(core.REG_BACKUP_DIR, exist_ok=True)
        os.startfile(core.REG_BACKUP_DIR)

    def _set_busy(self, busy: bool) -> None:
        ring = getattr(self, "busy_ring", None)
        if ring is not None:
            ring.setVisible(busy)

    def _show_tip(self, title: str, content: str) -> StateToolTip:
        tip = StateToolTip(title, content, self)
        tip.show()
        tip.move(max(8, self.width() - tip.width() - 24), 46)
        return tip

    def _state_tip(self, title: str, content: str) -> StateToolTip:
        tip = StateToolTip(title, content, self)
        tip.adjustSize()
        tip.move(max(20, self.width() - tip.width() - 30), 70)
        tip.show()
        tip.raise_()
        return tip

    def show_status(self, msg: str, timeout: int = 0) -> None:
        label = getattr(self, "status_label", None)
        if label is None:
            return
        label.setText(msg)
        if timeout:
            QTimer.singleShot(timeout, self._update_status)

    def set_app_theme(self, name: str) -> None:
        self.settings["theme"] = name
        core.save_settings(self.settings)
        apply_theme(QApplication.instance(), name)
        self.view.viewport().update()

    # ---- Filter / Vorschau / Auswahl ----------------------------------
    def _apply_filter(self) -> None:
        self.proxy.search = self.search.text().strip().lower()
        self.proxy.status_filter = self.filter_status.currentText()
        self.proxy.class_filter = self.filter_class.currentText() or "Alle"
        self.proxy.script_filter = self.filter_script.currentText() or "Alle"
        self.proxy.tag_filter = self.filter_tag.currentText() or "Alle"
        f = self.filter_foundry.currentText().strip()
        self.proxy.foundry_filter = f if f else "Alle"
        self.proxy.invalidateFilter()
        self._update_status()

    def _reset_filters(self) -> None:
        self.search.clear()
        for c in (self.filter_status, self.filter_class,
                  self.filter_script, self.filter_foundry, self.filter_tag):
            c.setCurrentIndex(0)

    def _apply_sample(self) -> None:
        self.model.set_sample(self.sample_edit.text(),
                              self.sample_px.value())
        self.settings["sample_text"] = self.sample_edit.text().strip()
        core.save_settings(self.settings)
        self.show_status(
            "Vorschautext geändert — Kacheln werden neu gerendert "
            "(einmalig, danach aus dem Cache).", 6000)

    def _apply_sort(self, key: str) -> None:
        self.proxy.sort_key = key
        self.proxy.invalidate()
        self.proxy.sort(0)

    def _refresh_filter_values(self) -> None:
        def refill(cb: QComboBox, values: set) -> None:
            current = cb.currentText()
            cb.blockSignals(True)
            cb.clear()
            cb.addItems(["Alle"] + sorted(values, key=str.lower))
            idx = -1
            try:
                idx = cb.findText(current)
            except AttributeError:
                for i in range(cb.count()):
                    if cb.itemText(i) == current:
                        idx = i
                        break
            cb.setCurrentIndex(idx if idx >= 0 else 0)
            cb.blockSignals(False)

        classes, scripts, foundries, tags = set(), set(), set(), set()
        for e in self.model.entries:
            if e.classification:
                classes.add(e.classification)
            scripts.update(e.scripts)
            if e.foundry:
                foundries.add(e.foundry)
            tags.update(e.tags)
        refill(self.filter_class, classes)
        refill(self.filter_script, scripts)
        refill(self.filter_foundry, foundries)
        refill(self.filter_tag, tags)
        self._apply_filter()

    def _visible_entries(self) -> list:
        return [self.proxy.index(r, 0).data(EntryRole)
                for r in range(self.proxy.rowCount())]

    def _check_all_deletable(self) -> None:
        self.model.set_checked_bulk(
            [e for e in self._visible_entries() if not e.protected], True)

    def _toggle_selection_checked(self) -> None:
        entries = [i.data(EntryRole)
                   for i in self.view.selectionModel().selectedIndexes()]
        entries = [e for e in entries if not e.protected]
        if not entries:
            return
        target = not all(e.checked for e in entries)
        self.model.set_checked_bulk(entries, target)

    # ---- Laden / Scan --------------------------------------------------
    def _reload_fonts(self) -> None:
        self._stop_meta_thread()
        self._set_busy(True)
        self.show_status("Lade installierte Schriften…")
        old_tip = getattr(self, "_load_tip", None)
        if old_tip is not None:
            try:
                old_tip.close()
            except RuntimeError:
                pass
        self._load_tip = self._show_tip("Schriften werden geladen",
                                        "Liste wird eingelesen…")
        self.loader = LoaderThread()
        self.loader.loaded.connect(self._on_loaded)
        self.loader.start()

    @Slot(list)
    def _on_loaded(self, entries: list) -> None:
        tip = getattr(self, "_load_tip", None)
        if tip is not None:
            try:
                tip.setContent(f"{len(entries)} Schriften geladen")
                tip.setState(True)      # grüner Haken + Auto-Schließen
            except RuntimeError:
                pass
            self._load_tip = None
        self.model.set_entries(entries)
        self.proxy.sort(0)
        self._refresh_filter_values()
        self._update_status()
        self._start_meta_scan()

    def _start_meta_scan(self) -> None:
        self._stop_meta_thread()
        self.show_status("Analysiere Schrift-Infos im Hintergrund…")
        self.meta_thread = MetaScanThread(self.model.entries)
        self.meta_thread.progress.connect(
            lambda i, n: self.show_status(
                f"Analysiere Metadaten… {i}/{n}"))
        self.meta_thread.finished_scan.connect(self._on_meta_done)
        self.meta_thread.start()

    def _stop_meta_thread(self) -> None:
        if self.meta_thread is not None and self.meta_thread.isRunning():
            self.meta_thread.requestInterruption()
            self.meta_thread.wait(5000)
        self.meta_thread = None

    @Slot()
    def _on_meta_done(self) -> None:
        self._set_busy(False)
        self._refresh_filter_values()
        self.view.viewport().update()
        self._update_status()
        self.show_status("Metadaten-Scan abgeschlossen.", 5000)

    def _rescan_meta(self) -> None:
        try:
            os.remove(core.META_CACHE_PATH)
        except OSError:
            pass
        for e in self.model.entries:
            e.classification, e.scripts, e.foundry, e.broken = "", [], "", \
                False
        self._start_meta_scan()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Sidebar skaliert mit dem Fenster: ~23 % Breite, 300–420 px.
        sb = getattr(self, "sidebar", None)
        if sb is not None:
            sb.setFixedWidth(max(300, min(420, int(self.width() * 0.23))))

    def closeEvent(self, event) -> None:
        self._save_geometry()
        self._stop_meta_thread()
        core.temp_deactivate_all()
        super().closeEvent(event)

    def _update_status(self) -> None:
        es = self.model.entries
        total = len(es)
        prot = sum(1 for e in es if e.protected)
        deact = sum(1 for e in es if e.deactivated)
        broken = sum(1 for e in es if e.broken)
        checked = self.model.checked_entries()
        csize = sum(e.size_bytes for e in checked)
        temp = len(core.temp_active_paths())
        msg = (f"{total} Schriften · {prot} geschützt · {deact} deaktiviert"
               f" · {broken} defekt · markiert: {len(checked)} "
               f"({core.format_size(csize)}) · angezeigt: "
               f"{self.proxy.rowCount()}")
        if temp:
            msg += f" · temporär geladen: {temp}"
        self.show_status(msg)

    # ---- Aktionen ------------------------------------------------------
    def _run_action(self, func, entries, title: str) -> None:
        self.progress = QProgressDialog(title, None, 0, len(entries), self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setCancelButton(None)
        self.progress.setMinimumDuration(0)
        self.worker = ActionThread(func, entries)
        self.worker.progress.connect(
            lambda i, n, name: (self.progress.setValue(i),
                                self.progress.setLabelText(name)))
        self.worker.finished_with.connect(self._on_action_done)
        self.worker.start()

    def _deactivate_checked(self) -> None:
        entries = [e for e in self.model.checked_entries()
                   if not e.deactivated]
        if not entries:
            QMessageBox.information(self, "Keine Auswahl",
                                    "Keine aktiven Schriften markiert.")
            return
        rc = QMessageBox.question(
            self, "Schriften deaktivieren",
            f"{len(entries)} Schrift(en) deaktivieren? Dateien bleiben "
            f"erhalten, jederzeit reaktivierbar.\n(Bei gerade genutzten "
            f"Fonts spätestens nach Neustart wirksam.)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if rc == QMessageBox.Yes:
            self._run_action(core.deactivate_fonts, entries,
                             "Deaktiviere Schriften…")

    def _reactivate_checked(self) -> None:
        entries = [e for e in self.model.checked_entries() if e.deactivated]
        if not entries:
            QMessageBox.information(
                self, "Keine Auswahl",
                "Keine deaktivierten Schriften markiert.\n"
                "Tipp: Statusfilter „Deaktiviert“.")
            return
        self._run_action(core.reactivate_fonts, entries,
                         "Reaktiviere Schriften…")

    def _delete_checked(self) -> None:
        entries = self.model.checked_entries()
        if not entries:
            QMessageBox.information(self, "Keine Auswahl",
                                    "Keine löschbaren Schriften markiert.")
            return
        total = core.format_size(sum(e.size_bytes for e in entries))
        preview = "\n".join(f"  • {e.display_name}" for e in entries[:12])
        if len(entries) > 12:
            preview += f"\n  … und {len(entries) - 12} weitere"
        rc = QMessageBox.question(
            self, "In den Papierkorb verschieben",
            f"{len(entries)} Schrift(en) mit insgesamt {total} werden "
            f"deinstalliert und für {core.TRASH_RETENTION_DAYS} Tage in "
            f"den Papierkorb verschoben.\nWindows-11-Standardschriften "
            f"sind grundsätzlich ausgeschlossen.\n\n{preview}\n\n"
            f"Fortfahren?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if rc == QMessageBox.Yes:
            self._run_action(core.uninstall_fonts, entries,
                             "Deinstalliere Schriften…")

    @Slot(object)
    def _on_action_done(self, res) -> None:
        self.progress.setValue(self.progress.maximum())
        if res.ok and not (res.errors or res.skipped_protected
                           or res.pending_reboot):
            SuccessPopup(self, f"{len(res.ok)} Schrift(en) erfolgreich "
                               f"verarbeitet.")
            self._reload_fonts()
            return
        lines = [f"Erfolgreich: {len(res.ok)}"]
        if res.pending_reboot:
            lines.append(f"Gesperrt, wird beim NEUSTART verschoben: "
                         f"{len(res.pending_reboot)}")
        if res.skipped_protected:
            lines.append(f"Übersprungen (geschützt / bereits vorhanden): "
                         f"{len(res.skipped_protected)}")
        if res.errors:
            lines.append(f"Fehler: {len(res.errors)}")
            lines += [f"  • {n}: {m}" for n, m in res.errors[:8]]
        QMessageBox.information(self, "Ergebnis", "\n".join(lines))
        self._reload_fonts()

    # ---- Feature 1: Duplikate -----------------------------------------
    def _find_duplicates(self) -> None:
        self.dup_prog = QProgressDialog("Suche Duplikate…", None, 0, 0,
                                        self)
        self.dup_prog.setWindowModality(Qt.WindowModal)
        self.dup_prog.setCancelButton(None)
        self.dup_prog.setMinimumDuration(0)
        self.dup_thread = DupScanThread(self.model.entries)
        self.dup_thread.progress.connect(
            lambda i, n: (self.dup_prog.setMaximum(n),
                          self.dup_prog.setValue(i)))
        self.dup_thread.done.connect(self._on_dups)
        self.dup_thread.start()

    @Slot(list)
    def _on_dups(self, groups: list) -> None:
        self.dup_prog.close()
        if not groups:
            SuccessPopup(self, "Keine Duplikate gefunden — deine "
                               "Sammlung ist sauber!")
            return
        DuplicatesDialog(groups, self.model, self).exec()
        self._update_status()

    # ---- Feature 5: Vergleich -----------------------------------------
    def _compare_checked(self) -> None:
        entries = self.model.checked_entries()
        if not entries:
            entries = [i.data(EntryRole) for i in
                       self.view.selectionModel().selectedIndexes()]
        entries = [e for e in entries if e.file_exists][:40]
        if len(entries) < 2:
            QMessageBox.information(
                self, "Vergleich",
                "Bitte mindestens 2 Schriften markieren oder auswählen "
                "(max. 40).")
            return
        CompareDialog(entries, self.model.sample_text, self).exec()

    # ---- Feature 6: Tags ------------------------------------------------
    def _save_all_tags(self) -> None:
        tags = {os.path.normcase(e.file_path): e.tags
                for e in self.model.entries if e.tags}
        core.save_tags(tags)
        self._refresh_filter_values()
        self.view.viewport().update()

    def _tag_add(self) -> None:
        entries = self.model.checked_entries()
        if not entries:
            QMessageBox.information(self, "Tags",
                                    "Bitte zuerst Schriften markieren.")
            return
        tag, ok = QInputDialog.getText(
            self, "Tag hinzufügen",
            f"Tag für {len(entries)} markierte Schrift(en):")
        tag = tag.strip().lstrip("#")
        if not ok or not tag:
            return
        for e in entries:
            if tag not in e.tags:
                e.tags.append(tag)
        self._save_all_tags()

    def _tag_remove(self) -> None:
        entries = self.model.checked_entries()
        if not entries:
            QMessageBox.information(self, "Tags",
                                    "Bitte zuerst Schriften markieren.")
            return
        existing = sorted({t for e in entries for t in e.tags})
        if not existing:
            QMessageBox.information(self, "Tags",
                                    "Die markierten Schriften haben keine "
                                    "Tags.")
            return
        tag, ok = QInputDialog.getItem(self, "Tag entfernen",
                                       "Tag:", existing, 0, False)
        if not ok:
            return
        for e in entries:
            if tag in e.tags:
                e.tags.remove(tag)
        self._save_all_tags()

    # ---- Feature 7: PDF-Katalog -----------------------------------------
    def _pdf_catalog(self) -> None:
        entries = [e for e in self._visible_entries() if e.file_exists]
        if not entries:
            QMessageBox.information(self, "PDF-Katalog",
                                    "Keine Schriften in der Ansicht.")
            return
        if len(entries) > 1500:
            rc = QMessageBox.question(
                self, "Großer Katalog",
                f"{len(entries)} Fonts ergeben ein sehr großes PDF. "
                f"Tipp: erst filtern.\nTrotzdem fortfahren?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if rc != QMessageBox.Yes:
                return
        dest, _ = QFileDialog.getSaveFileName(
            self, "PDF speichern", "Font-Musterkatalog.pdf", "PDF (*.pdf)")
        if not dest:
            return
        self.pdf_prog = QProgressDialog("Erstelle PDF…", None, 0,
                                        len(entries), self)
        self.pdf_prog.setWindowModality(Qt.WindowModal)
        self.pdf_prog.setCancelButton(None)
        self.pdf_prog.setMinimumDuration(0)
        self.pdf_thread = PdfCatalogThread(entries,
                                           self.model.sample_text, dest)
        self.pdf_thread.progress.connect(
            lambda i, n: self.pdf_prog.setValue(i))
        self.pdf_thread.done.connect(self._on_pdf_done)
        self.pdf_thread.start()

    @Slot(str, str)
    def _on_pdf_done(self, path: str, error: str) -> None:
        self.pdf_prog.close()
        if error:
            QMessageBox.warning(self, "PDF-Katalog", f"Fehler: {error}")
        else:
            QMessageBox.information(self, "PDF-Katalog",
                                    f"Katalog erstellt:\n{path}")

    # ---- Feature 8: Verwaiste Einträge ----------------------------------
    def _cleanup_orphans(self) -> None:
        orphans = [e for e in self.model.entries
                   if not e.file_exists and not e.protected]
        if not orphans:
            SuccessPopup(self, "Alles sauber — keine Einträge ohne "
                               "Datei gefunden.")
            return
        rc = QMessageBox.question(
            self, "Einträge ohne Datei aufräumen",
            f"{len(orphans)} Schriften-Einträge verweisen auf Dateien, "
            f"die nicht mehr existieren. Diese Karteileichen jetzt "
            f"entfernen?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if rc == QMessageBox.Yes:
            self._run_action(core.uninstall_fonts, orphans,
                             "Bereinige verwaiste Einträge…")

    # ---- Feature 3: temporär laden --------------------------------------
    def _temp_load(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Fonts nur temporär laden", "",
            "Fonts (*.ttf *.otf *.ttc *.otc)")
        if not paths:
            return
        res = core.temp_activate(paths)
        msg = (f"{len(res.ok)} Font(s) temporär aktiviert — in allen "
               f"Programmen verfügbar, bis Windows neu gestartet wird.")
        if res.errors:
            msg += f"\nFehler: {len(res.errors)}"
        QMessageBox.information(self, "Temporär geladen", msg)
        self._update_status()

    def _temp_unload(self) -> None:
        n = core.temp_deactivate_all()
        QMessageBox.information(
            self, "Temporäre Fonts",
            f"{n} temporär geladene Font(s) entladen."
            if n else "Es sind keine temporär geladenen Fonts aktiv.")
        self._update_status()

    # ---- Feature 4: Registry-Backup --------------------------------------
    def _startup_backup(self) -> None:
        if not core.has_registry_backup():
            self._startup_backup_thread = BackupThread()
            self._startup_backup_thread.done.connect(
                lambda files: files and self.show_status(
                    "Zur Sicherheit wurde eine Sicherung deiner "
                    "Schriftenliste angelegt.", 8000))
            self._startup_backup_thread.start()

    def _backup_now(self) -> None:
        tip = self._show_tip("Sicherung",
                             "Schriftenliste wird gesichert…")
        self._backup_thread = FuncThread(core.backup_font_registry)

        def done(files) -> None:
            ok = isinstance(files, list) and bool(files)
            try:
                tip.setContent("Sicherung erstellt" if ok
                               else "Sicherung fehlgeschlagen")
                tip.setState(True)
            except RuntimeError:
                pass
            if ok:
                SuccessPopup(self, "Sicherung deiner Schriftenliste "
                                   "erstellt.")
            else:
                QMessageBox.warning(
                    self, "Sicherung",
                    "Sicherung fehlgeschlagen — bitte als Administrator "
                    "erneut versuchen.")

        self._backup_thread.done.connect(done)
        self._backup_thread.start()

    # ---- Download / Import / Export ---------------------------------------
    def _download_fonts(self) -> None:
        dlg = DownloadDialog(self)
        dlg.exec()
        if dlg.installed_something:
            self._reload_fonts()

    def _export_fonts(self) -> None:
        checked = self.model.checked_entries()
        deletable = [e for e in self.model.entries if not e.protected]
        visible = [e for e in self._visible_entries() if not e.protected]
        dlg = ExportDialog(len(checked), len(deletable), len(visible), self)
        if dlg.exec() != QDialog.Accepted:
            return
        entries = {"checked": checked, "deletable": deletable,
                   "visible": visible}[dlg.scope()]
        if not entries:
            QMessageBox.information(self, "Export", "Keine Schriften.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export speichern als", "FontExport.zip",
            "ZIP-Archiv (*.zip)")
        if not dest:
            return
        from functools import partial
        self._run_action(partial(core.export_fonts, dest_zip=dest),
                         entries, "Exportiere Schriften…")

    def _install_fonts(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Fontdateien oder Export-ZIP auswählen", "",
            "Fonts / Export-ZIP (*.ttf *.otf *.ttc *.otc *.zip);;"
            "Alle Dateien (*)")
        if not paths:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Installationsziel")
        box.setText(f"{len(paths)} Datei(en) ausgewählt.\n\n"
                    f"Wo installieren?")
        b_user = box.addButton("Nur für mich (empfohlen)",
                               QMessageBox.AcceptRole)
        b_all = box.addButton("Für alle Benutzer (Admin)",
                              QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is b_user:
            per_user = True
        elif clicked is b_all:
            if not core.is_admin():
                QMessageBox.warning(self, "Adminrechte nötig",
                                    "Bitte als Administrator neu starten.")
                return
            per_user = False
        else:
            return
        from functools import partial
        self._run_action(partial(core.install_fonts, per_user=per_user),
                         paths, "Installiere Schriften…")

    # ---- Extras ------------------------------------------------------------
    def _restart_admin(self) -> None:
        if core.relaunch_as_admin():
            QApplication.quit()

    def _rebuild_font_cache(self) -> None:
        if not core.is_admin():
            QMessageBox.warning(self, "Adminrechte nötig",
                                "Diese Aktion erfordert Adminrechte.")
            return
        rc = QMessageBox.question(
            self, "Font-Anzeige-Cache erneuern",
            "Der Windows-Dienst für die Schriftanzeige wird neu "
            "gestartet und sein Zwischenspeicher geleert. Das kann "
            "einen Moment dauern. Fortfahren?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if rc != QMessageBox.Yes:
            return
        self._cache_tip = self._state_tip("Font-Cache",
                                          "Cache wird erneuert — einen "
                                          "Moment…")
        self.cache_thread = CacheRebuildThread()
        self.cache_thread.done.connect(self._on_cache_done)
        self.cache_thread.start()

    @Slot()
    def _on_cache_done(self) -> None:
        tip = getattr(self, "_cache_tip", None)
        if tip is not None:
            try:
                tip.setContent("Fertig")
                tip.setState(True)
            except RuntimeError:
                pass
            self._cache_tip = None
        SuccessPopup(self, "Der Font-Anzeige-Cache wurde erneuert.")

THEMES = {
    "light": dict(win="#f2f3f6", side="#f9f9fb", pane="#ffffff",
                  pane2="rgba(255,255,255,0.78)",
                  border="#dfe0e6", text="#1e1f24", sub="#6b6e78",
                  accent="#C5073D", accent_dark="#8a0a2e",
                  hover_bg="#fdeef2", sel_text="#ffffff",
                  tile="#ffffff", tile_border="#e1e2e8",
                  tile_sel="#fdeef2", stripe="#ebecf0"),
    "dark": dict(win="#141519", side="#1c1e24", pane="#23252d",
                 pane2="rgba(38,40,50,0.92)",
                 border="#3b3e49", text="#e9e9ee", sub="#9b9ea8",
                 accent="#E24B72", accent_dark="#ff8aa6",
                 hover_bg="#3a2733", sel_text="#ffffff",
                 tile="#ffffff", tile_border="#454956",
                 tile_sel="#f6dbe4", stripe="#1b1c22"),
}
# Aktive Design-Tokens — Delegate/Overlays lesen hieraus. Die Kacheln
# bleiben in beiden Themes weiß (Schriftmuster auf "Papier").
THEME: dict = dict(THEMES["light"])


def build_qss(t: dict) -> str:
    """Scoped Styles: Fluent-Widgets stylen sich selbst — hier nur
    Standard-Dialoge und unsere eigenen IDs."""
    return f"""
QDialog {{ background: {t['win']}; color: {t['text']}; }}
QDialog QLabel {{ color: {t['text']}; }}
QDialog QGroupBox {{ font-weight: 600; border: 1px solid {t['border']};
  border-radius: 12px; margin-top: 12px; padding-top: 10px;
  background: {t['pane2']}; color: {t['text']}; }}
QDialog QGroupBox::title {{ subcontrol-origin: margin; left: 12px;
  padding: 0 5px; color: {t['accent_dark']}; }}
QDialog QPushButton {{ background: {t['pane']};
  border: 1px solid {t['border']}; border-radius: 10px;
  padding: 7px 12px; color: {t['text']}; }}
QDialog QPushButton:hover {{ background: {t['hover_bg']};
  border-color: {t['accent']}; color: {t['text']}; }}
QDialog QLineEdit, QDialog QComboBox, QDialog QSpinBox {{
  border: 1px solid {t['border']}; border-radius: 10px; padding: 5px 8px;
  background: {t['pane']}; color: {t['text']};
  selection-background-color: {t['accent']};
  selection-color: {t['sel_text']}; }}
QDialog QComboBox QAbstractItemView {{ background: {t['pane']};
  color: {t['text']}; border: 1px solid {t['border']};
  selection-background-color: {t['accent']};
  selection-color: {t['sel_text']}; }}
QDialog QListWidget {{ background: {t['pane']}; color: {t['text']};
  border: 1px solid {t['border']}; border-radius: 10px; }}
QDialog QListWidget::item:hover {{ background: {t['hover_bg']};
  color: {t['text']}; }}
QDialog QListWidget::item:selected {{ background: {t['accent']};
  color: {t['sel_text']}; }}
QDialog QTableWidget {{ background: {t['pane']}; color: {t['text']};
  border: 1px solid {t['border']}; border-radius: 10px; }}
QDialog QTableWidget::item:selected {{ background: {t['accent']};
  color: {t['sel_text']}; }}
QDialog QHeaderView::section {{ background: {t['pane']};
  color: {t['text']}; border: none;
  border-bottom: 1px solid {t['border']}; padding: 5px; }}
QDialog QCheckBox, QDialog QRadioButton {{ color: {t['text']}; }}
QToolTip {{ background: {t['pane']}; color: {t['text']};
  border: 1px solid {t['accent']}; border-radius: 6px; padding: 4px; }}
#libraryPage QListView {{ background: {t['win']};
  border: 1px solid {t['border']}; border-radius: 10px;
  color: {t['text']}; }}
#libraryPage QScrollBar:vertical, QDialog QScrollBar:vertical {{
  background: transparent; width: 10px; margin: 2px; }}
#libraryPage QScrollBar::handle:vertical,
QDialog QScrollBar::handle:vertical {{ background: {t['border']};
  border-radius: 5px; min-height: 30px; }}
#libraryPage QScrollBar::handle:vertical:hover {{
  background: {t['accent']}; }}
#libraryPage QScrollBar::add-line, #libraryPage QScrollBar::sub-line {{
  height: 0; width: 0; }}
QScrollArea#sidebar {{ background: {t['side']}; border: none;
  border-right: 1px solid {t['border']}; border-radius: 0; }}
QScrollArea#sidebar > QWidget > QWidget {{ background: transparent; }}
QScrollArea#sidebar QLabel {{ color: {t['sub']};
  background: transparent; }}
QPushButton#sectionHeader {{ text-align: left; font-weight: 700;
  border: none; background: transparent; border-radius: 8px;
  padding: 10px 8px 6px 6px; color: {t['sub']}; }}
QPushButton#sectionHeader:hover {{ background: {t['hover_bg']};
  color: {t['accent_dark']}; }}
QFrame#sectionBody {{ background: transparent; border: none; }}
QLabel#statusLabel {{ color: {t['sub']}; padding: 4px 2px 0 2px; }}
"""


def apply_theme(app: QApplication, name: str) -> None:
    from PySide6.QtGui import QPalette
    t = THEMES.get(name, THEMES["light"])
    THEME.clear()
    THEME.update(t)
    setTheme(Theme.DARK if name == "dark" else Theme.LIGHT)
    setThemeColor(t["accent"])
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(t["win"]))
    pal.setColor(QPalette.WindowText, QColor(t["text"]))
    pal.setColor(QPalette.Base, QColor(t["pane"]))
    pal.setColor(QPalette.AlternateBase, QColor(t["stripe"]))
    pal.setColor(QPalette.Text, QColor(t["text"]))
    pal.setColor(QPalette.Button, QColor(t["pane"]))
    pal.setColor(QPalette.ButtonText, QColor(t["text"]))
    pal.setColor(QPalette.Highlight, QColor(t["accent"]))
    pal.setColor(QPalette.HighlightedText, QColor(t["sel_text"]))
    pal.setColor(QPalette.ToolTipBase, QColor(t["pane"]))
    pal.setColor(QPalette.ToolTipText, QColor(t["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(t["sub"]))
    app.setPalette(pal)
    app.setStyleSheet(build_qss(t))


def main() -> int:
    if sys.platform != "win32":
        print("Dieses Tool läuft nur unter Windows.")
        return 1
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Kopfsalto.FontManager.2")
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("FontManager")
    app.setStyle("Fusion")
    apply_theme(app, core.load_settings().get("theme", "light"))
    icon_path = _resource_path("FontManager.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
