"""
test_appliance_scanner.py - ECHONET Lite 家電（エアコン等）およびネットワークスキャナー進捗の単体テスト
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from echonet_appliance import EchonetApplianceClient, MODE_NAME_TO_CODE, MODE_CODE_TO_NAME
import network_scanner


class TestApplianceScanner(unittest.TestCase):

    def test_echonet_appliance_frame_builder(self):
        """ECHONET Lite エアコン制御電文の生成テスト"""
        client = EchonetApplianceClient(ip_address="192.168.2.55", timeout=0.5)
        
        # 電源 ON フレーム (0x30)
        frame_on = client._build_frame(
            deoj=bytes([0x01, 0x30, 0x01]),
            esv=0x61,
            epc=0x80,
            edt=bytes([0x30])
        )
        self.assertEqual(frame_on[0], 0x10) # EHD1
        self.assertEqual(frame_on[1], 0x81) # EHD2
        self.assertEqual(frame_on[4:7], bytes([0x05, 0xFF, 0x01])) # SEOJ コントローラ
        self.assertEqual(frame_on[7:10], bytes([0x01, 0x30, 0x01])) # DEOJ エアコン
        self.assertEqual(frame_on[10], 0x61) # ESV SET_C
        self.assertEqual(frame_on[12], 0x80) # EPC 動作状態
        self.assertEqual(frame_on[13], 0x01) # PDC 1 byte
        self.assertEqual(frame_on[14], 0x30) # EDT ON

        # 設定温度変更フレーム (26℃ -> 0x1A)
        frame_temp = client._build_frame(
            deoj=bytes([0x01, 0x30, 0x01]),
            esv=0x61,
            epc=0xB3,
            edt=bytes([26])
        )
        self.assertEqual(frame_temp[12], 0xB3) # EPC 温度
        self.assertEqual(frame_temp[14], 26)

    def test_mode_mappings(self):
        """エアコン運転モード定数の相互変換テスト"""
        for name, code in MODE_NAME_TO_CODE.items():
            self.assertEqual(MODE_CODE_TO_NAME[code], name)
        self.assertIn("冷房", MODE_NAME_TO_CODE)
        self.assertIn("暖房", MODE_NAME_TO_CODE)
        self.assertIn("除湿", MODE_NAME_TO_CODE)
        self.assertIn("自動", MODE_NAME_TO_CODE)

    def test_aircon_status_offline_handling(self):
        """実機未接続時のフォールバック処理テスト"""
        client = EchonetApplianceClient(ip_address="192.168.254.254", timeout=0.1)
        stat = client.get_aircon_status()
        self.assertFalse(stat["connected"])
        self.assertFalse(stat["is_on"])
        self.assertEqual(stat["set_temp"], 26)

    def test_network_scanner_progress_callback(self):
        """スキャナー進捗コールバックが呼ばれるかのモックテスト"""
        progress_events = []

        def callback(pct, msg):
            progress_events.append((pct, msg))

        # マルチキャスト探索のみモック
        orig_multicast = network_scanner.discover_echonet_multicast
        orig_check = network_scanner.check_ip_services
        try:
            network_scanner.discover_echonet_multicast = lambda timeout: []
            network_scanner.check_ip_services = lambda ip: None

            devs = network_scanner.scan_full_iot_network(progress_callback=callback)
            self.assertTrue(len(progress_events) >= 2)
            self.assertEqual(progress_events[-1][0], 1.0)
            self.assertIn("完了", progress_events[-1][1])
        finally:
            network_scanner.discover_echonet_multicast = orig_multicast
            network_scanner.check_ip_services = orig_check

    def test_apply_and_remove_appliance_config(self):
        """家電設定の追加・削除テスト"""
        test_ip = "192.168.2.99"
        ok_add = network_scanner.apply_device_to_config(test_ip, "aircon", "テスト用エアコン")
        self.assertTrue(ok_add)

        cfg = network_scanner.get_config_manager().load_config()
        apps = cfg.get("smart_appliances", [])
        matched = [a for a in apps if a.get("ip_address") == test_ip]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["name"], "テスト用エアコン")

        ok_del = network_scanner.remove_appliance_from_config(test_ip)
        self.assertTrue(ok_del)

        cfg2 = network_scanner.get_config_manager().load_config()
        apps2 = cfg2.get("smart_appliances", [])
        matched2 = [a for a in apps2 if a.get("ip_address") == test_ip]
        self.assertEqual(len(matched2), 0)


if __name__ == "__main__":
    unittest.main()
