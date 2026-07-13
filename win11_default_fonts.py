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
Whitelist der Schriftdateien, die zur Windows-11-Standardauslieferung gehören.

Quelle: Offizielle Microsoft-Dokumentation
  https://learn.microsoft.com/en-us/typography/fonts/windows_11_font_list
(Basis-Installation + alle "Feature on Demand"-Sprachpakete, da diese
 ebenfalls nach C:\\Windows\\Fonts installiert werden.)

Alle Dateinamen kleingeschrieben. Der Abgleich erfolgt IMMER gegen
os.path.basename(pfad).lower().

WICHTIG: Diese Liste ist bewusst großzügig (inkl. optionaler Sprachpakete).
Im Zweifel wird eine Schrift geschützt, nie umgekehrt. Zusätzlich greift in
font_core.check_protected() die zweite Schutzregel
(C:\\Windows\\Fonts + Besitzer TrustedInstaller) sowie der .fon-Schutz.
"""

WIN11_DEFAULT_FONT_FILES = frozenset(f.lower() for f in [
    # ---- Basis-Installation Windows 11 ----
    "arial.ttf", "ariali.ttf", "arialbd.ttf", "arialbi.ttf", "ariblk.ttf",
    "bahnschrift.ttf",
    "calibril.ttf", "calibrili.ttf", "calibri.ttf", "calibrii.ttf",
    "calibrib.ttf", "calibriz.ttf",
    "cambria.ttc", "cambriai.ttf", "cambriab.ttf", "cambriaz.ttf",
    "candaral.ttf", "candarali.ttf", "candara.ttf", "candarai.ttf",
    "candarab.ttf", "candaraz.ttf",
    "cascadiacode.ttf", "cascadiacode italic.ttf",
    "cascadiacodeitalic.ttf",
    "cascadiamono.ttf", "cascadiamono italic.ttf",
    "cascadiamonoitalic.ttf",
    "comic.ttf", "comici.ttf", "comicbd.ttf", "comicz.ttf",
    "consola.ttf", "consolai.ttf", "consolab.ttf", "consolaz.ttf",
    "constan.ttf", "constani.ttf", "constanb.ttf", "constanz.ttf",
    "corbell.ttf", "corbelli.ttf", "corbel.ttf", "corbeli.ttf",
    "corbelb.ttf", "corbelz.ttf",
    "cour.ttf", "couri.ttf", "courbd.ttf", "courbi.ttf",
    "ebrima.ttf", "ebrimabd.ttf",
    "framd.ttf", "framdit.ttf",
    "gabriola.ttf",
    "gadugi.ttf", "gadugib.ttf",
    "georgia.ttf", "georgiai.ttf", "georgiab.ttf", "georgiaz.ttf",
    "holomdl2.ttf",
    "impact.ttf",
    "inkfree.ttf",
    "javatext.ttf",
    "leelawui.ttf", "leeluisl.ttf", "leelauib.ttf",
    "lucon.ttf", "l_10646.ttf",
    "malgun.ttf", "malgunbd.ttf", "malgunsl.ttf",
    "marlett.ttf",
    "himalaya.ttf",
    "msjhl.ttc", "msjh.ttc", "msjhbd.ttc",
    "ntailu.ttf", "ntailub.ttf",
    "phagspa.ttf", "phagspab.ttf",
    "micross.ttf",
    "taile.ttf", "taileb.ttf",
    "msyhl.ttc", "msyh.ttc", "msyhbd.ttc",
    "msyi.ttf",
    "mingliub.ttc",
    "monbaiti.ttf",
    "msgothic.ttc",
    "mvboli.ttf",
    "mmrtext.ttf", "mmrtextb.ttf",
    "nirmalas.ttf", "nirmala.ttf", "nirmalab.ttf",
    "pala.ttf", "palai.ttf", "palab.ttf", "palabi.ttf",
    "segoeicons.ttf", "segmdl2.ttf",
    "segoepr.ttf", "segoeprb.ttf",
    "segoesc.ttf", "segoescb.ttf",
    "segoeuil.ttf", "seguili.ttf", "segoeuisl.ttf", "seguisli.ttf",
    "segoeui.ttf", "segoeuii.ttf", "seguisb.ttf", "seguisbi.ttf",
    "segoeuib.ttf", "segoeuiz.ttf", "seguibl.ttf", "seguibli.ttf",
    "seguiemj.ttf", "seguihis.ttf", "seguisym.ttf",
    "seguivar.ttf",
    "simsun.ttc", "simsunb.ttf",
    "sitkavf.ttf", "sitkavf-italic.ttf",
    "sylfaen.ttf",
    "symbol.ttf",
    "tahoma.ttf", "tahomabd.ttf",
    "times.ttf", "timesi.ttf", "timesbd.ttf", "timesbi.ttf",
    "trebuc.ttf", "trebucit.ttf", "trebucbd.ttf", "trebucbi.ttf",
    "verdana.ttf", "verdanai.ttf", "verdanab.ttf", "verdanaz.ttf",
    "webdings.ttf", "wingding.ttf",
    "yugothl.ttc", "yugothr.ttc", "yugothm.ttc", "yugothb.ttc",

    # ---- FOD: Arabische Schrift ----
    "aldhabi.ttf", "andlso.ttf", "arabtype.ttf",
    "msuighur.ttf", "msuighub.ttf",
    "majalla.ttf", "majallab.ttf",
    "simpo.ttf", "simpbdo.ttf", "simpfxo.ttf",
    "trado.ttf", "tradbdo.ttf",
    "urdtype.ttf", "urdtypeb.ttf",

    # ---- FOD: Bangla ----
    "shonar.ttf", "shonarb.ttf", "vrinda.ttf", "vrindab.ttf",

    # ---- FOD: Kanadische Silbenschrift / Cherokee ----
    "euphemia.ttf", "plantc.ttf",

    # ---- FOD: Devanagari ----
    "aparaj.ttf", "aparaji.ttf", "aparajb.ttf", "aparajbi.ttf",
    "kokila.ttf", "kokilai.ttf", "kokilab.ttf", "kokilabi.ttf",
    "mangal.ttf", "mangalb.ttf",
    "sanskr.ttf",
    "utsaah.ttf", "utsaahi.ttf", "utsaahb.ttf", "utsaahbi.ttf",

    # ---- FOD: Äthiopisch / Gujarati / Gurmukhi ----
    "nyala.ttf", "shruti.ttf", "shrutib.ttf", "raavi.ttf", "raavib.ttf",

    # ---- FOD: Chinesisch (vereinfacht/traditionell) ----
    "dengl.ttf", "deng.ttf", "dengb.ttf",
    "simfang.ttf", "simkai.ttf", "simhei.ttf",
    "kaiu.ttf", "mingliu.ttc",

    # ---- FOD: Hebräisch ----
    "ahronbd.ttf", "david.ttf", "davidbd.ttf", "frank.ttf",
    "gisha.ttf", "gishabd.ttf", "lvnm.ttf", "lvnmbd.ttf",
    "mriam.ttf", "mriamc.ttf", "nrkis.ttf", "rod.ttf",

    # ---- FOD: Japanisch ----
    "biz-udgothicr.ttc", "biz-udgothicb.ttc", "biz-udminchom.ttc",
    "meiryo.ttc", "meiryob.ttc", "msmincho.ttc",
    "uddigikyokashon-b.ttc", "uddigikyokashon-r.ttc",
    "yuminl.ttf", "yumin.ttf", "yumindb.ttf",

    # ---- FOD: Kannada / Khmer ----
    "tunga.ttf", "tungab.ttf",
    "daunpenh.ttf", "khmerui.ttf", "khmeruib.ttf", "moolbor.ttf",

    # ---- FOD: Koreanisch ----
    "batang.ttc", "gulim.ttc",

    # ---- FOD: Lao / Malayalam / Odia ----
    "dokchamp.ttf", "laoui.ttf", "laouib.ttf",
    "kartika.ttf", "kartikab.ttf",
    "kalinga.ttf", "kalingab.ttf",

    # ---- FOD: Pan-Europäisch ----
    "arialnova-light.ttf", "arialnova-lightitalic.ttf", "arialnova.ttf",
    "arialnova-italic.ttf", "arialnova-bold.ttf", "arialnova-bolditalic.ttf",
    "arialnovacond-light.ttf", "arialnovacond-lightitalic.ttf",
    "arialnovacond.ttf", "arialnovacond-italic.ttf",
    "arialnovacond-bold.ttf", "arialnovacond-bolditalic.ttf",
    "georgiapro-light.ttf", "georgiapro-lightitalic.ttf",
    "georgiapro-regular.ttf", "georgiapro-italic.ttf",
    "georgiapro-semibold.ttf", "georgiapro-semibolditalic.ttf",
    "georgiapro-bold.ttf", "georgiapro-bolditalic.ttf",
    "georgiapro-black.ttf", "georgiapro-blackitalic.ttf",
    "georgiapro-condlight.ttf", "georgiapro-condlightitalic.ttf",
    "georgiapro-condregular.ttf", "georgiapro-conditalic.ttf",
    "georgiapro-condsemibold.ttf", "georgiapro-condsemibolditalic.ttf",
    "georgiapro-condbold.ttf", "georgiapro-condbolditalic.ttf",
    "georgiapro-condblack.ttf", "georgiapro-condblackitalic.ttf",
    "gillsanslightnova.ttf", "gillsanslightitnova.ttf", "gillsansnova.ttf",
    "gillsansitnova.ttf", "gillsansbonova.ttf", "gillsansboitnova.ttf",
    "gillsansultrabonova.ttf",
    "gillsanscondlightnova.ttf", "gillsanscondlightitnova.ttf",
    "gillsanscondnova.ttf", "gillsansconditnova.ttf",
    "gillsanscondbonova.ttf", "gillsanscondboitnova.ttf",
    "gillsanscondextranova.ttf", "gillsanscondextraitnova.ttf",
    "gillsanscondultrabonova.ttf",
    "nhaasgrotesktxpro-rg.ttf", "nhaasgrotesktxpro-it.ttf",
    "rockwellnova.ttf", "rockwellnova-bold.ttf",
    "rockwellnova-bolditalic.ttf", "rockwellnovacond.ttf",
    "rockwellnovacond-bold.ttf", "rockwellnovacond-bolditalic.ttf",
    "rockwellnovacond-italic.ttf", "rockwellnovacond-light.ttf",
    "rockwellnovacond-lightitalic.ttf", "rockwellnova-extrabold.ttf",
    "rockwellnova-extrabolditalic.ttf", "rockwellnova-italic.ttf",
    "rockwellnova-light.ttf", "rockwellnova-lightitalic.ttf",
    "verdanapro-light.ttf", "verdanapro-lightitalic.ttf",
    "verdanapro-regular.ttf", "verdanapro-italic.ttf",
    "verdanapro-semibold.ttf", "verdanapro-semibolditalic.ttf",
    "verdanapro-bold.ttf", "verdanapro-bolditalic.ttf",
    "verdanapro-black.ttf", "verdanapro-blackitalic.ttf",
    "verdanapro-condlight.ttf", "verdanapro-condlightitalic.ttf",
    "verdanapro-condregular.ttf", "verdanapro-conditalic.ttf",
    "verdanapro-condsemibold.ttf", "verdanapro-condsemibolditalic.ttf",
    "verdanapro-condbold.ttf", "verdanapro-condbolditalic.ttf",
    "verdanapro-condblack.ttf", "verdanapro-condblackitalic.ttf",

    # ---- FOD: Singhalesisch / Syrisch / Tamil / Telugu ----
    "iskpota.ttf", "iskpotab.ttf",
    "estre.ttf",
    "latha.ttf", "lathab.ttf", "vijaya.ttf", "vijayab.ttf",
    "gautami.ttf", "gautamib.ttf", "vani.ttf", "vanib.ttf",

    # ---- FOD: Thai ----
    "angsana.ttc", "browalia.ttc", "cordia.ttc",
    "upcdl.ttf", "upcdi.ttf", "upcdb.ttf", "upcdbi.ttf",
    "upcel.ttf", "upcei.ttf", "upceb.ttf", "upcebi.ttf",
    "upcfl.ttf", "upcfi.ttf", "upcfb.ttf", "upcfbi.ttf",
    "upcil.ttf", "upcii.ttf", "upcib.ttf", "upcibi.ttf",
    "upcjl.ttf", "upcji.ttf", "upcjb.ttf", "upckbi.ttf",
    "upckl.ttf", "upcki.ttf", "upckb.ttf", "upcjbi.ttf",
    "leelawad.ttf", "leelawdb.ttf",
    "upcll.ttf", "upcli.ttf", "upclb.ttf", "upclbi.ttf",
])
