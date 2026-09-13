import requests
import yaml
import sys
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
session.get(login_url, params=params, timeout=5)

for p in ["/monitor1.html", "/monitor2.html", "/monitor3.html"]:
    r = session.get(f"http://{ip}{p}")
    r.encoding = 'shift_jis'
    print(f"=== {p} HTML Content Excerpt ===")
    lines = [line for line in r.text.splitlines() if "form" in line.lower() or "href" in line.lower() or "action" in line.lower() or "function" in line.lower() or "script" in line.lower() or "btn" in line.lower() or "today" in line.lower()]
    print("\n".join(lines[:30]))
    print("\n")
