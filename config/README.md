# Simboli e colori condivisi

Il file da modificare è **[identities.json](identities.json)**. È il registro unico scelto dal proprietario di Electo: viene pubblicato su GitHub Pages e usato da tutti gli utenti, sia nello storico sia nella diretta. Nessun utente dell’app modifica questo registro localmente.

Il registro iniziale è vuoto: non sono stati inventati colori o attribuiti simboli ai partiti. Un risultato non configurato appare in grigio con iniziali. Le statistiche e i nomi ministeriali restano invariati.

## Preparare una voce

1. Cerca la denominazione originale in [identity-candidates.json](https://ilmona98.github.io/electo-data/v1/identity-candidates.json). Per ogni nome trovi gli identificativi dei risultati e delle schede da cui proviene.
2. Modifica `config/identities.json` con l’editor GitHub e aggiungi una voce a `entities`, seguendo il modello sotto.
3. Se vuoi un logo, carica il PNG in `public/symbols/` con un nome semplice, per esempio `mio-partito.png`, e aggiungi `symbolPath`.
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
      "symbolPath": "symbols/mio-partito.png"
    }
  ]
}
```

L’esempio non assegna un colore a un partito reale. Sostituisci i valori con le tue scelte. Per iniziare senza logo ometti `symbolPath`: verrà usata la sigla. `shortLabel` è obbligatorio e deve contenere da 1 a 12 caratteri. `colorHex` contiene esattamente sei cifre esadecimali, senza `#`. `id` è una chiave stabile con lettere minuscole, numeri e trattini: non cambiarla quando cambia il nome da mostrare.

PNG supportati: massimo 2 MB, larghezza e altezza fino a 4096 pixel. Per il repository è preferibile un logo quadrato e leggero. SVG non è supportato dalla visualizzazione nativa attuale. Non inserire `symbolSHA256`: viene calcolato automaticamente dopo il controllo del PNG.

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
