import socket
import ipaddress
import concurrent.futures
import yaml
from echonet_nichicon import CLASS_CONTROLLER, CLASS_STORAGE_BATTERY, ESV_GET_REQ, EPC_BATTERY_SOC, EHD1_ECHONET_LITE, EHD2_FORMAT_1

ENET_PORT = 1369

def get_local_ip():
    """ローカルマシン自身のプライベートIPアドレスを取得する"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "192.168.1.15"

def check_echonet_tcp_device(ip_str):
    """指定したIPのポート3610/1369(TCP)に接続を試み、ニチコン/ECHONET機器か判定する"""
    for port in [3610, 1369]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.4)
            res = sock.connect_ex((ip_str, port))
            if res == 0:
                sock.close()
                return ip_str, True, f"Nichicon T5 ESS (ECHONET Lite TCP Port {port})", port
            sock.close()
        except Exception:
            pass
    return ip_str, False, None, None

def scan_local_network_for_echonet(timeout_sec=5):
    """
    ローカルサブネット(/24)をマルチスレッドで高速スキャンし、ニチコンT5等のECHONET Lite機器を自動発見する
    """
    local_ip = get_local_ip()
    network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
    
    print(f"[NetworkScanner] Starting auto-scan on subnet {network} (Local IP: {local_ip})...")
    
    found_devices = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_echonet_tcp_device, str(ip)): ip for ip in network.hosts()}
        for future in concurrent.futures.as_completed(futures):
            ip_str, is_found, device_type, port = future.result()
            if is_found:
                print(f"[NetworkScanner] Found device at {ip_str}:{port} ({device_type})")
                found_devices.append({
                    "ip": ip_str,
                    "type": device_type,
                    "port": port
                })
                
    return found_devices

def auto_update_config_with_discovered_ip(config_path="config.yaml"):
    """発見された機器のIPを config.yaml に自動反映する"""
    devices = scan_local_network_for_echonet()
    if not devices:
        print("[NetworkScanner] No ECHONET Lite TCP devices discovered.")
        return None
        
    first_device = devices[0]
    discovered_ip = first_device["ip"]
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            
        config["nichicon"]["ip_address"] = discovered_ip
        config["nichicon"]["enabled"] = True
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
            
        print(f"[NetworkScanner] Updated config.yaml with Nichicon IP: {discovered_ip}")
        return first_device
    except Exception as e:
        print(f"[NetworkScanner] Error updating config: {e}")
        return first_device

if __name__ == "__main__":
    result = auto_update_config_with_discovered_ip()
    print("Scan result:", result)
