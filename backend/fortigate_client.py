import requests
from backend.config import settings


BACKUP_ENDPOINT = "/api/v2/monitor/system/config/backup"
LOGIN_ENDPOINT = "/logincheck"
LOGIN_ENDPOINT_V2 = "/api/v2/authentication"
LOGOUT_ENDPOINT = "/logout"


def _try_login(session: requests.Session, base_url: str, username: str, password: str) -> str | None:
    """Attempt login using multiple methods. Returns CSRF token on success, raises on failure.
    
    Strategy:
    1. Try /api/v2/authentication (FortiOS 7.4+ SPA) - JSON-based
    2. Try /logincheck (legacy FortiOS) - form-based
    3. If both fail, raise ConnectionError with clear message
    """
    timeout = settings.fortigate_timeout_seconds

    # ── Method 1: FortiOS 7.4+ JSON API login ──
    try:
        r1 = session.post(
            f"{base_url}{LOGIN_ENDPOINT_V2}",
            json={"username": username, "secretkey": password},
            timeout=timeout,
        )
        if r1.status_code == 200:
            body = r1.json() if r1.headers.get("content-type", "").startswith("application/json") else {}
            status_msg = body.get("status_message", "")
            
            # Check cookies for session proof
            cookies = session.cookies.get_dict()
            csrf_token = None
            for name, value in cookies.items():
                if "ccsrf" in name.lower():
                    csrf_token = value.strip('"') if value else None
            
            if status_msg == "LOGIN_SUCCESS" or body.get("status") == 0:
                return csrf_token
            
            # Login explicitly failed
            if "LOGIN_FAILED" in status_msg or body.get("status") == -1:
                raise ConnectionError(
                    f"Credenciales inválidas para {base_url}. "
                    f"El usuario '{username}' o la contraseña son incorrectos en este FortiGate."
                )
    except ConnectionError:
        raise
    except Exception:
        pass  # Method 1 not available, fall through to Method 2

    # ── Method 2: Legacy /logincheck (FortiOS 6.x / 7.0-7.2) ──
    try:
        login_headers = {
            "Origin": base_url,
            "Referer": f"{base_url}/login",
        }
        r2 = session.post(
            f"{base_url}{LOGIN_ENDPOINT}",
            data={"username": username, "secretkey": password, "ajax": "1"},
            headers=login_headers,
            timeout=timeout,
        )
        response_text = r2.text.strip()

        cookies = session.cookies.get_dict()
        csrf_token = None
        has_auth_cookie = False

        for name, value in cookies.items():
            if "ccsrftoken" in name.lower() or "ccsrf" in name.lower():
                if value:
                    csrf_token = value.strip('"')
                    has_auth_cookie = True
            elif name.startswith("APSCOOKIE_"):
                has_auth_cookie = True

        if response_text.startswith("1") or has_auth_cookie:
            return csrf_token

        # Explicit failure codes
        if response_text == "0":
            raise ConnectionError(
                f"Credenciales inválidas para {base_url}. "
                f"El usuario '{username}' o la contraseña son incorrectos en este FortiGate."
            )
    except ConnectionError:
        raise
    except Exception:
        pass

    # ── Both methods failed ──
    raise ConnectionError(
        f"No se pudo iniciar sesión en {base_url} con el usuario '{username}'. "
        f"Verifique que las credenciales sean correctas y que el acceso API esté habilitado en el FortiGate."
    )


def _download_backup(session: requests.Session, base_url: str, csrf_token: str | None) -> bytes:
    """Download backup trying multiple scope configurations."""
    headers = {}
    if csrf_token:
        headers["X-CSRFTOKEN"] = csrf_token

    scope_attempts = [
        {"scope": "global", "destination": "file"},
        {"scope": "vdom", "vdom": "root", "destination": "file"},
        {"destination": "file"},
    ]

    last_response = None
    last_error = None
    for params in scope_attempts:
        try:
            response = session.get(
                f"{base_url}{BACKUP_ENDPOINT}",
                params=params,
                headers=headers,
                timeout=settings.fortigate_timeout_seconds,
            )
            last_response = response
            if response.ok and len(response.content) > 50:
                return response.content
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    # All scope attempts failed
    if last_response is not None:
        status = last_response.status_code
        if status in (401, 403):
            raise ConnectionError(
                f"Permiso denegado ({status}). El usuario no tiene privilegios suficientes "
                f"para descargar backups. Se necesita perfil 'Super_Admin' o permisos de lectura "
                f"sobre 'System Configuration' en el FortiGate."
            )
        raise ConnectionError(f"Error al descargar backup: HTTP {status}")
    
    # No response at all (all requests threw exceptions)
    raise ConnectionError(
        f"No se pudo conectar al FortiGate en {base_url} para descargar el backup. "
        f"{'Detalle: ' + last_error if last_error else 'Verifique la conectividad de red.'}"
    )


