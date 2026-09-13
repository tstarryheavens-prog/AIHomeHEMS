import socket
import struct
import random
import time

# ECHONET Lite Constant definitions
ENET_PORT = 3610
EHD1_ECHONET_LITE = 0x10
EHD2_FORMAT_1 = 0x81

# Class group and code
CLASS_STORAGE_BATTERY = bytes([0x02, 0x7D, 0x01])  # 住宅用蓄電池システム
CLASS_SOLAR_PV        = bytes([0x02, 0x79, 0x01])  # 住宅用太陽光発電システム
CLASS_CONTROLLER      = bytes([0x05, 0xFF, 0x01])  # コントローラ

# OPC Services
ESV_GET_RES = 0x72
ESV_GET_REQ = 0x62
ESV_SET_C_REQ = 0x61 # Write request

# Property Codes (EPC)
EPC_OPERATING_STATUS   = 0x80 # 動作状態 (0x30: ON)
EPC_BATTERY_SOC        = 0xE7 # 蓄電池残量SOC (%)
EPC_BATTERY_POWER      = 0xD3 # 蓄電/放電電力 (W)
EPC_BATTERY_MODE       = 0xDA # 運転モード
EPC_BATTERY_WH         = 0xE2 # 蓄電池残容量 (Wh)
EPC_CUM_DISCHARGE_KWH  = 0xE4 # 累積放電電力量 (kWh)
EPC_CUM_CHARGE_KWH     = 0xE5 # 累積充電電力量 (kWh)
EPC_PV_POWER           = 0xE0 # 太陽光瞬時発電電力 (W)
EPC_CUM_PV_KWH         = 0xE1 # 太陽光累積発電電力量 (0.1kWh)

