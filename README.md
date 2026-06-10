# DDNS Manager

A self-hosted Dynamic DNS manager with a web UI. Supports **GoDaddy** and **Cloudflare** A-record updates, scheduled IP checks, and optional Mailjet email alerts.

## Features

- Automatic public IP detection with multiple fallback sources
- Scheduled background updates (configurable interval)
- GoDaddy and Cloudflare provider support
- Email alerts on IP change, update failure, or upcoming API key expiry
- Web UI served from `/` (no extra frontend build step)
- SQLite database persisted in a Docker named volume

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:////data/ddns.db` | SQLAlchemy database URL. Change only if using a different path or engine. |
| `HOST` | `0.0.0.0` | Interface uvicorn binds to. |
| `PORT` | `8080` | Port uvicorn listens on. |

Email alerts are configured through the Settings page in the UI (stored in the database), not via env vars. Alternatively you can pre-seed the `settings` table directly.

---

## Running Locally with Docker Compose

```bash
# Build and start
docker compose up --build

# Run in background
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down
```

The UI is available at **http://localhost:8080** once the container is running.

To persist data across `docker compose down` the named volume `ddns-data` is used automatically. Your database survives container restarts and rebuilds.

---

## Deploying as a Portainer Stack

1. **Push this repo to GitHub** (or any Git host accessible from your server).

2. In Portainer, go to **Stacks → Add stack**.

3. Choose **Repository** as the build method and enter:
   - Repository URL: your GitHub repo URL
   - Reference: `main` (or your branch)
   - Compose path: `docker-compose.yml`

4. Under **Environment variables**, override any defaults you need (e.g. a custom `PORT`).

5. Click **Deploy the stack**.

Portainer will clone the repo, build the image, create the named volume, and start the container. Future deployments: update the stack via **Pull and redeploy** in Portainer after pushing changes to GitHub.

---

## Project Structure

```
ddns-app/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routes, lifespan
│   ├── database.py      # SQLAlchemy models + session
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── scheduler.py     # APScheduler background job
│   ├── email_service.py # Mailjet alert helpers
│   ├── ip_service.py    # Public IP detection
│   └── providers/
│       ├── base.py      # Abstract DNS provider
│       ├── cloudflare.py
│       └── godaddy.py
├── static/
│   └── index.html       # Single-page web UI
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## API Reference

Interactive docs are available at **http://localhost:8080/docs** (Swagger UI) when the container is running.

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Current IP, scheduler state, next run time |
| `POST` | `/api/update-now` | Trigger an immediate update cycle |
| `GET/POST` | `/api/records` | List / create DNS records |
| `GET/PUT/DELETE` | `/api/records/{id}` | Get / update / delete a record |
| `GET/PUT` | `/api/settings` | Read / update global settings |
| `GET` | `/api/logs` | Update history (filterable by record) |
| `POST` | `/api/test-email` | Send a test alert email |
| `GET` | `/api/detect-ip` | One-shot public IP detection |