def fetch_config(fortigate_ip: str, api_token: str) -> bytes:
    """Fetch config using API token authentication."""
    url = f"https://{fortigate_ip}{BACKUP_ENDPOINT}"
    headers = {
        "Authorization": f"Bearer {api_token}",
    }

    scope_attempts = [
        {"scope": "global"},
        {"scope": "vdom", "vdom": "root"},
        {},
    ]

    last_response = None
    last_error = None
    for params in scope_attempts:
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=settings.fortigate_timeout_seconds,
                verify=settings.fortigate_verify_ssl,
            )
            last_response = response
            if response.ok and len(response.content) > 50:
                return response.content
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    if last_response is not None:
        status = last_response.status_code
        if status in (401, 403):
            raise ConnectionError(
                f"Permiso denegado ({status}). El token API no tiene privilegios suficientes "
                f"para descargar backups o el scope VDOM está restringido."
            )
        raise ConnectionError(f"Error al descargar backup con token: HTTP {status}")
    raise ConnectionError(
        f"No se pudo conectar al FortiGate {fortigate_ip} para descargar el backup. "
        f"{'Detalle: ' + last_error if last_error else 'Verifique la conectividad.'}"
    )


def fetch_config_with_credentials(fortigate_ip: str, username: str, password: str) -> bytes:
    """Fetch config using session-based username/password authentication."""
    base_url = f"https://{fortigate_ip}"
    session = requests.Session()
    session.verify = settings.fortigate_verify_ssl

    # Step 1: Login (tries v2 JSON API first, then legacy /logincheck)
    csrf_token = _try_login(session, base_url, username, password)

    # Step 2: Download backup (tries global, then vdom, then no-scope)
    content = _download_backup(session, base_url, csrf_token)

    # Step 3: Logout cleanly
    try:
        headers = {"X-CSRFTOKEN": csrf_token} if csrf_token else {}
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

    scope_attempts = [
        {"scope": "global"},
        {"scope": "vdom", "vdom": "root"},
        {},
    ]

    last_response = None
    last_error = None
    for params in scope_attempts:
        try:
            files = {"file": ("config.conf", content)}
            response = requests.post(
                url,
                headers=headers,
                params=params,
                files=files,
                timeout=settings.fortigate_timeout_seconds,
                verify=settings.fortigate_verify_ssl,
            )
            last_response = response
            if response.ok:
                return
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    if last_response is not None:
        status = last_response.status_code
        if status in (401, 403):
            raise ConnectionError(
                f"Permiso denegado ({status}). El token API no tiene privilegios suficientes "
                f"para restaurar configuraciones."
            )
        raise ConnectionError(f"Error al restaurar backup con token: HTTP {status}")
    raise ConnectionError(
        f"No se pudo conectar al FortiGate {fortigate_ip} para restaurar. "
        f"{'Detalle: ' + last_error if last_error else 'Verifique la conectividad.'}"
    )


def restore_config_with_credentials(fortigate_ip: str, username: str, password: str, content: bytes) -> None:
    """Restore config using session-based username/password authentication."""
    base_url = f"https://{fortigate_ip}"
    session = requests.Session()
    session.verify = settings.fortigate_verify_ssl

    # Step 1: Login
    csrf_token = _try_login(session, base_url, username, password)

    # Step 2: Restore
    headers = {}
    if csrf_token:
        headers["X-CSRFTOKEN"] = csrf_token

    scope_attempts = [
        {"scope": "global"},
        {"scope": "vdom", "vdom": "root"},
        {},
    ]

    last_response = None
    last_error = None
    for params in scope_attempts:
        try:
            files = {"file": ("config.conf", content)}
            response = session.post(
                f"{base_url}{settings.fortigate_restore_endpoint}",
                headers=headers,
                params=params,
                files=files,
                timeout=settings.fortigate_timeout_seconds,
            )
            last_response = response
            if response.ok:
                break
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    if last_response and not last_response.ok:
        status = last_response.status_code
        if status in (401, 403):
            raise ConnectionError(
                f"Permiso denegado ({status}). El usuario '{username}' no tiene privilegios "
                f"suficientes para restaurar configuraciones."
            )
        raise ConnectionError(f"Error al restaurar backup: HTTP {status}")
    elif last_response is None:
        raise ConnectionError(
            f"No se pudo conectar al FortiGate {base_url} para restaurar. "
            f"{'Detalle: ' + last_error if last_error else 'Verifique la conectividad.'}"
        )

    # Step 3: Logout cleanly
    try:
        session.post(f"{base_url}{LOGOUT_ENDPOINT}", data={"ajax": "1"}, headers=headers, timeout=5)
    except Exception:
        pass
