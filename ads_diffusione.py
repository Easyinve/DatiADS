#!/usr/bin/env python3
"""
Scarica i dati mensili ADS (DMS) dei quotidiani da adsnotizie.it e produce una pagina HTML
nello stile dei grafici del Post, con:

1. Diffusione media giornaliera "individuale pagata": cartacee + abbonamenti cartacei + copie digitali
   vendute ad almeno il 30% del prezzo (colonne 2+3+4a; esclusa la 4b, digitali tra il 10 e il 30%)
2. Sole copie digitali individuali vendute ad almeno il 30% del prezzo ufficiale (colonna 4a),
   con la variazione degli abbonamenti superscontati (colonna 4b)
3. L'andamento nel tempo di queste serie, da gennaio 2021: il totale, o i giornali scelti (fino a sei)

Sono esclusi i quotidiani sportivi (Gazzetta dello Sport, Corriere dello Sport, Tuttosport).

Uso:
    python3 ads_diffusione.py                 # ultimo mese disponibile sul sito
    python3 ads_diffusione.py --mese 8 --anno 2026
    python3 ads_diffusione.py --force         # rigenera anche se già fatto
"""

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

BASE = "https://www.adsnotizie.it"
PAGE_URL = f"{BASE}/Dati/DMS_Page"
DOWNLOAD_URL = f"{BASE}/Dati/downloadDMS"
PERIODICITA_QUOTIDIANI = 1
HEADERS = {"User-Agent": "Mozilla/5.0 (ads_diffusione.py)"}

# Prima del 2021 il file ADS non ha il totale delle vendite individuali e le categorie
# potrebbero non essere confrontabili: le serie partono da qui.
INIZIO = (2021, 1)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dati"
OUT_DIR = ROOT / "grafici"
STILE = ROOT / "stile"

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

SERIE = {
    "ip": [COL_CARTACEE, COL_ABB_CARTACEI, COL_DIGITALI_30],  # individuale pagata
    "d30": [COL_DIGITALI_30],                                 # digitali >= 30%
    "ss": [COL_DIGITALI_10_30],                               # superscontati
}

# Quotidiani sportivi (e loro edizioni del lunedì) esclusi
ESCLUDI = re.compile(r"GAZZETTA SPORT|CORRIERE SPORT|TUTTOSPORT", re.IGNORECASE)

# Nomi da mostrare quando la regola generale (vedi nome_leggibile) non basta
NOMI = {
    "QN-Il Resto del Carlino": "Il Resto del Carlino",
    "QN-La Nazione": "La Nazione",
    "QN-Il Giorno": "Il Giorno",
    "CORRIERE Umbria/AR/SI": "Corriere dell’Umbria",
    "NUOVA DI VENEZIA E ME. (LA)": "La Nuova di Venezia e Mestre",
    "GAZZETTA DEL MEZZOGIORNO(LA)": "La Gazzetta del Mezzogiorno",
    "VERITA'(LA)": "La Verità",
    "LIBERTA'": "Libertà",
    "ALTOADIGE": "Alto Adige",
    "ITALIA OGGI": "ItaliaOggi",
    "SOLE 24 ORE (IL)": "Il Sole 24 Ore",
    "PROVINCIA (COMO) (LA)": "La Provincia di Como",
    "MANIFESTO (IL)": "il manifesto",
    "EDICOLA (L')": "L’Edicola del Sud",
    "SECOLO XIX (IL)": "Il Secolo XIX",
}
MINUSCOLE = {"di", "del", "della", "delle", "dei", "degli", "e", "ed", "da", "in"}


def nome_leggibile(raw: str) -> str:
    """'ECO DI BERGAMO (L')' -> 'L’Eco di Bergamo'."""
    raw = raw.strip()
    if raw in NOMI:
        return NOMI[raw]
    articolo = ""
    m = re.match(r"^(.*?)\s*\((IL|LA|L'|LO|I|LE|GLI)\)\s*$", raw, re.IGNORECASE)
    if m:
        raw, articolo = m.group(1), m.group(2)
    parole = []
    for i, p in enumerate(raw.split()):
        pl = p.lower()
        parole.append(pl if (i > 0 and pl in MINUSCOLE) else pl[:1].upper() + pl[1:])
    nome = " ".join(parole).replace("'", "’")
    if articolo:
        art = articolo.capitalize().replace("'", "’")
        nome = art + nome if art.endswith("’") else f"{art} {nome}"
    return nome


# ---------------------------------------------------------------- download

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
    time.sleep(0.3)  # gentilezza verso il sito ADS
    return dest


