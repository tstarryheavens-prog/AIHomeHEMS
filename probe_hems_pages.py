import requests
import yaml
import sys
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
r = session.get(login_url, params=params, timeout=5)

pages = [
    "ringhome.html", "monitor1.html", "e-flow.html", "cost.html", 
    "phvev.html", "notice.html", "advice.html", "check.html",
    "js/WB_main.js", "js/WB_phvev.js", "js/WBShowMessage.js"
]

print(f"=== Inspecting HEMS Authenticated Pages on {ip} ===")
for p in pages:
    res = session.get(f"http://{ip}/{p}", timeout=4)
    res.encoding = 'shift_jis'
    print(f"\n--- [/{p}] Status {res.status_code}, Length: {len(res.content)} bytes ---")
    print(res.text[:800])
    
    # Extract any sub-links, AJAX polling URLs, or data files in JS/HTML
    sub_urls = re.findall(r'(?:href|action|src|url|poll)\(?[\"\\\']?([^\"\\\' >\)]+)', res.text, re.IGNORECASE)
    if sub_urls:
        print("  Sub-links/URLs found:", set(sub_urls))
