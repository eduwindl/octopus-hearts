import sys
import argparse
from backend.fortigate_client import fetch_config_with_credentials, fetch_config
from backend.config import settings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
settings.fortigate_verify_ssl = False

def test_login():
    parser = argparse.ArgumentParser(description="Test FortiGate login and config backup.")
    parser.add_argument("ip", help="FortiGate IP Address")
    parser.add_argument("--user", help="Username")
    parser.add_argument("--password", help="Password")
    parser.add_argument("--token", help="API Token")
    
    args = parser.parse_args()

    print(f"[*] Testing connection to {args.ip}...")
    try:
        if args.token:
            print("[*] Using API Token auth...")
            content = fetch_config(args.ip, args.token)
        elif args.user and args.password:
            print(f"[*] Using Credentials auth (user: {args.user})...")
            content = fetch_config_with_credentials(args.ip, args.user, args.password)
        else:
            print("[-] Must provide either --token or --user/--password")
            sys.exit(1)

        print("[+] SUCCESS! Config downloaded.")
        print(f"[+] Config size: {len(content)} bytes.")
        print("[+] Preview of first 5 lines:")
        print(content.decode('utf-8', errors='ignore').split('\n')[:5])
        
    except Exception as e:
        print(f"[-] FAILED: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_login()
