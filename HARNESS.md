# THE HARNESS

**A research-grounded architecture for safety-critical medical AI agent systems.**

Covers two domain engines on one platform:
- **Engine A — Pharmacogenomic decision support** (build now)
- **Engine B — n-of-1 mRNA design harness** (designed now, built later)

Supersedes `AGENTS.md` and `ARCHITECTURE-V2.md`. Derived from the GenomicLens audit of `31e5f88` plus the evidence base in Part I.

---

## MANIFEST — every package and tool

Exact versions live in `uv.lock` and `pnpm-lock.yaml`; this table pins the *choice*, not the patch. Anything in the **Engine** or **Data** rows contributes to a clinical value and must therefore appear in `RunManifest` (Part IX.6).

### Runtime and packaging

| Package | Layer | Purpose |
|---|---|---|
| Python 3.12+ | runtime | Backend language |
| `uv` | build | Resolver and locked installs; determinism depends on the committed lock |
| Node 20+ / `pnpm` | build | Frontend toolchain |
| Docker + Compose | ops | Tool isolation, dev parity |

### Contracts, typing and boundaries

| Package | Layer | Purpose |
|---|---|---|
| `pydantic` v2 | domain | Frozen contracts; discriminated unions enforce I2 |
| `mypy` (strict) | CI | Invariants are type-level claims; unchecked types make them decorative |
| `ruff` | CI | Lint and format |
| **`import-linter`** | CI | **Enforces the layer contract in IV.8 — this is how I1 becomes mechanical rather than aspirational** |

### API and web

| Package | Layer | Purpose |
|---|---|---|
| `fastapi` | api | Routes; emits the OpenAPI schema that generates frontend types |
| `uvicorn` + `gunicorn` | api | ASGI server and workers |
| `sse-starlette` | api | Streaming run progress |
| `structlog` | platform | Structured JSON logs with correlation IDs |
| `opentelemetry-sdk` | platform | Traces |

### Data

| Package | Layer | Purpose |
|---|---|---|
| PostgreSQL 16 | data | Single store: relational, vector, full-text |
| `psycopg[pool]` v3 | data | Async driver with pooling — replaces per-query connect |
| `sqlalchemy` 2.0 (Core) | data | Explicit schema and queries; no ORM lazy-loading surprises |
| `alembic` | data | Migrations; fixtures become seeded rows |
| `pgvector` (ext + client) | data | Dense retrieval inside the transactional store |
| Postgres `tsvector` | data | Lexical retrieval; guideline text is keyword-heavy |
| `boto3` / MinIO | data | Content-addressed artifacts, tool stdout, reports |
| `cryptography` (Fernet) | platform | PII column encryption |
| `pyjwt` | platform | Single verified auth path, expiry enforced |

### Retrieval

| Package | Layer | Purpose |
|---|---|---|
| `fastembed` | evidence | ONNX CPU embeddings — offline, no torch, satisfies I4 |
| `fastembed` reranker | evidence | Cross-encoder rerank (optional in v1; RRF alone is acceptable) |

### Deterministic engines

| Tool | Engine | Purpose | Licence |
|---|---|---|---|
| **PharmCAT** (Java, pinned image) | A | Phenotyper + Reporter; CPIC/DPWG/FDA recommendations as JSON | Open source — **verify terms for your use** |
| `fhir.resources` | A | FHIR R4 parsing |  |
| RxNorm lexicon (local snapshot) | A | Drug normalisation; powers gate check 3 |  |
| CPIC guideline snapshots | A | Severity policy provenance | Public-domain-style CC |
| ClinPGx / PharmGKB corpus | A | Evidence retrieval | CC BY-SA — **isolate from `src/`** |
| pVACtools | B | Epitope prediction | **Verify** |
| NetMHCpan / MHCflurry | B | Peptide–MHC binding | NetMHCpan academic — **verify**; MHCflurry more permissive |
| LinearDesign | B | Joint codon + structure optimisation | **Verify** |
| ViennaRNA (RNAfold) | B | Folding, MFE |  |
| BLAST+ | B | Proteome self-similarity screen |  |
| OptiType / arcasHLA | B | HLA typing |  |

### AI layer

| Package | Layer | Purpose |
|---|---|---|
| `openai-agents` | ai | Agent composition via `as_tool()`; typed structured output; the tool loop. `handoff()` prohibited (ADR-0005) |
| Provider access | ai | Anthropic `claude-opus-5` reached through the SDK's LiteLLM extension, behind the internal `LlmClient` protocol — never imported outside `ai/` (ADR-0004) |

> No LLM package may be imported from `engines/`. `import-linter` fails the build if one is.

### Frontend

| Package | Purpose |
|---|---|
| `next` 15 + `react` 19 + `typescript` | Application shell |
| `@tanstack/react-query` | Server state; invalidation on gate transitions |
| `zod` | Runtime validation mirroring Pydantic contracts |
| `openapi-typescript` | Generated types from FastAPI's schema — makes I7 a compile error |
| `tailwindcss` | Styling |

### Testing and CI

| Package | Purpose |
|---|---|
| `pytest`, `pytest-asyncio`, `pytest-cov` | Test suite |
| `hypothesis` | Property tests over phenotype vocabularies and sequence invariants |
| **`testcontainers`** | **Real Postgres in tests — mocking the DB is what let silent write failures pass CI** |
| GitHub Actions | Pipeline in IX.5 |

---

---

## Part 0 — How to use this document

**If you are a coding agent:** Part II is binding. Every invariant has an owning test file. Do not implement anything that violates one; raise the conflict instead.

**If you are a reviewer:** Part I is the argument. Every design decision in Parts II–VII traces to a numbered finding in Part I. If you disagree with a design choice, check whether you disagree with the evidence behind it.

**If you are the author:** Part IX is what you build it with. Part X is the order of work. Part XI is what you still owe.

The central thesis, stated once:

> In safety-critical medicine, an LLM is a **rendering and inquiry layer over a verified deterministic core**, never the source of a clinical judgment. Every guarantee the system makes must be enforced by a mechanism outside the model, because a probabilistic component cannot bound its own error.

---

# PART I — EVIDENCE BASE

Twelve findings that constrain the design. Each is tagged with the design decision it forces.

## A. Regulatory boundary

**F1 — Non-device CDS requires all four statutory criteria.** Under §520(o)(1)(E) of the FD&C Act (21st Century Cures Act §3060), a clinical decision support function escapes medical-device regulation only if it satisfies *every* one of four criteria. Failing any single one places the software in device territory. FDA issued revised final guidance in January 2026, superseding the 2022 version, with expanded transparency expectations and a softened stance on single-recommendation output. [1][2][3]

→ *Forces:* Part III. Regulatory posture is an architectural constraint, not a marketing footnote.

**F2 — Criterion 4 is the one that dictates architecture.** The fourth criterion requires the software to enable a healthcare professional to *independently review the basis* for its recommendation, such that the professional is not intended to rely primarily on the software's output. [1][3]

→ *Forces:* provenance on every clinical value (I5), and the review UI in Part IV.6. **Provenance is not gold-plating — it is the regulatory boundary.** A system that shows a verdict without its basis fails criterion 4 by construction.

## B. What actually goes wrong in deployed CDS

**F3 — Alert override is the norm, not the exception.** A systematic review and meta-analysis of 16 studies found alerts generated on roughly 13% of orders, with about 90% of drug–drug interaction alerts overridden by prescribers (95% CI 85–95%). [4] Independent reviews report override ranges of 46–96%. [5][6]

**F4 — Most alerts are not clinically appropriate.** In an emergency-department study of 382 medication alert cases, only 7.3% were judged clinically appropriate. [7] A hospital DDI evaluation found 88.2% of very-severe alerts overridden, with false positives traced to overly broad screening intervals and missing patient context. [8]

→ *Forces:* **I6 — over-flagging is a tracked failure, not a safe default.** The audited system's measured 29% false-positive rate is not a minor blemish; it is the dominant deployed failure mode of this entire product category. A one-directional `max()` severity clamp makes it worse.

**F5 — Alert burden must be designed down, not up.** Expert consensus work identifies interaction classes that should be made non-interruptive specifically to preserve attention for the ones that matter. [9]

→ *Forces:* Part V.7, tiered alerting. Severity determines *interruptiveness*, not just a label.

## C. Human oversight is weaker than assumed

**F6 — A wrong flag makes clinicians worse, not neutral.** Work on prescribing CDS documented that when a system incorrectly flagged a medication as inappropriate, physician prescribing errors rose by 56.9%. The human in the loop did not absorb the error — the erroneous assistance induced mistakes the clinician would not otherwise have made. [10]

**F7 — Human-in-the-loop is widely characterised as symbolic rather than substantive.** A 2026 Lancet analysis argues HITL oversight functions more as reassurance than protection, because reviewers operate under constraints that preclude meaningful interrogation of algorithmic output. [11] Automation bias produces both omission errors (missing what the system missed) and commission errors (following the system against contrary evidence). [12][13]

