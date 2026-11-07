#!/usr/bin/env python3
"""
Scarica i dati mensili ADS (DMS) dei quotidiani da adsnotizie.it e produce due grafici:

1. Diffusione media giornaliera "individuale pagata": cartacee + abbonamenti cartacei + copie digitali
   vendute ad almeno il 30% del prezzo (colonne 2+3+4a; esclusa la 4b, digitali tra il 10 e il 30%)
2. Sole copie digitali individuali vendute ad almeno il 30% del prezzo ufficiale (colonna 4a)

Sono esclusi i quotidiani sportivi (Gazzetta dello Sport, Corriere dello Sport, Tuttosport).

Per ogni testata mostra il dato del mese e la variazione % rispetto allo stesso mese dell'anno prima.

Uso:
    python3 ads_diffusione.py                 # ultimo mese disponibile sul sito
    python3 ads_diffusione.py --mese 8 --anno 2026
    python3 ads_diffusione.py --force         # rigenera anche se già fatto
"""

import argparse
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests

BASE = "https://www.adsnotizie.it"
PAGE_URL = f"{BASE}/Dati/DMS_Page"
DOWNLOAD_URL = f"{BASE}/Dati/downloadDMS"
PERIODICITA_QUOTIDIANI = 1
HEADERS = {"User-Agent": "Mozilla/5.0 (ads_diffusione.py)"}

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dati"
OUT_DIR = ROOT / "grafici"

MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

# Posizioni delle colonne nel foglio DATI_DMS (le intestazioni sono su 4 righe unite)
COL_TESTATA = 0
COL_ANNO = 5
COL_MESE = 6
COL_CARTACEE = 10        # 2  – Vendite individuali cartacee
COL_ABB_CARTACEI = 11    # 3  – Abbonamenti individuali cartacei pagati
COL_DIGITALI_30 = 12     # 4a – Vendite copie digitali individuali >= 30% del prezzo
COL_DIGITALI_10_30 = 13  # 4b – Vendite copie digitali individuali tra il 10 e il 30% ("superscontate")
HEADER_ROWS = 4

# Quotidiani sportivi (e loro edizioni del lunedì) esclusi dai grafici
ESCLUDI = re.compile(r"GAZZETTA SPORT|CORRIERE SPORT|TUTTOSPORT", re.IGNORECASE)

METRICHE = {
    "individuale_pagata": {
        # 2 + 3 + 4a: escluse le copie digitali vendute tra il 10% e il 30% del prezzo (4b)
        "cols": [COL_CARTACEE, COL_ABB_CARTACEI, COL_DIGITALI_30],
        "titolo": "Diffusione media giornaliera individuale pagata",
        "sottotitolo": "Cartacee + abbonamenti cartacei + digitali vendute ad almeno il 30% del prezzo "
                       "(col. 2+3+4a ADS)",
        "colore": "#1f6fb4",
    },
    "digitale_30": {
        "cols": [COL_DIGITALI_30],
        "titolo": "Copie digitali individuali vendute ad almeno il 30% del prezzo",
        "sottotitolo": "Esclusi gli abbonamenti digitali venduti a meno del 30% del prezzo ufficiale (col. 4a ADS)",
        "colore": "#e07b39",
        # colonna aggiuntiva con la variazione degli abbonamenti superscontati
        "extra": ("superscontati", "superscontati\n(10-30%)"),
    },
}

# Serie calcolate solo per confronto (non hanno un grafico proprio)
SERIE_EXTRA = {"superscontati": [COL_DIGITALI_10_30]}
SERIE = {**{k: v["cols"] for k, v in METRICHE.items()}, **SERIE_EXTRA}


def ultimo_mese_disponibile() -> tuple[int, int]:
    """Legge la pagina DMS e restituisce (mese, anno) più recente per i quotidiani."""
    html = requests.get(PAGE_URL, headers=HEADERS, timeout=60).text
    trovati = {
        (int(a), int(m))
        for m, a in re.findall(
            rf"downloadDMS\?mese=(\d+)&anno=(\d+)&periodicita={PERIODICITA_QUOTIDIANI}&", html
        )
    }
    if not trovati:
        sys.exit("Nessun file dei quotidiani trovato sulla pagina ADS: forse è cambiata la struttura.")
    anno, mese = max(trovati)
    return mese, anno


def scarica(mese: int, anno: int, force: bool = False) -> Path:
    """Scarica (se serve) l'Excel ADS dei quotidiani per mese/anno e restituisce il percorso."""
    DATA_DIR.mkdir(exist_ok=True)
    dest = DATA_DIR / f"ads_quotidiani_{anno}_{mese:02d}.xlsx"
    if dest.exists() and not force:
        return dest
    params = {"mese": mese, "anno": anno, "periodicita": PERIODICITA_QUOTIDIANI,
              "nomeReport": "DMSFilePubblicato_3"}
    r = requests.get(DOWNLOAD_URL, params=params, headers=HEADERS, timeout=120)
    r.raise_for_status()
    if not r.content.startswith(b"PK"):
        raise RuntimeError(f"Il download di {mese}/{anno} non è un file Excel valido.")
    dest.write_bytes(r.content)
    return dest


