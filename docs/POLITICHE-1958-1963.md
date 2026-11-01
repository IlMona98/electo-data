# Politiche 1958 e 1963

Le consultazioni `politiche-19580525` e `politiche-19630428` sono configurate in due manifest, ciascuno con Camera e Senato. Si riutilizzano gli adattatori esistenti senza modificare il codice di conversione o il modello dell’app.

| Consultazione | Ramo | Seggi elettivi | Copertura verificata |
| --- | --- | ---: | --- |
| 25 maggio 1958 | Camera | 596 | Italia e 32 circoscrizioni |
| 25 maggio 1958 | Senato | 246 | Solo Italia |
| 28 aprile 1963 | Camera | 630 | Italia e 32 circoscrizioni |
| 28 aprile 1963 | Senato | 315 | Italia e 19 regioni |

Fonti: [Camera 1958](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=25/05/1958&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato 1958](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=25/05/1958&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Camera 1963](https://elezionistorico.interno.gov.it/index.php?tpel=C&dtel=28/04/1963&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A), [Senato 1963](https://elezionistorico.interno.gov.it/index.php?tpel=S&dtel=28/04/1963&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A).

I seggi provengono dalle celle nazionali Eligendo, compresi gli zeri. Ogni somma deve corrispondere alla capienza effettiva della rispettiva camera; nessun seggio è ricavato dalle percentuali. I senatori a vita sono esclusi. Gli emicicli e la lista dei risultati usano questi riparti.

## Differenza rilevata nel Senato 1958

I totali regionali di elettori e votanti coincidono con il nazionale, ma le regioni sommano 3.683.045 voti al PSI contro 3.682.945 pubblicati nella tabella nazionale: una differenza di 100 voti. Il convertitore ordinario rifiuta questa discordanza. Si pubblica quindi il riepilogo nazionale originale con copertura esplicita `national-only`, senza alterare i voti né inventare un territorio di compensazione. Il motivo è indicato nell’info della fonte.

Le altre tre schede si riconciliano esattamente per ogni lista/gruppo, elettori e votanti. Si conservano le circoscrizioni e le regioni storiche pubblicate, senza inventare dettagli comunali.

## Identità e confronti

Le nuove associazioni riguardano soltanto gli ID già definiti dal proprietario: PCI in entrambi i rami e anni, Partito Monarchico Popolare nel 1958 e Union Valdôtaine dove presente come UV. Non si modificano colori, nomi, simboli o ordinamenti. Le formazioni congiunte, fra cui PRI-P.RAD., PCI-PSI e DC-PRI, restano distinte dai singoli partiti: non vengono assegnati arbitrariamente voti o seggi a uno dei membri. PDIUM e le altre formazioni prive di identità configurata mantengono i nomi originali e la presentazione neutra.

I collegamenti storici sono 1958 → 1953 e 1963 → 1958, sempre nello stesso ramo e soltanto al nazionale. Non si equiparano automaticamente le suddivisioni territoriali, anche considerando l’ingresso di Trieste nel perimetro elettorale successivo al 1953.

## Verifiche e risultato

La fixture `tests/fixtures/votes-1958-1963/pages.json.gz` conserva estratti di 106 pagine ministeriali, con intestazioni, selettori e tabelle. I controlli verificano la riconciliazione delle tre serie complete, il rifiuto della discordanza del 1958, tutte e quattro le capienze, gli zeri e i riferimenti alle consultazioni precedenti. I controlli dell’app verificano anche le identità e la continuità dei grafici 1953–1958–1963.

Dopo l’aggiunta l’archivio comprende 31 schede in 19 consultazioni, 697 riepiloghi e 24 emicicli politici. Le 27 schede precedenti vengono conservate dal processo incrementale. Con la versione dell’app che già supporta il Senato 1953 nazionale, queste aggiunte arrivano aggiornando l’Archivio senza modifiche al codice dell’app.
