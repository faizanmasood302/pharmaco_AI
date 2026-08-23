# Data Model — 001 PGx Safety Harness

**Date**: 2026-08-23 | **Feeds**: [plan.md](./plan.md) · [contracts/openapi.yaml](./contracts/openapi.yaml)

Derived from the spec's fourteen key entities and `HARNESS.md` IV.1, IV.6, IV.9, V.2, V.5 and V.6.
Every type below lives in `src/domain/` and imports nothing internal. Every model is
`ConfigDict(frozen=True, extra="forbid")` unless stated otherwise — a frozen contract is what makes
Principles II, III and V enforceable at construction rather than at review.

## 1. The two type-level decisions that carry the safety argument

Both exist because the audited system got them wrong, and both are enforced by the type system and
the database rather than by tests alone.

### 1.1 `PhenotypeCall` is a discriminated union with no default branch

```python
class VocabularyClass(StrEnum):
    METABOLIZER     = "metabolizer"       # CYP2D6/2C19/2C9/3A4: PM, IM, NM, RM, UM
    FUNCTION        = "function"          # SLCO1B1, ABCG2: Poor/Decreased/Normal/Increased
    ACTIVITY_SCORE  = "activity_score"    # DPYD
    ALLELE_PRESENCE = "allele_presence"   # HLA-B: *57:01, *58:01 …

class KnownPhenotype(BaseModel):
    kind: Literal["known"] = "known"
    gene: Gene
    diplotype: str
    vocabulary: VocabularyClass
    term: str                             # validated ∈ ALLOWED_TERMS[gene]
    activity_score: Decimal | None
    source: ToolResult

class UnknownPhenotype(BaseModel):
    kind: Literal["unknown"] = "unknown"
    gene: Gene
    reason: Literal["not_genotyped", "ambiguous_diplotype",
                    "no_cpic_definition", "assay_does_not_cover"]
    raw_observation: str | None           # original unrecognised text, preserved (ADR-0003)

PhenotypeCall = Annotated[KnownPhenotype | UnknownPhenotype, Field(discriminator="kind")]
```

The `discriminator` is load-bearing. Without it Pydantic coerces by trying members in order, which
can silently produce the wrong branch and reintroduce exactly the fail-open behaviour the type
exists to eliminate. `ALLOWED_TERMS` is built from CPIC gene definition tables at build time and is
never hand-typed.

`GenomicProfile.calls` has an entry for **every** in-scope gene. A gene the assay did not cover is
present as `UnknownPhenotype(reason="assay_does_not_cover")`, never absent — absence is what let the
audited system proceed silently.

### 1.2 `Outcome` and `Severity` are disjoint and not orderable against each other

```python
class Outcome(StrEnum):          # NOT ordered, NOT comparable to Severity
    ACTIONABLE  = "actionable"   # guideline exists and implies a change
    NO_CHANGE   = "no_change"    # guideline exists, standard dosing
    NO_GUIDANCE = "no_guidance"  # no CPIC statement for this pair
    HALTED      = "halted"       # at least one relevant gene is UnknownPhenotype

class Severity(IntEnum):         # ordered, and only ever within itself
    LOW = 1; MODERATE = 2; HIGH = 3; CRITICAL = 4
```

`severity` is `None` whenever `outcome` is not `ACTIONABLE`. No `max()`, `sorted()`, `min()` or
clamp may accept both types. A one-directional `max()` severity clamp is prohibited outright: it is
the exact mechanism of the audited critical failure, in which a halt became a `"low"`.

The four-level scale is **settled** (ADR-0006), not assumed. `cpic_strength` and `severity` stay as
separate columns on the policy row: CPIC strength answers "how good is the evidence", severity
answers "what should this system do about it", and `HARNESS.md` V.4 makes the mapping between them a
product policy decision that belongs in reviewable data with a named reviewer. Collapsing the two
would move that judgment into an enum definition, where no pharmacist signs it.

## 2. Domain entities

