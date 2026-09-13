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

test_months = [f"2026{m:02d}01" for m in range(1, 8)] + [f"2025{m:02d}01" for m in range(1, 13)]

print("=== Testing Monthly History (monitor2.html) ===")
for m in test_months:
    session.get(f"http://{ip}/onLoad_Notify?enter=/monitor2.html?hToday={m}", timeout=2)
    poll_url = f"http://{ip}/monitor2.html?hToday={m}&action=poll"
    res = session.get(poll_url, timeout=3)
    res.encoding = 'shift_jis'
    match = re.search(r'\{.*\}', res.text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        disp = data.get("tEMonitorDate")
        cost = data.get("tEMonitorTodayright")
        self_suff = data.get("tEMonitorTodayleft")
        print(f"Month {m[:6]} -> Display: {disp}, Cost: Yen {cost}, Self Sufficiency: {self_suff}%")
