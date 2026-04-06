# AI Workflow, Handoff, Migrazione

## Obiettivo
Rendere trasferibile il contesto di lavoro tra sessioni/macchine senza perdere decisioni e stato.

## File guida
- `docs/ai/AI_HANDOFF_CURRENT.md`
- `docs/ai/AI_DECISIONS_LOG.md`
- `docs/ai/AI_MIGRATION_COMMAND.md`
- `docs/ai/AI_MIGRATION_PASS1_RUNBOOK.md`
- `docs/ai/AI_END_SESSION_CHECKLIST.md`
- `docs/ai/AI_BOOTSTRAP_PROMPT_TEMPLATE.md`

## Flusso sintetico
1. Prima di chiudere: test, aggiornamento handoff corrente, update decision log.
2. Passaggio macchina: clone, setup venv, env, test smoke.
3. Nuova sessione: leggere README + ARCHITECTURE + AI_HANDOFF_CURRENT.

## Rischi processo
- Handoff non aggiornato = perdita contesto.
- Decisioni non registrate = regressioni organizzative.
- Ambiente non allineato = test/run non riproducibili.

Fonti: `docs/ai/*.md`, `ISTRUZIONI_persistenza_contesto_cambio_macchina.md`
