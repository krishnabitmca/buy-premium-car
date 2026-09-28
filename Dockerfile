FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY config /app/config

RUN pip install --no-cache-dir -e . \
    && python -m playwright install --with-deps chromium \
    && crawl4ai-setup

CMD ["python", "-m", "src.main"]