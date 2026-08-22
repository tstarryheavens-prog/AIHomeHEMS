import socket
import ipaddress
import concurrent.futures
import yaml
import json
import urllib.request

def get_local_subnet():
    """ローカルマシン自身のIPから 192.168.2.0/24 等のサブネットを取得する"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "192.168.2.100"
    
    network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
    return network, local_ip

def check_ip_services(ip_str):
    """
    指定IPのオープンポートとサービスプロトコルを走査して機器種別を判定する
    ルーター(192.168.2.1)は除外
    """
    if ip_str.endswith(".1") or ip_str.endswith(".255"):
        return None

    open_ports = []
    ports_to_check = {
        80: "HTTP/Web",
        8080: "HTTP-Alt/ATOMCam",
        8554: "RTSP (ATOMCam Hack Stream)",
        554: "RTSP (Camera Stream)",
        3610: "ECHONET Lite (Nichicon/T5)",
        1369: "ECHONET Lite (Nichicon)",
        6668: "Tuya/SmartLife/PlusStyle",
        6667: "Tuya Encrypted",
        55443: "Yeelight/Yeelink Smart",
        8008: "Google Home / Chromecast",
        8009: "Google Cast",
        1900: "SSDP/UPnP (Hub3/Echo/SwitchBot)",
        5353: "mDNS/ZeroConf"
    }

    device_info = {
        "ip": ip_str,
        "name": f"Device ({ip_str})",
        "category": "Unknown",
        "ports": [],
        "details": "",
        "live_url": None
    }

    is_active = False

    for port, service_label in ports_to_check.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            res = sock.connect_ex((ip_str, port))
            sock.close()
            if res == 0:
                is_active = True
                open_ports.append(port)
        except Exception:
            pass

    if not is_active:
        return None

    device_info["ports"] = open_ports

    # 1. ニチコン / HEMS ECHONET Lite
    if 3610 in open_ports or 1369 in open_ports:
        device_info["name"] = f"ニチコン T5 V2H ({ip_str})"
        device_info["category"] = "蓄電池 / V2H"
        device_info["details"] = "ECHONET Lite 制御通信対応"

    # 2. ATOMCam (Hack / RTSP / MJPEG)
    elif 8554 in open_ports or 554 in open_ports or (8080 in open_ports and 80 in open_ports):
        device_info["name"] = f"ATOMCam 2 (HACK) [{ip_str}]"
        device_info["category"] = "ネットワークカメラ"
        device_info["details"] = "ATOMCam HACK ライブストリーム対応"
        device_info["live_url"] = f"http://{ip_str}:8080/live" if 8080 in open_ports else f"http://{ip_str}/"

    # 3. Yeelink / Yeelight Smart
    elif 55443 in open_ports:
        device_info["name"] = f"Yeelink Smart Lighting ({ip_str})"
        device_info["category"] = "スマート照明"
        device_info["details"] = "Yeelight LAN Control 有効"

    # 4. Tuya / Smart Life / +Style / Meross
    elif 6668 in open_ports or 6667 in open_ports:
        device_info["name"] = f"Tuya / Smart Life / +Style Hub ({ip_str})"
        device_info["category"] = "スマートホームハブ"
        device_info["details"] = "Tuya Local Protocol (Port 6668)"

    # 5. Google Home / Chromecast
    elif 8008 in open_ports or 8009 in open_ports:
        device_info["name"] = f"Google Home / Nest / Cast ({ip_str})"
        device_info["category"] = "スマートスピーカー / ハブ"
        device_info["details"] = "Google Cast Protocol (Port 8008/8009)"

    # 6. その他のWeb管理機器 / 赤外線ハブ3 (SwitchBot / Echo Show / Meross)
    elif 80 in open_ports or 8080 in open_ports:
        device_info["name"] = f"Smart Hub / Web Device ({ip_str})"
        device_info["category"] = "赤外線ハブ / スマート機器"
        device_info["details"] = f"Web Interface Active (Port {open_ports[0]})"
        device_info["live_url"] = f"http://{ip_str}/"

    else:
        device_info["name"] = f"IoT Network Device ({ip_str})"
        device_info["category"] = "LANネットワーク機器"
        device_info["details"] = f"Open Ports: {open_ports}"

    return device_info

def scan_full_iot_network():
    """全サブネットを高速マルチスレッド走査し、すべてのスマート機器を検出する"""
    network, local_ip = get_local_subnet()
    found_devices = []

    print(f"[NetworkScanner] Deep IoT Discovery scanning subnet {network}...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=60) as executor:
        futures = [executor.submit(check_ip_services, str(ip)) for ip in network.hosts()]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res is not None:
                found_devices.append(res)

    found_devices = sorted(found_devices, key=lambda x: [int(b) for b in x["ip"].split(".")])
    return found_devices

def auto_update_config_with_discovered_ip(config_path="config.yaml"):
    """発見された機器のIPを config.yaml に自動反映する"""
    devices = scan_full_iot_network()
    nichicon_devices = [d for d in devices if d["category"] == "蓄電池 / V2H"]
    if not nichicon_devices:
        return None
    first_device = nichicon_devices[0]
    discovered_ip = first_device["ip"]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        config["nichicon"]["ip_address"] = discovered_ip
        config["nichicon"]["enabled"] = True
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
        return first_device
    except Exception:
        return first_device

def scan_local_network_for_echonet(timeout_sec=5):
    """従来のECHONET機器検索との互換関数"""
    devices = scan_full_iot_network()
    echonet_devs = []
    for d in devices:
        if d["category"] == "蓄電池 / V2H" or 3610 in d["ports"] or 1369 in d["ports"]:
            echonet_devs.append({
                "ip": d["ip"],
                "type": d["name"],
                "port": d["ports"][0] if d["ports"] else 3610
            })
    return echonet_devs
