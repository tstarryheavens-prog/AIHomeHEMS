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

session = requests.Session()
session.get(f"http://{ip}/login.cgi", params={"user_id": hems_conf["user_id"], "password": hems_conf["password"], "hoji": "on"})

for p in ["/cost.html", "/best5.html"]:
    try:
        session.get(f"http://{ip}/onLoad_Notify?enter={p}", timeout=2)
        r = session.get(f"http://{ip}{p}", timeout=3)
        r.encoding = 'shift_jis'
        print(f"=== {p} Response (Length: {len(r.text)}) ===")
        print(r.text[:500])
        print("\n")
        
        # Poll payload
        r_poll = session.get(f"http://{ip}{p}?action=poll", timeout=3)
        r_poll.encoding = 'shift_jis'
        print(f"=== {p} Poll Payload ===")
        print(r_poll.text)
        print("\n")
    except Exception as e:
        print(f"Error for {p}: {e}")
