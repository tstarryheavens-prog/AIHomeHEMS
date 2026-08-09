import socket

ip = "192.168.2.12"
port = 3610

def query_epc(epc):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((ip, port))
        # DEOJ: Storage battery (0x027D01)
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

print(f"=== Sweep all EPCs on Storage Battery 0x027D ===")
for epc in range(0x80, 0x100):
    res = query_epc(epc)
    if res is not None:
        val_u = int.from_bytes(res, byteorder='big', signed=False)
        val_s = int.from_bytes(res, byteorder='big', signed=True)
        print(f"EPC 0x{epc:02X}: len={len(res)} hex={res.hex()} u_int={val_u} s_int={val_s}")
