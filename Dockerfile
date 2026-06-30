# 60_DEPLOYMENT.md — immutable, stateless container image for the API + SPA.
FROM python:3.12-slim

WORKDIR /app

# Install the package with the REST adapter extra.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[api]"

# Run from the source tree so bundled static assets resolve.
ENV PYTHONPATH=/app/src \
    DM_HOST=0.0.0.0 \
    DM_PORT=8000

EXPOSE 8000

# Liveness/readiness verification (60 §16).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "detective_monkey.interfaces.rest.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
