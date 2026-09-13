import requests
import yaml
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

hems_conf = config.get("hems_controller", {})
ip = hems_conf.get("ip_address", "192.168.1.100")
user_id = hems_conf.get("user_id", "")
password = hems_conf.get("password", "")

print(f"=== Testing Auth to HEMS Web at {ip} with ID: {user_id} ===")

session = requests.Session()

# Submit login
login_url = f"http://{ip}/login.cgi"
params = {"user_id": user_id, "password": password, "hoji": "on", "disp_url": ""}
r = session.get(login_url, params=params, timeout=5)
r.encoding = 'shift_jis'

print("Login Response Status:", r.status_code)
print("Login Response Length:", len(r.content))
print("HTML Title/Content Preview:")
print(r.text[:1000])

# Extract internal URLs or redirects in the authenticated response
links = re.findall(r'(?:href|action|src)=[\"\\\']?([^\"\\\' >]+)', r.text, re.IGNORECASE)
print("\nDiscovered authenticated links/CGIs:", set(links))

# Probe common authenticated CGI paths
auth_paths = [
    "top.cgi", "main.cgi", "menu.cgi", "home.cgi", "status.cgi", 
    "graph.cgi", "log.cgi", "csv.cgi", "history.cgi", "download.cgi",
    "room.cgi", "circuit.cgi", "solar.cgi", "battery.cgi", "denki.cgi"
]

print("\n=== Probing Authenticated CGIs ===")
for p in auth_paths:
    res = session.get(f"http://{ip}/{p}", timeout=3)
    res.encoding = 'shift_jis'
    print(f"  /{p:15s} -> Status {res.status_code}, Length {len(res.content)}")
    if res.status_code == 200 and len(res.content) != 3036 and len(res.content) != 126:
        print(f"    FOUND CONTENT! Preview: {res.text[:300]!r}")
