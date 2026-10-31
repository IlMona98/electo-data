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

I risultati Camera e Senato conservano file e identificativi separati. I campi opzionali `eventID` e `chamber` consentono all’app di presentarli nella stessa pagina Politiche: i 23 risultati attuali corrispondono a 15 consultazioni, senza sommare conteggi o territori delle due camere.

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

`sources.json` dichiara `previousElectionID`, `comparisonTerritories` (`national`, `regional`) ; i vecchi `comparisonAliases` sono conservati per compatibilità, ma non guidano più l’associazione nel nuovo client. Il confronto delle liste usa il medesimo ID canonico di `config/identities.json`, risolto con `bindings` o `aliases`. Le associazioni riguardano soltanto confronti verificati e non vengono dedotte da colori, label o somiglianza dei nomi. Camera 2022 si confronta con Camera 2018 solo a livello nazionale; non si equiparano le circoscrizioni dopo cambi di confine. Europee 2024/2019 si collegano rispettivamente a 2019/2014 nei perimetri domestici disponibili. Una lista mancante, un archivio precedente assente o un territorio non abilitato non produce una variazione pari a zero: il confronto resta assente.


### Riparti disponibili e limiti dell’estensione

I riparti completi dei seggi sono verificati per tutte le **16 schede Camera/Senato del 1994, 1996, 2001, 2006, 2008, 2013, 2018 e 2022**. Senato 2022 controlla nove pagine, includendo i sei collegi speciali del Trentino-Alto Adige: il totale è 200, senza completamenti stimati. Campobase è sommata al raggruppamento «Centrosinistra» nell’emiciclo; la composizione locale, comprendente anche Azione/Italia Viva, resta esplicita nelle note di verifica e non attribuisce il seggio a un singolo partito. Per la Camera 1994–2001 le quote proporzionale (155) e uninominale (475) sono sommate per coalizione/lista nella legenda: sommano esattamente 630 senza attribuire le vittorie di coalizione al suo partito maggiore. Camera 1994 verifica esplicitamente l’eletto di tutti i 475 collegi. Il Senato 2006 include le indicazioni di eletto da recupero nei collegi speciali, senza dedurre vincitori dalle percentuali.

I nuovi confronti con l’elezione precedente sono dichiarati esplicitamente e limitati al nazionale. Non si confronta il Senato 2022 con il perimetro diverso del 2018, né il voto di lista del Senato 2006 con i gruppi del 2001. Non si confrontano regioni storiche per somiglianza del nome. Il registro grafico del proprietario non viene modificato: le vecchie denominazioni senza associazione restano neutre e vengono incluse nel catalogo `identity-candidates.json`.


### Formati dei riparti storici

`scripts/historical_seats.py` legge tabelle semplici, liste collegate a candidati di coalizione e alberi di collegi selezionabili sul sito ministeriale. Ogni componente dichiara il proprio perimetro e la propria capienza; si verificano sia i totali di coalizione sia quelli del documento. L’albero della Camera 1994 controlla 475 collegi unici, senza contare i comuni che possono ripetere lo stesso eletto. Le richieste sono limitate a tre contemporanee; errori transitori possono essere ritentati, ma errori di schema, 403 e marcatori mancanti interrompono la pubblicazione.

`sourcePages` contiene i collegamenti di accesso alle componenti e `sourceDocuments` conserva URL e SHA-256 dei documenti controllati, inclusi quelli raggiunti tramite i selettori geografici. `originalGroups[].detail` conserva quota e perimetro della voce ministeriale prima dell’accorpamento. I nomi e le appartenenze provengono dalla fonte; componenti non attribuibili con certezza allo stesso raggruppamento restano distinte. Il catalogo `identity-candidates.json` include ora anche i gruppi dei seggi, con i rispettivi binding, e la stessa identità di coalizione si applica alla legenda e alla fascia laterale delle liste. Il file `config/identities.json` del proprietario non viene modificato.

### Componenti dei sistemi misti

Per i riparti 2018 e 2022 ogni gruppo espone `components`, un elenco di oggetti `label`/`seats` verificato contro il totale del gruppo: Italia proporzionale, Italia uninominale, estero e collegi speciali. La lettura preserva le due quote nazionali già presenti nella pagina e gli altri perimetri; non stima la distribuzione degli uninominali tra i partiti della stessa coalizione. `listSeats` resta il dato proporzionale Italia. L’app usa i gruppi verificati per mostrare i totali delle liste autonome e delle coalizioni, così non presenta i soli seggi proporzionali come se fossero il totale dell’emiciclo. Le nuove proprietà sono opzionali per compatibilità con cache e pubblicazioni precedenti.

### Totali supplementari per lista

