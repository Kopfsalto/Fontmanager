<p align="center">
  <img src="FontManager_Logo.png" alt="FontManager Logo" width="128">
</p>

<h1 align="center">FontManager für Windows 11</h1>

<p align="center">
  <b>Schriftarten wirklich deinstallieren — sicher, in Masse und mit Vorschau.</b><br>
  by <b>Kopfsalto</b>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/Lizenz-GPLv3-C5073D" alt="Lizenz: GPLv3"></a>
  <img src="https://img.shields.io/badge/Plattform-Windows%2011-blue" alt="Windows 11">
  <img src="https://img.shields.io/badge/Python-3.11%2B-yellow" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Preis-kostenlos-brightgreen" alt="kostenlos">
</p>

---

Wer über die Jahre tausende Schriften installiert hat, kennt das Problem:
Windows bietet keine komfortable Möglichkeit, viele Fonts auf einmal
**echt zu deinstallieren** (nicht nur auszublenden). FontManager wurde für
genau diesen Fall gebaut und wird auch mit Bibliotheken von 8500+ Fonts
flüssig fertig.

## ✨ Funktionen

- **Kachel-Bibliothek mit Live-Vorschau** — jede Schrift als Muster-Kachel,
  eigener Beispieltext und Vorschaugröße einstellbar
- **Echtes Deinstallieren** über die Windows-API (Registry + Datei), nicht
  nur Deaktivieren — wahlweise geht aber auch **nur Deaktivieren/Reaktivieren**
- **Dreistufiger Schutz der Windows-11-Standardschriften:** Whitelist der
  offiziellen Microsoft-Font-Liste, Systemschrift-Erkennung
  (TrustedInstaller / `C:\Windows\Fonts`) und eine zweite Schutzprüfung
  unmittelbar vor jedem Löschvorgang — Arial, Segoe UI & Co. können mit dem
  Tool **niemals** gelöscht werden
- **30-Tage-Papierkorb** als Sicherheitsnetz mit Wiederherstellen-Funktion
  (Aufbewahrungsdauer einstellbar)
- **Massenauswahl** per Checkbox, Strg/Shift-Klick, Filter und Suche
- **Filter nach Metadaten:** Klassifikation (Serif, Sans, Script, Monospace,
  Barcode …), Schriftsystem (Latein, Arabisch, Kyrillisch, CJK …), Hersteller,
  Status und eigene Tags
- **Werkzeuge:** Duplikat-Finder, Defekt-Erkennung, Vergleichsansicht,
  PDF-Musterkatalog, Bereinigung verwaister Registry-Einträge,
  Registry-Backup, Font-Cache-Reset
- **Export & Bulk-Installation:** Fonts als ZIP exportieren und auf einem
  anderen System gesammelt wieder installieren
- **Temporäres Laden** von Fonts ohne Installation (nur für die Sitzung)
- **Font-Download aus 4 freien Quellen** (Google Fonts, Fontsource,
  Fontshare, Font Squirrel) — ohne API-Key, ausschließlich frei
  lizenzierte Schriften
- **Modernes Fluent-UI** mit Dark-/Light-Mode, Setup-Assistent und
  optionaler interaktiver Tour

## 🖥️ Systemvoraussetzungen

- Windows 11 (Windows 10 ungetestet)
- Zum Löschen systemweiter Schriften: Administratorrechte (UAC-Abfrage
  erscheint automatisch); ohne Adminrechte lassen sich Benutzer-Schriften
  verwalten

## 🚀 Installation / Build

Es wird keine fertige exe mit ausgeliefert — der Build dauert nur wenige
Minuten:

```powershell
git clone https://github.com/DEIN-GITHUB-NAME/FontManager.git
cd FontManager
.\build.ps1        # oder Doppelklick auf build.bat
# Ergebnis: .\dist\FontManager.exe
```

Das Skript legt automatisch ein virtuelles Environment an, installiert die
Abhängigkeiten aus `requirements.txt` und baut die exe per PyInstaller
(inkl. eingebettetem Icon und UAC-Manifest).

Zum Entwickeln reicht:

```powershell
pip install -r requirements.txt
python font_manager.py
```

## 🛡️ Sicherheit & Datenschutz

- Das Tool arbeitet vollständig **lokal**. Eine Internetverbindung wird
  ausschließlich genutzt, wenn du aktiv den Font-Download aus den freien
  Quellen öffnest.
- Es werden **keine Telemetrie- oder Nutzungsdaten** erhoben oder gesendet.
- Vor der ersten Änderung legt das Tool automatisch ein **Registry-Backup**
  der Font-Einträge an; gelöschte Dateien wandern zuerst in den
  tool-eigenen Papierkorb.
- Alle Daten liegen unter `%LOCALAPPDATA%\FontManager\`.

Details: [PRIVACY.md](PRIVACY.md)

## 📖 Projektstatus

FontManager ist ein **privates, nicht-kommerzielles Hobby-Projekt** und wird
kostenlos bereitgestellt — ohne Werbung, ohne In-App-Käufe, ohne Konto.
Support-Anfragen gerne per Mail, aber ohne Anspruch auf Antwortzeiten. 🙂

- 📷 Instagram: [Kopfsalto](https://instagram.com/kopfsalto)
- 🎮 Twitch: [kopfsalto1337](https://twitch.tv/kopfsalto1337)
- ☕ Ko-Fi: [Kopfsalto](https://ko-fi.com/kopfsalto)
- ✉️ Support: mail@kopfsalto.de

## 📄 Lizenz

FontManager ist freie Software und steht unter der
**GNU General Public License v3.0 (oder später)** — siehe [LICENSE](LICENSE).

Du darfst das Programm nutzen, studieren, weitergeben und verändern, solange
abgeleitete Versionen ebenfalls unter der GPLv3 veröffentlicht werden und der
Quellcode verfügbar bleibt. Das Programm wird **ohne jede Gewährleistung**
bereitgestellt.

> **Wichtiger Hinweis zur UI-Bibliothek:** FontManager verwendet
> [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets),
> die dual-lizenziert ist (GPLv3 **oder** kommerzielle Lizenz des Autors).
> Dieses Projekt nutzt die GPLv3-Variante. Wer FontManager oder Ableitungen
> davon **kommerziell vertreiben** möchte, muss die Lizenzbedingungen von
> PySide6-Fluent-Widgets selbst prüfen und ggf. eine kommerzielle Lizenz
> beim Autor der Bibliothek erwerben.

Übersicht aller Fremdbibliotheken: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

---

<p align="center">Copyright © 2026 Kopfsalto · Made with ❤️ in Augsburg</p>
