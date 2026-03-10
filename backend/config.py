from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FortiGate Backup Manager"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg2://fgbm:fgbm@db:5432/fgbm"

    backups_root: str = "/backups"
    retention_count: int = 3

    fortigate_timeout_seconds: int = 30

    token_encryption_key: str = "CHANGE_ME__32_BYTES_BASE64"
    fortigate_verify_ssl: bool = False
    fortigate_restore_endpoint: str = "/api/v2/monitor/system/config/restore"

    scheduler_timezone: str = "America/Santo_Domingo"

    api_username: str | None = None
    api_password: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_from: str | None = None
    smtp_to: str | None = None

    slack_webhook_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
