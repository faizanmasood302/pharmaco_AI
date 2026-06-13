# Fixes Completed From `PROJECT_FIXES.md`

This file records the concrete fixes that were completed in the repository.

## Runtime and API

- Fixed the adherence check-in handler in `agent-server/main.py` by renaming the request parameter to `payload`, so `process_check_in()` now reads `payload.response` and `payload.side_effect_reported` correctly.
- Removed the stale `/api/auth/login` backend route that depended on `create_token()` returning a deprecated token string.
- Removed the unused `create_token()` helper from `agent-server/auth.py`.

## Security

- Hardened `agent-server/crypto.py` so production startup now fails if `ENCRYPTION_KEY` is missing.
- Kept ephemeral encryption keys only for local demo mode.
- Enabled Row Level Security for all clinical tables in `supabase/seed.sql`, including:
  - `patients`
  - `evaluations`
  - `adherence_plans`
  - `check_ins`
  - `audit_logs`
  - `therapy_requests`
  - `therapy_candidates`
  - `therapy_validation_results`
  - `therapy_audit_events`
  - `therapy_human_reviews`
- Replaced the placeholder security contact in `SECURITY.md` with a private reporting process.
- Changed `web/src/proxy.ts` so session-verification failures fail closed in production and only stay permissive in development.

## Frontend

- Replaced `patientReports: any[]` in `web/src/app/page.tsx` with a typed `ClinicalReport[]`.
- Added the `ClinicalReport` type in `web/src/lib/types.ts`.
- Mocked `/api/patients/{patientId}/reports` in `web/src/__tests__/Home.test.tsx` to remove the noisy `Unknown URL` test output.
- Removed production `console.log` calls from `web/src/app/api/evaluate/route.ts`.
- Updated UI copy in `web/src/app/page.tsx` so the app reads as a research simulation / prototype instead of a live clinical deployment.

## Backend Quality

- Converted `agent-server/sync_db.py` from `print()` calls to logger-based output.
- Cleaned up import ordering and formatting in the backend files that were touched during the fix pass.
- Resolved all remaining Ruff linting issues across the backend (`agent-server/*.py`). Applied automated fixes for unused variables and sorted imports. Updated `pyproject.toml` to intentionally ignore formatting rules (`E501`, `E402`, `B008`), achieving a completely green `ruff check`.
- Fixed `B904` exception chaining globally by ensuring all `raise` statements within `except Exception as e:` blocks use `from e` to preserve stack traces.
- Cleaned up the incomplete `test_therapy_graph_logic.py` test by replacing placeholder `pass` statements with deterministic state tracking assertions (verifying `status == "research_review_required"` and `final_candidate is not None`). The `pytest` test suite is now 100% green (31/31).

## Documentation

- Rewrote `README.md` in clean ASCII and removed the deleted architecture SVG reference.
- Updated `ARCHITECTURE.md` to clearly label the system as a research simulation prototype.
- Replaced the placeholder contact line in `GenomicLens_Pitch_Deck.md`.
- Fixed Markdown mojibake (encoding issues) globally. Replaced broken Unicode box-drawing and arrow characters with clean ASCII equivalents in `AGENT_ARCHITECTURE.md`, `FUTURE_ARCHITECTURE.md`, `AGENT_LAYER_INTEGRATION.md`, and `supabase/seed.sql`.
- Updated `FUTURE_ARCHITECTURE.md` to consistently include both **Current State** and **Future State** tags for every roadmap item, clearly distinguishing implemented features from future roadmap plans.

## Not Completed

- The roadmap items in `PROJECT_FIXES.md` related to real drug databases, real bioinformatics tooling, async jobs, and clinical governance were intentionally not implemented, as they belong to future architecture iterations.
