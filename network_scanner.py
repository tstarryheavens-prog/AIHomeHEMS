"""
network_scanner.py - 宅内IoT / ECHONET Lite / HEMS ネットワーク自動スキャナー
日本国内スマートホーム規格 (ECHONET Lite UDPマルチキャスト & TCPポート走査) に対応
"""

import socket
import ipaddress
import concurrent.futures
import time
import struct
from typing import List, Dict, Any, Optional

from config_manager import get_config_manager

ECHONET_MULTICAST_ADDR = "224.0.23.0"
ECHONET_PORT = 3610

# ECHONET Lite オブジェクトクラスの日本語名マッピング
ECHONET_CLASS_NAMES = {
    (0x02, 0x7D): {"name": "住宅用蓄電池システム", "category": "蓄電池 / V2H", "register_as": "battery"},
    (0x02, 0x7E): {"name": "EV充放電器 (V2H)", "category": "蓄電池 / V2H", "register_as": "battery"},
    (0x02, 0x79): {"name": "住宅用太陽光発電", "category": "太陽光発電 (PV)", "register_as": "solar"},
    (0x02, 0x88): {"name": "低圧スマート電力量メータ", "category": "スマートメーター", "register_as": "meter"},
    (0x02, 0x6B): {"name": "ヒートポンプ給湯機 (エコキュート)", "category": "給湯器", "register_as": "water_heater"},
    (0x01, 0x30): {"name": "家庭用エアコン", "category": "空調家電", "register_as": "aircon"},
    (0x02, 0x90): {"name": "単機能照明 (スマートLED)", "category": "スマート照明", "register_as": "lighting"},
    (0x05, 0xFD): {"name": "住宅用分電盤 (HEMS計測盤)", "category": "HEMS分電盤", "register_as": "hems"},
    (0x05, 0xFF): {"name": "コントローラ", "category": "HEMSコントローラー", "register_as": "hems"}
}


