# FortiGate Backup Manager

Centralized system to automate FortiGate configuration backups with history, alerting, and a simple NOC dashboard.

## Features

- Daily automatic backups at 18:00
- Per-center storage with retention (last 3 backups)
- PostgreSQL metadata
- FastAPI backend
- Scheduler service (APScheduler)
- Restore stub endpoint
- Diff viewer for backups
- Email or Slack alerts
- Docker deployment

## Project layout

```
fortigate-backup-manager
  backend
    api.py
    backup_engine.py
    scheduler.py
    config.py
  database
    db.py
    models.py
  storage
    file_manager.py
  alerts
    notifier.py
  frontend
    dashboard
      index.html
      app.js
      styles.css
  docker
    docker-compose.yml
    Dockerfile.api
    Dockerfile.frontend
```

## Quick start (Docker)

1. Copy `.env.example` to `.env` and set `TOKEN_ENCRYPTION_KEY`.
2. From `docker` directory run:

```
docker compose up --build
```

API will be available on `http://localhost:8000` and dashboard at `http://localhost:8080`.

## Authentication

Set `API_USERNAME` and `API_PASSWORD` to require Basic Auth on the API. The dashboard will prompt for these credentials.

## Scheduler

Run the scheduler in its own container or process:

```
python -m backend.scheduler
```

The schedule runs at 18:00 in `SCHEDULER_TIMEZONE`.

## Generating a Fernet key

Run this once and paste into `TOKEN_ENCRYPTION_KEY`:

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Core API routes

- `POST /centers`
- `GET /centers`
- `POST /backups/run`
- `POST /backups/run/{center_id}`
- `GET /backups?center_id=1`
- `GET /diff?center_id=1&from_backup_id=1&to_backup_id=2`
- `POST /restore/{backup_id}`

## Notes

- Restore uses the FortiOS config restore API endpoint defined by `FORTIGATE_RESTORE_ENDPOINT`.
- SSL verification is disabled by default; enable `FORTIGATE_VERIFY_SSL=true` in production.
