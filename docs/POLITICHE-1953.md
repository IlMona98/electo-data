# Politiche del 7 giugno 1953

La consultazione `politiche-19530607` comprende Camera e Senato nella stessa pagina. L’unico manifest è `DataPipeline/config/elections/politiche-19530607.json`, preparato come bozza e verificato tramite anteprima isolata prima dell’attivazione.

| Ramo | Voti validi nella tabella Eligendo | Seggi elettivi | Dettaglio pubblicato |
| --- | ---: | ---: | --- |
| Camera | 27.087.701 | 590 | Italia e 31 circoscrizioni |
| Senato | 24.296.277 | 237 | Solo Italia |

Le figure sono quelle delle tabelle Eligendo utilizzate: non sono sostituite con conteggi di altre fonti. I senatori a vita sono esclusi. I valori nazionali delle singole liste/gruppi e tutti i seggi sono letti dalle celle ministeriali, compresi gli zeri espliciti. Gli emicicli usano il numero di seggi effettivo e il layout adattivo già disponibile; non si assumono 630/315 per tutte le elezioni precedenti al taglio dei parlamentari.

Fonti:

- [Camera, Italia, 7 giugno 1953](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=07/06/1953&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).
- [Senato, Italia, 7 giugno 1953](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=07/06/1953&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).

## Copertura e limiti riscontrati

La Camera riconcilia esattamente il nazionale con tutte le 31 circoscrizioni: elettori, votanti e voti di ogni lista. Non sono necessari alias tra denominazioni territoriali e nazionali.

Per il Senato, invece, le 19 tabelle regionali pubblicate riportano complessivamente 27.171.039 elettori e 25.492.170 votanti, contro 27.172.871 e 25.483.201 nella tabella nazionale. Anche la distribuzione di alcuni voti fra gruppi differisce. La somma dei voti validi coincide, ma questo non rende coerenti gli altri dati. Le regioni non vengono corrette o riassegnate: la pubblicazione include esclusivamente il riepilogo nazionale originale, con `territorialCoverage: "national-only"` e motivazione nel pulsante info. Il selettore territoriale di quel ramo non è interattivo.

I file comunali del 1953 sono stati verificati e non sono utilizzati: comprendono unità con votanti superiori agli elettori e valori non allineati ai riepiloghi; il file dei candidati Senato contiene inoltre 248 marcatori di eletto contro 237 seggi. Non si introducono eccezioni massive per farli passare e non si deducono seggi da tali marcatori.

## Confronti e identità

I confronti con il 1948 sono limitati al nazionale e allo stesso ramo e tipo di voto. Non viene collegato PCI/PSI al Fronte Democratico Popolare come se fosse lo stesso partito. I quattro nuovi binding collegano PCI di Camera/Senato, PART.NAZ.MONARCHICO del Senato ed EDELWEISS agli ID già esistenti del proprietario, senza modificare label, colori, simboli, alias o ordinamento. Gli altri collegamenti già riconosciuti dal registro vengono riutilizzati; le liste prive di configurazione restano neutre.

## Verifiche

Gli estratti di 52 pagine ministeriali sono conservati nella fixture `tests/fixtures/votes-1953/pages.json.gz`, limitando il contenuto a intestazioni, selettori e tabelle ed escludendo immagini e codice estraneo ai controlli. I test riconciliano la Camera lista per lista, verificano i 590/237 seggi, dimostrano il rifiuto dei riepiloghi regionali discordanti e impediscono una copertura nazionale non esplicita. I controlli nativi verificano anche identità, zeri, emicicli e rifiuto di territori fittizi in una scheda nazionale.

La copia inclusa nell’app comprende ora 27 schede, accorpate in 17 consultazioni, con 610 riepiloghi e 20 emicicli politici. Per leggere il nuovo caso nazionale senza suddivisioni occorre la build aggiornata dell’app; le verifiche di coerenza dei record territoriali precedenti restano attive.
