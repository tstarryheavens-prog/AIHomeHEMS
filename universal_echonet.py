"""
universal_echonet.py - 汎用 ECHONET Lite / マルチメーカー対応クライアント
ECHONET Lite標準仕様 (一般社団法人エコーネットコンソーシアム規格) 準拠
国内主要蓄電池（ニチコン TCP、パナソニック/オムロン/シャープ/ダイヤゼブラ UDP 3610）に統合対応
"""

import socket
import struct
import random
import time
from typing import Dict, Any, Optional

from presets_jp import BATTERY_MANUFACTURERS

# ECHONET Lite Header Constants
ENET_PORT = 3610
EHD1_ECHONET_LITE = 0x10
EHD2_FORMAT_1 = 0x81

# Class Objects
CLASS_STORAGE_BATTERY = bytes([0x02, 0x7D, 0x01])  # 住宅用蓄電池システム
CLASS_SOLAR_PV        = bytes([0x02, 0x79, 0x01])  # 住宅用太陽光発電システム
CLASS_SMART_METER     = bytes([0x02, 0x88, 0x01])  # 低圧スマート電力量メータ
CLASS_CONTROLLER      = bytes([0x05, 0xFF, 0x01])  # コントローラ
CLASS_NODE_PROFILE    = bytes([0x0E, 0xF0, 0x01])  # ノードプロファイル

# OPC Services
ESV_SET_I_REQ = 0x60 # 書き込み (通知なし)
ESV_SET_C_REQ = 0x61 # 書き込み (応答要)
ESV_GET_REQ   = 0x62 # 読み出し要求
ESV_SET_RES   = 0x71 # 書き込み応答
ESV_GET_RES   = 0x72 # 読み出し応答
ESV_INF       = 0x73 # 通知
ESV_INFC      = 0x74 # 通知 (要応答)
ESV_SET_GET_REQ = 0x6E # 一括読み書き

# Standard Property Codes (EPC)
EPC_OPERATING_STATUS   = 0x80 # 動作状態 (0x30: ON, 0x31: OFF)
EPC_BATTERY_RATED_WH   = 0xD0 # 定格蓄電容量 (Wh)
EPC_BATTERY_POWER      = 0xD3 # 蓄電/放電電力 (W, signed 32bit or 16bit)
EPC_BATTERY_MODE       = 0xDA # 運転モード
EPC_BATTERY_WH         = 0xE2 # 蓄電池残容量 (Wh)
EPC_CUM_DISCHARGE_KWH  = 0xE4 # 累積放電電力量 (kWh)
EPC_CUM_CHARGE_KWH     = 0xE5 # 累積充電電力量 (kWh)
EPC_BATTERY_SOC        = 0xE7 # 蓄電池残量SOC (%)

# Solar PV EPCs
EPC_PV_POWER           = 0xE0 # 太陽光瞬時発電電力 (W)
EPC_CUM_PV_KWH         = 0xE1 # 太陽光累積発電電力量 (0.1kWh)

# Smart Meter EPCs
EPC_METER_INST_POWER   = 0xE7 # 瞬時電力計測値 (W)
EPC_METER_CUM_NORMAL   = 0xE0 # 積算電力量計測値 (正方向/買電 0.1kWh)
EPC_METER_CUM_REVERSE  = 0xE3 # 積算電力量計測値 (逆方向/売電 0.1kWh)

# Hardware Timer EPCs (Nichicon等)
EPC_CHARGE_TIMER_SETTING    = 0xC3 # 充電開始/終了時刻
EPC_DISCHARGE_TIMER_SETTING = 0xC4 # 放電開始/終了時刻


