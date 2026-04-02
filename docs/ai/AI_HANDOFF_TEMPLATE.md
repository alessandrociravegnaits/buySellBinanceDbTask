# AI Handoff Template

## 1) Project Snapshot
- Project:
- Goal (1-2 lines):
- Current branch:
- Last known good commit/tag:

## 2) Current Status
- What works:
- What is partially working:
- What is broken:
- Blocking issues:

## 3) Recent Changes
- Date:
- Files touched:
- Why these changes were made:
- Side effects to watch:

## 4) Technical Decisions (ADR-lite)
- Decision:
- Alternative considered:
- Why chosen:
- Impact:

## 5) Open Tasks (Top 3)
1. Task:
   - Definition of done:
   - Owner:
2. Task:
   - Definition of done:
   - Owner:
3. Task:
   - Definition of done:
   - Owner:

## 6) Risks and Assumptions
- Risk:
- Mitigation:
- Assumption:

## 7) Run and Verify
```bash
# Setup
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt

# Run
python main.py

# Tests
pytest -q
```

## 8) Environment
- Required env vars:
- Optional env vars:
- Local data dependencies:

## 9) Known Debug Shortcuts
- Useful logs:
- Useful commands:
- Typical failure signatures:

## 10) Next Session First Prompt
Paste this in the next AI session:

"Read README, ARCHITECTURE, and docs/ai/AI_HANDOFF_CURRENT.md first. Then summarize current state in 6 bullets, list top 3 risks, and propose the smallest safe next step."
