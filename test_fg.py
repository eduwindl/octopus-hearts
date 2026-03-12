import requests
import urllib3
urllib3.disable_warnings()

ip = "181.36.224.80:10443"
base_url = f"https://{ip}"
username = "sptisp"
password = "test"

# FortiOS 7.4+ SPA uses a different login mechanism
# Try JSON-based login via /api/v2/authentication 
print("--- Method A: JSON POST to /api/v2/authentication ---")
session = requests.Session()
session.verify = False
try:
    r = session.post(
        f"{base_url}/api/v2/authentication",
        json={"username": username, "secretkey": password},
        timeout=15,
    )
    print(f"  Status: {r.status_code}")
    print(f"  Text: {r.text[:200]}")
    print(f"  Cookies: {session.cookies.get_dict()}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# Try logincheck with credentials as query params 
print("\n--- Method B: logincheck with credentials as query params ---")
session2 = requests.Session()
session2.verify = False
try:
    r2 = session2.get(
        f"{base_url}/logincheck?username={username}&secretkey={password}&ajax=1",
        timeout=15,
    )
    print(f"  Status: {r2.status_code}")
    print(f"  Text: {r2.text[:80]}")
    print(f"  Cookies: {session2.cookies.get_dict()}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# Try the legacy /cgi-bin/module/flatui_auth approach
print("\n--- Method C: /cgi-bin/module/flatui_auth ---")
session3 = requests.Session()
session3.verify = False
try:
    r3 = session3.post(
        f"{base_url}/cgi-bin/module/flatui_auth",
        data={"username": username, "secretkey": password, "ajax": "1"},
        timeout=15,
    )
    print(f"  Status: {r3.status_code}")
    print(f"  Text: {r3.text[:80]}")
    print(f"  Cookies: {session3.cookies.get_dict()}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# Try adding X-Requested-With header (sometimes SPA firewalls need this)
print("\n--- Method D: logincheck with X-Requested-With ---")
session4 = requests.Session()
session4.verify = False
try:
    r4 = session4.post(
        f"{base_url}/logincheck",
        data={"username": username, "secretkey": password, "ajax": "1"},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Origin": base_url,
            "Referer": f"{base_url}/login",
            "Accept": "application/json, text/plain, */*",
        },
        timeout=15,
    )
    print(f"  Status: {r4.status_code}")
    print(f"  Text: {r4.text[:80]}")
    print(f"  Cookies: {session4.cookies.get_dict()}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# Try digest auth 
print("\n--- Method E: Digest Auth on backup ---")
try:
    from requests.auth import HTTPDigestAuth
    r5 = requests.get(
        f"{base_url}/api/v2/monitor/system/config/backup",
        auth=HTTPDigestAuth(username, password),
        params={"destination": "file"},
        verify=False,
        timeout=15,
    )
    print(f"  Status: {r5.status_code}, size: {len(r5.content)}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")
