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

**23 schede, 524 riepiloghi territoriali e 15 consultazioni nell’app**, dal 1994 al 2024:

- Politiche, **Camera e Senato**: 2022, 2018, 2013, 2008, 2006, 2001, 1996, 1994. I due rami sono accorpati nella stessa pagina ma conservano risultati distinti.
- Europee: 2024, 2019, 2014, 2009, 2004, 1999, 1994.

La Camera 1994–2001 riporta la scheda proporzionale; il Senato degli stessi anni riporta i gruppi/candidati. Il campo `resultKind` mantiene la distinzione nell’interfaccia. I file Senato di lista 2006, 2008, 2013 e 2022 escludono Valle d’Aosta, Trentino-Alto Adige ed estero; non si aggiungono voti uninominali a un denominatore di lista. Ogni record dichiara il perimetro in `coverage` e `note`.

Il nazionale è la somma esatta dei territori del rispettivo file. Le unità dei comuni suddivisi includono i collegi, per evitare doppioni o perdite. Per Camera e Senato 2018 le tabelle territoriali si riconciliano anche con le nazionali originali dello ZIP. I decimali a zero, per esempio `12345,00`, sono letti come interi esatti nelle tabelle aggregate.

Alcune fonti originali riportano più votanti che elettori per specifici comuni. I valori sono conservati tramite eccezioni revisionate per l’esatta unità e gli esatti conteggi; l’app li segnala nei pulsanti info. Camera 1994 contiene inoltre **-7 voti per RIN.SALENTINA** in `PUGLIA / Foggia - Lucera / Parte di Comune FOGGIA`: è conservata quella singola contribuzione nella somma, senza convertirla in positiva né azzerarla. Altre contribuzioni negative sono rifiutate. I risultati aggregati pubblicati sono sempre non negativi. Se la fonte corregge un’anomalia, la relativa nota non viene più emessa.

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

La suite comprende controlli sulle tabelle nazionali e territoriali del 2018, estratti comunali originali dal 1994, anomalie revisionate e collegi speciali del Senato 2022. Le fixture sono in `tests/fixtures/`; le stringhe sono state ricodificate in UTF-8, senza modificare nomi o conteggi. Non sono inclusi dati personali di candidati.

## Consultazioni politiche e identità visive

I risultati Camera e Senato conservano file e identificativi separati. I campi opzionali `eventID` e `chamber` consentono all’app di presentarli nella stessa pagina Politiche: i sei risultati attuali corrispondono a cinque pagine, senza sommare conteggi o territori delle due camere.

