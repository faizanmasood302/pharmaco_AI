# N-of-1 Implementation Log

This file tracks the implementation steps completed while upgrading the second experimental flow into a professional research simulation.

## Completed Steps

- Created the implementation log to keep the build trace explicit.
- Inspected the current `/api/generate-therapy` route, therapy models, current mock agents, tests, and LangGraph dependency.
- Confirmed the implementation will preserve the existing API route and legacy response fields while adding richer structured outputs.
- Added structured n-of-1 response models for evidence bundles, candidates, validation checks, validation results, candidate history, audit trail, safety notes, and human gate metadata.
- Added a local n-of-1 research simulation policy source under `agent-server/knowledge` so the therapy flow has dedicated RAG grounding.
- Added `agents/therapy_rag.py` for source-backed local retrieval with chunk scoring, evidence quality, known risks, open questions, and source snippets.
- Extended `agents/generative.py` with deterministic simulated mRNA candidate generation that records constraints, rationale, iteration, and evidence references.
- Extended `agents/validation.py` with deterministic research-sequence validation for RNA alphabet, frame, start/stop codons, internal stops, GC content, repeat risk, and immunogenic motif proxies.
- Replaced the manual therapy loop with a LangGraph state machine in `agents/therapy_orchestrator.py` while preserving the existing `orchestrate_therapy_generation` entry point.
- Wired `/api/generate-therapy` to pass the request-level `max_iterations` value into the new graph orchestrator.
- Added n-of-1 persistence helpers in `agent-server/db/supabase.py` with local offline storage for therapy requests, candidate history, validation results, audit events, and human-review metadata.
- Updated `/api/generate-therapy` to persist the full research simulation packet before returning the response.
- Added Supabase table definitions for `therapy_requests`, `therapy_candidates`, `therapy_validation_results`, `therapy_audit_events`, and `therapy_human_reviews`, including indexes, constraints, RLS enablement, and authenticated access policies.
- Added frontend TypeScript types and Zod schemas for the complete therapy-generation response.
- Added a Next.js proxy route at `web/src/app/api/generate-therapy/route.ts` for authenticated calls to the backend therapy endpoint.
- Added an `N-of-1 Research` workspace to the application shell with controls for target disease and max iterations plus result panels for candidate history, validation checks, evidence, and the human gate.
- Extended backend therapy-generation tests to verify that API responses persist the full request packet in the offline storage path.
- Added frontend coverage for the n-of-1 research workspace, including candidate iteration rendering and failed validation-check visibility.
- Refined the Target Selection Agent to use research evidence quality and confidence for deterministic branching.
- Added a conditional graph route to block candidate generation when evidence quality is insufficient.
- Implemented a backend Human Gate decision endpoint (`POST /api/therapy-requests/{id}/decision`) and supporting persistence in Supabase.
- Updated the frontend N-of-1 Research Workspace to include interactive Approve/Reject controls for clinicians.
- Added a comprehensive test suite in `agent-server/tests/test_therapy_graph_logic.py` covering human review persistence and graph failure paths.
- Integrated simulated bioinformatics tools (MFE, Homology, Immunogenicity) into the deterministic validation pipeline (Phase 4).
- Implemented versioned validator outputs with `validator_version` metadata.
- Created a formal N-of-1 Research Benchmark set in `agent-server/tests/test_n_of_1_benchmarks.py` to verify grounded vs. ungrounded research requests.