**F8 — Very high acceptance is itself an alarm.** Override rates falling below roughly 5% are read as a signal of automation bias rather than of system quality. [14] Deployment guidance recommends monitoring acceptance patterns for evidence that review has become perfunctory. [15]

→ *Forces:* **the single most important design consequence in this document.** The human approval gate **cannot be counted as mitigation** for engine error. Part IV.6 redesigns it from *approve/reject* to *review-the-basis*, and Part VII makes override rate a monitored metric with an alarm at **both** ends.

## D. LLM failure modes in clinical context

**F9 — Models amplify errors present in their input.** Testing six leading models against 300 physician-designed clinical vignettes each containing one fabricated element, models repeated or elaborated the planted error in up to 83% of cases. A mitigation prompt roughly halved the rate without eliminating it. [16]

→ *Forces:* input validation is a safety layer (Part IV.2). The LLM must never be the component that reconciles conflicting or suspect inputs. Garbage in produces confident, fluent, elaborated garbage out.

**F10 — Sycophancy and fabrication are measurable and large.** Reported medical sycophancy around 58%; fabricated references in a substantial fraction of AI-generated citations; a physician-validated hallucination benchmark found the best-performing model still at 29.1%, with some open models above 57%, failing particularly on fabricated data and non-existent guidelines. [16][17][18]

→ *Forces:* **citations must be verified against a local pinned corpus, never accepted as generated.** A fabricated guideline reference in a PGx report is indistinguishable from a real one to a rushed reader.

**F11 — Grounding works, and prompting alone does not.** Prompt-based mitigation reduced clinical-summary hallucination from roughly 64% to 43% — real, insufficient. By contrast, a grounded clinical documentation pipeline evaluated across 18 configurations and ~13,000 clinician-annotated sentences measured a 1.47% hallucination rate alongside a 3.45% omission rate. [17][19]

→ *Forces:* the grounding gate (Part IV.5) is justified quantitatively, not aesthetically. It also forces **omission** into the metric set — a grounded system's characteristic failure shifts from inventing to leaving out.

**F12 — Probabilistic supervision of probabilistic systems provides no floor.** The guardrail literature converges on a single principle: a model should not be responsible for enforcing its own constraints; that responsibility belongs to the surrounding system. LLM-as-judge inherits the failure modes of what it judges and cannot establish a deterministic lower bound on safety. Layered defence ("Swiss cheese") and runtime enforcement against explicit specifications are the recommended alternatives. [20][21][22]

→ *Forces:* deletion of the v1 LLM adjudicator, and the rule that every gate in this system is deterministic code, not a supervising model.

## E. Domain-specific implementation knowledge

**F13 — CPIC publishes machine-readable recommendations, and phenotype is the standard integration level.** CPIC maintains a structured, API-accessible database of recommendations with an informatics working group producing EHR-agnostic CDS resources, including trigger conditions and pre-test versus post-test alert context. Phenotype — not raw genotype — is the level most PGx guidelines and alerts operate on. [23][24][25]

**F14 — Interpretation is not standardised across the industry.** Commercial pharmacogenetic laboratories produce phenotype assignments and recommendations that diverge from CPIC. [26] Spurious gene–drug associations exist that should *not* generate alerts. [27]

→ *Forces:* CPIC as the single declared source of truth, versioned; concordance measured *against CPIC specifically*; and the severity policy table (Part V.4) as reviewable data rather than derived text.

---

# PART II — INVARIANTS

Binding. Each is enforced by types or tests, not convention. Each names its owning test file.

| # | Invariant | Enforcement | From |
|---|---|---|---|
| **I1** | No LLM output becomes a risk level, a drug choice, or a gate decision | `tests/invariants/test_llm_authority.py` — asserts no LLM client is importable from `engines/` | F12 |
| **I2** | Unknown is a first-class value that halts | `PhenotypeCall` union has no default branch; `Outcome` is not orderable against `Severity` | Audit CLIN-04/05 |
| **I3** | Every recommended drug has been assessed for *this* patient | `AlternativeSet` is constructible only from `Assessment` objects | Audit CLIN-03 |
| **I4** | The system is fully functional with the LLM disabled | Full eval suite green with `LLM_ENABLED=false` in CI | F12 |
| **I5** | Every clinical claim carries provenance to a guideline table | Report renderer refuses unprovenanced fields | F2 |
| **I6** | Over-flagging is a tracked failure, not a safe default | Concordance harness gates on false-positive rate and alert burden | F3, F4 |
| **I7** | Server state is never read from the client | Endpoints accept IDs, never state objects | Audit CLIN-01 |
| **I8** | Citations are verified against the pinned corpus before display | `gate.py` resolves every citation ID or rejects the narrative | F10 |
| **I9** | Input contradictions halt; they are never reconciled by a model | `ProfileValidator` raises on conflicting genotype sources | F9 |
| **I10** | The review gate is not counted as a safety control | Risk documentation must not cite human review as mitigation for engine error | F6, F7 |

---

# PART III — REGULATORY POSTURE

## III.1 Declared position

**Research and education only. Not a medical device. Does not provide medical advice.**

Rendered in: README, API root, every UI surface, every generated document footer. Generated clinical notes additionally carry a `SIMULATED` watermark and a synthetic patient identifier.

This posture is consistent with the dependency stack — PharmCAT itself ships marked for research use.

## III.2 Mapping the four criteria to architecture

Even while positioned as research software, build to satisfy all four criteria. It costs little now and is expensive to retrofit. [1][2][3]

| Criterion | Requirement | Architectural response |
|---|---|---|
| 1 — no image/IVD/signal analysis | Must not acquire, process or analyse medical images, IVD signals, or signal-acquisition patterns | Inputs are VCF, structured diplotypes and FHIR text. **Never ingest raw instrument signal or images.** Note: genomic data from an IVD assay is a live boundary question — see Part X |
| 2 — displays medical information | Must display/analyse/print patient or medical information | Guideline recommendations and patient genotype: squarely in scope |
| 3 — supports rather than directs | Provides recommendations to an HCP | Output is `Assessment` + ranked considered options, never an order. No auto-prescribe path exists in any code path |
| 4 — enables independent review | HCP can review the *basis*, not rely primarily on output | **This is the architecture.** Provenance chain (I5), `considered` set always returned, citation resolution (I8), the review UI in IV.6 |

## III.3 The line the product must not cross

| Permitted | Prohibited |
|---|---|
| "This genotype implies reduced codeine activation per CPIC Table 2" | "Prescribe duloxetine" |
| Ranked options with each one's own assessment and basis | A single directive with the reasoning hidden |
| "No PGx-safe option in this formulary" | Silence, or a fallback suggestion that was never assessed |

---

# PART IV — SYSTEM ARCHITECTURE

Roughly two-thirds of the system is domain-neutral. Build it once.

```
┌──────────────────────────────────────────────────────────────┐
│ IV.6  Review interface — basis-first, override-monitored     │
├──────────────────────────────────────────────────────────────┤
│ IV.5  Grounding gate — every LLM string validated            │
├──────────────────────────────────────────────────────────────┤
│ IV.4  Agent layer — inquiry only, structured output          │
├──────────────────────────────────────────────────────────────┤
│  ENGINE A (PGx)          │          ENGINE B (mRNA)          │
│  deterministic judgment  │  deterministic judgment           │
├──────────────────────────────────────────────────────────────┤
│ IV.3  Tool adapters — pinned, offline, content-hashed        │
├──────────────────────────────────────────────────────────────┤
│ IV.2  Input validation — fail closed on contradiction        │
├──────────────────────────────────────────────────────────────┤
│ IV.1  Provenance · persistence · authz · audit               │
└──────────────────────────────────────────────────────────────┘
```

## IV.1 Provenance primitives

Every scientific value in either engine originates from a `ToolResult`. This is what makes criterion 4 satisfiable.

```python
class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tool_name: str
    tool_version: str          # pinned in tools/registry.yaml
    container_digest: str      # sha256 of the OCI image actually executed
    input_sha256: str
    output_sha256: str
    started_at: datetime
    duration_ms: int
    exit_code: int
    parameters: dict[str, JsonValue]

class Provenanced[T](BaseModel):
    value: T
    source: ToolResult

class Citation(BaseModel):
    corpus_id: str
    corpus_snapshot_id: str    # immutable snapshot, never a live API
    document_id: str
    section: str | None
    span: tuple[int, int] | None   # char offsets — NOT the quoted text
```

Store **offsets, not text**, for third-party corpora. Rendering resolves the span from the licensed local snapshot at display time. This keeps CC BY-SA content (ClinPGx/PharmGKB) out of your source tree and prevents ShareAlike contamination of your own code.

