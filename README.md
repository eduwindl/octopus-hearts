# FortiGate Backup Manager (Desktop)

Plug-and-play desktop app for managing FortiGate configuration backups. No Docker, no browser, no Python required for end users.

## How to Run (End Users)

1. Download the latest release.
2. Run `fgbm.exe`.
3. Log in with your admin credentials.

The app will create a local database and start storing backups.

## First Run

On first launch, you will be asked to create an admin user. Passwords are stored securely using bcrypt.

## Features

- Add FortiGate centers
- Run backups on demand
- Daily scheduled backups at 18:00
- Restore a backup to a FortiGate
- User management (admin)

## Developer Build (EXE)

To build the portable EXE:

```
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

If Inno Setup is installed, it will also create a wizard installer `FGBM-Setup.exe`.

## Notes

- Backups are stored in `./backups`
- Database is stored in `./data/fgbm.db`
