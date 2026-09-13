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
session.get(login_url, params=params, timeout=5)

months_to_test = [
    "20260701", "20260601", "20260501", "20260401", "20260301", "20260201", "20260101",
    "20251201", "20250601", "20250101",
    "20241201", "20240601", "20240101",
    "20220101", "20200101", "20180101", "20160101"
]

print("=== Testing monitor3.html across multiple years ===")
for ym in months_to_test:
    session.get(f"http://{ip}/onLoad_Notify?enter=/monitor3.html?hToday={ym}", timeout=2)
    res = session.get(f"http://{ip}/monitor3.html?hToday={ym}&action=poll", timeout=3)
    res.encoding = 'shift_jis'
    match = re.search(r'\{.*\}', res.text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        date_str = data.get("tEMonitorDate")
        left = data.get("tEMonitorTodayleft")
        right = data.get("tEMonitorTodayright")
        unit = data.get("tEMonitorTodayrightUnit", "")
        print(f"Param {ym} -> Date: {date_str}, Left: {left}, Right: {right} {unit}")
