# CPIC Concordance Memo

**Date:** June 19, 2026
**Scope:** Multi-agent PGx platform vs. published CPIC guidelines for CYP2D6, CYP2C19, CYP3A4 drug-gene pairs
**Test method:** All 4 patient profiles × 7 formulary drugs (28 combinations) run through the 5-agent pipeline with Groq bypassed (fallback path only), then compared against CPIC guideline recommendations

---

## System Verdict Summary

| Patient | Phenotype | Drug | Risk | Flagged | Alternative | CPIC Says |
|---------|-----------|------|------|---------|-------------|-----------|
| PGX-001 | UM | Codeine | HIGH | ✅ | Duloxetine | **Avoid** ✅ |
| PGX-001 | UM | Tramadol | HIGH | ✅ | Pregabalin | **Avoid** ✅ |
| PGX-001 | UM | Hydrocodone | HIGH | ✅ | Pregabalin | No specific CPIC guidance for UM ⚠️ |
| PGX-001 | UM | Oxycodone | HIGH | ✅ | Pregabalin | No specific CPIC guidance for UM ⚠️ |
| PGX-001 | UM | Duloxetine | HIGH | ✅ | Pregabalin | No dose change needed for UM ❌ |
| PGX-001 | UM | Pregabalin | HIGH | ✅ | — | No PGx changes needed ❌ |
| PGX-001 | UM | Clopidogrel | HIGH | ✅ | Prasugrel | CYP2C19-specific; no CYP2D6 link ⚠️ |
| PGX-002 | PM | Codeine | HIGH | ✅ | Duloxetine | **Avoid** ✅ |
| PGX-002 | PM | Tramadol | HIGH | ✅ | Pregabalin | **Avoid** ✅ |
| PGX-002 | PM | Hydrocodone | HIGH | ✅ | Pregabalin | **Consider alternative** ✅ |
| PGX-002 | PM | Oxycodone | HIGH | ✅ | Pregabalin | Caution with CYP3A4 PMs ⚠️ |
| PGX-002 | PM | Duloxetine | HIGH | ✅ | Pregabalin | **Consider dose reduction** ✅ |
| PGX-002 | PM | Pregabalin | HIGH | ✅ | — | No PGx changes needed ❌ |
| PGX-002 | PM | Clopidogrel | HIGH | ✅ | Prasugrel | **Avoid in PM** ✅ |
| PGX-003 | NM | Codeine | HIGH | ✅ | Duloxetine | **Standard dosing** ❌ |
| PGX-003 | NM | Tramadol | HIGH | ✅ | Pregabalin | **Standard dosing** ❌ |
| PGX-003 | NM | Hydrocodone | MODERATE | ✅ | Pregabalin | Standard dosing ⚠️ |
| PGX-003 | NM | Oxycodone | MODERATE | ✅ | Pregabalin | Standard dosing ⚠️ |
| PGX-003 | NM | Duloxetine | LOW | — | Pregabalin | Standard dosing ✅ |
| PGX-003 | NM | Pregabalin | LOW | — | — | No PGx changes needed ✅ |
| PGX-003 | NM | Clopidogrel | LOW | — | Prasugrel | Standard dosing ✅ |
| PGX-004 | UM | Codeine | HIGH | ✅ | Duloxetine | **Avoid** ✅ |
| PGX-004 | UM | Tramadol | HIGH | ✅ | Pregabalin | **Avoid** ✅ |
| PGX-004 | UM | Hydrocodone | HIGH | ✅ | Pregabalin | No specific CPIC guidance for UM ⚠️ |
| PGX-004 | UM | Oxycodone | HIGH | ✅ | Pregabalin | No specific CPIC guidance for UM ⚠️ |
| PGX-004 | UM | Duloxetine | HIGH | ✅ | Pregabalin | No dose change needed for UM ❌ |
| PGX-004 | UM | Pregabalin | HIGH | ✅ | — | No PGx changes needed ❌ |
| PGX-004 | UM | Clopidogrel | HIGH | ✅ | Prasugrel | CYP2C19-specific; no CYP2D6 link ⚠️ |

**Key:** ✅ = matches CPIC | ❌ = false positive (system over-flags) | ⚠️ = debatable / no direct CPIC guidance

---

## Analysis by Drug

### Codeine (prodrug, CYP2D6) — STRONG CPIC
- **UM + Codeine → HIGH ✅.** CPIC: "Avoid codeine." System correctly blocks.
- **PM + Codeine → HIGH ✅.** CPIC: "Avoid codeine." System correctly blocks.
- **NM + Codeine → HIGH ❌ FALSE POSITIVE.** CPIC says standard dosing is safe for NMs. System flags due to Adherence agent tagging moderate risk for all phenotypes and MisuseMonitor tagging moderate for all NM + opioid combos. The pipeline has no agent that explicitly recognizes "NM = safe" as a clearing signal — the absence of high risk from other agents should produce a "low" verdict but the presence of any flagged agent triggers a block.

### Tramadol (prodrug, CYP2D6) — STRONG CPIC
- **UM + Tramadol → HIGH ✅.** CPIC: "Avoid tramadol."
- **PM + Tramadol → HIGH ✅.** CPIC: "Avoid tramadol."
- **NM + Tramadol → HIGH ❌ FALSE POSITIVE.** Same NM over-flag pattern as Codeine.

