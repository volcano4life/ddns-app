FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data directory for SQLite
RUN mkdir -p /data

ENV DATABASE_URL=sqlite:////data/ddns.db
ENV HOST=0.0.0.0
ENV PORT=8080

EXPOSE 8080

CMD uvicorn app.main:app --host "${HOST}" --port "${PORT}"
