import socket
import ipaddress
import concurrent.futures

def scan_ip_echonet(ip):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    
    # Send Get Self Node Instance List (0x0EF001 / EPC 0xD6)
    frame_node = bytes([0x10, 0x81, 0x00, 0x01, 0x05, 0xFF, 0x01, 0x0E, 0xF0, 0x01, 0x62, 0x01, 0xD6, 0x00])
    
    found_info = []
    try:
        sock.sendto(frame_node, (str(ip), 1369))
        data, _ = sock.recvfrom(1024)
        found_info.append(f"Node Profile Response: {data.hex()}")
    except Exception:
        pass
        
    # Also test Distribution Board (0x028701 / EPC 0xC0)
    frame_dist = bytes([0x10, 0x81, 0x00, 0x02, 0x05, 0xFF, 0x01, 0x02, 0x87, 0x01, 0x62, 0x01, 0xC0, 0x00])
    try:
        sock.sendto(frame_dist, (str(ip), 1369))
        data, _ = sock.recvfrom(1024)
        found_info.append(f"Distribution Board Response: {data.hex()}")
    except Exception:
        pass

    sock.close()
    if found_info:
        return str(ip), found_info
    return str(ip), None

def main():
    print("=== Scanning 192.168.2.0/24 for ECHONET Lite UDP 1369 (Distribution Board / Metering) ===")
    network = ipaddress.ip_network("192.168.2.0/24", strict=False)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(scan_ip_echonet, ip): ip for ip in network.hosts()}
        for future in concurrent.futures.as_completed(futures):
            ip_str, res = future.result()
            if res:
                print(f"[FOUND ECHONET UDP] {ip_str}: {res}")

if __name__ == "__main__":
    main()
