FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api ./apps/api

RUN uv sync --frozen --package evalforge-api --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "evalforge_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