Persistence: Postgres with an append-only provenance edge table (`artifact → produced_by → consumed`). This yields a queryable DAG — "show me everything that contributed to this verdict" — which *is* criterion 4 in database form.

## IV.2 Input validation (F9)

Because models elaborate planted errors in up to 83% of cases, the LLM must never see unvalidated or self-contradictory input.

- Every input passes schema validation before reaching any agent.
- **Contradiction halts (I9).** Two sources disagreeing on a genotype is `HALTED`, surfaced to the human, never silently resolved and never handed to a model to adjudicate.
- Provenance is recorded per input field: which file, which assay, which timestamp.
- PHI heuristics fail closed — synthetic and public data only.

## IV.3 Tool adapter layer

```python
class ToolAdapter(ABC):
    name: ClassVar[str]
    version: ClassVar[str]
    image: ClassVar[str]      # OCI ref, digest-pinned

    @abstractmethod
    def build_command(self, inp: ToolInput) -> list[str]: ...
    @abstractmethod
    def parse_output(self, raw: bytes) -> ToolOutput: ...
    def run(self, inp: ToolInput) -> ToolResult: ...
```

- One container per tool, digest-pinned. Bioinformatics dependency trees are mutually hostile; do not co-install.
- **No network inside tool containers.** Reference data mounted read-only from a versioned volume.
- Cache keyed on `(image_digest, input_sha256, parameters)` — makes reruns cheap and reproducibility verifiable.
- Adapters are pure translation. Zero clinical logic.
- Engine A wraps PharmCAT here. Engine B wraps pVACtools, LinearDesign, RNAfold, BLAST. Same abstraction.

## IV.4 Agent layer — inquiry, never judgment

> **Agents do inquiry. Engines do judgment.**

| Agent | Job | Cannot |
|---|---|---|
| **Intake** | Free-text med list / referral note → structured codes | Emit a code not resolved in RxNorm |
| **Evidence** | Retrieve and synthesise guideline passages | Produce a severity, verdict or drug choice |
| **Explain** | Render an `Assessment` for clinician or patient | Name a drug absent from the assessment; state a risk absent from a finding |
| **Q&A** | Answer follow-ups grounded in engine output + corpus | Answer beyond the retrieved and assessed set — must say "not covered" |
| **Coverage** | Report what is *missing*: untyped genes, no-guidance pairs, provisional policy rows | Downgrade a gap into a reassurance |

**Coverage is the highest-value agent and had no v1 equivalent.** A system that states clearly what it does not know is more clinically useful — and more criterion-4 compliant — than one that fills gaps with confident defaults.

**Deleted from v1:** Adjudicator (F12 — the core anti-pattern), RxRisk (engine does it deterministically), CostNavigator (unrelated to safety, likely fabricating), **MisuseMonitor** (unvalidated LLM scoring of patient opioid-misuse risk: no guideline backing, serious disparate-impact exposure, and a category of judgment that should not be model-made at all — deleting it is a safety and ethics improvement, not a scope cut).

All agent calls use Pydantic response schemas. Free text is confined to fields explicitly typed as narrative.

## IV.5 The grounding gate (F11)

The mechanism that turns "harness the LLM" from intention into enforcement. Every LLM-authored string passes here before reaching a human.

```python
class Narrative(BaseModel):
    text: str
    cites_finding_ids: list[str]     # model declares what it referenced
    cites_citation_ids: list[str]    # model declares its sources
    mentions_entities: list[str]     # model declares what it named

def gate(n: Narrative, a: Assessment) -> Grounded | Rejected:
    # 1. Declared finding IDs exist in this assessment
    # 2. Declared entities ⊆ {assessed drug} ∪ {validated alternatives}
    # 3. UNDECLARED entity scan: dictionary match of n.text against the full
    #    RxNorm lexicon. Any hit outside the allowed set → reject.
    #    (This is what catches "Tramadol".)
    # 4. Every citation ID resolves in the pinned corpus snapshot (I8, F10)
    # 5. No risk-bearing assertion contradicts a.severity / a.outcome
    # 6. If a.outcome ∈ {HALTED, NO_GUIDANCE}, text contains no reassurance
    # 7. Omission check: every blocker-severity finding appears in the text (F11)
```

**Failure policy:** reject → regenerate once with the violation fed back → reject again → **fall back to the deterministic template.** The template always exists (I4). The system degrades to plain correct prose rather than to fluent wrongness.

Check 7 exists because grounding shifts the characteristic failure from fabrication to omission — measured at 3.45% against 1.47% in the grounded pipeline literature. [19] A gate that only catches invention will miss the more common grounded failure.

Every rejection is logged with the offending text. That log is a **measured hallucination rate for your own system** — a research artifact almost nobody publishes.

*Applied to the audited v1 failure:* `recommended_alternative: "Tramadol"` fails check 2 and check 3. The fabricated pharmacological justification fails check 4. "Normal metabolizers process the drug as expected" for an ultra-rapid metabolizer fails check 5. All three caught mechanically.

## IV.6 The review interface (F6, F7, F8, I10)

**This section exists because the evidence says the naive version of your human gate does not work.**

An incorrect flag increased prescribing errors by 56.9% [10]; HITL is characterised in the 2026 Lancet literature as symbolic rather than substantive [11]. Therefore:

**The review gate is a workflow and accountability mechanism. It is not a safety control, and the risk documentation must not claim it as one (I10).**

Design consequences:

1. **Basis-first, verdict-second.** The reviewer sees the genotype, the guideline text, and the citation *before* the severity label. This directly serves criterion 4 and counters anchoring.
2. **The `considered` set is always shown.** What was ruled out, and why. A reviewer who sees only the winner cannot review the basis.
3. **Provisional and low-confidence findings are visually distinct.** Never rendered with the same authority as reviewed ones.
4. **Optional cognitive forcing:** for blocker-severity findings, the reviewer records their own assessment before the system's verdict is revealed. [15]
5. **Override rate is monitored with alarms at both ends.** Above ~90% means alert fatigue (F3). Below ~5% means automation bias (F8). Neither is health.
6. **Interruptiveness is tiered by severity (F5).** Only blockers interrupt. Warnings are passive and in-context. Informational findings are on-demand.

### Gate state machine

```
DRAFT → PENDING_REVIEW → APPROVED → (assessment changes) → SUPERSEDED
              │                                                │
              └────────────→ REJECTED ←───────────────────────┘
```

```python
class GateTransition(BaseModel):
    evaluation_id: str
    from_state: GateState
    to_state: GateState
    actor_id: str
    actor_role: Role
    rationale: str
    assessment_sha256: str      # hash of EXACTLY what was reviewed
    at: datetime
```

- **Append-only.** Current state is the fold over history. Closes the audited unlimited-re-approval defect.
- **Approval binds to a content hash.** If the assessment changes — new genotype, policy update, tool version bump — the hash no longer matches and the approval auto-transitions to `SUPERSEDED`. A clinician cannot have approved something they never saw.
- **Endpoints take IDs, never state objects (I7).** `POST /clinical-note` loads the record server-side, folds transitions, verifies `APPROVED`, verifies the hash still matches. The forged-body case is a regression test.

## IV.7 Authorization

Authentication without authorization is the gap that matters for a system modelling PHI access. Every patient-scoped route resolves `require_access(actor, patient_id, action)` against an explicit `care_team_assignment` table. No implicit access. Roles: `CLINICIAN`, `PHARMACIST` (only role that may approve), `RESEARCHER` (de-identified aggregate only), `ADMIN`.

Also: verify JWT expiry; never print secret prefixes to stdout; pin the database CA rather than disabling verification; keep patient identifiers out of application logs; make decryption failure raise rather than return ciphertext.

## IV.8 Module topology and the import contract

```
src/
  domain/                   # pure types · ZERO internal imports
    provenance.py           #   ToolResult, Provenanced, Citation
    genes.py                #   Gene, VocabularyClass, ALLOWED_TERMS
    phenotype.py            #   KnownPhenotype | UnknownPhenotype
    drugs.py                #   DrugCode, Indication, Formulary
    assessment.py           #   Outcome, Severity, Finding, Assessment
    gate.py                 #   GateState, GateTransition
    errors.py               #   HaltReason, EngineError

  engines/                  # deterministic judgment · NO ai/ IMPORT
    pgx/
      pharmcat/             #   adapter · outside_calls · parse
      severity.py           #   policy table loader + lookup
      alternatives.py       #   safe_alternatives()
      assess.py             #   assess() — the total function
    mrna/                   # Engine B, later, same shape

  evidence/                 # retrieval only · no judgment
    corpus.py               #   snapshot ingestion + pinning
    retrieval.py            #   BM25 + dense + RRF

  ai/                       # ALL LLM-touching code lives here
    client.py               #   LlmClient protocol
    agents/                 #   intake · evidence · explain · qa · coverage
    gate.py                 #   the grounding gate (plain Python, never a model)
    templates/              #   deterministic narrative fallbacks (I4)
    orchestration/          #   run assembly, agent wiring, turn and token budgets

  platform/
    db/                     #   pool · repositories · migrations
    auth/                   #   authn · authz · gate state machine
    audit/
    telemetry/

  api/
    routes/
    deps.py

policy/severity/            # one reviewed YAML per gene
tools/registry.yaml         # pinned versions, digests, licences
eval/                       # golden set, concordance, scorecards
tests/invariants/           # I1–I10, one file each
```