| Entity | Key fields | Invariants it carries |
|---|---|---|
| `ToolResult` | `tool_name`, `tool_version`, `container_digest`, `input_sha256`, `output_sha256`, `started_at`, `duration_ms`, `exit_code`, `parameters` | Principle V. Every scientific value originates from one |
| `Provenanced[T]` | `value`, `source: ToolResult` | Makes "unprovenanced" unrepresentable for wrapped values |
| `Citation` | `corpus_id`, `corpus_snapshot_id`, `document_id`, `section`, `span: tuple[int, int] \| None` | Offsets, **never quoted text** — keeps CC BY-SA corpora out of the source tree |
| `Gene`, `VocabularyClass`, `ALLOWED_TERMS` | — | Four vocabularies, not one (F13) |
| `KnownPhenotype` / `UnknownPhenotype` | see §1.1 | Principle II |
| `GenomicProfile` | `calls: Mapping[Gene, PhenotypeCall]`, `panel: PanelDefinition`, `reference_build` | Every in-scope gene present; `panel` records what the assay actually covered |
| `DrugCode` | RxNorm-resolved identifier | Unresolvable names are refused, never near-matched (FR-033c) |
| `Indication` | member of the curated version-controlled list | ADR-0001; required for alternatives |
| `Finding` | `gene`, `severity`, `action`, `policy_row_id`, `provisional`, `tool_result_id` | One gene-level contribution; provisional derives from reviewer absence |
| `Assessment` | `assessment_sha256`, `profile_id`, `drug_code`, `indication`, `outcome`, `severity \| None`, `findings`, `policy_version`, `corpus_snapshot_id`, `engine_version` | Immutable. Identified by a hash of its own content, which is what approvals bind to |
| `AlternativeSet` | `ranked: list[tuple[DrugCode, Assessment]]`, `considered: list[tuple[DrugCode, Assessment]]` | **Constructible only from `Assessment` objects** — Principle III becomes unrepresentable-if-violated |
| `NoSafeAlternative` | `reason`, `considered` | A first-class result, never replaced by a fallback suggestion |
| `SeverityPolicyRow` | `gene`, `phenotype_term`, `drug_code`, `cpic_strength`, `severity`, `action`, `interruptive`, `provenance`, `reviewed_by`, `reviewed_on`, `provisional` | Fails closed on missing provenance or reviewer |
| `Evaluation` | `assessment_id`, `created_by`, `created_at` | Current state is the fold of its transitions — there is no status field |
| `GateTransition` | `from_state`, `to_state`, `actor_id`, `actor_role`, `rationale`, `assessment_sha256`, `at` | Append-only. Principle VII |
| `Narrative` | `text`, `cites_finding_ids`, `cites_citation_ids`, `mentions_entities`, `gate_verdict`, `rejection_reasons`, `attempt`, `schema_parse_ok` | What the model declares, so the gate can check it. `schema_parse_ok` exists because the OpenAI-compatible layer does not guarantee schema conformance, so the parse-failure rate is measured rather than assumed (ADR-0005) |
| `EvaluationCase` | `patient_fixture`, `drug`, `expected_outcome`, `expected_severity`, `cpic_source`, `verified_by` | Transcribed from published tables; `verified_by` is human-only (FR-035a) |
| `RunManifest` | `spec_version`, `inputs`, `pins`, `node_transitions`, `seed`, `created_at` | Every pin that can affect output |
| `CareRelationship` | `clinician_id`, `patient_id`, `role`, `granted_at`, `revoked_at` | No implicit access |

### Engine signatures

```python
def assess(profile: GenomicProfile, drug: DrugCode) -> Assessment: ...

def safe_alternatives(
    profile: GenomicProfile, original: DrugCode, indication: Indication,
) -> AlternativeSet | NoSafeAlternative: ...
```

`safe_alternatives` scores every candidate with the **same engine against the same patient**, and
always returns the `considered` set including rejects and the reason for each. `indication` is a
required parameter, not an optional one: the audited system had none, which is why it offered
duloxetine as a codeine substitute.

## 3. Database schema

PostgreSQL 16. Immutable where it matters, append-only where it must be. Migrations via Alembic;
fixtures become seeded rows, never in-code literals.

```sql
-- Provenance spine -------------------------------------------------
tool_results(id, tool_name, tool_version, container_digest,
             input_sha256, output_sha256, parameters jsonb,
             started_at, duration_ms, exit_code, stdout_uri)

provenance_edges(artifact_id, produced_by_tool_result_id, consumed_artifact_id)

-- Patient and genomics ---------------------------------------------
patients(id, source, demographics_enc, created_at)
genomic_profiles(id, patient_id, reference_build, panel jsonb)

phenotype_calls(id, profile_id, gene,
                kind,                    -- 'known' | 'unknown'  (the discriminator)
                diplotype, vocabulary, term, activity_score,
                unknown_reason, raw_observation,
                tool_result_id,
                CHECK ((kind='known') = (term IS NOT NULL)))

-- Assessment (immutable) -------------------------------------------
assessments(id, assessment_sha256 UNIQUE,
            profile_id, drug_code, indication,
            outcome, severity,           -- severity NULL when outcome <> 'actionable'
            policy_version, corpus_snapshot_id, engine_version, created_at)

findings(id, assessment_id, gene, severity, action,
         policy_row_id, provisional bool, tool_result_id)

alternatives_considered(id, assessment_id, drug_code, outcome, severity,
                        rank int NULL, rejected_reason)

-- Review gate (append-only) ----------------------------------------
evaluations(id, assessment_id, created_by, created_at)

gate_transitions(id, evaluation_id, from_state, to_state,
                 actor_id, actor_role, rationale,
                 assessment_sha256, at)          -- INSERT ONLY

care_team_assignments(clinician_id, patient_id, role, granted_at, revoked_at)

-- Evidence ---------------------------------------------------------
corpus_snapshots(id, corpus_id, version, ingested_at, licence)
corpus_documents(id, snapshot_id, external_id, title, text)
corpus_chunks(id, document_id, span_start, span_end,
              embedding vector(384), lexeme tsvector)

-- Policy -----------------------------------------------------------
severity_policy_rows(id, policy_version, gene, phenotype_term, drug_code,
                     cpic_strength, severity, action, interruptive bool,
                     provenance jsonb, reviewed_by, reviewed_on,
                     provisional bool GENERATED ALWAYS AS (reviewed_by IS NULL) STORED)

-- AI accountability ------------------------------------------------
narratives(id, assessment_id, text, model_id, prompt_sha256, response_sha256,
           gate_verdict,        -- 'accepted' | 'regenerated' | 'template_fallback'
           rejection_reasons jsonb, attempt int)

run_manifests(id, spec_version, inputs jsonb, pins jsonb,
              node_transitions jsonb, seed, created_at)

audit_logs(id, actor_id, action, resource_type, resource_id, at, detail jsonb)
```

