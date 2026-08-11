import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

ip = "192.168.2.23"

# Fetch login.css
r = requests.get(f"http://{ip}/css/login.css")
r.encoding = 'shift_jis'
print("=== css/login.css ===")
print(r.text[:1000])

# Fetch login.cgi
r2 = requests.get(f"http://{ip}/login.cgi")
r2.encoding = 'shift_jis'
print("=== login.cgi ===")
print(r2.text[:1500])