### The import contract

Enforced by `import-linter` in CI. **This is how I1 stops being a promise and becomes a build failure.**

| Layer | May import | May **not** import |
|---|---|---|
| `domain` | nothing internal | everything |
| `engines` | `domain` | `ai`, `evidence`, `platform`, `api` |
| `evidence` | `domain` | `ai`, `engines`, `api` |
| `ai/agents`, `ai/gate` | `domain` | `engines`, `evidence`, `platform`, `api` |
| `ai/orchestration` | `domain`, `engines`, `evidence`, `ai/agents`, `ai/gate` | `platform.db`, `api` |
| `platform` | `domain` | `engines`, `ai` |
| `api` | all | — |

Two consequences worth naming:

**`engines` cannot reach `ai`.** A future contributor cannot "just ask the model" inside the assessment path without the build rejecting it.

**Agents cannot reach the engines.** `ai/agents/` receives already-computed `Assessment` objects and returns narrative. It has no way to invoke, influence, or re-run a judgment. This also makes every agent trivially unit-testable with a fixture.

## IV.9 Database schema

Immutable where it matters, append-only where it must be.

```sql
-- Provenance spine ------------------------------------------------
tool_results(
  id, tool_name, tool_version, container_digest,
  input_sha256, output_sha256, parameters jsonb,
  started_at, duration_ms, exit_code, stdout_uri)

provenance_edges(              -- the queryable DAG (criterion 4)
  artifact_id, produced_by_tool_result_id, consumed_artifact_id)

-- Patient and genomics --------------------------------------------
patients(id, source, demographics_enc, created_at)
genomic_profiles(id, patient_id, reference_build, panel jsonb)

phenotype_calls(              -- one row per gene, ALWAYS present
  id, profile_id, gene,
  kind,                       -- 'known' | 'unknown'  (the discriminator)
  diplotype, vocabulary, term, activity_score,
  unknown_reason,             -- NULL iff kind='known'
  tool_result_id,
  CHECK ((kind='known') = (term IS NOT NULL)))

-- Assessment (immutable) ------------------------------------------
assessments(
  id, assessment_sha256 UNIQUE,   -- binds approvals in IV.6
  profile_id, drug_code, indication,
  outcome, severity,              -- severity NULL when outcome not ACTIONABLE
  policy_version, corpus_snapshot_id, engine_version,
  created_at)

findings(id, assessment_id, gene, severity, action,
         policy_row_id, provisional bool, tool_result_id)

alternatives_considered(        -- ALWAYS written, including rejects
  id, assessment_id, drug_code, outcome, severity,
  rank int NULL, rejected_reason)

-- Review gate (append-only) ---------------------------------------
evaluations(id, assessment_id, created_by, created_at)

gate_transitions(               -- INSERT ONLY. No UPDATE, no DELETE.
  id, evaluation_id, from_state, to_state,
  actor_id, actor_role, rationale,
  assessment_sha256,            -- exactly what was reviewed
  at)

care_team_assignments(clinician_id, patient_id, role, granted_at, revoked_at)

-- Evidence --------------------------------------------------------
corpus_snapshots(id, corpus_id, version, ingested_at, licence)
corpus_documents(id, snapshot_id, external_id, title, text)
corpus_chunks(id, document_id, span_start, span_end,
              embedding vector(384), lexeme tsvector)

-- Policy ----------------------------------------------------------
severity_policy_rows(
  id, policy_version, gene, phenotype_term, drug_code,
  cpic_strength, severity, action, interruptive bool,
  provenance jsonb, reviewed_by, reviewed_on,
  provisional bool GENERATED ALWAYS AS (reviewed_by IS NULL) STORED)

-- AI accountability -----------------------------------------------
narratives(id, assessment_id, text, model_id,
           prompt_sha256, response_sha256,
           gate_verdict,               -- 'accepted'|'regenerated'|'template_fallback'
           rejection_reasons jsonb, attempt int)

run_manifests(id, spec_version, inputs jsonb, pins jsonb,
              node_transitions jsonb, seed, created_at)

audit_logs(id, actor_id, action, resource_type, resource_id, at, detail jsonb)
```

Three schema decisions carrying architectural weight:

- **`phenotype_calls` has a `CHECK` constraint tying `kind` to `term`.** The database refuses to store a "known" phenotype without a term. The fail-open default cannot be reintroduced even by a direct SQL write.
- **`alternatives_considered` stores rejects.** Criterion 4 requires showing what was ruled out; a schema that only stores winners cannot satisfy it.
- **`severity_policy_rows.provisional` is a generated column.** Provisional status is derived from the absence of a reviewer, so it cannot drift out of sync with reality.

## IV.10 API surface

Every endpoint takes identifiers. No endpoint accepts a state object (I7).

| Method | Path | Notes |
|---|---|---|
| `POST` | `/v1/profiles` | Ingest VCF / outside calls / FHIR. Halts on contradiction (I9) |
| `GET` | `/v1/profiles/{id}` | Includes **every** gene, unknowns explicit |
| `GET` | `/v1/profiles/{id}/coverage` | What is not known, and why |
| `POST` | `/v1/assessments` | `{profile_id, drug_code, indication}` — indication required |
| `GET` | `/v1/assessments/{id}` | Verdict, findings, alternatives |
| `GET` | `/v1/assessments/{id}/basis` | **Criterion 4 endpoint**: guideline text, citations, considered set, provenance chain |
| `POST` | `/v1/evaluations` | `{assessment_id}` — creates a reviewable record |
| `GET` | `/v1/evaluations/{id}` | Current state = fold over transitions |
| `POST` | `/v1/evaluations/{id}/transitions` | `{to_state, rationale, assessment_sha256}`. Rejects on hash mismatch or illegal transition |
| `GET` | `/v1/evaluations/{id}/history` | Full transition log |
| `POST` | `/v1/reports` | `{evaluation_id}` **only**. Loads server-side, folds state, re-verifies hash |
| `POST` | `/v1/qa` | `{assessment_id, question}` — grounded, refuses outside scope |
| `GET` | `/v1/runs/{run_id}/manifest` | Replay record |

`POST /v1/reports` is the endpoint that was exploitable in v1. Its contract now makes the attack unrepresentable: there is no field in which to supply a forged approval.

The transition endpoint requiring `assessment_sha256` gives content binding and optimistic concurrency in one move — a reviewer approving a stale assessment is rejected rather than silently accepted.

## IV.11 Request lifecycle

One assessment, end to end. Layer in brackets; recorded artifacts in italics.

```
 1. POST /v1/assessments                                    [api]
      require_access(actor, patient, READ) ─── denied ──► 403
 2. Load profile; validate                                  [platform → domain]
      contradiction? ──► HALTED, no further processing   (I9)
 3. Enter the run with pinned context                       [ai/orchestration]
      pins: engine, policy, corpus snapshot, model
      ↓
 4. assess(profile, drug)                                   [engines/pgx]
      a. PharmCAT phenotyper/reporter via adapter   → ToolResult
      b. severity policy lookup                     → Finding[]
      c. unmapped triple → NO_GUIDANCE (never 'low')
      d. any relevant gene unknown → HALTED
      ↓
 5. safe_alternatives(profile, drug, indication)            [engines/pgx]
      every candidate re-assessed for THIS patient  (I3)
      none safe → NoSafeAlternative(considered=…)
      ↓
 6. Persist Assessment; compute assessment_sha256           [platform/db]
      write findings + alternatives_considered (incl. rejects)
      write provenance_edges
      ↓
 7. Retrieve evidence for cited policy rows                 [evidence]
      pinned snapshot only; never a live API
      ↓
 8. Explain agent → Narrative                               [ai/agents]
      structured output; declares findings, citations, entities
      ↓
 9. gate(narrative, assessment)                             [ai/gate]
      pass ──────────────► accepted
      fail ──► regenerate once ──► fail ──► deterministic template
      record verdict + reasons in `narratives`
      ↓
10. Response: verdict · findings · ranked + considered
    alternatives · narrative · basis link · provenance IDs   [api]
      ↓
11. Optional: POST /v1/evaluations → review gate            [IV.6]
```

Steps 4–6 are the only steps that produce clinical values, and none of them can reach `ai/`. Steps 8–9 cannot reach `engines/`. The graph is the sole place they meet, and it passes data one way.