Four schema decisions carry architectural weight:

- **`phenotype_calls` CHECK constraint.** The database refuses to store a "known" phenotype without
  a term. The fail-open default cannot be reintroduced even by a direct SQL write.
- **`alternatives_considered` stores rejects.** Criterion 4 requires showing what was ruled out; a
  schema that stores only winners cannot satisfy it.
- **`severity_policy_rows.provisional` is a generated column.** Provisional status is derived from
  the absence of a reviewer, so it cannot drift.
- **`gate_transitions` has no companion status column.** There is nothing to update, so there is
  nothing to forge or to leave stale.

## 4. Gate state machine

```
DRAFT → PENDING_REVIEW → APPROVED → (assessment changes) → SUPERSEDED
              │                                                │
              └────────────→ REJECTED ←───────────────────────┘
```

Rules:

- **Append-only.** Current state is the fold over the transition history. This closes the audited
  unlimited-re-approval defect.
- **Approval binds to `assessment_sha256`.** If the assessment changes — new genotype, policy
  update, tool version bump — the hash no longer matches and the approval auto-transitions to
  `SUPERSEDED`. A clinician cannot have approved something they never saw.
- **The transition endpoint requires the hash**, giving content binding and optimistic concurrency
  in one move: approving a stale assessment is rejected rather than silently accepted.
- **Only `PHARMACIST` may transition to `APPROVED`.** `CLINICIAN`, `RESEARCHER` and `ADMIN` may not.
- **The gate is a workflow and accountability mechanism, not a safety control.** No document,
  comment or risk write-up may cite it as mitigation for engine error.

## 5. Halt and error propagation

| Condition | Result | Presentation |
|---|---|---|
| Gene not genotyped, or assay gap | `HALTED` | Interruptive, framed as **missing data**, never as risk |
| Contradictory input sources | `HALTED` | Blocks processing; names both sources |
| Ambiguous diplotype | `HALTED` | Names the ambiguity |
| No CPIC statement for the pair | `NO_GUIDANCE` | On demand only; explicitly "no guideline exists" |
| Policy row provisional | verdict plus a `provisional` flag | Visually distinct from reviewed findings |
| Tool container failure | `EngineError` | 5xx. **Never a fallback verdict** |
| Corpus snapshot unavailable | `EngineError` in `evidence` | The assessment proceeds; the narrative degrades to template |
| Gate rejects twice | template fallback | Logged as a measured hallucination event |
| Database write failure | `Result[T, WriteError]` propagated | 5xx. Never a success-shaped response |
| Provider unavailable | template fallback | Full functionality retained (Principle IV) |

The rule underneath the table: `NO_GUIDANCE` and `HALTED` are not severities and cannot be ordered
against them.

## 6. Validation rules by requirement

| Rule | Enforced by | Requirement |
|---|---|---|
| Every in-scope gene has an entry | `GenomicProfile` construction | FR-004 |
| A known phenotype cannot exist without a term | Pydantic union + DB CHECK | FR-004, Principle II |
| Relevant gene unknown → halt | `assess()` | FR-005, FR-033b |
| CYP2D6 from a VCF is `assay_does_not_cover` until the second caller lands | Profile ingest, `vcf` branch | ADR-0007 |
| Absent policy triple → `NO_GUIDANCE` | `severity.py` lookup | FR-007 |
| Alternatives require an indication from the curated list | `safe_alternatives()` signature | FR-010, ADR-0001 |
| Every presented alternative carries its own `Assessment` | `AlternativeSet` constructor | FR-009 |
| Policy row missing provenance or reviewer → refuse to start | Fail-closed loader | FR-016 |
| Claim without a source → refuse to render | Renderer | FR-014 |
| Request carrying approval status → reject | Endpoint signature; generated TS types | FR-020 |
| Approval against a stale hash → reject | Transition handler | FR-023 |
| Unresolvable drug name → refuse | Local lexicon lookup | FR-033c |
| Unmapped gene → explicit unknown, original text kept | Import path | FR-033a, ADR-0003 |
| Contradictory sources → halt naming both | `ProfileValidator` | FR-031 |

---

*Research and education only. Synthetic data only. Not a medical device.*
