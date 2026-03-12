import requests
import paramiko
import time
from backend.config import settings


BACKUP_ENDPOINT = "/api/v2/monitor/system/config/backup"
LOGIN_ENDPOINT = "/logincheck"
LOGIN_ENDPOINT_V2 = "/api/v2/authentication"
LOGOUT_ENDPOINT = "/logout"


def _is_valid_config(content: bytes) -> bool:
    """Check if the content looks like a real FortiGate configuration file."""
    if len(content) < 500:
        return False
    
    text = content.decode("utf-8", errors="ignore")
    markers = ["#config-version", "#FortiGate", "config system global", "config global", "config system interface"]
    return any(marker in text for marker in markers)


def _try_login(session: requests.Session, base_url: str, username: str, password: str) -> str | None:
    """Attempt login using multiple methods. Returns CSRF token on success, raises on failure.
    
    Strategy:
    1. Try /api/v2/authentication (FortiOS 7.4+ SPA) - JSON-based
    2. Try /logincheck (legacy FortiOS) - form-based
    3. If both fail, raise ConnectionError with clear message
    """
    timeout = settings.fortigate_timeout_seconds
    details = []

    # 0. Initial GET to establish session/cookies (Critical for FortiOS 7.0+)
    try:
        session.get(base_url, timeout=timeout)
    except Exception:
        pass
    # ── Method 1: FortiOS 7.4+ JSON API login ──
    try:
        r1 = session.post(
            f"{base_url}{LOGIN_ENDPOINT_V2}",
            json={"username": username, "secretkey": password},
            timeout=timeout,
        )
        details.append(f"V2: HTTP {r1.status_code}")
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
            details.append(f"V2 Body: {str(body)[:100]}")
    except ConnectionError:
        raise
    except Exception as e:
        details.append(f"V2 Error: {str(e)}")
        pass

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
        details.append(f"V1: HTTP {r2.status_code}")

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
            if "Unknown action" in response_text or "error" in response_text.lower():
                details.append(f"V1: Login falso positivo ({response_text[:20]})")
            else:
                return csrf_token

        # Explicit failure codes
        if response_text == "0" or "Unknown action" in response_text:
            header_hints = []
            if "X-FGT-ERROR" in r2.headers:
                header_hints.append(f"FGT-Error: {r2.headers['X-FGT-ERROR']}")
            
            hint_str = f" ({', '.join(header_hints)})" if header_hints else ""
            raise ConnectionError(
                f"Credenciales inválidas o acceso bloqueado por 'Trusted Hosts' en {base_url}. "
                f"Respuesta: '{response_text[:20]}'{hint_str}."
            )
        
        if "<html" in response_text.lower():
            details.append("V1: Recibió HTML (posible Disclaimer o Bloqueo)")
        else:
            details.append(f"V1 Body: {response_text[:50]}")
    except ConnectionError:
        raise
    except Exception as e:
        details.append(f"V1 Error: {str(e)}")
        pass

    # ── Both methods failed ──
    raise ConnectionError(
        f"No se pudo iniciar sesión en {base_url} con el usuario '{username}'.\n"
        f"Detalles técnicos: {', '.join(details)}"
    )


def _download_backup(session: requests.Session, base_url: str, csrf_token: str | None) -> bytes:
    """Download backup trying multiple scope configurations."""
    headers = {}
    if csrf_token:
        headers["X-CSRFTOKEN"] = csrf_token

    # Aggressive list of parameter combinations to try
    scope_attempts = [
        {"scope": "global", "destination": "file"},
        {"scope": "vdom", "vdom": "root", "destination": "file"},
        {"destination": "file"},
        {},  # Completely naked request (no params at all)
        {"scope": "global"},
        {"scope": "vdom", "vdom": "root"},
        {"mkey": "system"},
    ]

    last_response = None
    last_error = ""
    error_424_body = ""
    
    for params in scope_attempts:
        try:
            response = session.get(
                f"{base_url}{BACKUP_ENDPOINT}",
                params=params,
                headers=headers,
                timeout=settings.fortigate_timeout_seconds,
            )
            last_response = response
            if response.ok and _is_valid_config(response.content):
                return response.content
            
            if response.ok and not _is_valid_config(response.content):
                details = response.text[:100].strip()
                last_error = f"Respuesta inválida (no es una config): {details}"
                continue
            
            if response.status_code == 424:
                error_424_body = response.text[:200].strip()
                last_error = f"Error 424 (params={params}): {error_424_body}"
                continue

        except requests.exceptions.Timeout:
            last_error = "Tiempo de espera agotado (Timeout). Verifique si la IP y el PUERTO son correctos."
            continue
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    # All scope attempts failed
    if last_response is not None:
        status = last_response.status_code
        if status in (401, 403):
            raise ConnectionError(
                f"Permiso denegado ({status}). El usuario no tiene privilegios suficientes "
                f"para descargar backups (requiere Super_Admin o permiso de lectura en System Config)."
            )
        if status == 424:
            raise ConnectionError(
                f"Error 424: El FortiGate rechazó TODAS las combinaciones de backup. "
                f"Respuesta del equipo: {error_424_body or 'sin detalle'}. "
                f"El usuario posiblemente no tiene permiso para descargar configuraciones."
            )
        raise ConnectionError(f"Error al descargar backup: HTTP {status}")
    
    # No response at all (all requests threw exceptions)
    err_msg = f"No se pudo conectar al FortiGate en {base_url}. "
    if "10443" in base_url:
        err_msg += "Verifique si el puerto 10443 es correcto para este equipo o pruebe con el 443."
    else:
        err_msg += f"Detalle Técnico: {last_error}"
    
    raise ConnectionError(err_msg)


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
    """Fetch config trying SSH CLI first, then falling back to REST API."""
    errors = []
    
    # ── Attempt 1: SSH CLI (Preferred) ──
    try:
        return _download_backup_cli(fortigate_ip, username, password)
    except Exception as e:
        errors.append(f"CLI/SSH Error: {str(e)}")

    # ── Attempt 2: REST API (Primary Port) ──
    ports_to_try = []
    if ":" in fortigate_ip:
        main_ip, main_port = fortigate_ip.split(":", 1)
        ports_to_try.append(main_port)
        # If 10443 failed, always try 443 as fallback
        if main_port == "10443":
            ports_to_try.append("443")
    else:
        main_ip = fortigate_ip
        ports_to_try = ["443", "10443"]

    for port in ports_to_try:
        try:
            base_url = f"https://{main_ip}:{port}"
            session = requests.Session()
            session.verify = settings.fortigate_verify_ssl
            
            csrf_token = _try_login(session, base_url, username, password)
            content = _download_backup(session, base_url, csrf_token)
            
            # Clean logout
            try:
                headers = {"X-CSRFTOKEN": csrf_token} if csrf_token else {}
                session.post(f"{base_url}{LOGOUT_ENDPOINT}", data={"ajax": "1"}, headers=headers, timeout=5)
            except Exception:
                pass
                
            return content
        except Exception as e:
            # If it's a "Connection Refused" and we have more ports to try, continue
            if "10061" in str(e) or "refused" in str(e).lower():
                errors.append(f"API Port {port}: Connection Refused")
                continue
            errors.append(f"API Port {port}: {str(e)}")

    raise ConnectionError(f"No se pudo obtener el backup por ningún método:\n" + "\n".join(errors))


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