def leggi(path: Path, mese: int, anno: int) -> pd.DataFrame:
    df = pd.read_excel(path, header=None, skiprows=HEADER_ROWS)
    df = df[df[COL_TESTATA].notna()]
    df = df[(pd.to_numeric(df[COL_ANNO], errors="coerce") == anno)
            & (pd.to_numeric(df[COL_MESE], errors="coerce") == mese)]
    df = df[~df[COL_TESTATA].astype(str).str.contains(ESCLUDI)]
    out = pd.DataFrame({
        "testata": df[COL_TESTATA].astype(str).str.strip(),
        **{k: df[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
           for k, cols in SERIE.items()},
    })
    if out.empty:
        raise RuntimeError(f"Nessuna riga per {mese}/{anno} in {path.name}")
    return out


def confronta(mese: int, anno: int, force: bool) -> pd.DataFrame:
    cur = leggi(scarica(mese, anno, force), mese, anno)
    prev = leggi(scarica(mese, anno - 1, force), mese, anno - 1)
    df = cur.merge(prev, on="testata", how="left", suffixes=("", "_prec"))
    for k in SERIE:
        prec = df[f"{k}_prec"].where(df[f"{k}_prec"] > 0)
        df[f"{k}_var"] = (df[k] / prec - 1) * 100
    return df


def fmt_int(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", ".")


def grafico(df: pd.DataFrame, chiave: str, mese: int, anno: int) -> Path:
    cfg = METRICHE[chiave]
    d = df[df[chiave] > 0].sort_values(chiave)
    n = len(d)
    fig, ax = plt.subplots(figsize=(11, 0.28 * n + 2.2))
    y = range(n)
    ax.barh(y, d[chiave], color=cfg["colore"], height=0.7)
    ax.set_yticks(list(y), d["testata"], fontsize=8.5)
    ax.set_ylim(-0.6, n - 0.4)
    xmax = d[chiave].max()
    extra = cfg.get("extra")
    x_var = xmax * 1.31
    x_extra = xmax * 1.50
    ax.set_xlim(0, (x_extra if extra else x_var) + xmax * 0.01)

    def scrivi_var(x, yi, var, bold=True):
        if pd.isna(var):
            txt, col = "n.d.", "#888888"
        else:
            txt = f"{var:+.1f}%".replace(".", ",")
            col = "#1a8f3c" if var >= 0 else "#c62828"
        ax.text(x, yi, txt, va="center", ha="right", fontsize=8, color=col,
                fontweight="bold" if bold else "normal")

    for yi, (_, r) in enumerate(d.iterrows()):
        ax.text(r[chiave] + xmax * 0.01, yi, fmt_int(r[chiave]), va="center", fontsize=8)
        scrivi_var(x_var, yi, r[f"{chiave}_var"])
        if extra:
            k = extra[0]
            if not r[f"{k}_prec"]:
                ax.text(x_extra, yi, "nuovo" if r[k] else "nessuno", va="center", ha="right",
                        fontsize=7.5, color="#888888", style="italic")
            else:
                scrivi_var(x_extra, yi, r[f"{k}_var"], bold=False)

    ax.text(x_var, n - 0.2, f"vs {MESI[mese][:3]} {anno - 1}", ha="right",
            va="bottom", fontsize=8, color="#555555")
    if extra:
        ax.text(x_extra, n - 0.2, f"{extra[1]}\nvs {MESI[mese][:3]} {anno - 1}", ha="right",
                va="bottom", fontsize=7.5, color="#555555", linespacing=1.1)

    tot, tot_prec = d[chiave].sum(), df.loc[d.index, f"{chiave}_prec"].sum()
    var_tot = (tot / tot_prec - 1) * 100 if tot_prec else float("nan")
    fig.suptitle(f"{cfg['titolo']} – {MESI[mese]} {anno}", x=0.02, ha="left",
                 fontsize=13, fontweight="bold")
    var_txt = f"{var_tot:+.1f}".replace(".", ",")
    ax.set_title(f"{cfg['sottotitolo']}\nTotale testate: {fmt_int(tot)} copie "
                 f"({var_txt}% rispetto a {MESI[mese]} {anno - 1})",
                 loc="left", fontsize=9, color="#444444")
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt_int(v)))
    ax.tick_params(axis="x", labelsize=8)
    # l'asse si ferma sotto le barre, non sotto le colonne delle variazioni
    ax.set_xticks([t for t in ax.get_xticks() if 0 <= t <= xmax * 1.08])
    ax.spines["bottom"].set_bounds(0, xmax * 1.08)
    ax.grid(axis="x", alpha=0.3)
    ax.set_axisbelow(True)
    fig.text(0.02, 0.005, "Fonte: ADS – Accertamenti Diffusione Stampa, dati DMS. "
             "Media giornaliera per numero uscito.", fontsize=7, color="#777777")
    fig.tight_layout(rect=(0, 0.01, 1, 0.98))

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{anno}_{mese:02d}_{chiave}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mese", type=int)
    p.add_argument("--anno", type=int)
    p.add_argument("--force", action="store_true", help="riscarica i dati e rigenera i grafici")
    a = p.parse_args()

    if a.mese and a.anno:
        mese, anno = a.mese, a.anno
    else:
        mese, anno = ultimo_mese_disponibile()

    gia_fatti = [OUT_DIR / f"{anno}_{mese:02d}_{k}.png" for k in METRICHE]
    if all(f.exists() for f in gia_fatti) and not a.force:
        print(f"{MESI[mese]} {anno}: grafici già presenti, niente da fare.")
        return

    print(f"Elaboro {MESI[mese]} {anno} (confronto con {MESI[mese]} {anno - 1})…")
    df = confronta(mese, anno, a.force)
    csv = OUT_DIR / f"{anno}_{mese:02d}_dati.csv"
    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(csv, index=False, sep=";", decimal=",")
    for k in METRICHE:
        print("  →", grafico(df, k, mese, anno))
    print("  →", csv)


if __name__ == "__main__":
    main()