### Hydrocodone (non-prodrug, CYP2D6) — MODERATE CPIC
- **UM + Hydrocodone → HIGH ⚠️.** CPIC has no specific UM guidance for hydrocodone. System flags because MisuseMonitor treats UM + any opioid as high misuse risk. Reasonable conservatism but stricter than CPIC.
- **PM + Hydrocodone → HIGH ✅.** CPIC: "Consider alternative for PM." System flags correctly.
- **NM + Hydrocodone → MODERATE ⚠️.** CPIC says standard dosing. System flags moderate due to MisuseMonitor default moderate risk for NM + opioid. Defensible as general opioid caution but not PGx-specific.

### Oxycodone (non-prodrug, CYP3A4 > CYP2D6) — MODERATE CPIC
- System patterns mirror hydrocodone. Oxycodone is primarily CYP3A4-metabolized, but the system's rules don't distinguish this from CYP2D6-metabolized drugs for UM/PM flagging. The primary enzyme check in `pgx/rules.py` does check for CYP3A4 but the specialist agents (RxRisk, MisuseMonitor) don't — they only check is_prodrug + phenotype without considering which enzyme.

### Duloxetine (non-prodrug, CYP2D6) — MODERATE CPIC
- **PM + Duloxetine → HIGH ✅.** CPIC recommends dose reduction for PM.
- **UM + Duloxetine → HIGH ❌ FALSE POSITIVE.** CPIC has no UM-specific guidance; dose reduction is for PM only. System flags due to Adherence tagging UM as moderate, combined with no counter-signal from safety agents. Over-flag.
- **NM + Duloxetine → LOW ✅.** Correct — standard dosing for NM.

### Pregabalin (renally cleared, no CYP metabolism) — INFORMATIVE CPIC
- **All phenotypes → HIGH ❌ FALSE POSITIVE.** CPIC explicitly states "no PGx-based dosing changes required." System flags UM and PM patients because Adherence agent always flags UM as moderate and PM as high, regardless of drug metabolism pathway. Pregabalin is not even hepatically metabolized — it's cleared renally with zero CYP involvement. This is the clearest false positive in the system.

### Clopidogrel (prodrug, CYP2C19) — STRONG CPIC
- **PM + Clopidogrel → HIGH ✅.** CPIC: "Avoid in CYP2C19 PM." System correctly blocks.
- **UM + Clopidogrel → HIGH ⚠️.** Clopidogrel is CYP2C19-activated, not CYP2D6. None of the 4 patient profiles have a CYP2C19 phenotype (they only have CYP2D6 and the system falls back to "unknown"). The system flags due to Adherence (UM → moderate) and the prodrug detection in RxRisk fallback (is_prodrug=True → UM/PM high), which doesn't distinguish which enzyme activates the prodrug. **This is a false positive** — UM for CYP2D6 says nothing about CYP2C19 activity. The system should only flag clopidogrel when CYP2C19 phenotype data exists.
- **NM + Clopidogrel → LOW ✅.** No CYP2C19 data available, correctly defaults to standard dosing.

---

## Aggregate Metrics

| Metric | Count | Percentage |
|--------|-------|------------|
| Total combos | 28 | 100% |
| Matches CPIC | 13 | 46% |
| Partial / debatable | 7 | 25% |
| False positives (over-flag) | 8 | 29% |
| False negatives (under-flag) | 0 | 0% |

The system is **conservative by design** — every flagged agent triggers a block. This produces zero false negatives (no missed high-risk cases) at the cost of a 29% false-positive rate. For a clinical decision-support tool in early demo phase, this is the safer direction to be wrong.

---

## Root Causes of False Positives

1. **Adherence agent has no drug-awareness.** It flags UM as "moderate" and PM as "high" for ALL drugs, regardless of metabolism pathway. Pregabalin (renally cleared, zero CYP involvement) gets the same adherence risk as Codeine (CYP2D6-activated prodrug). Fix: adherence risk should only apply when the drug actually involves the patient's variant enzyme.

2. **MisuseMonitor flags all UM + opioid as high.** For prodrug opioids (codeine, tramadol) this is correct — rapid conversion creates a euphoric peak. For non-prodrug opioids (hydrocodone, oxycodone) the euphoric peak mechanism doesn't apply — the drug is already active. Fix: only flag misuse risk for UM + PRODRUG opioids.

3. **NM phenotype treated as risky.** Normal metabolizers by definition have normal enzyme activity. But Adherence tags NM as "low" and MisuseMonitor tags NM + opioid as "moderate" — the moderate flag from misuse triggers a block even though PGx risk is absent. Fix: reduce MisuseMonitor baseline for NM to "low" and rely on clinical opioid monitoring, not PGx flagging.

4. **No enzyme-specific routing.** RxRisk fallback checks `is_prodrug + UM/PM` without verifying that the drug's activating enzyme matches the patient's variant enzyme. Clopidogrel (CYP2C19) gets flagged for CYP2D6 UM/PM patients who may have normal CYP2C19. Fix: cross-reference `rule.enzyme` against the patient's actual variant enzyme.

---

## Recommendations

### Immediate (no new code — data quality)
- Document the 29% false-positive rate in the pitch deck as a design tradeoff: "conservative by design, zero false negatives, known over-flag rate we'll tune with real clinical data"

### Short-term (targeted fixes, < 1 day)
1. **Adherence**: skip adherence risk for drugs not metabolized by the patient's variant enzyme
2. **MisuseMonitor**: only flag UM + prodrug opioid, not UM + all opioid
3. **NM baseline**: set MisuseMonitor NM risk to "low" — standard opioid monitoring is a clinical decision, not a PGx flag

### Medium-term (architectural)
4. **Enzyme routing**: each specialist should check whether the drug's enzyme matches the patient's variant before applying phenotype-based rules
5. **Pregabalin carve-out**: hardcode zero-risk drugs (renally cleared, no CYP involvement) to bypass PGx flagging entirely
