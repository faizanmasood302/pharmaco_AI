# YC Application Brief — Pharmacogenomic Harness

*Use this to draft your YC form answers. Customize with your name, traction, and team.*

---

## One-liner

**AI agent harness that uses n-of-1 pharmacogenomics to block unsafe opioid prescriptions and recommend biologically matched alternatives before the first pill is dispensed.**

---

## What are you building?

An **intelligent prescribing layer** for pain clinics and telehealth: clinicians propose a drug; our multi-agent system pulls the patient's CYP2D6 phenotype (from cheap PGx tests or synthetic FHIR data), runs deterministic CPIC-aligned rules plus optional LLM narrative, and returns a structured decision — **flag, risk level, safe alternative, agent audit trail**.

Unlike population-average dosing, we treat each patient as an **n-of-1 trial**: the treatment decision changes at the point of care (e.g., ultra-rapid metabolizer + codeine → block → duloxetine).

**Live demo:** `PGX-001` + Codeine → critical block + 3D metabolic alert.

---

## Why now? (maps to YC RFS)

1. **Intelligent agents** — Claude/Groq-class models can orchestrate research → analysis → critique on personalized health data; we wrap them in a harness with deterministic clinical rules so demos don't hallucinate.
2. **Cheaper diagnostics** — PGx panels are commoditizing; we ingest phenotype, not raw VCF, for fast clinic workflows.
3. **Dual crisis = huge market** — $1.45T substance abuse + $290B non-adherence share one root cause: one-size-fits-all prescribing.
4. **Regulatory tailwind** — CPIC guidelines + FDA openness to personalized approaches; we start with decision support, not novel molecules.

---

## Who is the customer?

**Phase 1 (now):** Independent pain management clinics and DTC telehealth platforms that can adopt synthetic/FHIR-linked PGx without a 18-month Epic integration.

**Phase 2:** Payers and PBMs — prove reduced adverse events and adherence lift via structured outcomes.

---

## How do you make money?

- **SaaS per clinician seat** ($200–500/mo) for PGx decision support at prescribing
- **Per-evaluation API** for telehealth platforms embedding the harness
- **Payer contracts** when we show reduced opioid initiation in ultra-rapid metabolizers

---

## What do you understand that others don't?

Population-average medicine fails at the **individual metabolic phenotype**. The opioid pipeline (21–29% misuse of chronic opioid Rx; 4–6% transition to heroin) starts when we prescribe prodrugs like codeine to **ultra-rapid CYP2D6 metabolizers** — massive morphine spikes. Poor metabolizers get **no relief → dose escalation → non-adherence**.

The fix isn't another reminder app; it's **changing the prescription before it's written**, with agents + cheap PGx + visual alerts clinicians actually notice.

---

## Competition

- **Epic/Cerner CDS** — slow, hospital-centric, generic alerts
- **One-off PGx labs** — report PDFs, no agent workflow, no prescribing intercept
- **Pill reminder apps** — treat adherence symptoms, not PGx mismatch

We combine **agent orchestration + deterministic PGx rules + prescribing UX** in one harness deployable without enterprise EHR.

---

## Traction (fill in honestly)

- [x] MVP demo (this repo) — FHIR ingest, multi-agent PGx, adherence check-ins
- [ ] Live deployed URL (see DEPLOY.md)
- [ ] X pilot clinics / telehealth LOIs
- [ ] X evaluations run (Supabase-backed audit log)
- [x] CPIC rule coverage for 6 pain drugs + CYP3A4 oxycodone note

---

## 2-minute demo script

1. "48M Americans have a substance use disorder; much of the opioid crisis starts in the clinic with wrong prodrugs."
2. Open app → Maria Chen, Ultra-Rapid metabolizer.
3. Propose Codeine → Evaluate.
4. Show: CRITICAL flag, CPIC note, Duloxetine alternative, Research/Analyst/Critic steps, red pulsing metabolic model.
5. Switch to Sarah Patel (Normal) → same drug → approved.
6. "We're the agent harness between cheap PGx and the prescription pad — n-of-1 care at software speed."

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Regulatory (SaMD) | Start as clinical decision support; synthetic data; physician-in-loop |
| LLM hallucination | Deterministic rules engine; LLM only for narrative |
| EHR integration | FHIR-first; wedge with clinics that don't need Epic |

---

## Ask

We're applying to YC to find design partners (pain clinics / telehealth), ship FHIR ingest, and hire a clinical advisor (PGx / pain medicine).
