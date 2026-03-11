import requests
from backend.config import settings


BACKUP_ENDPOINT = "/api/v2/monitor/system/config/backup"
LOGIN_ENDPOINT = "/logincheck"
LOGOUT_ENDPOINT = "/logout"


def fetch_config(fortigate_ip: str, api_token: str) -> bytes:
    """Fetch config using API token authentication."""
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


def fetch_config_with_credentials(fortigate_ip: str, username: str, password: str) -> bytes:
    """Fetch config using session-based username/password authentication."""
    base_url = f"https://{fortigate_ip}"
    session = requests.Session()
    session.verify = settings.fortigate_verify_ssl

    # Step 1: Login via /logincheck
    login_response = session.post(
        f"{base_url}{LOGIN_ENDPOINT}",
        data={"username": username, "secretkey": password, "ajax": "1"},
        timeout=settings.fortigate_timeout_seconds,
    )

    # FortiOS returns 200 even on failed login. With ajax=1, success is "1".
    response_text = login_response.text.strip()
    if not response_text.startswith("1"):
        raise ConnectionError(f"Login failed for {fortigate_ip} with user '{username}'. Response: {response_text[:40]}")

    # Step 2: Grab the CSRF token from cookies
    cookies = session.cookies.get_dict()
    csrf_token = None
    for name, value in cookies.items():
        if "ccsrftoken" in name.lower():
            csrf_token = value.strip('"')
            break

    headers = {}
    if csrf_token:
        headers["X-CSRFTOKEN"] = csrf_token

    # Step 3: Download the backup
    params = {"scope": "global", "destination": "file"}
    response = session.get(
        f"{base_url}{BACKUP_ENDPOINT}",
        params=params,
        headers=headers,
        timeout=settings.fortigate_timeout_seconds,
    )
    response.raise_for_status()
    content = response.content

    # Step 4: Logout cleanly
    try:
        session.post(f"{base_url}{LOGOUT_ENDPOINT}", data={"ajax": "1"}, headers=headers, timeout=5)
    except Exception:
        pass

    return content


def restore_config(fortigate_ip: str, api_token: str, content: bytes) -> None:
    """Restore config using API token authentication."""
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


def restore_config_with_credentials(fortigate_ip: str, username: str, password: str, content: bytes) -> None:
    """Restore config using session-based username/password authentication."""
    base_url = f"https://{fortigate_ip}"
    session = requests.Session()
    session.verify = settings.fortigate_verify_ssl

    # Login
    login_response = session.post(
        f"{base_url}{LOGIN_ENDPOINT}",
        data={"username": username, "secretkey": password, "ajax": "1"},
        timeout=settings.fortigate_timeout_seconds,
    )

    response_text = login_response.text.strip()
    if not response_text.startswith("1"):
        raise ConnectionError(f"Login failed for {fortigate_ip} with user '{username}'. Response: {response_text[:40]}")

    cookies = session.cookies.get_dict()
    csrf_token = None
    for name, value in cookies.items():
        if "ccsrftoken" in name.lower():
            csrf_token = value.strip('"')
            break

    headers = {}
    if csrf_token:
        headers["X-CSRFTOKEN"] = csrf_token

    files = {"file": ("config.conf", content)}
    params = {"scope": "global"}
    response = session.post(
        f"{base_url}{settings.fortigate_restore_endpoint}",
        headers=headers,
        params=params,
        files=files,
        timeout=settings.fortigate_timeout_seconds,
    )
    response.raise_for_status()

    try:
        session.post(f"{base_url}{LOGOUT_ENDPOINT}", data={"ajax": "1"}, headers=headers, timeout=5)
    except Exception:
        pass
