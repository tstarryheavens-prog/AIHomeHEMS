import time
import random

class BRouteCollector:
    def __init__(self, port="COM3", baudrate=115200, broute_id="", broute_pass="", enabled=False):
        self.port = port
        self.baudrate = baudrate
        self.broute_id = broute_id
        self.broute_pass = broute_pass
        self.enabled = enabled
        self.ser = None

    def connect(self):
        if not self.enabled:
            print("[BRoute] Wi-SUN Dongle disabled in config. Running in simulation mode.")
            return False

        try:
            import serial
            self.ser = serial.Serial(self.port, self.baudrate, timeout=2.0)
            print(f"[BRoute] Serial opened on {self.port}")
            # SKSTACK Wi-SUN Initial handshake commands:
            # 1. SKSETPWD 0 C <broute_pass>
            # 2. SKSETRBID <broute_id>
            # 3. SKSCAN 2 ...
            # 4. SKJOIN <IPv6_addr>
            return True
        except Exception as e:
            print(f"[BRoute] Failed to open serial port {self.port}: {e}")
            self.enabled = False
            return False

    def read_instantaneous_power(self):
        """
        スマートメーターから瞬時電力(W)を取得する
        正: 系統からの買電(W)
        負: 系統への売電(W)
        """
        if not self.enabled:
            # モックデータ：時間帯に応じて適度な買電/売電状態をシミュレート
            hour = time.localtime().tm_hour
            if 10 <= hour <= 15:
                # 昼間はPV売電傾向
                grid_w = random.randint(-3500, -200)
            else:
                # 夜間〜朝夕は買電傾向
                grid_w = random.randint(300, 2500)
            return {
                "connected": False,
                "is_mock": True,
                "grid_w": grid_w
            }
        
        # 実機シリアル通信処理
        try:
            # Send ECHONET Lite E7 (Instantaneous Power) Get request over Wi-SUN
            # SKSENDAC 1 <IPv6> 0E1A 1 0 000C1081...
            pass
        except Exception as e:
            print(f"[BRoute] Serial read error: {e}")
        return {"connected": True, "grid_w": 0}

if __name__ == "__main__":
    collector = BRouteCollector(enabled=False)
    data = collector.read_instantaneous_power()
    print(f"B-Route Data: {data}")
