import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

ip = "192.168.1.100"

cgis = [
    "top.cgi", "home.cgi", "main.cgi", "menu.cgi", "graph.cgi", "room.cgi",
    "power.cgi", "history.cgi", "log.cgi", "csv.cgi", "meter.cgi", "detail.cgi",
    "system.cgi", "config.cgi", "hems.cgi", "monitor.cgi", "list.cgi"
]

print("=== Checking common CGI endpoints with default session / GET ===")
for c in cgis:
    r = requests.get(f"http://{ip}/{c}")
    print(f"/{c:15s} -> Status {r.status_code}, len {len(r.content)}")

# Test login attempts
test_creds = [
    ("", ""),
    ("admin", "admin"),
    ("guest", "guest"),
    ("000000000", "0000"),
    ("123456789", "1234")
]

print("\n=== Testing login.cgi attempts ===")
for uid, pw in test_creds:
    r = requests.get(f"http://{ip}/login.cgi", params={"user_id": uid, "password": pw})
    r.encoding = 'shift_jis'
    print(f"login ({uid}:{pw}) -> Status {r.status_code}, len {len(r.content)}")
    if "エラー" not in r.text and "Incorrect" not in r.text and len(r.content) != 3036:
        print("  Possible success/redirect! Text snippet:", r.text[:300])
