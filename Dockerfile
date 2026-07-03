FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex

RUN git config --global --add safe.directory /app \
    && git config --global user.name "startups-radar" \
    && git config --global user.email "radar@localhost"

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY prompts ./prompts
COPY scrapers ./scrapers

CMD ["python", "-m", "radar.main"]
