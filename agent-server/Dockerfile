# Production-grade multi-stage Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY --from=builder /app/.venv .venv
ARG CACHEBUST=1
COPY . .
USER appuser
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/api/health || exit 1

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}
