import requests
from backend.config import settings


BACKUP_ENDPOINT = "/api/v2/monitor/system/config/backup"


def fetch_config(fortigate_ip: str, api_token: str) -> bytes:
    url = f"https://{fortigate_ip}{BACKUP_ENDPOINT}"
    headers = {
        "Authorization": f"Bearer {api_token}",
    }
    params = {"scope": "global"}
    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=settings.fortigate_timeout_seconds,
        verify=settings.fortigate_verify_ssl,
    )
    response.raise_for_status()
    return response.content


def restore_config(fortigate_ip: str, api_token: str, content: bytes) -> None:
    url = f"https://{fortigate_ip}{settings.fortigate_restore_endpoint}"
    headers = {
        "Authorization": f"Bearer {api_token}",
    }
    files = {"file": ("config.conf", content)}
    params = {"scope": "global"}
    response = requests.post(
        url,
        headers=headers,
        params=params,
        files=files,
        timeout=settings.fortigate_timeout_seconds,
        verify=settings.fortigate_verify_ssl,
    )
    response.raise_for_status()
