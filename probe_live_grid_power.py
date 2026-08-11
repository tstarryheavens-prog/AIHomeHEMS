import requests
import yaml
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

hems_conf = config.get("hems_controller", {})
ip = hems_conf.get("ip_address", "192.168.2.23")
user_id = hems_conf.get("user_id", "")
password = hems_conf.get("password", "")

session = requests.Session()
login_url = f"http://{ip}/login.cgi"
params = {"user_id": user_id, "password": password, "hoji": "on"}
session.get(login_url, params=params, timeout=5)

session.get(f"http://{ip}/onLoad_Notify?enter=/e-flow.html", timeout=2)
res = session.get(f"http://{ip}/e-flow.html?action=poll", timeout=3)
res.encoding = 'shift_jis'

print("=== /e-flow.html Realtime Poll Payload ===")
print(res.text)

match = re.search(r'\{.*\}', res.text, re.DOTALL)
if match:
    data = json.loads(match.group(0))
    tTradePow = data.get("tTradePow", "0")
    tTradeTitle = data.get("tTradeTitle", "買電")
    tGenPow = data.get("tGenPow", "0")
    print(f"\nParsed Live Values -> 発電 (PV): {tGenPow} W | 買電/売電方向: {tTradeTitle} | 電力 (Trade Pow): {tTradePow} W")
