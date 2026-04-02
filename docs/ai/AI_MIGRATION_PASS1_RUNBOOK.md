# PASS1 Migration Runbook

## Goal
Chiudere una sessione in modo ripetibile e riaprire il contesto su un'altra macchina con impatto minimo.

## Close on current machine
1. Lancia test base: `python -m pytest -q`
2. Aggiorna handoff corrente: `docs/ai/AI_HANDOFF_CURRENT.md`
3. Verifica checklist: `docs/ai/AI_END_SESSION_CHECKLIST.md`
4. Se serve, aggiorna decision log: `docs/ai/AI_DECISIONS_LOG.md`

## Files to carry to the next machine
- `README.md`
- `ARCHITECTURE.md`
- `requirements.txt`
- `docs/ai/AI_HANDOFF_CURRENT.md`
- `docs/ai/AI_MIGRATION_COMMAND.md`
- `docs/ai/AI_END_SESSION_CHECKLIST.md`
- `docs/ai/AI_DECISIONS_LOG.md` (se presente)

## Open on new machine
1. Clona repository e crea ambiente virtuale.
2. Installa dipendenze da `requirements.txt`.
3. Configura variabili ambiente richieste.
4. Lancia il comando prompt di riapertura descritto in `docs/ai/AI_MIGRATION_COMMAND.md`.

## Definition of done (PASS1)
- Test base eseguiti.
- Handoff aggiornato con stato e priorita.
- Rischi dichiarati.
- Comandi run/test riproducibili inclusi.
