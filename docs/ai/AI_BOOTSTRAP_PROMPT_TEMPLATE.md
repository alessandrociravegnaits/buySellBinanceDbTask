# AI Bootstrap Prompt Template

Copy, fill, and paste this at the start of a new AI session.

---

Context:
- Project type:
- Business goal:
- Current milestone:

Constraints:
- Do not break existing behavior.
- Keep changes minimal and testable.
- Preserve data compatibility.
- Follow repository conventions.

Read first (in this order):
1. README.md
2. ARCHITECTURE.md
3. docs/ai/AI_HANDOFF_CURRENT.md
4. Files related to this task

Task:
- Primary objective:
- Non-goals:
- Acceptance criteria:

Output format required:
1. Plan (max 5 steps)
2. Code changes
3. Verification commands run
4. Risks/edge cases
5. Suggested next step

Hard checks before finishing:
- Code compiles/runs.
- Tests pass or failures explained.
- Changelog/handoff updated.

---

Fast variant (30 seconds):
"Read README + ARCHITECTURE + docs/ai/AI_HANDOFF_CURRENT.md. Implement [task]. Keep patch minimal. Run tests. Report changed files and residual risks."

Migration variant (PASS1):
"Read README.md, ARCHITECTURE.md, docs/ai/AI_HANDOFF_CURRENT.md, and docs/ai/AI_MIGRATION_COMMAND.md. Execute `/pass1-migrazione` flow and then propose the smallest safe next step."
