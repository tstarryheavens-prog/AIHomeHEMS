import requests
import yaml
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

hems_conf = config.get("hems_controller", {})
ip = hems_conf.get("ip_address", "192.168.2.23")

session = requests.Session()
session.get(f"http://{ip}/login.cgi", params={"user_id": hems_conf["user_id"], "password": hems_conf["password"], "hoji": "on"})

pages = ["/ringhome.html", "/phvev.html", "/notice.html", "/check.html", "/advice.html", "/monitor1.html", "/monitor2.html", "/monitor3.html", "/e-flow.html"]

all_links = set()

for p in pages:
    try:
        r = session.get(f"http://{ip}{p}")
        r.encoding = 'shift_jis'
        links = re.findall(r'href=["\']([^"\']+)["\']', r.text)
        for l in links:
            if not l.startswith("http") and not l.startswith("#"):
                all_links.add(l.split("?")[0])
    except Exception:
        pass

print("=== All Discovered HEMS Web HTML Pages ===")
for l in sorted(all_links):
    print("  -", l)
