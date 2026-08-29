import requests
import yaml
import re
import json
import time
import socket

def probe_hems_web():
    with open("config.yaml", "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f).get("hems_controller", {})
        
    ip = conf.get("ip_address", "192.168.2.23")
    user_id = conf.get("user_id", "")
    password = conf.get("password", "")
    
    print(f"=== 1. Probing HEMS Controller Web at http://{ip} ===")
    s = requests.Session()
    login_url = f"http://{ip}/login.cgi"
    res = s.get(login_url, params={"user_id": user_id, "password": password, "hoji": "on"}, timeout=4)
    print(f"Login Status: {res.status_code}")
    
    candidates = [
        "e-flow.html", "monitor1.html", "monitor2.html", "monitor3.html", 
        "cost.html", "best5.html", "advice.html", "check.html", "ringhome.html",
        "phvev.html", "notice.html", "branch.html", "circuit.html", "room.html",
        "detail.html", "electric.html", "breakdown.html", "aircon.html", "kitchen.html",
        "living.html", "ranking.html", "power.html", "realtime.html"
    ]
    
    found_pages = {}
    
    for p in candidates:
        try:
            s.get(f"http://{ip}/onLoad_Notify?enter=/{p}", timeout=1.5)
            r = s.get(f"http://{ip}/{p}?action=poll", timeout=2)
            r.encoding = 'shift_jis'
            if r.status_code == 200 and len(r.text.strip()) > 5:
                found_pages[p] = r.text.strip()
                print(f"[FOUND POLL DATA] /{p} -> Length {len(r.text)}: {r.text[:180]}")
            else:
                r_direct = s.get(f"http://{ip}/{p}", timeout=2)
                r_direct.encoding = 'shift_jis'
                if r_direct.status_code == 200 and len(r_direct.text.strip()) > 50:
                    found_pages[p] = r_direct.text.strip()
                    print(f"[FOUND HTML PAGE] /{p} -> Length {len(r_direct.text)}")
        except Exception:
            pass
            
    # 全JSファイルの走査から隠しURL・変数を抽出
    js_files = ["js/WB_main.js", "js/WB_phvev.js", "js/WBShowMessage.js"]
    for j in js_files:
        try:
            r_js = s.get(f"http://{ip}/{j}", timeout=2)
            r_js.encoding = 'shift_jis'
            if r_js.status_code == 200:
                urls = set(re.findall(r'[\'\"/]([a-zA-Z0-9_\-]+\.html|\.cgi)[\'\"]?', r_js.text))
                print(f"[JS {j}] Discovered internal targets: {urls}")
        except Exception:
            pass

def probe_echonet_distribution_boards():
    print("\n=== 2. Probing ECHONET Lite Distribution Board / Power Meter (Class 0x0287 / 0x0288) ===")
    ips_to_test = ["192.168.2.23", "192.168.2.12"]
    
    for target_ip in ips_to_test:
        for port in [3610, 1369]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.0)
            frame_dist = bytes([0x10, 0x81, 0x00, 0x01, 0x05, 0xFF, 0x01, 0x02, 0x87, 0x01, 0x62, 0x01, 0xC0, 0x00])
            try:
                sock.sendto(frame_dist, (target_ip, port))
                data, _ = sock.recvfrom(1024)
                print(f"[ECHONET FOUND] {target_ip}:{port} Class 0x0287 (Distribution Board) -> {data.hex()}")
            except Exception:
                pass
            sock.close()

if __name__ == "__main__":
    probe_hems_web()
    probe_echonet_distribution_boards()
