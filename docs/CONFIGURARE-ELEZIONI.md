# Configurare una consultazione

Una consultazione corrisponde a un file in `DataPipeline/config/elections/`. Le politiche contengono insieme Camera e Senato; le Europee una sola scheda. I 16 file iniziali conservano esattamente tutte le configurazioni delle 25 schede precedenti, comprese eccezioni revisionate, componenti dei seggi, ordinamenti e confronti. `identities.json` rimane il registro condiviso del proprietario e non viene riscritto dal sistema.

## Percorso consigliato

1. Creare una **bozza** da un formato verificato, senza copiare indirizzi vecchi, seggi, associazioni, confronti o eccezioni:

   ```sh
   python scripts/configure_election.py new --template europee-2024 --event europee-2029 --year 2029 --date-label '10 giugno 2029'
   ```

   L’anno e la data nell’esempio sono illustrativi. Per le politiche usare, per esempio, `--template politiche-20220925` e l’ID e la data reali della nuova consultazione. Il comando non indovina fonti o dati futuri. Per i formati storici speciali si prepara una configurazione esplicita, riutilizzando l’adattatore verificato appropriato.

2. Completare l’unico file creato: indirizzi ufficiali, file/colonne e perimetro dei voti. Per le politiche configurare i riparti in `seats` e, se disponibili, `partySeats` e `seatGroups`. I seggi sono letti dalle fonti, mai ricavati dalle percentuali. Se non disponibili, dichiarare `seatsPolicy: "unavailable"` e motivarlo in `seatsUnavailableReason`. Una bozza incompleta non entra negli aggiornamenti automatici. Gli ID nuovi devono essere univoci; per due consultazioni nello stesso anno assegnare ID distinti espliciti.

3. Su GitHub: **Actions → Configura e pubblica elezioni → Run workflow**, indicare l’ID e scegliere **preview**. Scaricare l’artefatto `anteprima-elezioni`, disponibile per 7 giorni. Il riepilogo compare direttamente nella pagina di esecuzione; `report.md` lo conserva in forma leggibile e `report.json` mostra fonti e impronte, voti, elettori, votanti, seggi attesi/riportati, copertura territoriale, differenze dalla versione precedente, partiti senza associazione e schede preservate. La cartella `public` contiene la copia completa preparata; nessun dato online cambia.

4. Controllare le associazioni mancanti in `identities.json`, mantenendo gli ID già utilizzati dal partito. I confronti con anni precedenti vanno dichiarati solo se stesso ramo, tipo di voto e perimetro sono confrontabili; nomi simili non creano collegamenti automatici. Ripetere l’anteprima dopo correzioni.

5. Selezionare **publish** con lo stesso ID: il processo ricontrolla la configurazione attuale, prepara e installa una nuova copia coerente e attiva la consultazione. **publish riesegue i controlli e non equivale all’approvazione immutabile di un artefatto scaricato in precedenza**. Le richieste HTTP riutilizzano la cache verificata quando il Ministero lo consente. L’app legge il catalogo aggiornato senza modifiche a Xcode per i formati supportati.

## Uso locale

Dalla directory `DataPipeline`, con i requisiti installati:

```sh
python scripts/configure_election.py check
python scripts/configure_election.py plan
python scripts/configure_election.py prepare --event europee-2024 --output /tmp/electo-preview
python scripts/configure_election.py apply --prepared /tmp/electo-preview
```

`prepare` non modifica `public`, manifest o registro originale. L’output deve essere nuovo e fuori da `public`. `apply` verifica le impronte della configurazione, del codice e dell’intera copia di partenza: qualsiasi cambiamento dopo la preparazione impone una nuova verifica. Anche una modifica al rapporto o ai file preparati blocca l’installazione. Un errore durante l’installazione ripristina copia pubblica e configurazioni. Questi comandi locali non eseguono commit o pubblicazioni remote.

## Prestazioni e protezioni

- Un solo processo automatico coordina configurazioni, voti, identità, territori e ricerca. I quattro precedenti workflow restano disponibili esclusivamente come recupero manuale.
- Su modifiche vengono rielaborate soltanto le consultazioni senza ricevuta valida o con configurazione/adattatori cambiati. Cambiando un ramo si verifica l’intera consultazione politica. Modifiche ai soli simboli/identità aggiornano i collegamenti senza scaricare voti.
- La verifica programmata giornaliera continua a controllare tutte le fonti attive: l’elaborazione incrementale non impedisce di scoprire correzioni ministeriali.
- Lo stesso download verificato alimenta voti, gerarchia e ricerca; non si richiede nuovamente il file per convertire i comuni.
- Una ricevuta include configurazione, versione effettiva degli script/requisiti e impronta della fonte. Non si considera aggiornata una fonte non controllata.
- Tutte le schede selezionate devono riuscire. Un errore di fonte, totali o territori interrompe la preparazione e lascia online la copia precedente.
- I dati elettorali delle schede non selezionate rimangono identici. I soli collegamenti alle identità possono essere aggiornati globalmente, senza modificare voti, seggi o date di acquisizione.
- Le elezioni precedenti e i documenti immutabili non vengono eliminati. Non è consentito rimuovere una consultazione pubblicata semplicemente cancellandone il manifest.
- La pubblicazione remota avviene con un unico commit e un singolo artefatto Pages. Se nel frattempo il ramo cambia, il push viene rifiutato: non si forza mai una sovrascrittura.

`sources.json`, `config/seats.json`, `config/party-seats.json` e `config/seat-groups.json` sono esportazioni di compatibilità, generate dopo un’installazione riuscita. Per aggiungere o correggere una consultazione modificare il suo manifest, non queste copie. I formati nuovi, i sistemi elettorali diversi e le fonti ambigue richiedono comunque verifica e, quando necessario, un adattatore nuovo: il sistema non inventa colonne, coalizioni, seggi o collegamenti storici.
