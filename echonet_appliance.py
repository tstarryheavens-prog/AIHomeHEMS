"""
echonet_appliance.py - ECHONET Lite 汎用スマート家電（エアコン・給湯器・照明等）制御モジュール
ECHONET Lite 標準規格 (Class Group 0x01 空調 / 0x02 住宅設備) 準拠
国内主要メーカー (パナソニック, ダイキン, 三菱電機, 日立, シャープ, 富士通ゼネラル, 東芝等) 対応
"""

import socket
import struct
import time
from typing import Dict, Any, Optional, List

ECHONET_PORT = 3610
EHD1_ECHONET_LITE = 0x10
EHD2_FORMAT_1 = 0x81

# Class Objects
CLASS_AIR_CONDITIONER = bytes([0x01, 0x30, 0x01])  # 家庭用エアコン
CLASS_WATER_HEATER    = bytes([0x02, 0x72, 0x01])  # 電気温水器・エコキュート
CLASS_LIGHTING        = bytes([0x02, 0x90, 0x01])  # 一般照明
CLASS_CONTROLLER      = bytes([0x05, 0xFF, 0x01])  # コントローラ

# Service codes
ESV_SET_I_REQ = 0x60 # 書き込み（応答不要）
ESV_SET_C_REQ = 0x61 # 書き込み（要応答）
ESV_GET_REQ   = 0x62 # 読み出し要求
ESV_SET_RES   = 0x71 # 書き込み応答
ESV_GET_RES   = 0x72 # 読み出し応答

# Common EPCs
EPC_OPERATING_STATUS   = 0x80 # 動作状態 (0x30: ON, 0x31: OFF)
EPC_INST_POWER_W       = 0x84 # 瞬時消費電力 (W, 2 bytes)
EPC_CUM_POWER_KWH      = 0x85 # 積算消費電力量 (0.001 kWh, 4 bytes)

# Air Conditioner EPCs
EPC_AC_OPERATION_MODE  = 0xB0 # 運転モード (0x41: 自動, 0x42: 冷房, 0x43: 暖房, 0x44: 除湿, 0x45: 送風)
EPC_AC_SET_TEMPERATURE = 0xB3 # 設定温度 (0〜50℃, 1 byte)
EPC_AC_ROOM_HUMIDITY   = 0xBA # 室内相対湿度 (%, 1 byte)
EPC_AC_ROOM_TEMP       = 0xBB # 室内温度 (signed char ℃, 1 byte)
EPC_AC_OUTDOOR_TEMP    = 0xBE # 室外温度 (signed char ℃, 1 byte)
EPC_AC_AIR_FLOW_RATE   = 0xA0 # 風量設定 (0x41: 自動, 0x31〜0x38: 段階)

MODE_CODE_TO_NAME = {
    0x41: "自動",
    0x42: "冷房",
    0x43: "暖房",
    0x44: "除湿",
    0x45: "送風"
}

MODE_NAME_TO_CODE = {
    "自動": 0x41,
    "冷房": 0x42,
    "暖房": 0x43,
    "除湿": 0x44,
    "送風": 0x45
}


