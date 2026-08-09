import requests
import yaml
import sys
import json
import re
import time

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

hems_conf = config.get("hems_controller", {})
ip = hems_conf.get("ip_address", "192.168.2.23")

session = requests.Session()
session.get(f"http://{ip}/login.cgi", params={"user_id": hems_conf["user_id"], "password": hems_conf["password"], "hoji": "on"})

print("=== Deep Probing monitor3.html (Yearly/Monthly) across 2016-2026 ===")
for year in range(2016, 2027):
    ym = f"{year}0101"
    try:
        session.get(f"http://{ip}/onLoad_Notify?enter=/monitor3.html?hToday={ym}", timeout=3)
        time.sleep(0.3)
        r = session.get(f"http://{ip}/monitor3.html?hToday={ym}&action=poll", timeout=4)
        r.encoding = 'shift_jis'
        match = re.search(r'\{.*\}', r.text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            date_disp = data.get("tEMonitorDate")
            kwh = data.get("tEMonitorTodayleft")
            cost = data.get("tEMonitorTodayright")
            unit = data.get("tEMonitorTodayrightUnit", "")
            print(f"Year {year} -> Display: {date_disp}, Left: {kwh}, Right: {cost} {unit}")
    except Exception as e:
        print(f"Error querying year {year}: {e}")
    time.sleep(0.5)
