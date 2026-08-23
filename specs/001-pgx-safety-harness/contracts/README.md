# Contracts — 001 PGx Safety Harness

`openapi.yaml` is the **design-time** contract for the v1 API: thirteen endpoints, matching
`HARNESS.md` IV.10. At implementation time it stops being the source of truth — FastAPI emits the
authoritative schema from the Pydantic domain types, and this file becomes the thing that schema is
checked against.

## Contract propagation is one-directional

```
src/domain/*.py  (Pydantic, frozen=True, extra="forbid")
   └─► FastAPI OpenAPI schema
          ├─► openapi-typescript  ──►  web/src/lib/api-types.ts
          └─► zod schemas         ──►  web/src/lib/schema.ts
```

Generated artifacts are committed. Drift between the backend contract and the frontend type is a
failing build, not a runtime surprise. Today `web/src/lib/schema.ts` is hand-maintained, which is
why a backend model change currently breaks the frontend at runtime instead of at build; Phase 8
replaces it with generation.

## The rule this contract exists to enforce

**Every endpoint accepts identifiers.** No endpoint accepts a state object, a gate status, an
approval flag, or assessment content from a request body. This is constitution Principle VII.

The generated types are how it gets enforced cheaply: when the type for `POST /v1/reports` accepts
only `{evaluation_id: string}`, a client *cannot* post a state object — it is a compile error, not a
policy someone has to remember. The audited system read `human_gate.status` out of the request body
of `POST /clinical-note`, so a forged approval was simply accepted. The corrected contract makes the
attack unrepresentable rather than merely rejected.

Two endpoints carry most of that weight:

- `POST /v1/reports` — `{evaluation_id}` only. The server loads the record, folds the transition
  history, verifies `APPROVED`, and re-verifies the content hash.
- `POST /v1/evaluations/{id}/transitions` — requires `assessment_sha256`, which gives content
  binding and optimistic concurrency in one move. Approving a stale assessment is rejected rather
  than silently accepted.

## Generation commands (Phase 8)

```bash
# backend → schema
cd agent-server && uv run python -m src.api.export_openapi > ../web/openapi.json

# schema → types and runtime validators
cd web
pnpm exec openapi-typescript ../web/openapi.json -o src/lib/api-types.ts
pnpm exec ts-to-zod                # or the equivalent generator chosen at implementation time
git diff --exit-code src/lib/      # CI `contracts` job: regenerated output must match committed
```

## Verification checklist for the `contracts` CI job

- [ ] The emitted FastAPI schema matches `openapi.yaml` in paths, methods, and request-body shape.
- [ ] No request body anywhere contains `status`, `gate_state`, `approved`, `human_gate`, or an
      embedded assessment object.
- [ ] Every request-body schema sets `additionalProperties: false`.
- [ ] `severity` is nullable everywhere and `outcome` is never typed as a severity.
- [ ] Regenerated TypeScript types and Zod schemas match the committed ones.

---

*Research and education only. Synthetic data only. Not a medical device.*
