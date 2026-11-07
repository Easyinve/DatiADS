# Diffusione quotidiani – dati ADS

Ogni mese scarica da [ADS](https://www.adsnotizie.it/Dati/DMS_Page) i dati DMS dei quotidiani e genera una pagina HTML nello stile dei grafici del Post (tema chiaro e scuro, pensata prima per il telefono):

- **Diffusione individuale pagata**: copie cartacee, abbonamenti cartacei e copie digitali vendute ad almeno il 30% del prezzo (col. 2+3+4a ADS), con la variazione sullo stesso mese dell'anno prima
- **Copie digitali vendute ad almeno il 30% del prezzo** (col. 4a), con accanto la variazione degli abbonamenti superscontati (10-30% del prezzo, col. 4b)
- **Andamento nel tempo** da gennaio 2021, con un grafico a linee per la diffusione individuale pagata, uno per i digitali ad almeno il 30% e uno per i superscontati

All'apertura nessun giornale è evidenziato e i grafici a linee mostrano il totale. Con la ricerca (o toccando le barre) si possono evidenziare fino a sei giornali, ognuno con il suo colore in tutti i grafici. Sono esclusi i quotidiani sportivi.

## File prodotti

- `grafici/index.html`: la pagina dell'ultimo mese disponibile
- `grafici/AAAA_MM.html`: la pagina di ogni mese, per archivio
- `grafici/dati_storici.csv`: tutti i dati usati, mese per mese
- `dati/`: gli Excel originali di ADS

L'aspetto della pagina è in `stile/pagina.html` (modello) e `stile/theme.css` (colori e caratteri del Post).

## Esecuzione automatica

Il workflow `.github/workflows/ads.yml` parte il 1° e il 15 di ogni mese e salva nel repository le pagine nuove.
Per lanciarlo a mano: tab **Actions** → *Dati ADS mensili* → **Run workflow** (si può indicare mese e anno).

## In locale

```bash
pip install -r requirements.txt
python3 ads_diffusione.py                    # ultimo mese disponibile
python3 ads_diffusione.py --mese 8 --anno 2026
```
