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

Il documento completo rimane un JSON compatto: l’iPhone non deve scaricare gli archivi originali, che complessivamente superano i 170 MB. Il catalogo contiene i riepiloghi e i collegamenti ai singoli documenti. I JSON pubblici includono date di acquisizione, ultimo controllo della fonte, file originale e hash. Queste date non sono una data di proclamazione o di ultimo aggiornamento ministeriale.

## Attivazione

Il workflow è `.github/workflows/refresh-data.yml`. Si esegue quando cambiano script/configurazione, su richiesta da **Actions → Aggiorna dati Eligendo → Run workflow**, e ogni giorno alle **04:37 UTC**. Gli orari programmati di GitHub possono subire ritardi.

Per Pages: **Settings → Pages → Build and deployment → Source → GitHub Actions**. I JSON sul ramo `main` restano accessibili tramite l’endpoint alternativo anche se Pages non è ancora attivo. Se GitHub segnala restrizioni sulla scrittura del workflow, l’amministratore del repository deve autorizzare i permessi richiesti.

I job hanno permessi limitati: scrittura dei contenuti per salvare i soli risultati e, nel job separato di pubblicazione, scrittura Pages e token OIDC per il deploy. Non servono token personali salvati come secret. Il token temporaneo è quello fornito da Actions.

## Copertura attuale

- Europee 8–9 giugno 2024: Italia e 20 regioni, esclusi estero e fuori sede.
- Camera 25 settembre 2022: Italia e 27 circoscrizioni del file proporzionale, esclusi Valle d’Aosta ed estero; sono sommati i VOTILISTA originali senza aggiungere i riparti dei voti ai soli candidati.
- Europee 26 maggio 2019: Italia e 20 regioni, escluso estero.
- Camera 4 marzo 2018: Italia e 27 circoscrizioni; Valle d’Aosta ed estero esclusi.
- Senato 4 marzo 2018: Italia e 19 regioni del file; Valle d’Aosta ed estero esclusi.
- Europee 25 maggio 2014: Italia e 20 regioni, escluso estero.

Totale: **6 consultazioni e 139 riepiloghi territoriali**. Per Camera e Senato 2018 i voti di ciascuna lista e l’affluenza sono verificati contro le tabelle nazionali pubblicate nello stesso ZIP. I conteggi con decimali a zero, per esempio `12345,00`, sono letti come interi esatti: valori frazionari vengono rifiutati.

Nel file Europee 2014 Montescano (Pavia) riporta 348 elettori e 352 votanti. Il convertitore conserva questi valori e pubblica una nota nel campo `note` e in `qualityNotes`. L’eccezione è limitata a quell’unità e a quei conteggi esatti; altre incoerenze continuano a fermare la pubblicazione. Se la fonte corregge i valori, la nota non viene più emessa.

Le percentuali si riferiscono al perimetro dei file. Non sono assegnazioni di seggi. Nuove consultazioni o formati richiedono un adattatore verificato e una voce in `sources.json`: la pipeline aggiorna automaticamente le fonti supportate, non promette di interpretare qualsiasi futuro file del Ministero.

Fonti e attribuzione: **Ministero dell’Interno — Archivio storico delle elezioni / Eligendo**. Catalogo originale: https://elezionistorico.interno.gov.it/eligendo/opendata.php. Tutti gli indirizzi originali sono conservati in `sources.json` e nei risultati.

## Esecuzione locale e test

Python 3.10 o successivo. CairoSVG prepara i simboli SVG; l’aggregazione dei dati elettorali usa la libreria standard. [Documentazione CairoSVG](https://cairosvg.org/documentation/).

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 scripts/sync.py
```

I file originali e i metadati HTTP vengono conservati in `.cache/`, esclusa da Git. Quando la fonte supporta ETag o Last-Modified, vengono usate richieste condizionali; una risposta 304 riutilizza una copia il cui hash viene verificato. La cache non sostituisce una fonte fallita fingendo un nuovo controllo riuscito.

Gli output sono in `public/v1/`. Il catalogo viene pubblicato soltanto dopo i documenti a cui punta. Gli oggetti immutabili precedenti sono conservati per evitare che un catalogo in cache punti a file già eliminati.

## Verifiche dei formati storici

La suite comprende 30 test, inclusi controlli su tabelle territoriali e nazionali originali del 2018 e un estratto comunale originale del 2014. Le fixture sono in `tests/fixtures/`; le stringhe sono state ricodificate in UTF-8, senza modificare nomi o conteggi. Non sono inclusi dati personali di candidati.

## Consultazioni politiche e identità visive

I risultati Camera e Senato conservano file e identificativi separati. I campi opzionali `eventID` e `chamber` consentono all’app di presentarli nella stessa pagina Politiche: i sei risultati attuali corrispondono a cinque pagine, senza sommare conteggi o territori delle due camere.

Il proprietario definisce simboli e colori comuni a tutti gli utenti in [`config/identities.json`](config/identities.json). Il registro iniziale è vuoto: nessun colore politico è assegnato arbitrariamente. Per configurarlo segui la [guida](config/README.md), usando il [catalogo dei nomi originali](https://ilmona98.github.io/electo-data/v1/identity-candidates.json). Le immagini SVG o PNG si caricano in `public/symbols/`. Modifiche al registro o ai simboli avviano la validazione e la pubblicazione automatica.

Endpoint del registro compilato: `https://ilmona98.github.io/electo-data/v1/identities.json`. La pipeline verifica associazioni non ambigue, colori, percorsi, integrità dei simboli SVG/PNG e genera gli hash delle immagini. Un registro non valido ferma la pubblicazione. Gli esempi sono illustrativi e non vengono applicati automaticamente.

I simboli SVG originali restano in `public/symbols/`. La pubblicazione genera PNG trasparenti da 512 × 512 pixel, con percorso immutabile basato sull’hash. Il registro compilato resta compatibile con l’app iOS esistente; per le sigle sempre bianche serve la nuova build. Gli SVG devono essere autonomi e statici, senza risorse esterne.