If the LLM is disabled, steps 8–9 collapse to the template and everything else is unchanged — which is what makes I4 testable rather than aspirational.

## IV.12 Halt and error propagation

Failures are typed and never degrade into reassurance.

| Condition | Outcome | Presentation |
|---|---|---|
| Gene not genotyped / assay gap | `HALTED` | Interruptive, framed as **missing data**, never as risk |
| Contradictory input sources | `HALTED` | Blocks processing; names both sources |
| Ambiguous diplotype | `HALTED` | Names the ambiguity |
| No CPIC/DPWG/FDA statement for pair | `NO_GUIDANCE` | On-demand only; explicitly "no guideline exists" |
| Policy row provisional | verdict + `provisional` flag | Visually distinct from reviewed findings |
| Tool container failure | `EngineError` | 5xx. **Never a fallback verdict** |
| Corpus snapshot unavailable | `EngineError` | Assessment proceeds; narrative degrades to template |
| Gate rejects twice | template fallback | Logged as a measured hallucination event |
| DB write failure | `Result[T, WriteError]` propagated | 5xx. Never a success-shaped response |
| LLM provider unavailable | template fallback | Full functionality retained (I4) |

The rule underneath the table: **`NO_GUIDANCE` and `HALTED` are not severities and are not orderable against them.** `Severity` is an `IntEnum`; `Outcome` is not. No arithmetic can turn a halt into a "low", which was the mechanism of the audited failure.



## V.1 What it does

A drug is proposed for a patient. The engine determines whether that patient's genotype implies a guideline-supported change, and surfaces alternatives that have been assessed against the *same* genotype.

Scope boundary: it interprets and cites. It does not prescribe (Part III.3).

## V.2 Domain model — the root fix

The audited system stored phenotype as a `str`, regex-extracted from a serialized blob, defaulting to `"normal metabolizer"` on failure. That single modelling error produced three of the five criticals.

PGx uses **four different phenotype vocabularies** (F13). v1 modelled one.

```python
class VocabularyClass(StrEnum):
    METABOLIZER     = "metabolizer"      # CYP2D6/2C19/2C9/3A4: PM,IM,NM,RM,UM
    FUNCTION        = "function"         # SLCO1B1, ABCG2: Poor/Decreased/Normal/Increased
    ACTIVITY_SCORE  = "activity_score"   # DPYD
    ALLELE_PRESENCE = "allele_presence"  # HLA-B: *57:01, *58:01 …

class KnownPhenotype(BaseModel):
    gene: Gene
    diplotype: str
    vocabulary: VocabularyClass
    term: str                     # validated ∈ ALLOWED_TERMS[gene]
    activity_score: Decimal | None
    source: ToolResult

class UnknownPhenotype(BaseModel):
    gene: Gene
    reason: Literal["not_genotyped", "ambiguous_diplotype",
                    "no_cpic_definition", "assay_does_not_cover"]
    raw_observation: str | None

PhenotypeCall: TypeAlias = KnownPhenotype | UnknownPhenotype
```

`ALLOWED_TERMS` loads from CPIC gene definition tables at build time. Never hand-typed.

```python
class GenomicProfile(BaseModel):
    calls: Mapping[Gene, PhenotypeCall]   # EVERY in-scope gene has an entry
    panel: PanelDefinition                # what the assay actually covered
```

A gene the assay did not cover is present as `UnknownPhenotype(reason="assay_does_not_cover")`. **Never absent** — absence is what let the audited system silently proceed.

## V.3 Deterministic core — wrap PharmCAT

Stop maintaining a hand-copied slice of CPIC. Use the reference implementation from the consortium that publishes the guidelines.

| Hand-rolled v1 | PharmCAT |
|---|---|
| Regex phenotype extraction from a text blob | Phenotyper module, per-gene, correct vocabulary |
| `guidelines.json` — partial hand transcription | CPIC + DPWG + FDA label recommendations, machine-readable JSON |
| 6 genes / 20 drugs, 5 with no entries | Wide coverage, updated with the guidelines |
| Transporter genes unrepresentable | Function assignments; rs4149056 fallback per the CPIC statin guideline |

Integration facts that matter:

- **Outside-call files** accept diplotypes determined elsewhere — exactly your fixture and FHIR path.
- **Modules run independently** (Named Allele Matcher / Phenotyper / Reporter), so you can enter at the phenotyper.
- **Reporter emits JSON for machine parsing** — no HTML scraping.

```
engines/pgx/pharmcat/
  adapter.py        # containerized JAR, JSON in/out
  outside_calls.py  # GenomicProfile → outside-call TSV
  parse.py          # PharmCAT JSON → domain types
```

Adapter is pure translation. Version pinned. A version bump requires re-running the concordance harness in the same PR (Part VII).

## V.4 Severity policy — curated data, never derived from prose

Two of the audited criticals came from reading clinical meaning out of free text (`"avoid" in evidence.lower()`, and substring phenotype matching). Deriving severity from CPIC's recommendation prose would be the same error a third time.

```yaml
# policy/severity/SLCO1B1.yaml
policy_version: "1.0"
gene: SLCO1B1
rows:
  - phenotype: "Poor Function"
    drug: simvastatin
    cpic_strength: Strong
    severity: critical
    action: block
    interruptive: true          # F5 — only blockers interrupt
    provenance:
      guideline: "CPIC statin guideline"
      table: "Table 2"
      guideline_version: "2022"
      doi: "10.1002/cpt.2557"
    reviewed_by: "TODO(clinical-review)"
    reviewed_on: null
```

- Import **fails closed** on any row missing provenance or a reviewer field.
- A `(gene, phenotype, drug)` triple absent from the table yields `NO_GUIDANCE` — **never `low`**.
- Rows marked `TODO(clinical-review)` load as `provisional` and every assessment touching one is flagged provisional in output. You ship with provisional rows; you never hide them.
- The table is *scaffolded* once from PharmCAT's structured output, then human-reviewed. Scaffolding is not a runtime path.
- The mapping from "Strong recommendation to avoid" to "block this prescription" is a **product policy decision**, not a fact (F14). Policy decisions belong in reviewable data with a named reviewer.

## V.5 Assessment

```python
class Outcome(StrEnum):
    ACTIONABLE  = "actionable"    # guideline exists, implies a change
    NO_CHANGE   = "no_change"     # guideline exists, standard dosing
    NO_GUIDANCE = "no_guidance"   # no CPIC/DPWG/FDA statement for this pair
    HALTED      = "halted"        # ≥1 relevant gene is UnknownPhenotype

def assess(profile: GenomicProfile, drug: DrugCode) -> Assessment: ...
```

**`NO_GUIDANCE` and `HALTED` are not severities and are not comparable to them.** `Severity` is an `IntEnum`; `Outcome` is not. You cannot accidentally `max()` a halt into a "low" — which was the audited failure's mechanism.

## V.6 Alternatives (I3)

```python
def safe_alternatives(
    profile: GenomicProfile, original: DrugCode, indication: Indication,
) -> AlternativeSet | NoSafeAlternative:
    candidates = formulary.for_indication(indication, exclude={original})
    scored = [(c, assess(profile, c)) for c in candidates]   # SAME engine, SAME patient
    safe = [(c, a) for c, a in scored
            if a.outcome is Outcome.NO_CHANGE
            or (a.outcome is Outcome.ACTIONABLE and a.severity <= Severity.LOW)]
    if not safe:
        return NoSafeAlternative(reason="no_pgx_safe_option_in_formulary",
                                 considered=scored)
    return AlternativeSet(ranked=sorted(safe, key=...), considered=scored)
```

- `AlternativeSet` **cannot be constructed** without `Assessment` objects. The audited defect becomes unrepresentable rather than merely tested-for.
- `NoSafeAlternative` is a legitimate first-class result.
- `considered` is **always** returned — this is criterion 4 in the alternatives path.
- Requires `indication`. The audited system had none, which is why it offered duloxetine as a codeine substitute.
- The six reproduced audit cases become named regression tests.

## V.7 Alert tiering (F3, F4, F5)

| Severity | Presentation |
|---|---|
| `critical` / blocker | Interruptive |
| `high` | Passive, in-context, persistent |
| `moderate` / `low` | In-context, non-persistent |
| `NO_GUIDANCE` | On-demand only |
| `HALTED` | Interruptive, but framed as *missing data*, never as risk |

Alert burden is a CI-gated metric (Part VII). A change that raises it must justify itself.

Also model **pre-test versus post-test context** (F13): a patient with results on file is a different alerting situation from one without.

---

# PART VI — ENGINE B: n-of-1 mRNA DESIGN

Designed now, built after Engine A ships. The platform slot is reserved so this does not require a rewrite.

## VI.1 Relationship to Engine A

The honest bridge: Engine A's `NoSafeAlternative` is the clinical situation in which custom therapy is considered. Architecturally clean.

