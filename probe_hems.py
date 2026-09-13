import requests
import re
import socket

ip = "192.168.1.100"
print(f"=== Probing HEMS Controller at {ip} ===")

# 1. Probe Web pages & common CGIs / paths
paths = [
    "", "login.cgi", "main.cgi", "top.cgi", "menu.cgi", "status.cgi", 
    "graph.cgi", "log.cgi", "csv.cgi", "history.cgi", "download.cgi",
    "room.cgi", "circuit.cgi", "data.cgi", "get_data.cgi", "api/data",
    "js/login.js", "js/main.js", "js/common.js", "css/login.css"
]

for p in paths:
    url = f"http://{ip}/{p}"
    try:
        r = requests.get(url, timeout=2)
        print(f"  /{p:15s} -> Status {r.status_code}, Len {len(r.content)}")
        if r.status_code == 200 and ("cgi" in p or "js" in p or "data" in p):
            print(f"    Snippet: {r.text[:200]!r}")
    except Exception as e:
        print(f"  /{p:15s} -> Error {e}")

# 2. Probe ECHONET Lite on 192.168.1.100 (Power Distribution Board 0x0287, Metering 0x0288, Controller 0x05FF)
print("\n=== Probing ECHONET Lite Classes on 192.168.1.100 ===")
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(1.5)

# Test various ECHONET Lite class queries
classes_to_test = [
    ("Distribution Board 0x0287", bytes([0x02, 0x87, 0x01]), 0xC0), # 住宅用分電盤 (分岐回路電力)
    ("Metering Unit 0x0288",      bytes([0x02, 0x88, 0x01]), 0xE7), # 電力計測ユニット
    ("Smart Meter 0x0288",        bytes([0x02, 0x88, 0x02]), 0xE7),
    ("Node Profile 0x0EF0",       bytes([0x0E, 0xF0, 0x01]), 0xD6), # ノードプロファイル Instance List
]

for name, deoj, epc in classes_to_test:
    frame = bytes([0x10, 0x81, 0x00, 0x01, 0x05, 0xFF, 0x01]) + deoj + bytes([0x62, 0x01, epc, 0x00])
    try:
        sock.sendto(frame, (ip, 1369))
        data, addr = sock.recvfrom(1024)
        print(f"  [UDP 1369] {name} RESPONSE: {data.hex()}")
    except Exception:
        print(f"  [UDP 1369] {name}: No response")

sock.close()
