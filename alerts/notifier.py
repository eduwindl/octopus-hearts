import smtplib
from email.message import EmailMessage
import requests
from backend.config import settings


def send_email(subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_to or not settings.smtp_from:
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.smtp_to
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_user and settings.smtp_pass:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_pass)
        server.send_message(msg)


def send_slack(message: str) -> None:
    if not settings.slack_webhook_url:
        return
    try:
        requests.post(settings.slack_webhook_url, json={"text": message}, timeout=10)
    except requests.RequestException:
        pass


def notify_failure(center_name: str, reason: str) -> None:
    subject = f"Backup failed: {center_name}"
    body = f"Center: {center_name}\nReason: {reason}"
    send_email(subject, body)
    send_slack(body)