`scripts/party_seats.py` integra soltanto i totali verificati configurati in `config/party-seats.json`, dopo il recupero Eligendo e prima della pubblicazione. Le fonti sono i dati elettorali SPARQL ufficiali della Camera e i rapporti finali OSCE/ODIHR. Nessun totale di partito è scritto a mano nella configurazione. Si controllano coorte, mandati univoci, data di riferimento, somme, lista esplicita, attribuzione della lista estera congiunta e seggi proporzionali minimi già verificati. Si escludono i mandati successivi e i senatori a vita non vengono coinvolti. Le richieste sono riusate all’interno dello stesso aggiornamento. Una fonte errata o incoerente impedisce il deploy; l’ultima pubblicazione resta online.

Copertura: Camera 2006/2008/2013 secondo le liste di elezione esplicite dei mandati; Camera e Senato 2018 con tutte le liste nazionali, dopo la riconciliazione delle identità e delle quote estere/speciali; Camera e Senato 2022 secondo la classificazione del rapporto OSCE/ODIHR del 13 gennaio 2023. Per i due eletti Camera 2022 della lista estera congiunta si verifica l’appartenenza iniziale documentata dalla Camera. Gli indipendenti restano distinti. Questo criterio può produrre conteggi differenti da altre ricostruzioni politiche: viene dichiarato nel dettaglio dell’app, senza sostituire i riparti ministeriali degli emicicli.

`seats.partyTotals` contiene `resultID`, `name`, `seats`, `components`, `sourcePages` con impronte SHA-256, `note` e `referenceDate`. Lo zero deriva da una cella esplicita della fonte oppure, nel 2018, da un riparto chiuso riconciliato integralmente; una voce non verificata viene omessa, non convertita in zero. La copertura rimane parziale: non si assegna un totale alle quote Camera 1994–2001 senza ulteriori riscontri. Testi e mandati originali minimizzati sono in `tests/fixtures/party-seats/`.


### Accorpamento della legenda e riconciliazione 2018

`config/seat-groups.json` contiene esclusivamente associazioni revisionate fra le denominazioni ministeriali delle diverse quote e la voce unica del grafico. `seat_groups.py` somma proporzionale, uninominale, estero e collegi speciali per lo stesso raggruppamento, anche negli anni 1994–2013; conserva `originalGroups` e le componenti, verifica che nessun seggio venga perso o duplicato e non modifica i risultati dei voti. Le liste estere autonome restano liste autonome; le affinità politiche da sole non generano accorpamenti. Nel 1994 il centrodestra comprende entrambi i Poli e le liste collegate, come dichiarato nella nota del riparto.

`reconcile_2018.py` risolve le quattro etichette invertite nell’allegato Camera del rapporto OSCE (PD/FI e +Europa/Civica Popolare). Le identità sono esplicitamente revisionate nella configurazione, non dedotte dal partito con il numero di voti più vicino. I voti ministeriali sono un riscontro supplementare, con un margine massimo del 3,5% per le differenze fra rapporto e archivio; **i seggi di ogni coalizione devono coincidere esattamente**, senza margini o arrotondamenti. Le prime appartenenze parlamentari servono soltanto a ripartire le liste estere congiunte. Il Senato verifica 314 mandati elettivi iniziali, escludendo senatori a vita e subentri; il seggio siciliano M5S rimasto vacante non è conteggiato tra gli assegnati.

Riscontri finali 2018: Camera PD 112, FI 104, Lega 125, FdI 32, M5S 227; Senato PD 53, FI 57, Lega 58, FdI 18, M5S 111. `seats.partyReconciliation` conserva le coppie di voti controllate, i seggi delle liste esterne alla scheda nazionale, i totali delle coalizioni e le tre pagine ministeriali con impronta. La somma delle liste nazionali più quelle esterne coincide con tutti i seggi assegnati. Un errore di riconciliazione interrompe l’aggiornamento prima della pubblicazione.


### Identità canoniche, confronti ed emiciclo

Dopo l’accorpamento dei seggi, `apply_identity_links` collega liste e gruppi ai medesimi ID del registro del proprietario. Pubblica `entityID` e `coalitionEntityID`, mantenendo gli identificativi e i conteggi elettorali. Il client confronta solo ID comuni in elezioni e territori già abilitati; omonimie, assenze e associazioni multiple non producono variazioni inventate. La pubblicazione del registro conserva il campo opzionale `hemicycleOrder` (intero 0–100), usato dal client per l’ordine dei blocchi da sinistra a destra. Senza configurazione vale 50; i pareggi sono risolti con seggi decrescenti e ID. La legenda mantiene l’ordinamento per seggi. Istruzioni in [config/README.md](config/README.md).
