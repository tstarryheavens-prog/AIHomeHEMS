import socket

ip = "192.168.1.200"
port = 3610

def query_epc(epc):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect((ip, port))
        deoj = bytes([0x02, 0x7D, 0x01])
        frame = bytes([0x10, 0x81, 0x00, 0x01, 0x05, 0xFF, 0x01]) + deoj + bytes([0x62, 0x01, epc, 0x00])
        s.sendall(frame)
        data = s.recv(1024)
        s.close()
        if len(data) >= 14 and data[10] in (0x72, 0x52):
            pdc = data[13]
            return data[14:14+pdc]
    except Exception:
        pass
    return None

timers = [
    (0xC2, "Timer Enable Status"),
    (0xC3, "Charge Start Time"),
    (0xC4, "Charge End Time"),
    (0xC5, "Discharge Start Time"),
    (0xC6, "Discharge End Time"),
]

for epc, name in timers:
    edt = query_epc(epc)
    if edt:
        print(f"EPC 0x{epc:02X} ({name}): len={len(edt)} hex={edt.hex()}")
    else:
        print(f"EPC 0x{epc:02X} ({name}): No response")