class UniversalEchonetClient:
    """
    国内全メーカー対応 汎用ECHONET Liteクライアント
    - TCP (ニチコン T5系)
    - UDP (パナソニック, オムロン, ダイヤゼブラ, シャープ, 京セラ, 長州産業, 汎用ECHONET)
    - Mock / シミュレーション
    """

    def __init__(
        self,
        ip_address: str = "192.168.1.200",
        port: int = 3610,
        manufacturer: str = "nichicon",
        enabled: bool = True,
        capacity_kwh: Optional[float] = None
    ):
        self.ip_address = ip_address
        self.port = port
        self.manufacturer = manufacturer
        self.enabled = enabled
        self.tid = 1

        # メーカー仕様プロファイルの取得
        self.profile = BATTERY_MANUFACTURERS.get(
            manufacturer,
            BATTERY_MANUFACTURERS["generic_echonet"]
        )
        self.protocol = self.profile.get("protocol", "echonet_udp")
        self.capacity_kwh = float(capacity_kwh) if capacity_kwh else float(self.profile.get("default_capacity_kwh", 14.9))
        self._cache_time = 0.0
        self._cache_info = None

    def _next_tid(self) -> bytes:
        tid_bytes = struct.pack(">H", self.tid)
        self.tid = (self.tid + 1) % 65535
        if self.tid == 0:
            self.tid = 1
        return tid_bytes

    def _build_frame(self, seoj: bytes, deoj: bytes, esv: int, epc: int, edt: bytes = bytes()) -> bytes:
        """ECHONET Lite 通信電文 (Format 1) を生成"""
        tid_bytes = self._next_tid()
        pdc = len(edt)
        return bytes([EHD1_ECHONET_LITE, EHD2_FORMAT_1]) + tid_bytes + seoj + deoj + bytes([esv, 1, epc, pdc]) + edt

    def _query(self, deoj: bytes, epc: int) -> Optional[bytes]:
        """
        機器へEPCのGet要求を送信してEDT（応答データ）を取得する
        プロトコル（TCP / UDP）を自動判別
        """
        if not self.enabled:
            return None

        # 1. TCP 通信 (ニチコン T5系 等)
        if self.protocol == "echonet_tcp":
            ports_to_try = [self.port, 3610, 1369]
            for p in dict.fromkeys(ports_to_try):
                for retry in range(2):
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2.5)
                        sock.connect((self.ip_address, p))
                        frame = self._build_frame(CLASS_CONTROLLER, deoj, ESV_GET_REQ, epc)
                        sock.sendall(frame)
                        data = sock.recv(1024)
                        sock.close()
                        if len(data) >= 14 and data[10] in (ESV_GET_RES, 0x52):
                            pdc = data[13]
                            return data[14:14+pdc]
                    except Exception:
                        time.sleep(0.15)
            return None

        # 2. UDP 通信 (国内標準ECHONET Lite: パナソニック, オムロン, シャープ等)
        elif self.protocol == "echonet_udp":
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.0)
            frame = self._build_frame(CLASS_CONTROLLER, deoj, ESV_GET_REQ, epc)
            try:
                sock.sendto(frame, (self.ip_address, self.port))
                data, _ = sock.recvfrom(1024)
                sock.close()
                if len(data) >= 14 and data[10] in (ESV_GET_RES, 0x52):
                    pdc = data[13]
                    return data[14:14+pdc]
            except Exception:
                sock.close()
            return None

        # 3. その他 / テスラAPI等の拡張余地
        return None

    def _write(self, deoj: bytes, epc: int, edt: bytes) -> bool:
        """機器へEPCのSetC要求を送信して設定を変更する"""
        if not self.enabled:
            return True

        if self.protocol == "echonet_tcp":
            ports_to_try = [self.port, 3610, 1369]
            for p in dict.fromkeys(ports_to_try):
                for retry in range(3):
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(3.0)
                        sock.connect((self.ip_address, p))
                        frame = self._build_frame(CLASS_CONTROLLER, deoj, ESV_SET_C_REQ, epc, edt)
                        sock.sendall(frame)
                        data = sock.recv(1024)
                        sock.close()
                        if len(data) >= 12 and data[10] in (ESV_SET_RES, 0x51):
                            return True
                    except Exception:
                        time.sleep(0.2)
            return False

        elif self.protocol == "echonet_udp":
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.5)
            frame = self._build_frame(CLASS_CONTROLLER, deoj, ESV_SET_C_REQ, epc, edt)
            try:
                sock.sendto(frame, (self.ip_address, self.port))
                data, _ = sock.recvfrom(1024)
                sock.close()
                if len(data) >= 12 and data[10] in (ESV_SET_RES, 0x51):
                    return True
            except Exception:
                sock.close()
            return False

        return False

    def get_full_system_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        蓄電池・太陽光発電から全メトリクス（SOC, 充放電W, PV瞬時W, PV累積kWh, 蓄電池容量Wh）を取得
        """
        now = time.time()
        if not force_refresh and self._cache_info and (now - self._cache_time < 3.0):
            return self._cache_info

        if not self.enabled or self.protocol == "mock":
            # モック / デモモード用の自然なシミュレーション値
            hour = time.localtime().tm_hour
            is_solar_time = (6 <= hour <= 18)
            pv_w = random.randint(1200, 3800) if is_solar_time else 0
            soc = random.randint(45, 95)
            mock_res = {
                "connected": False,
                "is_mock": True,
                "manufacturer": self.manufacturer,
                "soc": soc,
                "power_w": 800 if pv_w > 0 else -1200,
                "battery_wh": int(self.capacity_kwh * 1000 * (soc / 100.0)),
                "pv_w": pv_w,
                "cum_pv_kwh": 7120.5,
                "cum_discharge_kwh": 140,
                "cum_charge_kwh": 160,
                "mode": "AUTO"
            }
            self._cache_time = now
            self._cache_info = mock_res
            return mock_res

        # 1. 蓄電池データ取得 (Class 0x027D)
        edt_soc = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_SOC)
        edt_pow = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_POWER)
        edt_mode = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_MODE)
        edt_wh = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_WH)
        edt_rated = self._query(CLASS_STORAGE_BATTERY, EPC_BATTERY_RATED_WH)
        edt_dis = self._query(CLASS_STORAGE_BATTERY, EPC_CUM_DISCHARGE_KWH)
        edt_cha = self._query(CLASS_STORAGE_BATTERY, EPC_CUM_CHARGE_KWH)

        # 2. 太陽光データ取得 (Class 0x0279)
        edt_pv_w = self._query(CLASS_SOLAR_PV, EPC_PV_POWER)
        edt_pv_cum = self._query(CLASS_SOLAR_PV, EPC_CUM_PV_KWH)

        pow_val = int.from_bytes(edt_pow, byteorder='big', signed=True) if edt_pow else 0
        wh_val = int.from_bytes(edt_wh, byteorder='big') if edt_wh else 0
        default_rated_wh = int(self.capacity_kwh * 1000)
        rated_wh_val = int.from_bytes(edt_rated, byteorder='big') if edt_rated else default_rated_wh
        if rated_wh_val <= 0:
            rated_wh_val = default_rated_wh

        # 💡 SOC (%) の判定と正確な算出
        # ECHONET Lite標準仕様 (EPC 0xE7) は 1バイト unsigned char (0〜100%)。
        # ニチコンT5系など一部の実機では EPC 0xE7 が未実装で、4バイト無効値 0x3B9AC9FF (999,999,999) を返します。
        # 単純に edt_soc[0] を参照すると 0x3B (= 59%) と誤認されるため、データ長と有効範囲(0〜100)を厳密にチェックします。
        soc_val = None
        if edt_soc:
            if len(edt_soc) == 1:
                v1 = edt_soc[0]
                if 0 <= v1 <= 100:
                    soc_val = v1
            elif len(edt_soc) == 2:
                v2 = int.from_bytes(edt_soc, byteorder='big')
                if 0 <= v2 <= 100:
                    soc_val = v2

        # EPC 0xE7 が無効値（4バイト 0x3B9AC9FF 等）または未取得の場合:
        # 残容量Wh (EPC 0xE2) と定格容量 (rated_wh_val) から物理演算で真のSOCを算出
        if soc_val is None:
            if edt_wh is not None and rated_wh_val > 0:
                soc_val = min(100, max(0, int(round((wh_val / float(rated_wh_val)) * 100.0))))
            else:
                soc_val = 20  # 安全フォールバック

        raw_mode = edt_mode[0] if edt_mode else 0x45
        mode_str = "AUTO"
        if raw_mode == 0x42:
            mode_str = "CHARGE"
        elif raw_mode == 0x43:
            mode_str = "DISCHARGE"
        elif raw_mode == 0x44:
            mode_str = "STANDBY"

        pv_w_val = int.from_bytes(edt_pv_w, byteorder='big') if edt_pv_w else 0
        pv_cum_val = (int.from_bytes(edt_pv_cum, byteorder='big') * 0.1) if edt_pv_cum else 0.0

        cum_dis_val = int.from_bytes(edt_dis, byteorder='big') if edt_dis else 0
        cum_cha_val = int.from_bytes(edt_cha, byteorder='big') if edt_cha else 0

        is_connected = bool(edt_soc is not None or edt_pow is not None or edt_mode is not None or edt_wh is not None)

        res = {
            "connected": is_connected,
            "is_mock": False,
            "manufacturer": self.manufacturer,
            "soc": soc_val,
            "power_w": pow_val,
            "battery_wh": wh_val,
            "rated_wh": rated_wh_val,
            "mode": mode_str,
            "raw_mode": hex(raw_mode),
            "pv_w": pv_w_val,
            "cum_pv_kwh": round(pv_cum_val, 1),
            "cum_discharge_kwh": cum_dis_val,
            "cum_charge_kwh": cum_cha_val
        }
        self._cache_time = now
        self._cache_info = res
        return res

    def set_battery_mode(self, target_mode: int) -> bool:
        """
        蓄電池の運転モードを変更する
        0x42: 急速充電 / 強制充電
        0x43: 自家消費 / 放電優先
        0x44: 待機
        0x45: 自動 / グリーンモード
        """
        self._cache_info = None  # キャッシュ無効化
        if not self.enabled or self.protocol == "mock":
            return True
        return self._write(CLASS_STORAGE_BATTERY, EPC_BATTERY_MODE, bytes([target_mode]))

    def set_battery_timer_schedule(
        self,
        charge_start_h: int = 3, charge_start_m: int = 0,
        charge_end_h: int = 6, charge_end_m: int = 30,
        discharge_start_h: int = 6, discharge_start_m: int = 35,
        discharge_end_h: int = 21, discharge_end_m: int = 0
    ) -> bool:
        """
        ハードウェア内部タイマー (EPC 0xC3/0xC4) への時刻スケジュール同期 (ニチコン等対応機種)
        """
        if not self.enabled or not self.profile.get("supports_timer_sync", False):
            return True

        c_data = bytes([charge_start_h, charge_start_m, charge_end_h, charge_end_m])
        d_data = bytes([discharge_start_h, discharge_start_m, discharge_end_h, discharge_end_m])

        res_c = self._write(CLASS_STORAGE_BATTERY, EPC_CHARGE_TIMER_SETTING, c_data)
        res_d = self._write(CLASS_STORAGE_BATTERY, EPC_DISCHARGE_TIMER_SETTING, d_data)
        return res_c and res_d


# 互換用エイリアス
NichiconEchonetClient = UniversalEchonetClient
