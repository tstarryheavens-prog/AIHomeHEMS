import socket

ip = "192.168.2.12"
port = 3610

def query_epc(deoj, epc):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((ip, port))
        frame = bytes([0x10, 0x81, 0x00, 0x01, 0x05, 0xFF, 0x01]) + deoj + bytes([0x62, 0x01, epc, 0x00])
        s.sendall(frame)
        data = s.recv(1024)
        s.close()
        if len(data) >= 14 and data[10] in (0x72, 0x52):
            return data[14:14+data[13]]
    except Exception:
        pass
    return None

# Test Distribution Board 0x028701 with various EPCs
print("=== Probing Distribution Board 0x028701 EPCs ===")
deoj = bytes([0x02, 0x87, 0x01])
for epc in range(0x80, 0xFF):
    edt = query_epc(deoj, epc)
    if edt is not None:
        print(f"  0x028701 EPC 0x{epc:02X} -> HEX: {edt.hex()}")

# Test Metering Unit 0x028801 with various EPCs
print("=== Probing Metering Unit 0x028801 EPCs ===")
deoj = bytes([0x02, 0x88, 0x01])
for epc in range(0x80, 0xFF):
    edt = query_epc(deoj, epc)
    if edt is not None:
        print(f"  0x028801 EPC 0x{epc:02X} -> HEX: {edt.hex()}")
