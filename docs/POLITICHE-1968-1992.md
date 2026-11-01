# Politiche 1968–1992

Aggiunte le consultazioni del 19 maggio 1968, 7 maggio 1972, 20 giugno 1976, 3 giugno 1979, 26 giugno 1983, 14 giugno 1987 e 5 aprile 1992, ciascuna con Camera e Senato. I sette manifest sono in `config/elections/`; si riutilizzano gli adattatori esistenti, senza modifiche al codice dell’app o di conversione.

Tutte le quattordici tabelle nazionali Eligendo riportano riparti completi da **630 deputati e 315 senatori elettivi**. I valori delle singole liste/gruppi, compresi gli zeri, sono letti dalle celle dei seggi. Non si assegnano seggi dai voti né si includono senatori a vita.

| Anno | Camera | Senato |
| --- | --- | --- |
| 1968 | Italia e 32 circoscrizioni | Italia e 20 regioni |
| 1972 | Italia e 32 circoscrizioni | Italia e 20 regioni |
| 1976 | Italia e 32 circoscrizioni | Italia e 20 regioni |
| 1979 | Italia e 32 circoscrizioni | Italia e 20 regioni |
| 1983 | Italia e 32 circoscrizioni | Italia e 20 regioni |
| 1987 | Italia e 32 circoscrizioni | Solo Italia |
| 1992 | Solo Italia | Solo Italia |

## Fonti originali

- 1968: [Camera](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=19/05/1968&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=19/05/1968&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).
- 1972: [Camera](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=07/05/1972&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=07/05/1972&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).
- 1976: [Camera](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=20/06/1976&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=20/06/1976&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).
- 1979: [Camera](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=03/06/1979&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=03/06/1979&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).
- 1983: [Camera](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=26/06/1983&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=26/06/1983&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).
- 1987: [Camera](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=14/06/1987&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=14/06/1987&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).
- 1992: [Camera](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=05/04/1992&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=05/04/1992&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).

## Riconciliazione e limiti

Undici schede riconciliano esattamente nazionale e territori per ogni lista/gruppo, elettori e votanti. Nella Camera 1979 si dichiara un solo alias controllato: `UNITA DELLA SINISTRA` delle circoscrizioni corrisponde a `UNITA' DELLA SINISTRA` del nazionale, per 23.909 voti. Non cambiano nomi o voti originali: il legame è conservato in `nationalResultID`.

Le tabelle della Campania al Senato 1987 ripetono DC e PSI; quella del 1992 ripete PSI. Il convertitore rifiuta tali righe senza sommarle arbitrariamente. La Camera 1992 presenta denominazioni territoriali non riconciliabili con i raggruppamenti nazionali, con differenze anche nei voti del Partito Pensionati. Queste tre schede sono quindi esplicitamente `national-only`, con spiegazione nell’info della fonte. Si mantengono i nazionali originali; non si inventano territori di compensazione.

## Identità e confronti

Si aggiungono solo binding alle identità già definite dal proprietario, senza modificare colori, label, simboli, alias o ordine. Le associazioni riguardano PCI, MSI-DN, Democrazia Proletaria, Partito Radicale, UV e la Lista Verde. Nel 1992 la denominazione ministeriale `LEGA LOMBARDA` del risultato nazionale con 55 deputati/25 senatori è collegata a `lega-nord`; non viene esteso lo stesso legame alle distinte liste regionali precedenti.

Le formazioni congiunte restano separate: PCI-PSIUP, PSU, alleanze valdostane e cartelli laici non vengono attribuiti per intero a un singolo partito. PDS e Rifondazione Comunista del 1992 mantengono identità differenti dal PCI; i passaggi organizzativi non sono equiparati automaticamente. Le formazioni senza identità configurata restano neutre.

La catena dei confronti nazionali collega ogni consultazione alla precedente, dal 1963 al 1992, separando Camera e Senato. Le osservazioni mancanti del singolo partito restano mancanti, per esempio il PCI al Senato 1968/1972 quando si presenta il gruppo PCI-PSIUP. I grafici usano tratti tratteggiati attraverso queste interruzioni. Il passaggio ai sistemi misti del 1994 non viene reso equivalente automaticamente: le configurazioni precedenti restano invariate.

## Verifiche e copertura

Sono conservati estratti di 378 pagine ufficiali in sette fixture annuali `tests/fixtures/votes-1968-1992/*.json.gz`, con intestazioni, selettori e tabelle. I controlli verificano tutti i seggi, gli zeri, le undici serie territoriali, il rifiuto dei casi incoerenti, l’alias del 1979 e i confronti per ID canonico senza confondere coalizioni e partiti.

L’archivio comprende ora **45 schede in 26 consultazioni**, con **1.003 riepiloghi** e **38 emicicli politici**. Sono presenti tutte le consultazioni politiche dal 1948 al 1992, oltre a quelle già incluse dal 1994. I dati delle 31 schede precedenti restano invariati. L’aggiunta è incrementale e arriva aggiornando l’Archivio nella versione dell’app già compatibile con le coperture nazionali.
