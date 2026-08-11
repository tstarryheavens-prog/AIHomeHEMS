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
params = {"user_id": user_id, "password": password, "hoji": "on", "disp_url": ""}
session.get(login_url, params=params, timeout=5)

print("=== Analyzing monitor2.html (Monthly) ===")
session.get(f"http://{ip}/onLoad_Notify?enter=/monitor2.html?hToday=20260701", timeout=2)
res2 = session.get(f"http://{ip}/monitor2.html?hToday=20260701&action=poll", timeout=3)
res2.encoding = 'shift_jis'
print("monitor2.html response:")
print(res2.text)

print("\n=== Analyzing monitor3.html (Yearly) ===")
session.get(f"http://{ip}/onLoad_Notify?enter=/monitor3.html?hToday=20260701", timeout=2)
res3 = session.get(f"http://{ip}/monitor3.html?hToday=20260701&action=poll", timeout=3)
res3.encoding = 'shift_jis'
print("monitor3.html response:")
print(res3.text)
