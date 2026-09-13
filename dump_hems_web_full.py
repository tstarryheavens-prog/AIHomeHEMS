import requests
import yaml
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

hems_conf = config.get("hems_controller", {})
ip = hems_conf.get("ip_address", "192.168.1.100")
user_id = hems_conf.get("user_id", "")
password = hems_conf.get("password", "")

session = requests.Session()
login_url = f"http://{ip}/login.cgi"
params = {"user_id": user_id, "password": password, "hoji": "on", "disp_url": ""}
res_login = session.get(login_url, params=params, timeout=5)
print("Login status:", res_login.status_code)

# Check all possible HTML/CGI pages on HEMS Controller
pages = [
    "/monitor1.html",
    "/monitor2.html",
    "/monitor3.html",
    "/e-flow.html",
    "/csv_down.cgi",
    "/history.html",
    "/log_download.cgi",
    "/export.cgi"
]

print("=== Probing HEMS Controller Web Endpoints ===")
for p in pages:
    try:
        session.get(f"http://{ip}/onLoad_Notify?enter={p}", timeout=2)
        r = session.get(f"http://{ip}{p}", timeout=3)
        print(f"Endpoint {p} -> HTTP {r.status_code}, Length: {len(r.text)}")
        if "action=poll" in r.text or "<table" in r.text.lower() or "download" in r.text.lower():
            print(f"  Excerpt: {r.text[:300]}...")
    except Exception as e:
        print(f"Endpoint {p} -> Error: {e}")
