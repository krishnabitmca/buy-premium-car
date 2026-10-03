FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md requirements.txt /app/
COPY src /app/src
COPY api /app/api
COPY config /app/config
COPY index.html /app/index.html
COPY render_server.py /app/render_server.py

RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir -r requirements.txt

EXPOSE 10000
CMD ["python", "render_server.py"]
