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

for d in ["20260701", "20260601", "20251201"]:
    session.get(f"http://{ip}/onLoad_Notify?enter=/monitor2.html?hToday={d}")
    res = session.get(f"http://{ip}/monitor2.html?hToday={d}&action=poll")
    res.encoding = 'shift_jis'
    print(f"=== Date {d} monitor2.html RAW XML ===")
    print(res.text)
