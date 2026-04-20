# Copilot Memory (Project)

Questa cartella contiene riassunti di sessione e note operative in formato Markdown, organizzati per argomento.

## 🚀 QUICK START

**Inizia da qui:**  
👉 [session-summary-2026-04-20.md](session-summary-2026-04-20.md) - ultima sessione consolidata

**Ultima sessione (2026-04-20):**  
📄 [session-summary-2026-04-20.md](session-summary-2026-04-20.md) - ✅ Touch per-leg OCO + UI/DB alignment

---

## 📚 Convenzione
- Un file per argomento.
- Contenuto sintetico, operativo, aggiornabile.
- Fonti sempre riportate nel file `00-fonti-md.md`.

## 📁 File Organization (per argomento)

### 🏗️ Architettura & Design
- `00-fonti-md.md`: Inventario markdown del progetto
- `01-architettura-runtime.md`: Panoramica componenti e ciclo runtime
- `02-dati-storage-oco.md`: Modello dati, OCO, persistenza
- `04-ai-handoff-migrazione.md`: Processo AI/handoff e passaggio macchina

### 🚀 Operazioni & Setup
- `03-operazioni-run.md`: Bootstrap, run, test, comandi utili

### 💼 Features Implementate
- `06-ordinepulito-acquistopulito.md`: Clean entry e gating buy/OCO
- `07-documentazione-gain-next.md`: Gain storico e trailing sync
- `08-xrpusdc-trailing-buy.md`: Trailing buy XRPUSDC
- `09-supporti-resistenze-ui.md`: UI SR legacy reference
- `sr-book-rules.md`: User reference per SR book rules ⭐

### 📊 Support & Resistance (Latest 2026-04-17)
- `sr-book-rules.md` ⭐: Regole implementate e modello di scoring
- `10-database-path-fix.md` ⭐: Fix del database persistence
- `session-summary-2026-04-17.md` ⭐: Session recap

### 📝 Session Summaries
- `session-summary-2026-04-20.md`: ✅ Touch per-leg OCO + UI/DB alignment
- `session-summary-2026-04-17.md`: ✅ SR + DB Fix (LATEST)
- `session-summary-2026-04-16.md`: Previous session
- `session-summary-2026-04-14.md`: Previous session
- `session-summary-2026-04-13.md`: Previous session

---

## ✨ Latest Updates (2026-04-20)

### ✅ Implementate
- Per-leg OCO touch support (`tp_touch`, `sl_touch`, leg 1 / leg 2 touch)
- Wizard UI allineata con i nuovi step touch
- Runtime OCO schedulato a 60s quando serve touch intrabar
- Close confirmation breakout validation (8% weight)
- Role reversal detection (6% weight)
- Round number proximity scoring (4% weight)
- Timeframe weighting (0.92× for 1m → 1.10× for 1w)
- Database path fix (orders now persist correctly)

### 📊 Test Results
- 95/95 tests passing
- New tests added for OCO touch wizard and auto-OCO touch semantics
- No regressions

### 📚 Documentation
- Documentazione consolidata per argomento (senza duplicati)
- Ready for production deployment

---

## 🎯 Nota preferenza utente
I riassunti di sessione vengono salvati qui in `.copilot-memory/`, in formato MD e suddivisi per argomento.

**Per ogni sessione, aggiungere:**
1. `session-summary-YYYY-MM-DD.md` con recap
2. File di dettaglio per ogni feature/bug completati
3. Aggiornare questa `README.md` se cambia la struttura

---

**Last Updated:** 2026-04-17  
**Status:** ✅ Production Ready
