# Sfide tra candidati: suppletive e future regionali

La scheda «Il risultato», quando `resultKind` è `candidates`, mostra i due candidati più votati. I colori partono dalle estremità, la linea centrale indica il 50% dei **voti validi complessivi**. I voti degli altri candidati restano nello spazio neutro: i primi due non vengono normalizzati al 100%. Il riferimento al 50% non determina da solo l’elezione. Nessun candidato viene dichiarato vincitore dalla barra.

La scheda e i dettagli usano la stessa identità politica. Si possono toccare nomi, percentuali e segmenti per aprire il dettaglio. La composizione completa dei sostenitori resta visibile nel dettaglio.

## Configurazione condivisa in `config/identities.json`

I colori restano quelli di `entities[].colorHex`. Sulle coalizioni si può impostare `politicalSide`:

- `left`: a sinistra;
- `center`: al centro dell’ordinamento;
- `right`: a destra.

Si mostrano comunque solo due candidati: se manca una collocazione, l’ordine usa `hemicycleOrder` e infine l’ID per essere stabile, senza assegnare etichette politiche inventate.

### Riconoscere combinazioni di sostenitori

La sezione facoltativa `candidateRules` collega l’insieme **esatto** di ID dei partiti a una identità esistente. Esempio con gli ID presenti nel registro:

```json
"candidateRules": [
  {
    "entityID": "centrodestra",
    "supporterIDs": [
      "fratelli-d-italia", "lega", "noi-moderati", "unione-di-centro", "forza-italia"
    ]
  }
]
```

L’ordine dei partiti non conta. Un partito aggiuntivo, sconosciuto o mancante impedisce il riconoscimento di quella combinazione. Si può usare un solo `supporterID` per associare una candidatura sostenuta da un solo partito a una coalizione. Una regola può avere `electionID` per applicarsi solo a una consultazione; questa ha precedenza su una regola generale per lo stesso insieme.

Il connettore conserva `supporterNames`, i nomi originali delle liste sostenitrici. Il nome completo viene cercato prima di dividerlo ai separatori ministeriali, così un alias come «Azione - Italia Viva» resta una formazione unica. Nuovi connettori possono fornire direttamente `supporterIDs`. Non si utilizzano corrispondenze parziali o somiglianze dei nomi.

Le associazioni esplicite `bindings` e `entityID` hanno precedenza. Anche un alias dell’intera coalizione rimane autorevole. Per la suppletiva 2026 sono configurate le due denominazioni complete pubblicate da Eligendo tra gli alias di centrodestra e centrosinistra; questo permette di riconoscere anche la lista civica senza inventarle un ID o un colore autonomo.

Se non esiste alcuna regola per un singolo partito noto, rimane il colore del partito. Le combinazioni non riconosciute restano neutre. Nessuna assegnazione dipende dai voti o dalla posizione in classifica.

### Cambio politico del seggio

La sezione facoltativa `candidateContests` contiene un riferimento per il **medesimo seggio/collegio**, con:

- `electionID`: consultazione attuale;
- `territoryID`: territorio completo del collegio;
- `previousEntityID`: identità della precedente area politica;
- `sourceURL`: pagina ministeriale verificata che documenta l’esito precedente.

Il segno compare solo se la fonte attuale assegna ufficialmente il singolo seggio (`seats` con un solo eletto e nessun seggio pendente), il territorio corrisponde alla fonte dell’assegnazione e sono note entrambe le `politicalSide`, diverse tra loro. Include il collegamento alla fonte precedente. Il cambio tra coalizioni della stessa area non viene chiamato cambio politico. Un risultato comunale e un vantaggio provvisorio non producono il segno.

Il registro iniziale mantiene `candidateContests` vuoto: non è ancora verificato il riferimento del precedente assegnatario di questo collegio. Il segno resta quindi assente, senza confronti ipotetici. Per le regionali il componente grafico è riutilizzabile; il relativo connettore dovrà fornire l’esito ufficiale e la regola di assegnazione pertinente prima di attivare il confronto sul governatore.

## Verifiche

Il compilatore del registro rifiuta ID sconosciuti, sostenitori duplicati, regole ambigue, confronti duplicati e fonti non ministeriali. L’app valida di nuovo il registro e conserva l’ultima configurazione valida se l’aggiornamento è errato. I test coprono denominatore, orientamento, combinazioni esatte, regole per consultazione, nomi composti, esito ufficiale e isolamento del confronto per collegio.
