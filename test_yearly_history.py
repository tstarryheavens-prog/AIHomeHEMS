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

years = [str(y) + "0101" for y in range(2016, 2027)]

print("=== Testing Yearly History (monitor3.html) from 2016 to 2026 ===")
for y in years:
    session.get(f"http://{ip}/onLoad_Notify?enter=/monitor3.html?hToday={y}", timeout=2)
    poll_url = f"http://{ip}/monitor3.html?hToday={y}&action=poll"
    res = session.get(poll_url, timeout=3)
    res.encoding = 'shift_jis'
    match = re.search(r'\{.*\}', res.text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        print(f"Year {y[:4]} -> Display: {data.get('tEMonitorDate')}, Electricity Cost: Yen {data.get('tEMonitorTodayright')}, Self Sufficiency: {data.get('tEMonitorTodayleft')}%")
