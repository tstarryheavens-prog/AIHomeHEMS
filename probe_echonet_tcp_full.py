import socket
import ipaddress
import concurrent.futures

def check_tcp_echonet(ip):
    # Test connection on TCP 3610
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    res = sock.connect_ex((str(ip), 3610))
    if res != 0:
        sock.close()
        return str(ip), None

    results = []

    # 1. Distribution Board (0x028701 / EPC 0xC0 - Number of channels, 0xC1 - Branch Instantaneous Power List)
    frame_c0 = bytes([0x10, 0x81, 0x00, 0x01, 0x05, 0xFF, 0x01, 0x02, 0x87, 0x01, 0x62, 0x01, 0xC0, 0x00])
    frame_c1 = bytes([0x10, 0x81, 0x00, 0x02, 0x05, 0xFF, 0x01, 0x02, 0x87, 0x01, 0x62, 0x01, 0xC1, 0x00])
    frame_e0 = bytes([0x10, 0x81, 0x00, 0x03, 0x05, 0xFF, 0x01, 0x02, 0x87, 0x01, 0x62, 0x01, 0xE0, 0x00]) # 主幹電力

    try:
        sock.sendall(frame_c0)
        d0 = sock.recv(512)
        results.append(f"Dist Board C0: {d0.hex()}")
    except Exception:
        pass

    try:
        sock.sendall(frame_c1)
        d1 = sock.recv(512)
        results.append(f"Dist Board C1: {d1.hex()}")
    except Exception:
        pass

    try:
        sock.sendall(frame_e0)
        de0 = sock.recv(512)
        results.append(f"Dist Board Main E0: {de0.hex()}")
    except Exception:
        pass

    sock.close()
    return str(ip), results

def main():
    print("=== Scanning 192.168.1.0/24 for TCP 3610 ECHONET Lite Distribution Board / Room Circuits ===")
    network = ipaddress.ip_network("192.168.1.0/24", strict=False)
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_tcp_echonet, ip): ip for ip in network.hosts()}
        for future in concurrent.futures.as_completed(futures):
            ip_str, res = future.result()
            if res:
                print(f"[FOUND ECHONET TCP 3610] {ip_str}: {res}")

if __name__ == "__main__":
    main()
