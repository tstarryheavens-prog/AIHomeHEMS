import requests
import yaml
import sys
import time

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
session.get(login_url, params=params, timeout=5)

target_pages = [
    "e-flow.html", "monitor1.html", "cost.html", "phvev.html", "ringhome.html"
]

print("=== Polling HEMS Data Endpoints via action=poll ===")
for page in target_pages:
    # 1. Notify
    session.get(f"http://{ip}/onLoad_Notify?enter=/{page}", timeout=3)
    
    # 2. Fetch page with action=poll
    no_cache = int(time.time() * 1000)
    poll_url = f"http://{ip}/{page}?action=poll&cache={no_cache}"
    res = session.get(poll_url, timeout=3)
    res.encoding = 'shift_jis'
    
    print(f"\n[/{page}?action=poll]")
    print(f"Status: {res.status_code}, Length: {len(res.content)} bytes")
    print(res.text[:1000])