**The honest limit:** n-of-1 therapy is reserved for ultra-rare disease with no approved treatment. Nobody designs a custom mRNA for statin intolerance. So this is **a second product on a shared platform**, not a second stage of the first. Do not market it as an escalation ladder from the current indication set.

## VI.2 Domain spine

```
tumor/germline variants → mutant peptides → patient HLA type
  → peptides that patient can actually present → ranked epitopes
  → assembled construct → codon- and structure-optimized mRNA
```

Every arrow is real biology. Precedent exists: individualized neoantigen mRNA therapy has reached Phase 3 readout, and nucleic-acid n-of-1 therapy has an FDA draft-guidance pathway for individualized antisense oligonucleotides.

**Critical domain note:** PGx genotype does **not** determine mRNA sequence. mRNA is translated then degraded by RNases; it is not a CYP450 substrate. Any code path where a CYP allele influences sequence design is a bug. HLA typing, not CYP genotype, is the personalization axis here.

## VI.3 Deterministic core

| Stage | Tool |
|---|---|
| HLA typing | OptiType (WES/WGS) or arcasHLA (RNA-seq) |
| Epitope prediction | pVACtools, wrapping NetMHCpan / MHCflurry |
| Codon + structure optimization | LinearDesign (joint codon/MFE optimization for mRNA) |
| Folding | ViennaRNA / RNAfold |
| Self-similarity screen | BLASTp against human proteome |

The LLM does not emit nucleotides. It selects bounded parameters, ranks tool-computed candidates, and writes narrative that passes the same gate (IV.5).

## VI.4 Validation checks

Registry-driven, same discipline as V.4 — stable IDs, thresholds as configuration, mandatory `threshold_rationale`.

| Check | Severity |
|---|---|
| Proteome self-similarity (autoimmunity risk) | blocker |
| Off-target / frameshift ORFs | blocker |
| Allergen motif screen | blocker |
| Construct length within synthesis bounds | blocker |
| Folding stability (MFE) | warning |
| 5′ end accessibility | warning |
| GC content window | warning |
| Homopolymer runs (esp. poly-U) | warning |
| Cryptic splice sites | warning |

Verdict is a pure function of findings. An agent may *explain* a verdict; no code path mutates it.

## VI.5 Minimum honest first slice

If you want something before Engine A is finished: wrap **one** tool — codon optimization plus folding — end-to-end through the platform. Adapter, pinned container, provenance, gate. Labeled a sequence-design sandbox. No therapy claims, no patient linkage. ~15% of the spec, proves the platform supports a second engine, and is honest about what it does.

---

# PART VII — MEASUREMENT

**Build this before making the engine authoritative.** Promoting an unmeasured oracle to binding authority is the same error class as defaulting an unknown phenotype to normal.

The audited system's only measured concordance was 46% with a 29% false-positive rate. The 85% in the pitch document is an estimate.

## VII.1 Why the bar is ~100%, not "good accuracy"

PGx guideline concordance is a **lookup**, not a prediction. If CPIC says avoid codeine in a CYP2D6 ultra-rapid metabolizer, there is one correct answer and it is knowable. Anything below near-total agreement on covered pairs is a bug, not model error. This is also why wrapping PharmCAT is the fix rather than an optimization — it makes the lookup correct by construction.

## VII.2 Golden set

```python
@dataclass(frozen=True)
class GoldenCase:
    patient: PatientFixture
    drug: DrugCode
    expected_outcome: Outcome
    expected_severity: Severity | None
    cpic_source: Provenance     # the guideline table this expectation came from
```

Transcribed from CPIC's published tables with provenance per row, then reviewed. **Not** generated from current system output — that measures self-consistency, not correctness.

## VII.3 Metrics

| Metric | Why |
|---|---|
| **Concordance** — exact `(outcome, severity)` match | Headline |
| **False negative rate** | Missed harm |
| **False positive rate** | **Co-primary, not secondary.** F3/F4: over-flagging is the dominant deployed failure mode of this product category |
| **Alert burden** — % of combinations flagged, weighted by interruptiveness | Tracks FP drift; directly predicts fatigue |
| **Halt rate** — % `HALTED`/`NO_GUIDANCE` | Expect a **sharp jump** when V.2 lands. That is the bug becoming visible, not a regression |
| **Narrative rejection rate** (IV.5) | Measured hallucination rate for your system |
| **Narrative omission rate** | Grounded systems fail by omitting (F11) |
| **Citation resolution failure rate** | Fabricated-reference rate (F10) |
| **Override rate**, alarmed at both ends | >~90% fatigue (F3); <~5% automation bias (F8) |
| **Per-gene / per-drug-class breakdown** | A 46% aggregate hides which module is broken |
| **Determinism** — same input + seed → identical output | Failure here is P0 |

## VII.4 CI gates

Concordance and both error rates asserted with floors. A PR moving any of them fails. A PharmCAT or policy-table version bump requires re-measurement in the same PR. Scorecards committed as versioned JSON so the delta appears in every diff.

## VII.5 Ablation

Run the full suite with `LLM_ENABLED=false` (I4) and compare. **If the agent layer does not beat the deterministic baseline, report that honestly.** That finding is publishable and demonstrates more judgment than hiding it.

---

# PART VIII — FAILURE CATALOGUE

Generalized from the audit. Each is a recurring pattern, not a one-off bug.

| Pattern | v1 instance | Structural fix |
|---|---|---|
| **Unknown rendered as safe** | Phenotype defaults to "normal metabolizer" | I2 — sealed union, no default branch |
| **Missing rendered as safe** | Vocabulary mismatch returns low-risk standard-dosing text | `NO_GUIDANCE` not comparable to `Severity` |
| **Output trusted without revalidation** | Alternatives never re-scored for the patient | I3 — type makes it unrepresentable |
| **Unvalidated component given authority** | LLM adjudicator overrules the engine | I1 + measure before promoting |
| **Clinical meaning derived from prose** | `"avoid" in evidence.lower()` | V.4 — curated reviewed table |
| **Client-supplied server state** | Gate status read from request body | I7 |
| **Silent degradation** | In-memory cache permanently shadows DB; writes fail silently | Explicit flagged degraded mode; `Result[T, WriteError]` |
| **Confident value with no basis** | Fabricated `*1/*2` diplotype for unknown FHIR gene | I5 + fail closed on unmapped input |
| **Test suite measures liveness, not correctness** | 225 combinations assert no exception | Part VII golden set |
| **Estimated number in an authoritative document** | "85%" beside a measured 46% | Part VII.4 committed scorecards |

---

# PART IX — TECHNOLOGY STACK

Several audited defects were stack choices, not logic errors: an ephemeral vector client re-embedding on every process, per-query database connections whose latency motivated the hardcoded-fixture shortcut, an MCP layer that silently fell through to direct calls, and two authentication paths where one skipped expiry checking. Stack decisions are safety decisions here.

## IX.0 Selection rules

1. **Fewer moving parts wins.** Every additional service is a failure mode, a divergence point between workers, and one more thing whose version must be pinned.
2. **If it cannot be pinned, it cannot be in the science path.** Reproducibility is a P0 metric (Part VII.3), so anything contributing to a clinical value must have a recordable version and digest.
3. **Anything required by I4 cannot depend on a model provider.** The system must run complete with `LLM_ENABLED=false`, so no core path may route through an LLM API.

## IX.1 The stack

### Backend core

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.12+ | Bioinformatics ecosystem; existing codebase |
| Packaging | `uv` with committed `uv.lock` | Fast, fully locked — required for determinism (rule 2) |
| Contracts | Pydantic v2, `frozen=True`, `extra="forbid"` | Enforces I2/I3/I5 at construction time |
| Type checking | `mypy --strict` on `engines/` and `domain/` | The invariants are type-level claims; unchecked types make them decorative |
| Lint / format | `ruff` | Single tool, fast |
| API | FastAPI | Async, emits OpenAPI (feeds IX.4) |
| Server | `uvicorn` behind `gunicorn` workers | — |

**Discriminated unions matter here.** `PhenotypeCall` (Part V.2) must be a tagged union, not a loose `Union`:

```python
PhenotypeCall = Annotated[
    KnownPhenotype | UnknownPhenotype,
    Field(discriminator="kind"),
]
```

Without the discriminator, Pydantic coerces by trying members in order, which can silently produce the wrong branch — reintroducing the fail-open behaviour the type was designed to eliminate.

### Data

