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

test_dates = ["20260731", "20260730", "20260729", "20260728", "20260727", "20260720", "20260701"]

print("=== Probing monitor2.html (売電 kWh / 買電 kWh) Across Dates ===")
for d in test_dates:
    session.get(f"http://{ip}/onLoad_Notify?enter=/monitor2.html?hToday={d}", timeout=2)
    res = session.get(f"http://{ip}/monitor2.html?hToday={d}&action=poll", timeout=3)
    res.encoding = 'shift_jis'
    match = re.search(r'\{.*\}', res.text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        sale_kwh = data.get("tEMonitorTodayleft") # 売電量 (kWh)
        buy_kwh = data.get("tEMonitorTodayright") # 買電量 (kWh)
        print(f"Date {d} -> 売電 (Export): {sale_kwh} kWh, 買電 (Buy): {buy_kwh} kWh")

print("\n=== Probing e-flow.html (エネルギーフロー) ===")
session.get(f"http://{ip}/onLoad_Notify?enter=/e-flow.html", timeout=2)
res_flow = session.get(f"http://{ip}/e-flow.html?action=poll", timeout=3)
res_flow.encoding = 'shift_jis'
print("e-flow.html response:")
print(res_flow.text)
