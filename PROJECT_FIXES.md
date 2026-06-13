# Project Fixes And Improvement Checklist

This file captures the concrete fixes and follow-up work identified during the project review of the Pharmacogenomic Harness, including `FUTURE_ARCHITECTURE.md`.

## Immediate Runtime Fixes

- Fix the adherence check-in endpoint in `agent-server/main.py`.
  - Current issue: `submit_check_in()` receives a parameter named `request`, but calls `payload.response` and `payload.side_effect_reported`.
  - Expected fix: rename the parameter to `payload` or update the call to use `request.response` and `request.side_effect_reported`.
  - Impact: the adherence check-in route can fail at runtime.

- Fix or remove the stale backend login route.
  - Current issue: `/api/auth/login` calls `create_token()`, but `create_token()` returns `"deprecated"`.
  - Current auth flow uses BetterAuth sessions stored in Supabase, so this endpoint can return an unusable token.
  - Expected fix: either fully migrate this route to BetterAuth-compatible session handling or remove it to avoid confusion.

- Clean up frontend report-fetch test noise.
  - Current issue: frontend tests pass but repeatedly print `Unknown URL` for `/api/patients/{patientId}/reports`.
  - Expected fix: mock that route in `Home.test.tsx` or adjust the component fetch behavior for tests.
  - Impact: test output is noisy and can hide real warnings later.

## Security And Compliance Fixes

- Align Supabase RLS with the README claims.
  - Current issue: `supabase/seed.sql` defines policies for clinical tables, but only visibly enables RLS for `medications` and `clinical_reports`.
  - Expected fix: explicitly enable RLS for all clinical tables, including `patients`, `evaluations`, `adherence_plans`, `check_ins`, `audit_logs`, `therapy_requests`, `therapy_candidates`, `therapy_validation_results`, `therapy_audit_events`, and `therapy_human_reviews`.

- Review the middleware fail-open behavior in `web/src/proxy.ts`.
  - Current issue: if session verification fails, middleware logs a warning and allows the request to continue.
  - Expected fix: decide whether production should fail closed, or restrict fail-open behavior to local development only.

- Harden encryption configuration.
  - Current issue: `agent-server/crypto.py` generates an ephemeral encryption key if `ENCRYPTION_KEY` is missing.
  - Expected fix: keep ephemeral keys only for local demo mode; fail startup in production when the key is absent.

- Replace placeholder security reporting details.
  - Current issue: `SECURITY.md` still uses `security@example.com`.
  - Expected fix: replace with the real reporting email/process before public release.

## Clinical Safety And Product Scope Fixes

- Keep the project clearly labeled as synthetic/demo-only until real compliance work is complete.
  - Current issue: some docs and UI copy imply enterprise or clinical readiness ahead of implementation.
  - Expected fix: use precise wording such as "research simulation", "prototype", and "not for clinical use" where appropriate.

- Expand the deterministic medication safety engine.
  - Current state: the deterministic rules cover a small demo formulary.
  - Future target: expand from roughly 7-9 demo medications to 50+ high-impact medications.
  - Priority classes from `FUTURE_ARCHITECTURE.md`: SSRIs, statins, opioids, antiplatelets, and common primary-care prescriptions.

- Add real drug database integration.
  - Future target: integrate RxNorm, First Databank, or another structured medication database.
  - Purpose: support real-world polypharmacy, contraindications, dose limits, and drug-drug interactions.

- Move clinical claims to structured provenance.
  - Future target: every clinical claim should include source guideline, chunk ID, guideline version, and confidence score.
  - Purpose: reduce reliance on narrative LLM justification.

## Agent And Bioinformatics Fixes

- Replace simulated bioinformatics with real scientific tooling.
  - Current state: MFE, homology, and immunogenicity checks are deterministic simulations.
  - Future target: integrate ViennaRNA for MFE, BLAST for homology, and AlphaFold or equivalent structural tooling where appropriate.

- Add async processing for long-running simulations.
  - Future target: Celery + Redis or equivalent queue.
  - Frontend target: live status updates via WebSockets or polling.
  - Purpose: avoid blocking API requests for heavy bioinformatics jobs.

- Add multi-model benchmarking.
  - Future target: compare Groq/Llama, GPT-4o, Claude, and Gemini/MedLM against deterministic baselines.
  - Metrics: latency, JSON reliability, evidence faithfulness, safety agreement, and cost.