def mesi_tra(inizio: tuple[int, int], fine: tuple[int, int]) -> list[tuple[int, int]]:
    """Lista di (anno, mese) da inizio a fine compresi."""
    out, (a, m) = [], inizio
    while (a, m) <= fine:
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def leggi(path: Path, mese: int, anno: int) -> pd.DataFrame:
    df = pd.read_excel(path, header=None, skiprows=HEADER_ROWS)
    df = df[df[COL_TESTATA].notna()]
    df = df[(pd.to_numeric(df[COL_ANNO], errors="coerce") == anno)
            & (pd.to_numeric(df[COL_MESE], errors="coerce") == mese)]
    df = df[~df[COL_TESTATA].astype(str).str.contains(ESCLUDI)]
    out = pd.DataFrame({
        "testata": df[COL_TESTATA].astype(str).str.strip(),
        "anno": anno,
        "mese": mese,
        **{k: df[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
           for k, cols in SERIE.items()},
    })
    if out.empty:
        raise RuntimeError(f"Nessuna riga per {mese}/{anno} in {path.name}")
    return out


def storico(fino_a: tuple[int, int], force_ultimo: bool) -> pd.DataFrame:
    """Scarica (se mancano) e legge tutti i mesi da INIZIO a fino_a."""
    mesi = mesi_tra(INIZIO, fino_a)
    parti = []
    for a, m in mesi:
        ultimi = (a, m) == fino_a or (a + 1, m) == fino_a
        parti.append(leggi(scarica(m, a, force_ultimo and ultimi), m, a))
    return pd.concat(parti, ignore_index=True)


# ---------------------------------------------------------------- pagina

def dati_pagina(df: pd.DataFrame, fino_a: tuple[int, int]) -> dict:
    mesi = mesi_tra(INIZIO, fino_a)
    chiavi = [f"{a}-{m:02d}" for a, m in mesi]
    df = df.assign(chiave=df["anno"].astype(str) + "-" + df["mese"].map("{:02d}".format))
    # solo i giornali presenti nell'ultimo mese
    attuali = df.loc[df["chiave"] == chiavi[-1], "testata"].unique()
    testate = []
    for raw in sorted(attuali):
        d = df[df["testata"] == raw].set_index("chiave")
        voce = {"raw": raw, "n": nome_leggibile(raw)}
        for k in SERIE:
            s = d[k].reindex(chiavi)
            voce[k] = [None if pd.isna(v) else int(v) for v in s]
        testate.append(voce)
    oggi = date.today()
    return {"mesi": chiavi, "testate": testate,
            "aggiornato": f"{oggi.day} {MESI[oggi.month]} {oggi.year}"}


def scrivi_pagina(dati: dict, dest: Path) -> None:
    modello = (STILE / "pagina.html").read_text(encoding="utf-8")
    pagina = (modello
              .replace("/*__CSS__*/", (STILE / "theme.css").read_text(encoding="utf-8"))
              .replace("__LOGO_CHIARO__", (STILE / "logo-ilpost.datauri.txt").read_text().strip())
              .replace("__LOGO_SCURO__", (STILE / "logo-ilpost-scuro.datauri.txt").read_text().strip())
              .replace("/*__DATA__*/null", json.dumps(dati, ensure_ascii=False, separators=(",", ":"))))
    dest.write_text(pagina, encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mese", type=int)
    p.add_argument("--anno", type=int)
    p.add_argument("--force", action="store_true",
                   help="riscarica l'ultimo mese (e lo stesso mese dell'anno prima) e rigenera la pagina")
    a = p.parse_args()

    if a.mese and a.anno:
        mese, anno = a.mese, a.anno
    else:
        mese, anno = ultimo_mese_disponibile()

    OUT_DIR.mkdir(exist_ok=True)
    pagina_mese = OUT_DIR / f"{anno}_{mese:02d}.html"
    if pagina_mese.exists() and not a.force:
        print(f"{MESI[mese]} {anno}: pagina già presente, niente da fare.")
        return

    print(f"Elaboro {MESI[mese]} {anno} (storico da {MESI[INIZIO[1]]} {INIZIO[0]})…")
    df = storico((anno, mese), a.force)

    df.sort_values(["testata", "anno", "mese"]).to_csv(
        OUT_DIR / "dati_storici.csv", index=False, sep=";", decimal=",")
    dati = dati_pagina(df, (anno, mese))
    scrivi_pagina(dati, pagina_mese)
    # index.html è sempre l'ultimo mese disponibile
    ultimo = max(OUT_DIR.glob("[0-9][0-9][0-9][0-9]_[0-9][0-9].html"))
    if ultimo == pagina_mese:
        scrivi_pagina(dati, OUT_DIR / "index.html")
    for f in (pagina_mese, OUT_DIR / "index.html", OUT_DIR / "dati_storici.csv"):
        print("  →", f)


if __name__ == "__main__":
    main()