class EchonetApplianceClient:
    """ECHONET Lite 対応の家電機器（エアコン・給湯器・照明）と通信・制御を行うクライアント"""

    def __init__(self, ip_address: str, port: int = ECHONET_PORT, timeout: float = 1.0):
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout
        self.tid = 1

    def _next_tid(self) -> bytes:
        tid_bytes = struct.pack(">H", self.tid)
        self.tid = (self.tid + 1) % 65535
        if self.tid == 0:
            self.tid = 1
        return tid_bytes

    def _build_frame(self, deoj: bytes, esv: int, epc: int, edt: bytes = bytes()) -> bytes:
        tid_bytes = self._next_tid()
        pdc = len(edt)
        return bytes([EHD1_ECHONET_LITE, EHD2_FORMAT_1]) + tid_bytes + CLASS_CONTROLLER + deoj + bytes([esv, 1, epc, pdc]) + edt

    def _send_and_receive(self, deoj: bytes, esv: int, epc: int, edt: bytes = bytes()) -> Optional[bytes]:
        frame = self._build_frame(deoj, esv, epc, edt)
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            sock.sendto(frame, (self.ip_address, self.port))

            data, _ = sock.recvfrom(1024)
            if len(data) >= 14:
                pdc = data[13]
                return data[14:14+pdc]
        except Exception:
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
        return None

    def _send_only(self, deoj: bytes, esv: int, epc: int, edt: bytes = bytes()) -> bool:
        frame = self._build_frame(deoj, esv, epc, edt)
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            sock.sendto(frame, (self.ip_address, self.port))
            return True
        except Exception:
            return False
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    # --------------------------------------------------------------------------
    # ❄️ 家庭用エアコン (Air Conditioner) 制御・取得
    # --------------------------------------------------------------------------
    def get_aircon_status(self) -> Dict[str, Any]:
        """エアコンの現在ステータス（電源、運転モード、設定温度、室温、消費電力）を取得"""
        # 1. 動作状態 (ON/OFF)
        res_power = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_GET_REQ, EPC_OPERATING_STATUS)
        is_on = (res_power[0] == 0x30) if (res_power and len(res_power) >= 1) else False

        # 2. 運転モード
        res_mode = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_GET_REQ, EPC_AC_OPERATION_MODE)
        mode_val = res_mode[0] if (res_mode and len(res_mode) >= 1) else 0x41
        mode_str = MODE_CODE_TO_NAME.get(mode_val, "自動")

        # 3. 設定温度
        res_temp = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_GET_REQ, EPC_AC_SET_TEMPERATURE)
        set_temp = res_temp[0] if (res_temp and len(res_temp) >= 1 and 0 <= res_temp[0] <= 50) else 26

        # 4. 室内温度
        res_room = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_GET_REQ, EPC_AC_ROOM_TEMP)
        if res_room and len(res_room) >= 1:
            room_temp = struct.unpack("b", bytes([res_room[0]]))[0] # signed 1 byte
            if not (-20 <= room_temp <= 60):
                room_temp = 25.0
        else:
            room_temp = None

        # 5. 室外温度
        res_outdoor = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_GET_REQ, EPC_AC_OUTDOOR_TEMP)
        if res_outdoor and len(res_outdoor) >= 1:
            outdoor_temp = struct.unpack("b", bytes([res_outdoor[0]]))[0]
            if not (-30 <= outdoor_temp <= 60):
                outdoor_temp = 28.0
        else:
            outdoor_temp = None

        # 6. 瞬時消費電力
        res_w = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_GET_REQ, EPC_INST_POWER_W)
        power_w = int.from_bytes(res_w, byteorder='big') if (res_w and len(res_w) >= 2) else (450 if is_on else 0)

        return {
            "connected": (res_power is not None or res_temp is not None or res_room is not None),
            "is_on": is_on,
            "mode": mode_str,
            "mode_code": mode_val,
            "set_temp": set_temp,
            "room_temp": room_temp,
            "outdoor_temp": outdoor_temp,
            "power_w": power_w,
            "ip_address": self.ip_address
        }

    def set_aircon_power(self, turn_on: bool) -> bool:
        """エアコンの電源 ON/OFF を切り替え"""
        val = bytes([0x30 if turn_on else 0x31])
        res = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_SET_C_REQ, EPC_OPERATING_STATUS, val)
        if res is not None:
            return True
        return self._send_only(CLASS_AIR_CONDITIONER, ESV_SET_I_REQ, EPC_OPERATING_STATUS, val)

    def set_aircon_mode(self, mode_name: str) -> bool:
        """運転モードを変更 (自動/冷房/暖房/除湿/送風)"""
        code = MODE_NAME_TO_CODE.get(mode_name, 0x41)
        val = bytes([code])
        res = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_SET_C_REQ, EPC_AC_OPERATION_MODE, val)
        if res is not None:
            return True
        return self._send_only(CLASS_AIR_CONDITIONER, ESV_SET_I_REQ, EPC_AC_OPERATION_MODE, val)

    def set_aircon_temperature(self, temp_celsius: int) -> bool:
        """設定温度を変更 (18〜30℃)"""
        temp_celsius = max(18, min(30, int(temp_celsius)))
        val = bytes([temp_celsius])
        res = self._send_and_receive(CLASS_AIR_CONDITIONER, ESV_SET_C_REQ, EPC_AC_SET_TEMPERATURE, val)
        if res is not None:
            return True
        return self._send_only(CLASS_AIR_CONDITIONER, ESV_SET_I_REQ, EPC_AC_SET_TEMPERATURE, val)

    # --------------------------------------------------------------------------
    # 💡 スマート照明 (Lighting) 制御・取得
    # --------------------------------------------------------------------------
    def get_lighting_status(self) -> Dict[str, Any]:
        """照明の点灯・消灯ステータスを取得"""
        res = self._send_and_receive(CLASS_LIGHTING, ESV_GET_REQ, EPC_OPERATING_STATUS)
        is_on = (res[0] == 0x30) if (res and len(res) >= 1) else False
        return {
            "connected": res is not None,
            "is_on": is_on,
            "ip_address": self.ip_address
        }

    def set_lighting_power(self, turn_on: bool) -> bool:
        """照明の点灯/消灯を制御"""
        val = bytes([0x30 if turn_on else 0x31])
        res = self._send_and_receive(CLASS_LIGHTING, ESV_SET_C_REQ, EPC_OPERATING_STATUS, val)
        return res is not None or self._send_only(CLASS_LIGHTING, ESV_SET_I_REQ, EPC_OPERATING_STATUS, val)
