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
    # Fallback to VDOM scope if global is denied
    if response.status_code in (403, 401):
        params_fallback = {"scope": "vdom", "vdom": "root"}
        fallback_res = requests.get(url, headers=headers, params=params_fallback, timeout=settings.fortigate_timeout_seconds, verify=settings.fortigate_verify_ssl)
        if fallback_res.ok:
            response = fallback_res

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if response.status_code in (401, 403):
            raise ConnectionError(f"Permission denied ({response.status_code}). Token lacks 'Super_Admin' privileges or correct VDOM scope.") from e
        raise ConnectionError(f"API Error {response.status_code}: {e}") from e

    return response.content


def fetch_config_with_credentials(fortigate_ip: str, username: str, password: str) -> bytes:
    """Fetch config using session-based username/password authentication."""
    base_url = f"https://{fortigate_ip}"
    session = requests.Session()
    session.verify = settings.fortigate_verify_ssl
    # Step 1: Login via /logincheck
    login_headers = {
        "Origin": base_url,
        "Referer": f"{base_url}/login",
    }
    login_response = session.post(
        f"{base_url}{LOGIN_ENDPOINT}",
        data={"username": username, "secretkey": password, "ajax": "1"},
        headers=login_headers,
        timeout=settings.fortigate_timeout_seconds,
    )

    response_text = login_response.text.strip()

    # Step 2: Grab the CSRF token from cookies and verify authentication
    cookies = session.cookies.get_dict()
    csrf_token = None
    has_auth_cookie = False
    
    for name, value in cookies.items():
        if "ccsrftoken" in name.lower():
            csrf_token = value.strip('"')
            has_auth_cookie = True
        elif name.startswith("APSCOOKIE_"):
            has_auth_cookie = True

    # FortiOS returns 200 even on failed login. With ajax=1, explicit success is "1".
    # However, some configurations (or disclaimers) return HTML instead. We check if an auth cookie was set.
    if not response_text.startswith("1") and not has_auth_cookie:
        if "<html" in response_text.lower() or "<!doctype" in response_text.lower():
            raise ConnectionError(f"Login failed for {fortigate_ip} with user '{username}'. (Invalid credentials or FortiOS blocked the login API request).")
        else:
            raise ConnectionError(f"Login failed or intercepted for {fortigate_ip} with user '{username}'. Response snippet: {response_text[:100]}")

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

    # Fallbacks for restricted admins (e.g. prof_admin) that get 403 on scope=global
    if response.status_code in (403, 401):
        for fallback_params in [
            {"scope": "vdom", "vdom": "root", "destination": "file"},
            {"destination": "file"},
        ]:
            fallback_response = session.get(
                f"{base_url}{BACKUP_ENDPOINT}",
                params=fallback_params,
                headers=headers,
                timeout=settings.fortigate_timeout_seconds,
            )
            if fallback_response.ok:
                response = fallback_response
                break

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if response.status_code in (401, 403):
            raise ConnectionError(f"Permission denied ({response.status_code}). User '{username}' lacks 'Super_Admin' privileges or REST API access is blocked.") from e
        raise ConnectionError(f"API Error {response.status_code}: {e}") from e

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

    # Fallback to VDOM scope or no scope if global is denied
    if response.status_code in (403, 401):
        for params_fallback in [
            {"scope": "vdom", "vdom": "root"},
            {},
        ]:
            files_fallback = {"file": ("config.conf", content)}
            fallback_res = requests.post(
                url, headers=headers, params=params_fallback, files=files_fallback, timeout=settings.fortigate_timeout_seconds, verify=settings.fortigate_verify_ssl
            )
            if fallback_res.ok:
                response = fallback_res
                break

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if response.status_code in (401, 403):
            raise ConnectionError(f"Permission denied ({response.status_code}). Token lacks 'Super_Admin' privileges or VDOM restricts upload.") from e
        raise ConnectionError(f"API Error {response.status_code}: {e}") from e


def restore_config_with_credentials(fortigate_ip: str, username: str, password: str, content: bytes) -> None:
    """Restore config using session-based username/password authentication."""
    base_url = f"https://{fortigate_ip}"
    session = requests.Session()
    session.verify = settings.fortigate_verify_ssl
    # Login
    login_headers = {
        "Origin": base_url,
        "Referer": f"{base_url}/login",
    }
    login_response = session.post(
        f"{base_url}{LOGIN_ENDPOINT}",
        data={"username": username, "secretkey": password, "ajax": "1"},
        headers=login_headers,
        timeout=settings.fortigate_timeout_seconds,
    )

    response_text = login_response.text.strip()

    cookies = session.cookies.get_dict()
    csrf_token = None
    has_auth_cookie = False
    
    for name, value in cookies.items():
        if "ccsrftoken" in name.lower():
            csrf_token = value.strip('"')
            has_auth_cookie = True
        elif name.startswith("APSCOOKIE_"):
            has_auth_cookie = True

    if not response_text.startswith("1") and not has_auth_cookie:
        if "<html" in response_text.lower() or "<!doctype" in response_text.lower():
            raise ConnectionError(f"Login failed for {fortigate_ip} with user '{username}'. (Invalid credentials or FortiOS blocked the login API request).")
        else:
            raise ConnectionError(f"Login failed or intercepted for {fortigate_ip} with user '{username}'. Response snippet: {response_text[:100]}")

    headers = {
        "Origin": base_url,
        "Referer": f"{base_url}/login",
    }
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

    if response.status_code in (403, 401):
        for fallback_params in [
            {"scope": "vdom", "vdom": "root"},
            {},
        ]:
            files_fallback = {"file": ("config.conf", content)}
            fallback_response = session.post(
                f"{base_url}{settings.fortigate_restore_endpoint}",
                headers=headers,
                params=fallback_params,
                files=files_fallback,
                timeout=settings.fortigate_timeout_seconds,
            )
            if fallback_response.ok:
                response = fallback_response
                break

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if response.status_code in (401, 403):
            raise ConnectionError(f"Permission denied ({response.status_code}). User '{username}' lacks 'Super_Admin' privileges or REST API restrict uploads.") from e
        raise ConnectionError(f"API Error {response.status_code}: {e}") from e

    try:
        session.post(f"{base_url}{LOGOUT_ENDPOINT}", data={"ajax": "1"}, headers=headers, timeout=5)
    except Exception:
        pass
