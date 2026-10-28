# Electo Data

Recupero automatico degli open data elettorali del Ministero dell’Interno e distribuzione di JSON per l’app Electo. Nessun progetto Xcode, credenziale o dato personale viene pubblicato qui.

## Come funziona

1. GitHub Actions scarica i file originali del Ministero, seguendo soltanto reindirizzamenti HTTPS ai suoi domini verificati.
2. Il convertitore deduplica gli elettori e i votanti ripetuti sulle righe di lista, aggrega i territori e riconcilia i conteggi.
3. Soltanto se tutte le fonti superano i controlli vengono aggiornati i JSON e pubblicati su Pages. Se una fonte fallisce, l’ultima versione pubblica resta intatta e il workflow fallisce in modo visibile.
4. Electo recupera il JSON online e conserva una copia sul dispositivo. La fonte dei dati resta il Ministero; GitHub ne distribuisce gli estratti.

## Endpoint

- Archivio completo compatto: `https://ilmona98.github.io/electo-data/v1/archive.json`.
- Catalogo leggero: `https://ilmona98.github.io/electo-data/v1/catalog.json`.
- Per ciascuna consultazione il catalogo indica un file immutabile e il suo SHA-256.
- Endpoint alternativo utilizzato dall’app se Pages non è disponibile: `https://raw.githubusercontent.com/IlMona98/electo-data/main/public/v1/archive.json`.

Il file completo iniziale è circa **83 KB**: l’iPhone non deve scaricare gli archivi originali, che complessivamente superano i 170 MB. Il catalogo è circa 7 KB. I JSON pubblici includono date di acquisizione, ultimo controllo della fonte, file originale e hash. Queste date non sono una data di proclamazione o di ultimo aggiornamento ministeriale.

## Attivazione

Il workflow è `.github/workflows/refresh-data.yml`. Si esegue quando cambiano script/configurazione, su richiesta da **Actions → Aggiorna dati Eligendo → Run workflow**, e ogni giorno alle **04:37 UTC**. Gli orari programmati di GitHub possono subire ritardi.

Per Pages: **Settings → Pages → Build and deployment → Source → GitHub Actions**. I JSON sul ramo `main` restano accessibili tramite l’endpoint alternativo anche se Pages non è ancora attivo. Se GitHub segnala restrizioni sulla scrittura del workflow, l’amministratore del repository deve autorizzare i permessi richiesti.

I job hanno permessi limitati: scrittura dei contenuti per salvare i soli risultati e, nel job separato di pubblicazione, scrittura Pages e token OIDC per il deploy. Non servono token personali salvati come secret. Il token temporaneo è quello fornito da Actions.

## Copertura attuale

- Europee 8–9 giugno 2024: Italia e 20 regioni, esclusi estero e fuori sede.
- Camera 25 settembre 2022: Italia e 27 circoscrizioni del file proporzionale, esclusi Valle d’Aosta ed estero; sono sommati i VOTILISTA originali senza aggiungere i riparti dei voti ai soli candidati.
- Europee 26 maggio 2019: Italia e 20 regioni, escluso estero.

Le percentuali si riferiscono al perimetro dei file. Non sono assegnazioni di seggi. Nuove consultazioni o formati richiedono un adattatore verificato e una voce in `sources.json`: la pipeline aggiorna automaticamente le fonti supportate, non promette di interpretare qualsiasi futuro file del Ministero.

Fonti e attribuzione: **Ministero dell’Interno — Archivio storico delle elezioni / Eligendo**. Catalogo originale: https://elezionistorico.interno.gov.it/eligendo/opendata.php. Tutti gli indirizzi originali sono conservati in `sources.json` e nei risultati.

## Esecuzione locale e test

Python 3.9 o successivo; soltanto libreria standard.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/sync.py
```

I file originali e i metadati HTTP vengono conservati in `.cache/`, esclusa da Git. Quando la fonte supporta ETag o Last-Modified, vengono usate richieste condizionali; una risposta 304 riutilizza una copia il cui hash viene verificato. La cache non sostituisce una fonte fallita fingendo un nuovo controllo riuscito.

Gli output sono in `public/v1/`. Il catalogo viene pubblicato soltanto dopo i documenti a cui punta. Gli oggetti immutabili precedenti sono conservati per evitare che un catalogo in cache punti a file già eliminati.