def _download_backup_cli(host_with_port: str, username: str, password: str) -> bytes:
    """Download config using SSH CLI (show full-configuration)."""
    # Extract IP only, SSH usually on port 22
    host = host_with_port.split(":")[0] if ":" in host_with_port else host_with_port
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(
            host, 
            port=22, 
            username=username, 
            password=password, 
            timeout=settings.fortigate_timeout_seconds,
            look_for_keys=False,
            allow_agent=False
        )
        
        # METHOD 1: SFTP (Cleanest method, bypasses disclaimers and terminal noise)
        try:
            sftp = ssh.open_sftp()
            # FortiGate path for full configuration download
            with sftp.open("/config/retrieval/full-config") as f:
                config_data = f.read()
            sftp.close()
            
            if _is_valid_config(config_data):
                ssh.close()
                return config_data
        except Exception:
            pass # Fallback to shell if SFTP is not allowed

        # METHOD 2: Interactive Shell (For devices with disclaimers or restricted commands)
        # 1. Start session shell
        shell = ssh.invoke_shell()
        shell.settimeout(20)
        
        # 2. Clear banners/disclaimers (Send multiple Enter)
        for _ in range(3):
            shell.send("\n")
            time.sleep(0.5)
        
        # 3. Disable paging
        shell.send("config system console\n")
        shell.send("set output standard\n")
        shell.send("end\n")
        time.sleep(1)
        
        # 4. Try standard backup command
        shell.send("show full-configuration\n")
        
        # Read output in chunks
        output = ""
        start_time = time.time()
        max_time = settings.fortigate_timeout_seconds + 120
        
        while time.time() - start_time < max_time:
            if shell.recv_ready():
                chunk = shell.recv(65535).decode("utf-8", errors="ignore")
                output += chunk
                
                # Check for "Command fail" or "Unknown action" to try 'config global'
                if ("Unknown action" in output or "Command fail" in output) and "config global" not in output:
                    shell.send("config global\n")
                    shell.send("show full-configuration\n")
                    # Clear output to start fresh with global config
                    output = ""
                    continue

                if (output.strip().endswith("#") or output.strip().endswith("$")) and ("config system " in output or "config global" in output):
                    break
            time.sleep(0.5)
            
        ssh.close()
        
        # Clean up output
        config_data = output.encode("utf-8")
        try:
            # Look for the last 'show full-configuration' or 'config global' to find the start
            markers = ["show full-configuration", "config global"]
            start_pos = -1
            for m in markers:
                pos = output.rfind(m)
                if pos > start_pos:
                    start_pos = pos + len(m)
            
            if start_pos != -1:
                config_part = output[start_pos:]
                config_lines = []
                for line in config_part.splitlines():
                    if (line.strip().endswith("#") or line.strip().endswith("$")) and len(line) < 50:
                        break
                    config_lines.append(line)
                config_data = "\n".join(config_lines).strip().encode("utf-8")
        except Exception:
            pass

        if _is_valid_config(config_data):
            return config_data
            
        sample = config_data.decode("utf-8", errors="ignore")[:500].replace("\n", " ").strip()
        raise ConnectionError(f"CLI no devolvió una config válida. Recibido: [{sample}]")

    except Exception as e:
        raise ConnectionError(f"Fallo en CLI/SSH: {str(e)}")


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
