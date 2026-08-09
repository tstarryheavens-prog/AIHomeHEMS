import requests
import yaml
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

hems_conf = config.get("hems_controller", {})
ip = hems_conf.get("ip_address", "192.168.2.23")

session = requests.Session()
res = session.get(f"http://{ip}/js/WB_main.js")
res.encoding = 'shift_jis'
print("=== WB_main.js Content ===")
print(res.text[:3000])
