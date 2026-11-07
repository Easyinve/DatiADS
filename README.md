# Diffusione quotidiani – dati ADS

Ogni mese scarica da [ADS](https://www.adsnotizie.it/Dati/DMS_Page) i dati DMS dei quotidiani e genera due grafici in `grafici/`:

- **`AAAA_MM_individuale_pagata.png`**: diffusione media giornaliera individuale pagata (cartacee + abbonamenti cartacei + digitali vendute ad almeno il 30% del prezzo, col. 2+3+4a ADS) e variazione % sullo stesso mese dell'anno precedente
- **`AAAA_MM_digitale_30.png`**: sole copie digitali individuali vendute ad almeno il 30% del prezzo ufficiale (col. 4a ADS)
- **`AAAA_MM_dati.csv`**: i numeri usati nei grafici

Sono esclusi i quotidiani sportivi. Gli Excel originali vengono salvati in `dati/`.

## Esecuzione automatica

Il workflow `.github/workflows/ads.yml` parte il 1° e il 15 di ogni mese e salva nel repository i grafici nuovi.
Per lanciarlo a mano: tab **Actions** → *Dati ADS mensili* → **Run workflow** (si può indicare mese e anno).

## In locale

```bash
pip install -r requirements.txt
python3 ads_diffusione.py                    # ultimo mese disponibile
python3 ads_diffusione.py --mese 8 --anno 2026
```