Il proprietario definisce simboli e colori comuni a tutti gli utenti in [`config/identities.json`](config/identities.json). Il registro iniziale è vuoto: nessun colore politico è assegnato arbitrariamente. Per configurarlo segui la [guida](config/README.md), usando il [catalogo dei nomi originali](https://ilmona98.github.io/electo-data/v1/identity-candidates.json). Le immagini SVG o PNG si caricano in `public/symbols/`. Modifiche al registro o ai simboli avviano la validazione e la pubblicazione automatica.

Endpoint del registro compilato: `https://ilmona98.github.io/electo-data/v1/identities.json`. La pipeline verifica associazioni non ambigue, colori, percorsi, integrità dei simboli SVG/PNG e genera gli hash delle immagini. Un registro non valido ferma la pubblicazione. Gli esempi sono illustrativi e non vengono applicati automaticamente.

I simboli SVG originali restano in `public/symbols/`. La pubblicazione genera PNG trasparenti da 512 × 512 pixel, con percorso immutabile basato sull’hash. Il registro compilato resta compatibile con l’app iOS esistente; per le sigle sempre bianche serve la nuova build. Gli SVG devono essere autonomi e statici, senza risorse esterne.

## Seggi delle elezioni politiche

`config/seats.json` configura il recupero automatico dei seggi da Eligendo Archivio per Camera e Senato in tutti gli anni dal 1994 al 2022: indirizzi di Italia, estero e Valle d’Aosta, capienza e associazioni tra liste e coalizioni. Non contiene conteggi dei partiti né dipende da IPU. La pipeline legge le celle ministeriali, somma uninominale e proporzionale senza duplicazioni, verifica i totali di ogni pagina e riconcilia l’intera camera prima di allegare `seats`. Le fonti, con impronta e controllo, sono incluse in `sourcePages` e `checkedAt`. Qualsiasi pagina mancante, data errata, coalizione ambigua o totale incoerente blocca la pubblicazione e conserva i dati precedenti. Il Senato 2018 riporta 314 dei 315 seggi elettivi: il seggio non riportato resta vuoto. Gli estratti originali utilizzati nei test sono in `tests/fixtures/seats/` e `tests/fixtures/historical-seats/`.

Le associazioni tra liste e coalizioni sono dichiarate per denominazione ufficiale: i conteggi sono letti ogni volta dalle pagine, senza attribuire gli uninominali al partito maggiore. Nuove coalizioni o differenze rispetto alla capienza attesa richiedono una revisione della configurazione; non vengono completate con stime. I download automatici ministeriali comprendono sia voti sia seggi. Colori, simboli e label restano definiti separatamente in `config/identities.json`.

Fonti: [Camera 2018](https://data.ipu.org/parliament/IT/IT-LC01/election/IT-LC01-E20180304/), [Senato 2018](https://data.ipu.org/parliament/IT/IT-UC01/election/IT-UC01-E20180304/), [Camera 2022](https://data.ipu.org/parliament/IT/IT-LC01/election/IT-LC01-E20220925/).

## Liste, coalizioni e confronti

Le tabelle nazionali Eligendo arricchiscono i risultati con `coalitionID` e `coalitionName` per le liste effettivamente collegate nello stesso raggruppamento nazionale. Gli identificativi coincidono con quelli del riepilogo dei seggi; colori e label continuano a provenire da `identities.json`. I gruppi si ordinano nell’app per somma dei voti nel territorio selezionato; le liste interne per voti propri. Le liste indipendenti partecipano allo stesso ordinamento come gruppi singoli.

`listSeats` indica **solo i seggi proporzionali di lista in Italia, esclusa Valle d’Aosta ed estero**, letti dalla colonna Seggi delle righe di lista. È pubblicato solo sul riepilogo nazionale; nei territori senza riparto verificato il campo resta assente. Non comprende gli uninominali della coalizione e non va sommato ai totali dell’emiciclo. Lo zero è un conteggio esplicito, l’assenza è un dato non disponibile.

`sources.json` dichiara `previousElectionID`, `comparisonTerritories` (`national`, `regional`) ed eventuali `comparisonAliases`, da denominazione attuale a denominazione precedente. Le associazioni riguardano soltanto confronti verificati e non vengono dedotte da colori, label o somiglianza dei nomi. Camera 2022 si confronta con Camera 2018 solo a livello nazionale; non si equiparano le circoscrizioni dopo cambi di confine. Europee 2024/2019 si collegano rispettivamente a 2019/2014 nei perimetri domestici disponibili. Una lista mancante, un archivio precedente assente o un territorio non abilitato non produce una variazione pari a zero: il confronto resta assente.


### Riparti disponibili e limiti dell’estensione

I riparti completi dei seggi sono verificati per tutte le **16 schede Camera/Senato del 1994, 1996, 2001, 2006, 2008, 2013, 2018 e 2022**. Senato 2022 controlla nove pagine, includendo i sei collegi speciali del Trentino-Alto Adige: il totale è 200, senza completamenti stimati. La formazione locale Campobase rimane una voce distinta: non viene forzata in una coalizione nazionale che non ne descrive tutti i componenti. Per la Camera 1994–2001 le quote proporzionale (155) e uninominale (475) rimangono distinte in legenda: sommano esattamente 630 senza attribuire le vittorie di coalizione al suo partito maggiore. Camera 1994 verifica esplicitamente l’eletto di tutti i 475 collegi. Il Senato 2006 include le indicazioni di eletto da recupero nei collegi speciali, senza dedurre vincitori dalle percentuali.

I nuovi confronti con l’elezione precedente sono dichiarati esplicitamente e limitati al nazionale. Non si confronta il Senato 2022 con il perimetro diverso del 2018, né il voto di lista del Senato 2006 con i gruppi del 2001. Non si confrontano regioni storiche per somiglianza del nome. Il registro grafico del proprietario non viene modificato: le vecchie denominazioni senza associazione restano neutre e vengono incluse nel catalogo `identity-candidates.json`.


### Formati dei riparti storici

`scripts/historical_seats.py` legge tabelle semplici, liste collegate a candidati di coalizione e alberi di collegi selezionabili sul sito ministeriale. Ogni componente dichiara il proprio perimetro e la propria capienza; si verificano sia i totali di coalizione sia quelli del documento. L’albero della Camera 1994 controlla 475 collegi unici, senza contare i comuni che possono ripetere lo stesso eletto. Le richieste sono limitate a tre contemporanee; errori transitori possono essere ritentati, ma errori di schema, 403 e marcatori mancanti interrompono la pubblicazione.

`sourcePages` contiene i collegamenti di accesso alle componenti e `sourceDocuments` conserva URL e SHA-256 dei documenti controllati, inclusi quelli raggiunti tramite i selettori geografici. `groups[].detail` specifica quota e perimetro della voce. I nomi e le appartenenze provengono dalla fonte; componenti non attribuibili con certezza allo stesso raggruppamento restano distinte. Il catalogo `identity-candidates.json` include ora anche i gruppi dei seggi, con i rispettivi binding, e la stessa identità di coalizione si applica alla legenda e alla fascia laterale delle liste. Il file `config/identities.json` del proprietario non viene modificato.
