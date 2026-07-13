# Drittbibliotheken & Lizenzen

FontManager (GPLv3) verwendet folgende Open-Source-Bibliotheken.
Alle Angaben ohne Gewähr — maßgeblich sind die Lizenztexte der
jeweiligen Projekte.

| Bibliothek | Zweck | Lizenz |
|---|---|---|
| [PySide6 / Qt for Python](https://doc.qt.io/qtforpython/) | GUI-Framework | LGPLv3 |
| [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) | Fluent-Design-Widgets | **Dual: GPLv3 (nicht-kommerziell) oder kommerzielle Lizenz** |
| [fontTools](https://github.com/fonttools/fonttools) | Font-Metadaten-Analyse | MIT |
| [Pillow](https://python-pillow.org/) | Thumbnail-Rendering, PDF-Katalog | MIT-CMU (HPND) |
| [PyInstaller](https://pyinstaller.org/) | exe-Packaging (nur Build-Zeit) | GPLv2+ mit Bootloader-Ausnahme |

## Hinweis zu PySide6-Fluent-Widgets

Die Bibliothek ist dual-lizenziert. Dieses Projekt nutzt sie unter der
**GPLv3** und wird ausschließlich **kostenlos und nicht-kommerziell**
verbreitet. Wer dieses Projekt forkt und kommerziell vertreiben möchte
(Verkauf, kostenpflichtige Distribution, Bündelung mit Bezahlprodukten),
ist selbst dafür verantwortlich, die Lizenzbedingungen von
PySide6-Fluent-Widgets einzuhalten und ggf. eine kommerzielle Lizenz beim
Autor der Bibliothek zu erwerben — oder die UI-Schicht durch eine
lizenzfreie Alternative zu ersetzen.

## Font-Download-Quellen

Der optionale Font-Download greift auf öffentliche, keylose APIs zu:

- Google Fonts (via google-webfonts-helper, gwfh.mranftl.com) — Fonts unter OFL/Apache
- Fontsource (api.fontsource.org) — Open-Source-Fonts
- Fontshare (api.fontshare.com, Indian Type Foundry) — frei für private & kommerzielle Nutzung
- Font Squirrel (fontsquirrel.com) — kuratierte Free-Fonts

Die Lizenz jeder heruntergeladenen Schrift liegt beim jeweiligen
Schriftenhersteller; im Zweifel vor kommerzieller Nutzung einer Schrift
deren Lizenz prüfen.
