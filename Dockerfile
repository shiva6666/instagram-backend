FROM python:3.15-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install dependencies first (layer caching: only rebuilds when uv.lock / pyproject.toml change)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code and install project
COPY app ./app
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

