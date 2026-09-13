import requests
import yaml
import sys
import time

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

# Fetch full HTML of monitor1.html
r = session.get(f"http://{ip}/monitor1.html")
r.encoding = 'shift_jis'
print("=== monitor1.html Full Content ===")
print(r.text)

# Test querying past dates on monitor1.html
dates = ["20260730", "20260729", "20260728", "20260727"]

print("\n=== Testing Historical Date Queries on monitor1.html ===")
for d in dates:
    session.get(f"http://{ip}/onLoad_Notify?enter=/monitor1.html?hToday={d}", timeout=3)
    no_cache = int(time.time() * 1000)
    poll_url = f"http://{ip}/monitor1.html?hToday={d}&action=poll&cache={no_cache}"
    res = session.get(poll_url, timeout=3)
    res.encoding = 'shift_jis'
    print(f"Date {d} -> Status {res.status_code}, Length {len(res.content)} bytes")
    print(res.text[:400])