def get_local_subnet():
    """ローカルマシン自身のIPから 192.168.x.0/24 サブネットを取得する"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "192.168.1.50"

    network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
    return network, local_ip


def discover_echonet_multicast(timeout: float = 2.0) -> List[Dict[str, Any]]:
    """
    ECHONET Lite UDP マルチキャスト (224.0.23.0:3610) による機器探索
    全ノードプロファイルの自ノードインスタンスリストS (EPC 0xD6) をクエリ
    """
    discovered = []
    # 電文: EHD1(0x10) EHD2(0x81) TID(0x00, 0x01) SEOJ(0x05, 0xFF, 0x01) DEOJ(0x0E, 0xF0, 0x01) ESV(0x62) OPC(0x01) EPC(0xD6) PDC(0x00)
    req_frame = bytes([0x10, 0x81, 0x00, 0x01, 0x05, 0xFF, 0x01, 0x0E, 0xF0, 0x01, 0x62, 0x01, 0xD6, 0x00])

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)

        # マルチキャスト送信
        try:
            sock.sendto(req_frame, (ECHONET_MULTICAST_ADDR, ECHONET_PORT))
        except Exception:
            pass

        # サブネットブロードキャスト送信（マルチキャストが通らないルーター環境向けフォールバック）
        network, local_ip = get_local_subnet()
        broadcast_addr = str(network.broadcast_address)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(req_frame, (broadcast_addr, ECHONET_PORT))
        except Exception:
            pass

        start_time = time.time()
        seen_ips = set()

        while time.time() - start_time < timeout:
            try:
                data, (ip, port) = sock.recvfrom(1024)
                if ip in seen_ips or ip == local_ip:
                    continue

                if len(data) >= 14 and data[10] in (0x72, 0x52):
                    seen_ips.add(ip)
                    pdc = data[13]
                    edt = data[14:14+pdc]
                    detected_classes = []

                    if len(edt) >= 1:
                        num_instances = edt[0]
                        offset = 1
                        for _ in range(num_instances):
                            if offset + 3 <= len(edt):
                                cg = edt[offset]
                                cc = edt[offset + 1]
                                detected_classes.append((cg, cc))
                                offset += 3

                    # デバイス情報の構築
                    primary_class = detected_classes[0] if detected_classes else (0x02, 0x7D)
                    cls_info = ECHONET_CLASS_NAMES.get(primary_class, {
                        "name": f"ECHONET Lite 機器 ({hex(primary_class[0])}:{hex(primary_class[1])})",
                        "category": "スマート家電",
                        "register_as": "generic_echonet"
                    })

                    discovered.append({
                        "ip": ip,
                        "name": f"{cls_info['name']} ({ip})",
                        "category": cls_info["category"],
                        "ports": [3610],
                        "protocol": "echonet_udp",
                        "details": f"ECHONET Lite UDP応答 (検知クラス数: {len(detected_classes)})",
                        "register_as": cls_info["register_as"],
                        "live_url": None
                    })
            except socket.timeout:
                break
            except Exception:
                pass
        sock.close()
    except Exception as e:
        print(f"[NetworkScanner] Multicast discovery error: {e}")

    return discovered


def check_ip_services(ip_str: str) -> Optional[Dict[str, Any]]:
    """
    指定IPのTCPオープンポートとサービスを走査して機器種別を判定
    """
    if ip_str.endswith(".1") or ip_str.endswith(".255"):
        return None

    open_ports = []
    ports_to_check = {
        80: "HTTP/Web",
        8080: "HTTP-Alt/ATOMCam",
        8554: "RTSP (ATOMCam Stream)",
        554: "RTSP (Camera Stream)",
        3610: "ECHONET Lite (Nichicon/T5/UDP)",
        1369: "ECHONET Lite (Nichicon TCP)",
        6668: "Tuya/SmartLife",
        55443: "Yeelight LAN",
        8008: "Google Cast / Nest"
    }

    is_active = False
    for port in ports_to_check:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.25)
            res = sock.connect_ex((ip_str, port))
            sock.close()
            if res == 0:
                is_active = True
                open_ports.append(port)
        except Exception:
            pass

    if not is_active:
        return None

    device_info = {
        "ip": ip_str,
        "name": f"Device ({ip_str})",
        "category": "Unknown",
        "ports": open_ports,
        "protocol": "tcp",
        "details": "",
        "register_as": None,
        "live_url": None
    }

    # 1. ニチコン / 独自TCP ECHONET Lite (Port 3610 または 1369)
    if 1369 in open_ports or (3610 in open_ports and 80 not in open_ports):
        device_info["name"] = f"ニチコン T5 V2H / 蓄電池 ({ip_str})"
        device_info["category"] = "蓄電池 / V2H"
        device_info["protocol"] = "echonet_tcp"
        device_info["details"] = "ニチコンTCP ECHONET Lite制御通信ポート開放"
        device_info["register_as"] = "battery"

    # 2. HEMS Web コントローラー (CenteHTTPd / パナホーム等)
    elif 80 in open_ports and (3610 in open_ports or 8080 in open_ports or any(ip_str.endswith(f".{x}") for x in [100, 23, 20])):
        device_info["name"] = f"住宅用 HEMS Webコントローラー ({ip_str})"
        device_info["category"] = "HEMSコントローラー"
        device_info["protocol"] = "http"
        device_info["details"] = "CenteHTTPd Web管理インターフェース (買電/売電計測)"
        device_info["register_as"] = "hems"
        device_info["live_url"] = f"http://{ip_str}/"

    # 3. ATOMCam / ネットワークカメラ (Hack / RTSP / MJPEG)
    elif 8554 in open_ports or 554 in open_ports or (8080 in open_ports and 80 in open_ports):
        device_info["name"] = f"ATOMCam ネットワークカメラ ({ip_str})"
        device_info["category"] = "ネットワークカメラ"
        device_info["details"] = "RTSP / Webストリーミング対応カメラ"
        device_info["register_as"] = "camera"
        device_info["live_url"] = f"http://{ip_str}:8080/live" if 8080 in open_ports else f"http://{ip_str}/"

    # 4. スマート照明 / ハブ
    elif 55443 in open_ports:
        device_info["name"] = f"Yeelight スマート照明 ({ip_str})"
        device_info["category"] = "スマート照明"
        device_info["details"] = "Yeelight LAN Control"

    elif 6668 in open_ports:
        device_info["name"] = f"Tuya / Smart Life 機器 ({ip_str})"
        device_info["category"] = "スマートプラグ / 家電 (Tuya)"
        device_info["details"] = "Tuya Local 通信ポート開放 (スマートプラグ・照明・スイッチ・赤外線リモコン等)"
        device_info["register_as"] = "tuya"

    # 5. 一般Web機器
    elif 80 in open_ports or 8080 in open_ports:
        device_info["name"] = f"Web管理機器 / HEMS候補 ({ip_str})"
        device_info["category"] = "Web機器 / HEMS"
        device_info["details"] = f"HTTP Port {open_ports[0]} 開放"
        device_info["register_as"] = "hems"
        device_info["live_url"] = f"http://{ip_str}/"

    else:
        device_info["name"] = f"LAN機器 ({ip_str})"
        device_info["category"] = "LANネットワーク機器"
        device_info["details"] = f"Open Ports: {open_ports}"

    return device_info


def scan_full_iot_network(progress_callback=None) -> List[Dict[str, Any]]:
    """
    全サブネットを走査し、ECHONET Lite UDPマルチキャストとTCPポート走査を統合して全デバイスを検出
    progress_callback: Callable[[float, str], None] (進捗率0.0〜1.0, メッセージ)
    """
    found_devices = []
    seen_ips = set()

    # Step 1: ECHONET Lite マルチキャスト探索 (高速 1.5秒)
    if progress_callback:
        progress_callback(0.05, "📡 Step 1/2: ECHONET Lite UDPマルチキャスト探索中 (224.0.23.0)...")
    print("[NetworkScanner] Running ECHONET Lite Multicast Discovery...")
    udp_devices = discover_echonet_multicast(timeout=1.5)
    for dev in udp_devices:
        found_devices.append(dev)
        seen_ips.add(dev["ip"])

    if progress_callback:
        progress_callback(0.20, f"📡 Step 1/2 完了: ECHONET Lite 機器 {len(udp_devices)} 台を発見 (エアコン・蓄電池等)")

    # Step 2: サブネット高速TCPスキャン
    network, _ = get_local_subnet()
    hosts = list(network.hosts())
    total_hosts = len(hosts)
    print(f"[NetworkScanner] Scanning subnet {network} for TCP services ({total_hosts} hosts)...")

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=60) as executor:
        futures = {executor.submit(check_ip_services, str(ip)): str(ip) for ip in hosts}
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            res = future.result()
            if res is not None:
                ip = res["ip"]
                if ip not in seen_ips:
                    found_devices.append(res)
                    seen_ips.add(ip)
                else:
                    # 既にUDPで検出されていた機器にTCPポート情報をマージ
                    for existing in found_devices:
                        if existing["ip"] == ip:
                            existing["ports"] = sorted(list(set(existing["ports"] + res["ports"])))
                            if res["protocol"] == "echonet_tcp":
                                existing["protocol"] = "echonet_tcp"
                                existing["category"] = "蓄電池 / V2H"
                                existing["register_as"] = "battery"

            if progress_callback and (completed % 15 == 0 or completed == total_hosts):
                pct = 0.20 + 0.78 * (completed / max(1, total_hosts))
                progress_callback(pct, f"🔍 Step 2/2: サブネット走査中 ({completed}/{total_hosts} IP完了) ... 検出計 {len(found_devices)} 台")

    found_devices = sorted(found_devices, key=lambda x: [int(b) for b in x["ip"].split(".")])
    if progress_callback:
        progress_callback(1.0, f"✅ スキャン完了！ 全 {len(found_devices)} 台の機器を検出しました。")
    return found_devices


def apply_device_to_config(ip: str, role: str, name: str = "") -> bool:
    """
    スキャンで検出された機器を設定ファイルにワンクリック適用する
    role: "battery" | "hems" | "aircon" | "appliance" | "lighting"
    """
    cm = get_config_manager()
    cfg = cm.load_config()

    if role == "battery":
        cfg["battery_system"]["ip_address"] = ip
        cfg["battery_system"]["enabled"] = True
        return cm.save_config(cfg)

    elif role == "hems":
        cfg["hems_controller"]["ip_address"] = ip
        cfg["hems_controller"]["enabled"] = True
        cfg["grid_measurement"]["source"] = "hems_web"
        cfg["grid_measurement"]["enabled"] = True
        return cm.save_config(cfg)

    elif role in ("aircon", "appliance", "lighting", "smart_plug", "tuya", "hub", "camera", "switch", "sensor"):
        if "smart_appliances" not in cfg or not isinstance(cfg["smart_appliances"], list):
            cfg["smart_appliances"] = []

        # 既存登録の重複チェック
        existing = [a for a in cfg["smart_appliances"] if a.get("ip_address") == ip]
        if not existing:
            role_labels = {
                "aircon": f"エアコン ({ip})",
                "smart_plug": f"スマートプラグ ({ip})",
                "lighting": f"スマート照明 ({ip})",
                "camera": f"ネットワークカメラ ({ip})",
                "switch": f"スマートスイッチ ({ip})",
                "tuya": f"Tuya機器 ({ip})",
                "hub": f"スマートハブ ({ip})",
                "sensor": f"スマートセンサー ({ip})",
                "appliance": f"スマート家電 ({ip})"
            }
            default_name = name or role_labels.get(role, f"スマート機器 ({ip})")
            cfg["smart_appliances"].append({
                "id": f"app_{ip.replace('.', '_')}",
                "name": default_name,
                "ip_address": ip,
                "category": role,
                "enabled": True
            })
            return cm.save_config(cfg)
        return True

    return False


def remove_appliance_from_config(ip: str) -> bool:
    """登録済み家電機器を設定から削除"""
    cm = get_config_manager()
    cfg = cm.load_config()
    if "smart_appliances" in cfg and isinstance(cfg["smart_appliances"], list):
        cfg["smart_appliances"] = [a for a in cfg["smart_appliances"] if a.get("ip_address") != ip]
        return cm.save_config(cfg)
    return False


# 互換用関数
def scan_local_network_for_echonet(timeout_sec=5):
    devs = scan_full_iot_network()
    return [{"ip": d["ip"], "type": d["name"], "port": d["ports"][0] if d["ports"] else 3610} for d in devs if d.get("category") == "蓄電池 / V2H"]

def auto_update_config_with_discovered_ip(config_path="config.yaml"):
    cm = get_config_manager()
    devs = scan_full_iot_network()
    bats = [d for d in devs if d.get("register_as") == "battery"]
    if bats:
        apply_device_to_config(bats[0]["ip"], "battery")
        return bats[0]
    return None
