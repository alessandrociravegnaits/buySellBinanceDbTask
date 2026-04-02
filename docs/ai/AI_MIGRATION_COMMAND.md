# AI Migration Command Rule

## Command
`/pass1-migrazione`

## Purpose
Eseguire una chiusura sessione standardizzata su questa macchina e preparare la riapertura su un'altra macchina senza perdita di contesto operativo.

## Mandatory flow on command
1. Eseguire validazione minima:
   - `python -m pytest -q`
2. Aggiornare `docs/ai/AI_HANDOFF_CURRENT.md` con:
   - completato in questa sessione,
   - top 3 task successivi in ordine di priorita,
   - rischi/issue noti,
   - comandi run/test verificati.
3. Aggiornare `docs/ai/AI_END_SESSION_CHECKLIST.md` e confermare che tutte le voci obbligatorie siano coperte nel report finale.
4. Se e stata presa una decisione tecnica, aggiornare `docs/ai/AI_DECISIONS_LOG.md`.
5. Restituire all'utente:
   - stato sintetico,
   - file aggiornati,
   - comando di riapertura per nuova macchina.

## Reopen command for new machine
Usare questo prompt all'avvio della nuova sessione AI:

"Apri README.md, ARCHITECTURE.md, docs/ai/AI_HANDOFF_CURRENT.md e docs/ai/AI_MIGRATION_COMMAND.md. Esegui il flusso PASS1, poi proponi il prossimo passo minimo sicuro."
