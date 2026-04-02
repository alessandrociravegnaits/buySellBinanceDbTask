# AI End Session Checklist (60 seconds)

## Comando rapido (PASS1)
- Trigger: `/pass1-migrazione`
- Regola: quando viene ricevuto questo comando, eseguire il flusso descritto in `docs/ai/AI_MIGRATION_COMMAND.md` e aggiornare i file di handoff in `docs/ai`.

## Must do before closing
- [x] Tests or validation command executed.
- [x] Handoff file updated with what changed.
- [x] Top 3 next tasks written.
- [x] Risks/known issues explicitly listed.
- [x] Commands to reproduce run/test confirmed.

## Update these files
- [x] docs/ai/AI_HANDOFF_CURRENT.md
- [x] docs/ai/AI_DECISIONS_LOG.md (optional, if a decision was made)
- [x] README.md / ARCHITECTURE.md (if behavior changed; N/A in this docs-only PASS1 migration update)

## Handoff minimum content
- [x] What was completed.
- [x] What remains and priority order.
- [x] Exact files touched.
- [x] Any migration or env changes.

## Quality gates
- [x] No TODO left without owner/action.
- [x] No silent failure path introduced.
- [x] Error messages are actionable.

## Ready-to-paste closing note
"Session closed. See docs/ai/AI_HANDOFF_CURRENT.md for status, next tasks, and run/test commands."
