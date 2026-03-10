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

## Plug-and-play (Docker)

1. Install Docker Desktop (one time).
2. Double-click `start-docker.bat`.

It will ask for a username and password once and then open the dashboard.

**URLs**
- Dashboard: `http://localhost:8080`
- API: `http://localhost:8000`

**What the start script does**
- Creates `.env` if missing
- Fills defaults for required settings
- Generates a secure `TOKEN_ENCRYPTION_KEY`
- Prompts for dashboard username/password
- Starts containers
- Opens the dashboard

## Plug-and-play (No Docker, local)

If you prefer no Docker, you can run locally with SQLite:

```
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Then open `frontend/dashboard/index.html` in your browser and point it to the API.

## Troubleshooting

- If it says Docker is not running, start Docker Desktop and retry.
- If the dashboard stays blank, wait 10-20 seconds and refresh.

## Authentication and Users

An admin user is created on first start using:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

Passwords are stored as bcrypt hashes. You can add more users via the API:

```
POST /users
```

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
