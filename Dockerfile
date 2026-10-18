FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 HOST=0.0.0.0
WORKDIR /app

COPY pyproject.toml README.md requirements.txt /app/
COPY src /app/src
COPY api /app/api
COPY config /app/config
COPY index.html /app/index.html
COPY buyer_state.js /app/buyer_state.js
COPY render_server.py wsgi.py gunicorn.conf.py /app/

RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir -r requirements.txt

EXPOSE 10000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]
