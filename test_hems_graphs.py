import requests
import yaml
import sys

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

graph_paths = [
    "./image/eMonitorGraph1.bmp?hToday=20260730",
    "./image/eMonitorGraph1.bmp?hToday=20260729",
    "./image/eMonitorGraph2.bmp?hToday=20260730",
]

print("=== Fetching HEMS Historical Graph Images ===")
for g in graph_paths:
    r = session.get(f"http://{ip}/{g}", timeout=3)
    print(f"Graph /{g:45s} -> Status {r.status_code}, Length {len(r.content)} bytes")