- Add agent drift and hallucination monitoring.
  - Future target: LangSmith, Arize Phoenix, or an internal trace evaluator.
  - Purpose: detect outputs that diverge from deterministic rules, guidelines, or historical expert decisions.

- Implement clinician disagreement capture.
  - Current state: approval/rejection rationale exists.
  - Future target: structure disagreement reasons and store them as a learning/evaluation dataset.

## Frontend Fixes

- Fix the ESLint failure in `web/src/app/page.tsx`.
  - Current issue: `patientReports` is typed as `any[]`.
  - Expected fix: define a `ClinicalReport` type or Zod schema and use `useState<ClinicalReport[]>([])`.

- Remove production `console.log` calls from API routes.
  - Example: `web/src/app/api/evaluate/route.ts`.
  - Expected fix: use structured logging or remove debug logging.

- Make UI claims match backend reality.
  - Current issue: some labels imply live orchestration or real clinical surveillance where the backend is still deterministic/mock-heavy.
  - Expected fix: keep UI language accurate until live integrations exist.

- Improve the reasoning-trace UI.
  - Future target from `FUTURE_ARCHITECTURE.md`: add a Review Flow tab showing the internal dialogue between Reasoning and Critic agents.

- Complete the interactive adherence lab.
  - Future target: finish patient simulator behavior and make dose misses/side-effect alerts testable in real time.

## Backend Quality Fixes

- Get Ruff passing.
  - Current result: `uv run ruff check . --statistics` reports 226 errors.
  - Main categories: line length, unsorted imports, unused imports, unused variables, undefined names, print statements, and exception chaining.

- Clean up unfinished or weak tests.
  - Example: `test_therapy_graph_logic.py` contains unused variables and a test body that ends with `pass`.
  - Expected fix: replace placeholder tests with deterministic assertions or remove incomplete scaffolding.

- Review exception chaining.
  - Current Ruff issue: `B904 raise-without-from-inside-except`.
  - Expected fix: use `raise ... from exc` where errors are translated.

- Replace ad hoc print/debug scripts with logger-based utilities.
  - Example: `agent-server/sync_db.py` uses `print`.

## Documentation Fixes

- Fix markdown encoding issues.
  - Current issue: several files show mojibake such as broken emoji, arrows, and box-drawing characters.
  - Affected examples: `README.md`, `ARCHITECTURE.md`, `AGENT_ARCHITECTURE.md`, `AGENT_LAYER_INTEGRATION.md`, and `supabase/seed.sql`.

- Restore or update missing architecture assets.
  - Current issue: `README.md` references `v4_dual_pipeline_architecture.svg`, but that file is deleted in the working tree.
  - Expected fix: restore the SVG, replace the link, or remove the image reference.

- Update docs to distinguish implemented features from roadmap items.
  - Current issue: some docs describe Google Healthcare APIs, MedLM, real-world bioinformatics, HIPAA deployment, and SMART-on-FHIR as future work but the project can read as if some are already complete.
  - Expected fix: add "Current State" and "Future State" labels consistently.

- Replace placeholder contact and pitch-deck fields.
  - Example: `GenomicLens_Pitch_Deck.md` still has `[Website / Contact Info]`.

## Future Architecture Priorities

- MedLM / medically tuned Gemini migration.
  - Swap model calls in Reasoning, Critic, and Reporter agents to Vertex AI when moving toward clinical deployment.

- Google Healthcare API integration.
  - Replace or augment the custom FHIR parser with managed FHIR APIs.
  - Add Healthcare NLP for structured extraction from clinical notes.

- Local PHI de-identification.
  - Add a local PII/PHI scrubber before data is sent to external inference providers.

- SMART-on-FHIR write-back.
  - Add OAuth2 handshakes and EHR write-back endpoints for Epic/Cerner-style integration.

- Formal SaMD governance.
  - Establish hazard analysis, ISO 14971 risk management, validation plans, and human-gate risk controls.

- Guideline version control.
  - Track CPIC/FDA guideline versions, timestamps, retired guidance, and conflicting authority resolution.

- Outcome tracking.
  - Measure whether recommendations improve patient outcomes over time.
  - This is necessary for serious clinical validation and future regulatory work.

## Verification Status From Review

- Backend tests: `uv run pytest` passed with 31 tests.
- Frontend tests: `npm run test` passed with 7 tests, but emitted report-fetch warning noise.
- Frontend build: `npm run build` passed.
- Backend lint: `uv run ruff check .` failed.
- Frontend lint: `npm run lint` failed due to `any[]` in `web/src/app/page.tsx`.
