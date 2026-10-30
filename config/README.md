# Simboli e colori condivisi

Il file da modificare è **[identities.json](identities.json)**. È il registro unico scelto dal proprietario di Electo: viene pubblicato su GitHub Pages e usato da tutti gli utenti, sia nello storico sia nella diretta. Nessun utente dell’app modifica questo registro localmente.

Il registro iniziale è vuoto: non sono stati inventati colori o attribuiti simboli ai partiti. Un risultato non configurato appare in grigio con iniziali. Le statistiche e i nomi ministeriali restano invariati.

## Preparare una voce

1. Cerca la denominazione originale in [identity-candidates.json](https://ilmona98.github.io/electo-data/v1/identity-candidates.json). Per ogni nome trovi gli identificativi dei risultati e delle schede da cui proviene.
2. Modifica `config/identities.json` con l’editor GitHub e aggiungi una voce a `entities`, seguendo il modello sotto.
3. Se vuoi un logo, carica lo SVG in `public/symbols/` con un nome semplice, per esempio `mio-partito.svg`, e aggiungi `symbolPath`.
4. Salva sul ramo `main`. GitHub Actions valida, genera l’hash dell’immagine e pubblica il registro. Nell’app premi Aggiorna o riaprila.

```json
{
  "schemaVersion": 1,
  "entities": [
    {
      "id": "mio-partito",
      "label": "Il nome scelto da te",
      "shortLabel": "MP",
      "kind": "party",
      "colorHex": "123456",
      "aliases": ["DENOMINAZIONE ESATTA NEL FILE MINISTERIALE"],
      "bindings": [],
      "symbolPath": "symbols/mio-partito.svg"
    }
  ]
}
```

L’esempio non assegna un colore a un partito reale. Sostituisci i valori con le tue scelte. Per iniziare senza logo ometti `symbolPath`: verrà usata la sigla. `shortLabel` è obbligatorio e deve contenere da 1 a 12 caratteri. `colorHex` contiene esattamente sei cifre esadecimali, senza `#`. `id` è una chiave stabile con lettere minuscole, numeri e trattini: non cambiarla quando cambia il nome da mostrare.

Sono supportati **SVG** e PNG, entro 2 MB. Carica lo SVG originale in `public/symbols/` e indica, per esempio, `"symbolPath": "symbols/mio-partito.svg"`. Il file di configurazione conserva il riferimento allo SVG; GitHub genera automaticamente una versione PNG trasparente da 512 × 512 pixel, con proporzioni e colori del logo conservati, e inserisce nel registro pubblicato il percorso e l’hash di quella versione. Non occorre convertire il file manualmente né cambiare il formato del registro usato dall’app. Gli output generati hanno nomi immutabili: non modificarli a mano.

Esporta SVG statici e autonomi, preferibilmente con `viewBox` e testi convertiti in tracciati. Collegamenti a immagini o font esterni, script e animazioni non sono supportati. I PNG già presenti restano compatibili (massimo 4096 pixel per lato). Non inserire `symbolSHA256`: viene calcolato automaticamente.

Le sigle nei riquadri colorati dell’app sono sempre bianche. I loghi caricati conservano i colori del file originale.

## Nomi alternativi e regole di corrispondenza

`aliases` contiene tutte le denominazioni esatte da associare alla stessa identità. Maiuscole, accenti, spazi ripetuti e varianti tipografiche dell’apostrofo vengono normalizzati. Non si usano sottostringhe, ricerche approssimative o posizioni in classifica: una lista che include due partiti non viene associata automaticamente a uno di essi.

La priorità è:

1. Un’associazione esplicita in `bindings` per la coppia `electionID` + `resultID`.
2. L’eventuale `entityID` canonico già presente nei dati.
3. Un nome alternativo completo in `aliases`.
4. Stile neutro, se non esiste una corrispondenza.

Per una sigla o un simbolo storico diverso, crea un’identità distinta senza alias globali e usa `bindings` solo per le schede interessate. Per esempio, un’associazione alla Camera 2018 non si applica automaticamente al Senato 2018. Le chiavi da usare rimangono `camera-2018` e `senato-2018`, anche se nell’interfaccia sono raggruppate nella pagina Politiche 2018.

## Coalizioni e candidati

Per una coalizione usa `kind: "coalition"`. Nella diretta ai candidati il nome confrontato è la denominazione completa delle liste collegate, quando presente. In alternativa puoi associare direttamente l’identificativo del candidato con `bindings`.

La diretta attualmente collegata ha `electionID: "camera-20260927-182315"` e gli identificativi `candidate-1`, `candidate-2`, ecc., derivati dalla posizione ministeriale. Queste associazioni vanno sempre limitate alla relativa consultazione. Il catalogo automatico dei nomi elenca le liste storiche; non pretende di elencare candidati di dirette non ancora collegate.

Il registro descrive solo l’identità grafica: non somma voti, non crea nuove coalizioni statistiche e non altera i risultati originali. L’elenco dei membri e il totale di una coalizione richiedono dati elettorali specifici della consultazione.

## Controlli e aggiornamenti

Alias ambigui, associazioni duplicate, colori non validi e immagini mancanti/corrotte fermano la pipeline. Un nome non può appartenere a due identità globali. Puoi però assegnare lo stesso risultato in schede differenti tramite coppie di identificativi distinte.

Il documento pubblicato è [v1/identities.json](https://ilmona98.github.io/electo-data/v1/identities.json). Il client conserva l’ultimo registro valido e le immagini già caricate; le immagini sono verificate tramite SHA-256. Un errore non sostituisce il registro valido con dati non verificati. Le modifiche raggiungono gli utenti dopo la pubblicazione Actions e un aggiornamento del registro nell’app, senza ulteriori build.

[identities.example.json](identities.example.json) è un esempio separato e non viene applicato automaticamente.

## Due errori comuni

L’identificativo tecnico `id` accetta solo lettere minuscole, numeri e trattini: per +Europa usa per esempio `piu-europa`. Il nome visibile e gli alias possono contenere il segno `+`.

Ogni nome alternativo deve essere una stringa distinta: `"aliases": ["Lega", "Lega Salvini Premier", "Lega - Salvini Premier"]`. Inserire tutte le varianti in una sola stringa separata da virgole cerca invece quella frase intera, che non corrisponde alle singole liste.

Per le liste congiunte, come `AZIONE - ITALIA VIVA - CALENDA`, scegli un’identità dedicata o assegna esplicitamente il nome completo a un’unica identità. Non inserire lo stesso alias in due partiti. Il file pubblicato `public/v1/identities.json` è generato: modifica sempre `config/identities.json` e controlla che l’ultima esecuzione di Actions sia verde prima di aggiornare il registro nell’app.
