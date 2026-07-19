# mud-tool (MUD design half) — FastAPI sidecar on :8042
# Build context: ./mud-tool
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Package (src layout under python-sidecar), plus the design-knowledge data,
# and the shared JSON-UML schema.
COPY python-sidecar/ ./python-sidecar/
COPY data/ ./data/
COPY common/ ./common/

RUN pip install --no-cache-dir -e ./python-sidecar

# Skills/guidelines live at the repo-level data/ dir (not python-sidecar/data),
# so point the loaders at them explicitly (fixes the stale absolute paths that
# were in the old .env).
ENV MUD_HOST=0.0.0.0 \
    MUD_PORT=8042 \
    MUD_SKILLS_DIR=/app/data/skills \
    MUD_GUIDELINES_DIR=/app/data/guidelines

EXPOSE 8042

CMD ["mudtool-server"]
