# Deployment Guide

## Prerequisites

- Supabase project with [supabase/seed.sql](supabase/seed.sql) applied
- Groq API key (optional, for LLM narrative)

## Backend (Railway / Fly / Docker)

1. Deploy `agent-server/` using the included [Dockerfile](agent-server/Dockerfile).
2. Set environment variables:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `GROQ_API_KEY` (optional)
3. Note the public URL (e.g. `https://your-api.railway.app`).

## Frontend (Vercel)

1. Import the `web/` directory in Vercel.
2. Set `AGENT_SERVER_URL` to your deployed API URL.
3. Deploy.

## Local development

```bash
# Terminal 1
cd agent-server && uv run uvicorn main:app --reload

# Terminal 2
cd web && npm run dev
```

## Demo video checklist

1. Import FHIR sample (Alex Rivera, ultra-rapid)
2. Evaluate Codeine → CRITICAL block
3. Show evaluation history (with Supabase)
4. Approve Pregabalin for Sarah Patel → start adherence → submit check-in with side effect

## YC application

Update [YC_APPLICATION.md](YC_APPLICATION.md) traction with your live URL when deployed.