class NichiconEchonetClient:
    def __init__(self, ip_address="192.168.1.200", port=3610, enabled=True):
        self.ip_address = ip_address
        self.port = port
        self.enabled = enabled
        self.tid = 1

    def _build_frame(self, seoj, deoj, esv, epc, edt=bytes()):
        tid_bytes = struct.pack(">H", self.tid)
        self.tid = (self.tid + 1) % 65535
        pdc = len(edt)
        return bytes([EHD1_ECHONET_LITE, EHD2_FORMAT_1]) + tid_bytes + seoj + deoj + bytes([esv, 1, epc, pdc]) + edt

    def _query(self, deoj, epc):
        """
        ニチコンT5固有仕様: 独自拡張 TCP/IP (Port 3610 / 1369) 専用通信
        """
        ports_to_try = [self.port, 3610, 1369]
        for p in dict.fromkeys(ports_to_try):
            for retry in range(2):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3.0) # ニチコン基板応答用の安全タイムアウト
                    sock.connect((self.ip_address, p))
                    frame = self._build_frame(CLASS_CONTROLLER, deoj, ESV_GET_REQ, epc)
                    sock.sendall(frame)
                    data = sock.recv(1024)
                    sock.close()
                    if len(data) >= 14 and data[10] in (0x72, 0x52):
                        pdc = data[13]
                        return data[14:14+pdc]
                except Exception:
                    time.sleep(0.2)
        return None

    def get_full_system_info(self):
        """
        ニチコンT5・太陽光発電から全メトリクス（SOC, 充放電W, PV瞬時W, PV累積kWh, 蓄電池容量Wh）を取得
        """
        if not self.enabled:
            return {
                "connected": False,
                "is_mock": True,
                "soc": 60,
                "power_w": 0,
                "battery_wh": 6600,
                "pv_w": 1200,
                "cum_pv_kwh": 6899.8,
                "cum_discharge_kwh": 86,
                "cum_charge_kwh": 100,
                "mode": "AUTO"
            }

        # 1. 蓄電池データ取得 (Class 0x027D)
        edt_soc = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_SOC)
        edt_pow = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_POWER)
        edt_mode = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_MODE)
        edt_wh = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_WH)
        edt_rated = self._query(CLASS_STORAGE_BATTERY, 0xD0) # 定格容量Wh (EPC 0xD0)
        edt_dis = self._query(CLASS_STORAGE_BATTERY, EPC_CUM_DISCHARGE_KWH)
        edt_cha = self._query(CLASS_STORAGE_BATTERY, EPC_CUM_CHARGE_KWH)

        # 2. 太陽光データ取得 (Class 0x0279)
        edt_pv_w = self._query(CLASS_SOLAR_PV, EPC_PV_POWER)
        edt_pv_cum = self._query(CLASS_SOLAR_PV, EPC_CUM_PV_KWH)

        pow_val = int.from_bytes(edt_pow, byteorder='big', signed=True) if edt_pow else 0
        wh_val = int.from_bytes(edt_wh, byteorder='big') if edt_wh else 0
        rated_wh_val = int.from_bytes(edt_rated, byteorder='big') if edt_rated else 14960
        dis_val = int.from_bytes(edt_dis, byteorder='big') if edt_dis else 0
        cha_val = int.from_bytes(edt_cha, byteorder='big') if edt_cha else 0

        # ニチコンT5固有処理: 
        # EPC 0xE7 は Nichicon T5 実機仕様により無効値 0x3B9AC9FF (999999999) を返します。
        # したがって、残容量Wh (EPC 0xE2) と 14.9kWh (定格 14,900 Wh) から正確な SOC% を物理演算算出します。
        soc_val = None
        if edt_soc and len(edt_soc) == 1:
            raw_b = edt_soc[0]
            if 0 <= raw_b <= 100:
                soc_val = raw_b

        if soc_val is None:
            # 14.9kWh ニチコンT5 蓄電池容量 (14900 Wh)
            capacity_wh = 14900
            if wh_val >= 0 and edt_wh is not None:
                soc_val = min(100, max(0, int(round((wh_val / float(capacity_wh)) * 100))))
            else:
                soc_val = 15

        pv_w_val = int.from_bytes(edt_pv_w, byteorder='big') if edt_pv_w else 0
        pv_cum_val = (int.from_bytes(edt_pv_cum, byteorder='big') / 10.0) if edt_pv_cum else 0.0

        mode_code = edt_mode[0] if edt_mode else 0x45
        if mode_code == 0x42:
            mode_str = "CHARGE"
        elif mode_code == 0x43:
            mode_str = "DISCHARGE"
        elif mode_code == 0x44:
            mode_str = "STANDBY"
        elif mode_code == 0x45:
            mode_str = "AUTO"
        else:
            mode_str = f"UNKNOWN ({hex(mode_code)})"


        # 3. 系統買電・売電電力
        # ※ニチコンT5 ECHONET Lite (Class 0x027D) は蓄電池本体プロトコルであり、系統買電量(EPC 0xE0)は実装されていないため、
        # 買電・売電実測値はHEMS Web (e-flow.html の tTradeData) より正確に取得します。
        return {
            "connected": True,
            "is_mock": False,
            "soc": soc_val,
            "power_w": pow_val,
            "battery_wh": wh_val,
            "pv_w": pv_w_val,
            "grid_w": None,
            "cum_pv_kwh": round(pv_cum_val, 1),
            "cum_discharge_kwh": dis_val,
            "cum_charge_kwh": cha_val,
            "mode": mode_str
        }

    def set_battery_mode(self, mode_code):
        if not self.enabled:
            return True
        ports_to_try = [self.port, 3610, 1369]
        for p in dict.fromkeys(ports_to_try):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((self.ip_address, p))
                frame = self._build_frame(CLASS_CONTROLLER, CLASS_STORAGE_BATTERY, ESV_SET_C_REQ, EPC_BATTERY_MODE, bytes([mode_code]))
                sock.sendall(frame)
                data = sock.recv(1024)
                sock.close()
                return True
            except Exception:
                pass
        return False

    def set_battery_timer_schedule(
        self, 
        charge_start_h=3, charge_start_m=0, 
        charge_end_h=6, charge_end_m=30,
        discharge_start_h=6, discharge_start_m=35,
        discharge_end_h=2, discharge_end_m=55
    ):
        """
        スマホアプリと同等：ニチコンT5実機の内部基板タイマーへ
        1. 充電開始時間 (EPC 0xC3) & 充電終了時間 (EPC 0xC4)
        2. 放電開始時間 (EPC 0xC5) & 放電終了時間 (EPC 0xC6)
        を5分間の切替インターバル(バッファ)を確保して直接書き込み保存。
        """
        if not self.enabled:
            return True
        ports_to_try = [self.port, 3610, 1369]
        for p in dict.fromkeys(ports_to_try):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((self.ip_address, p))
                
                # 1. タイマー設定を有効化 (EPC 0xC2 = 0x30 ON)
                f1 = self._build_frame(CLASS_CONTROLLER, CLASS_STORAGE_BATTERY, ESV_SET_C_REQ, 0xC2, bytes([0x30]))
                sock.sendall(f1)
                try: sock.recv(512)
                except Exception: pass
                
                # 2. 充電開始時間設定 (EPC 0xC3)
                f2 = self._build_frame(CLASS_CONTROLLER, CLASS_STORAGE_BATTERY, ESV_SET_C_REQ, 0xC3, bytes([int(charge_start_h), int(charge_start_m)]))
                sock.sendall(f2)
                try: sock.recv(512)
                except Exception: pass
                
                # 3. 充電終了時間設定 (EPC 0xC4)
                f3 = self._build_frame(CLASS_CONTROLLER, CLASS_STORAGE_BATTERY, ESV_SET_C_REQ, 0xC4, bytes([int(charge_end_h), int(charge_end_m)]))
                sock.sendall(f3)
                try: sock.recv(512)
                except Exception: pass
                
                # 4. 放電開始時間設定 (EPC 0xC5)
                f4 = self._build_frame(CLASS_CONTROLLER, CLASS_STORAGE_BATTERY, ESV_SET_C_REQ, 0xC5, bytes([int(discharge_start_h), int(discharge_start_m)]))
                sock.sendall(f4)
                try: sock.recv(512)
                except Exception: pass

                # 5. 放電終了時間設定 (EPC 0xC6)
                f5 = self._build_frame(CLASS_CONTROLLER, CLASS_STORAGE_BATTERY, ESV_SET_C_REQ, 0xC6, bytes([int(discharge_end_h), int(discharge_end_m)]))
                sock.sendall(f5)
                try: sock.recv(512)
                except Exception: pass

                sock.close()
                return True
            except Exception:
                pass
        return False

if __name__ == "__main__":
    client = NichiconEchonetClient(enabled=True)
    info = client.get_full_system_info()
    print("Full Nichicon System Info:", info)
