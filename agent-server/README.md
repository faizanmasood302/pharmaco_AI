# Agent Server

FastAPI backend for the pharmacogenomic agent harness.

## Run

```bash
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Test

```bash
uv run pytest tests/ -q
```

## Supabase

Run [../supabase/seed.sql](../supabase/seed.sql) in your Supabase SQL editor, then set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env`.