| Concern | Choice | Rationale |
|---|---|---|
| Database | PostgreSQL 16 | Single store for relational, vector and full-text |
| Driver + pool | `psycopg` 3 with `AsyncConnectionPool` | Removes the per-query connect that motivated the fixture shortcut |
| Migrations | Alembic | Fixtures become seeded rows, not in-code literals |
| Vector search | `pgvector` extension | **Replaces ChromaDB entirely** — see IX.3 |
| Lexical search | Postgres `tsvector` + `ts_rank_cd` | Guideline text is keyword-heavy; dense-only retrieval loses exact gene and allele tokens |
| Fusion | Reciprocal-rank fusion in SQL | No extra service |
| Embeddings | `fastembed` (ONNX, CPU, offline) | No torch dependency, no network call, deterministic — satisfies rule 3 |
| Object storage | S3-compatible (MinIO in dev) | Tool stdout, generated reports, content-addressed keys |

### Deterministic engines

| Concern | Choice | Rationale |
|---|---|---|
| Engine A core | **PharmCAT**, pinned, as a separate service | Reference implementation; Java, so it does not live in the Python process |
| Engine A invocation | HTTP call to a thin wrapper service, or a queued job | Avoids Docker-in-Docker on managed hosts — see IX.3 |
| Engine B core (later) | pVACtools, LinearDesign, RNAfold, BLAST | Same adapter interface, one service or batch job each |
| Adapter contract | `ToolAdapter` ABC (Part IV.3) | Records `tool_version`, `container_digest`, input/output hashes |
| Result cache | Postgres table keyed on `(image_digest, input_sha256, params)` | Makes reruns cheap and reproducibility auditable |

### AI layer

| Concern | Choice | Rationale |
|---|---|---|
| Orchestration | OpenAI Agents SDK, `as_tool()` composition only | Every clinical value is computed outside the agent layer, so what remains is a few stateless agents producing narrative and inquiry. A graph runtime is ceremony for that shape; the SDK's guardrail primitives are the closer fit. `handoff()` is prohibited — it transfers control of a run, which is how a judgment would migrate into `ai/`. SDK tracing is disabled: the audit trail belongs in `RunManifest`, not a third party (ADR-0005) |
| Provider | Abstracted behind an internal `LlmClient` protocol | I4 requires the whole layer to be switchable off; provider lock-in makes that hard |
| Structured output | Pydantic response schemas with bounded enums | An out-of-range value is rejected before reaching application code |
| Settings | None. `temperature`, `top_p` and `seed` are not settable on the pinned model and are rejected by the API | Determinism was never claimed for this layer — IX.3 says so. Removing these removes a setting, not a guarantee; the LLM layer is covered by narrative rejection and omission rates. Schema parse-failure rate is measured alongside them, because the OpenAI-compatible layer does not guarantee schema conformance (ADR-0004, ADR-0005) |
| Gate | Plain Python in `ai/gate.py` | **Never a model.** F12: probabilistic supervision provides no floor |
| Drug lexicon | Local RxNorm-derived term list | Powers gate check 3 (undeclared entity scan); must be offline and complete |

### Frontend

| Concern | Choice | Rationale |
|---|---|---|
| Framework | Next.js + TypeScript | Existing |
| Server state | TanStack Query | Cache invalidation on gate transitions |
| Runtime validation | `zod` schemas generated from OpenAPI | Mirrors Pydantic contracts across the boundary |
| Types | `openapi-typescript` from FastAPI's schema | Endpoints take IDs, and generated types make I7 violations a compile error |

### Platform

| Concern | Choice | Rationale |
|---|---|---|
| Auth | Single validation path — full JWT verification including expiry, audience and issuer, plus session lookup | Two paths caused the expiry-skip defect |
| Authorization | `care_team_assignment` table + `require_access()` on every patient-scoped route | Part IV.7 |
| Encryption | Fernet for PII columns; refuses to boot without a key | Decryption failure raises, never returns ciphertext |
| Audit | Append-only Postgres table + provenance edge table | Criterion 4 in database form |
| Observability | OpenTelemetry traces + structured JSON logs, correlation IDs | Already partly present |
| LLM tracing | Recorded into `RunManifest` (prompt hash, response hash, tokens, gate verdict); Langfuse optional and self-hosted | Keeps the audit trail in your own store rather than a third party |
| Testing | pytest, `hypothesis` for property tests, `pytest-cov` | Vocabulary and sequence invariants are natural property tests |
| CI | GitHub Actions | IX.5 |
| Containers | Docker + Compose (dev), same images in production | Compose must actually build — the audited file referenced a nonexistent Dockerfile |

## IX.2 Removals

| Remove | Replace with | Closes |
|---|---|---|
| ChromaDB | pgvector + tsvector in Postgres | Ephemeral re-embedding across six subprocesses |
| `psycopg2` per-query connect | `psycopg3` async pool | Connection latency; the fixture shortcut's root cause |
| In-memory fallback dicts | Explicit flagged degraded mode | Permanent DB shadowing after one timeout |
| Hardcoded `PATIENTS` dict | Alembic-seeded rows | Fixtures outranking the database |
| MCP stdio subprocess layer | Direct in-process calls | A decorative abstraction with an invisible fallback |
| LangSmith reference | `RunManifest` + optional self-hosted tracing | A commit claiming an observability layer absent from the tree |
| Dual auth paths | One verified path | Indefinitely valid expired tokens |

## IX.3 Decisions worth defending

**Postgres absorbs the vector store.** ChromaDB's ephemeral client re-embedded seven files per process, six times over on cold start. The deeper problem is that corpus snapshots must be *transactionally consistent* with the assessments citing them (I8) — a separate vector service makes that a distributed-systems problem for no benefit at your scale. pgvector plus `tsvector` gives hybrid retrieval, snapshot pinning as a table column, and one fewer service. *Verify pgvector availability on your managed Postgres before committing; it is widely supported but confirm.*

**PharmCAT runs as a service, not a subprocess.** The ideal is container-per-tool with no network. That is impractical on managed hosts where Docker-in-Docker is unavailable. The workable compromise: PharmCAT and its JRE baked into one pinned image, exposed by a thin HTTP wrapper, called by the Python app. You keep version pinning, digest recording and process isolation; you lose only the strict no-network guarantee, which matters less for a tool with no network-dependent behaviour. Record the image digest in every `ToolResult` regardless.

**MCP goes, unless it earns its place.** The audit found every failure — including genuine bugs inside tools — re-raised and silently caught, falling through to direct Python calls. The MCP layer could be entirely broken with no observable difference. For a single-deployment system, a subprocess boundary between your own code and your own tools is cost without benefit. Keep MCP only if external clients need to consume these tools; if so, make the fallback loud and metered, never silent.

**Determinism applies to the engine path only.** Part VII.3 gates on byte-identical output for identical input and seed. That guarantee holds for `engines/` — pinned tools, hashed inputs, pure functions. It does **not** hold for LLM output even at temperature zero with a seed, since providers do not guarantee reproducibility across serving conditions. State this explicitly: the determinism metric covers the deterministic core, and the LLM layer is instead covered by the narrative rejection and omission rates. Conflating the two would be a false reproducibility claim.

**Groq is fine, lock-in is not.** Speed and cost suit this workload. But I4 requires the entire AI layer to be removable, so route everything through an internal `LlmClient` protocol and pin the exact model identifier in `RunManifest`. Verify structured-output support for your chosen model rather than assuming it — support varies by model within a provider.

## IX.4 Contract propagation

One source of truth, flowing outward:

```
domain/*.py  (Pydantic)
   └─► FastAPI OpenAPI schema
          └─► openapi-typescript  ──►  frontend types
          └─► zod schemas         ──►  runtime validation
```

Generated in CI and committed. A drift between backend contract and frontend type becomes a failing build rather than a runtime surprise. This is also how I7 gets enforced cheaply: if the generated type for `POST /clinical-note` accepts only `{evaluation_id: string}`, a client cannot post a state object without a type error.

## IX.5 CI pipeline

| Job | Gate |
|---|---|
| `lint` | ruff clean |
| `typecheck` | mypy strict on `domain/`, `engines/` |
| `test` | Full pytest suite |
| `invariants` | `tests/invariants/` — I1 through I10, one file each |
| `llm-disabled` | Full suite with `LLM_ENABLED=false` (I4) |
| `concordance` | Golden-set run; fails if concordance drops or either error rate rises (Part VII.4) |
| `alert-burden` | Fails if interruptive-alert rate rises without an accompanying policy-change note |
| `determinism` | Same input + seed twice → identical engine output |
| `contracts` | Regenerated TS types match committed ones |
| `frontend` | tsc, lint, build |

The concordance and alert-burden gates are the distinctive ones. They make it structurally difficult to ship a change that degrades clinical correctness or increases fatigue, which is the whole point.

## IX.6 What must be pinned

Recorded in `RunManifest` on every run. If it is not on this list and it affects output, it is an unpinned dependency and a reproducibility bug:

- `uv.lock` hash
- Every tool image digest and tool version
- Corpus snapshot IDs, per corpus
- Severity policy table version
- Embedding model name and version
- LLM model identifier (sampling parameters are not settable on the pinned model; nothing to pin)
- Golden-set version
- Application `spec_version`

