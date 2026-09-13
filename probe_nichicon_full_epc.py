import socket

ip = "192.168.1.200"
port = 3610

def query_epc(deoj, epc):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect((ip, port))
        
        # Frame: EHD1(0x10) EHD2(0x81) TID(0x0001) SEOJ(0x05FF01) DEOJ ESV(0x62) OPC(1) EPC PDC(0)
        frame = bytes([0x10, 0x81, 0x00, 0x01, 0x05, 0xFF, 0x01]) + deoj + bytes([0x62, 0x01, epc, 0x00])
        s.sendall(frame)
        data = s.recv(1024)
        s.close()
        
        if len(data) >= 14 and data[10] in (0x72, 0x52): # Get_Res
            pdc = data[13]
            edt = data[14:14+pdc]
            return edt
    except Exception as e:
        pass
    return None

classes = [
    ("Storage Battery 0x027D", bytes([0x02, 0x7D, 0x01]), [
        (0x80, "Operating Status"),
        (0xE7, "SOC %"),
        (0xD3, "Charge/Discharge Power W"),
        (0xDA, "Operating Mode"),
        (0xE2, "Remaining Capacity Wh"),
        (0xE4, "Cumulative Discharge kWh"),
        (0xE5, "Cumulative Charge kWh"),
    ]),
    ("Solar PV 0x0279", bytes([0x02, 0x79, 0x01]), [
        (0x80, "Operating Status"),
        (0xE0, "PV Instantaneous Power W"),
        (0xE1, "Cumulative PV Generation kWh"),
    ]),
    ("Distribution Board 0x0287", bytes([0x02, 0x87, 0x01]), [
        (0xC0, "Branch Channels Count"),
        (0xC1, "Branch Instantaneous Power W List"),
        (0xC2, "Branch Cumulative Energy kWh List"),
        (0xE0, "Main Grid Power W"),
    ]),
    ("Metering Unit 0x0288", bytes([0x02, 0x88, 0x01]), [
        (0xE0, "Cumulative Buy Energy kWh"),
        (0xE3, "Cumulative Sell Energy kWh"),
        (0xE7, "Instantaneous Power W"),
    ])
]

print(f"=== Deep EPC Inspection on {ip}:{port} ===")
for class_name, deoj, epcs in classes:
    print(f"\n[{class_name}]")
    for epc, epc_name in epcs:
        edt = query_epc(deoj, epc)
        if edt is not None:
            # Parse raw bytes / int
            val_int = int.from_bytes(edt, byteorder='big', signed=(epc in [0xD3, 0xE7]))
            print(f"  EPC 0x{epc:02X} ({epc_name}): HEX={edt.hex()} -> INT={val_int}")
        else:
            print(f"  EPC 0x{epc:02X} ({epc_name}): No response")