## IX.7 Deployment topology

```
┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐
│  Next.js UI  │──►│  FastAPI app    │──►│ PharmCAT service │
└──────────────┘   │  + Agents SDK   │   │  (pinned image)  │
                   └────────┬────────┘   └──────────────────┘
                            ▼
                   ┌─────────────────┐   ┌──────────────────┐
                   │   PostgreSQL    │   │  S3 / MinIO      │
                   │ + pgvector      │   │  artifacts       │
                   └─────────────────┘   └──────────────────┘
```

Four services. Dev via Compose; production the same images. Engine B later adds one service per tool behind the same adapter interface, which is exactly why the interface exists.

---

# PART X — DELIVERY ORDER

Ranked by clinical risk removed per unit of work.

| # | Step | Closes |
|---|---|---|
| 1 | Golden set + concordance harness + CI gate. Measure the current engine honestly | VII, I6 |
| 2 | Typed phenotype model; unknown halts | V.2, I2 |
| 3 | Alternatives validated against the same patient | V.6, I3 |
| 4 | Gate re-read server-side + state machine + content hash | IV.6, I7 |
| 5 | PharmCAT adapter replaces hand-rolled rules and `guidelines.json` | V.3 |
| 6 | Severity policy table | V.4 |
| 7 | Delete adjudicator; engine authoritative | I1 |
| 8 | Grounding gate | IV.5, I8 |
| 9 | Review interface redesign + override monitoring | IV.6, I10 |
| 10 | Authorization model + auth hardening | IV.7 |
| 11 | Data layer honesty + connection pool | — |
| 12 | Alert tiering | V.7 |
| 13 | Delete therapy slice, MisuseMonitor, CostNavigator | IV.4 |
| 14 | Re-measure and correct all documentation | VII |
| 15 | *(later)* Engine B minimum slice | VI.5 |

Steps 1–4 remove most of the clinical risk. If nothing else ships, ship those.

---

# PART XI — OPEN DECISIONS

Record in `docs/adr/` as resolved. Do not silently pick.

1. **Clinical reviewer.** V.4 needs a named pharmacist to sign the severity table. This is a dependency, not a nice-to-have — it is what makes the table meaningful rather than decorative.
2. **Criterion 1 boundary.** Genomic data derived from an IVD assay sits near the "signal from an in vitro diagnostic device" line. Structured diplotype input is clearly safer than raw instrument output. Get a regulatory read before any non-research positioning.
3. **PharmCAT licence and gene coverage.** Verify licence terms for the intended use; confirm coverage of your gene/drug set. Anything uncovered is `NO_GUIDANCE`, never a hand-rolled fallback.
4. **Source precedence.** PharmCAT can emit CPIC, DPWG and FDA recommendations. They will sometimes disagree (F14). Decide precedence explicitly, in policy, not code.
5. **Indication vocabulary.** V.6 requires it. ICD-10, SNOMED, or a curated enum?
6. **Severity scale.** Keep four levels, or adopt CPIC's own strength vocabulary directly? Fewer translation layers means fewer places to be wrong.
7. **FHIR scope.** Support all in-scope genes properly, or restrict imports to genes with real LOINC mappings and reject the rest. Inventing a diplotype for an unrecognised gene must not survive in any form.
8. **Engine B timing and reviewer.** Needs a computational biologist, not a pharmacist. Different person, different sign-off.
9. **pgvector availability** on the chosen managed Postgres. Widely supported, but confirm before removing ChromaDB.
10. **Structured-output support** for the specific LLM model behind the provider abstraction. Varies by model within a provider; verify rather than assume.
11. **Host capability for a second service.** The PharmCAT service is required. Confirm the deployment target supports it, or move to a host that does — this constraint should drive the hosting choice, not the reverse.

---

# REFERENCES

1. Covington & Burling. *5 Key Takeaways from FDA's Revised Clinical Decision Support Software Guidance.* Jan 2026. https://www.cov.com/news-and-insights/insights/2026/01/5-key-takeaways-from-fdas-revised-clinical-decision-support-cds-software-guidance
2. FDA. *Clinical Decision Support Software — Guidance for Industry and FDA Staff.* Jan 2026. Docket FDA-2017-D-6569. https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
3. Arnold & Porter. *FDA "Cuts Red Tape" on Clinical Decision Support Software.* Jan 2026. https://www.arnoldporter.com/en/perspectives/advisories/2026/01/fda-cuts-red-tape-on-clinical-decision-support-software
4. Felisberto M, et al. *Override rate of drug-drug interaction alerts in clinical decision support systems: systematic review and meta-analysis.* Health Informatics J, 2024. doi:10.1177/14604582241263242
5. Nanji KC, et al. *Overrides of medication-related clinical decision support alerts in outpatients.* JAMIA. PMID 24166725
6. Poly TN, et al. *Appropriateness of Overridden Alerts in CPOE: Systematic Review.* JMIR Med Inform 2020;8(7):e15653
7. *Appropriateness of Alerts and Physicians' Responses With a Medication-Related CDSS.* JMIR Med Inform 2022;10:e40511
8. *Overall performance of a drug–drug interaction clinical decision support system.* PMC8864797
9. Phansalkar S, et al. *Drug-drug interactions that should be non-interruptive to reduce alert fatigue in EHRs.* JAMIA. PMID 23011124
10. *The Illusion of Control: Why "Human in the Loop" Is Clinical AI's Biggest Regulatory Fiction.* Apr 2026. https://beyondtheslide.substack.com/p/the-illusion-of-control-why-human
11. *Who's really in the loop? Rethinking oversight in AI-assisted health care.* The Lancet, 2026. doi:10.1016/S0140-6736(26)00204-7
12. *Bias recognition and mitigation strategies in artificial intelligence healthcare applications.* npj Digital Medicine, 2025. doi:10.1038/s41746-025-01503-7
13. MedPro Group. *Artificial Intelligence Risks: Automation Bias.*
14. Censinet. *When the Model Is Wrong: Clinical Override Protocols for AI Recommendations.* Apr 2026
15. Censinet. *When Algorithms Fail: Preparing for AI Incidents in Clinical Settings.* Jun 2026
16. Omar M, et al. *Multi-model assurance analysis showing large language models are highly vulnerable to adversarial hallucination attacks during clinical decision support.* Communications Medicine, 2025. doi:10.1038/s43856-025-01021-3
17. *MHB: Medical Hallucination Benchmark for LLMs in Complex Clinical Tasks.* AAAI 2026
18. *MedPRESS: A Multi-turn Benchmark for Patient-Pressure-Induced Medical Sycophancy in LLMs.* arXiv:2608.02520
19. Asgari E, et al. *A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation.* npj Digital Medicine 2025;8:274. doi:10.1038/s41746-025-01670-7
20. Shamsujjoha M, et al. *Swiss Cheese Model for AI Safety: A Taxonomy and Reference Architecture for Multi-Layered Guardrails of Foundation Model Based Agents.* ICSA 2025
21. *Provably Secure Agent Guardrail.* arXiv:2605.29251
22. Wang H, et al. *AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents.*
23. Wake DT, et al. *Pharmacogenomic Clinical Decision Support: A Review, How-to Guide, and Future Vision.* Clin Pharmacol Ther, 2022. doi:10.1002/cpt.2387
24. Smith DM, et al. *Pharmacogenomic Clinical Decision Support: A Scoping Review.* Clin Pharmacol Ther 2023;113:803-815. doi:10.1002/cpt.2711
25. CPIC. https://cpicpgx.org/ · PharmCAT. https://pharmcat.clinpgx.org/
26. Nguyen TT, et al. *Comparing commercial pharmacogenetic testing results and recommendations for antidepressants with established CPIC guidelines.* Front Pharmacol, 2024. doi:10.3389/fphar.2024.1500235
27. PRSB. *Guidance for using pharmacogenomic information in clinical practice.*

---

*Version 1.1 · amended 23 Aug 2026 · Update on any change to Part II invariants or Part VII gates.*

**Amendment log**

| Date | Change | Authority |
|---|---|---|
| 2026-08-23 | IX.1 orchestration row: LangGraph → OpenAI Agents SDK, `as_tool()` only, `handoff()` prohibited, tracing disabled | ADR-0005 |
| 2026-08-23 | IX.1 settings row and IX.6 pin list: `temperature=0` and `seed` removed — not settable on the pinned model | ADR-0004 |
| 2026-08-23 | MANIFEST AI-layer table brought into line with ADR-0004: provider row names Anthropic rather than Groq; `instructor` removed, superseded by the SDK's typed output | ADR-0004, ADR-0005 |
| 2026-08-23 | `ai/graph` renamed `ai/orchestration` in IV.8, IV.11 and IX.7. A rename, not a change to the contract: the same layer, the same permitted and forbidden edges | ADR-0005 |
