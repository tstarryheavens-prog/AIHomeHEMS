"""
test_generalization.py - 汎用化・自動スキャン・国内規格/メーカー個別設定の統合テスト
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import presets_jp
from universal_echonet import UniversalEchonetClient
from config_manager import ConfigManager, get_default_config
import network_scanner


class TestGeneralizationSystem(unittest.TestCase):

    def test_presets_jp_coverage(self):
        """国内メーカー、全国電力会社、地域プリセットが網羅されているかテスト"""
        mfgs = presets_jp.get_supported_manufacturers()
        self.assertTrue(len(mfgs) >= 8)
        mfg_ids = [m["id"] for m in mfgs]
        self.assertIn("nichicon", mfg_ids)
        self.assertIn("panasonic", mfg_ids)
        self.assertIn("omron", mfg_ids)
        self.assertIn("sharp", mfg_ids)
        self.assertIn("generic_echonet", mfg_ids)

        comps = presets_jp.get_supported_companies()
        self.assertTrue(len(comps) >= 8)
        comp_ids = [c["id"] for c in comps]
        self.assertIn("chuden", comp_ids)
        self.assertIn("tepco", comp_ids)
        self.assertIn("kepco", comp_ids)

        chuden_plans = presets_jp.get_plans_for_company("chuden")
        self.assertTrue(len(chuden_plans) >= 2)
        tepco_plans = presets_jp.get_plans_for_company("tepco")
        self.assertTrue(len(tepco_plans) >= 2)

        locs = presets_jp.get_location_presets()
        self.assertTrue(len(locs) >= 10)

    def test_universal_echonet_client(self):
        """UniversalEchonetClient のモック動作とフレーム生成をテスト"""
        # 1. モッククライアント
        client_mock = UniversalEchonetClient(enabled=False, manufacturer="generic_echonet")
        info = client_mock.get_full_system_info()
        self.assertEqual(info["connected"], False)
        self.assertEqual(info["is_mock"], True)
        self.assertIn("soc", info)
        self.assertIn("battery_wh", info)

        # 2. フレーム生成テスト
        frame = client_mock._build_frame(
            bytes([0x05, 0xFF, 0x01]),
            bytes([0x02, 0x7D, 0x01]),
            0x62,
            0xE7
        )
        self.assertEqual(frame[0], 0x10) # EHD1
        self.assertEqual(frame[1], 0x81) # EHD2
        self.assertEqual(frame[10], 0x62) # ESV
        self.assertEqual(frame[12], 0xE7) # EPC

        # 3. タイマースケジュール (ニチコン)
        client_nichicon = UniversalEchonetClient(enabled=False, manufacturer="nichicon")
        self.assertTrue(client_nichicon.set_battery_timer_schedule(3, 0, 6, 30))

    def test_nichicon_soc_precision_calculation(self):
        """ニチコンT5仕様（EPC 0xE7 が 4バイト無効値 0x3B9AC9FF を返す）における正確なSOC算出テスト"""
        client = UniversalEchonetClient(enabled=True, manufacturer="nichicon", capacity_kwh=14.9)
        
        # モック _query:
        # EPC 0xE7 は Nichicon特有の 0x3B9AC9FF (先頭バイトが0x3B = 59)
        # EPC 0xE2 は 2980 Wh (20% of 14.9 kWh)
        def mock_query(deoj, epc):
            if epc == 0xE7:
                return bytes([0x3B, 0x9A, 0xC9, 0xFF])  # 無効値 999,999,999
            elif epc == 0xE2:
                return (2980).to_bytes(4, byteorder='big') # 2,980 Wh
            elif epc == 0xD0:
                return (14900).to_bytes(4, byteorder='big') # 14,900 Wh
            elif epc == 0xDA:
                return bytes([0x44]) # 待機
            elif epc == 0xD3:
                return (0).to_bytes(4, byteorder='big')
            return None

        client._query = mock_query
        info = client.get_full_system_info(force_refresh=True)

        # 59% (0x3B誤認) ではなく、正確に 20% と計算されること！
        self.assertEqual(info["soc"], 20)
        self.assertEqual(info["battery_wh"], 2980)
        self.assertTrue(info["connected"])

        # 標準1バイト 0xE7 を返す機器 (パナソニック等: 20%) のテスト
        client_std = UniversalEchonetClient(enabled=True, manufacturer="panasonic", capacity_kwh=6.3)
        client_std._query = lambda deoj, epc: bytes([20]) if epc == 0xE7 else None
        info_std = client_std.get_full_system_info(force_refresh=True)
        self.assertEqual(info_std["soc"], 20)

    def test_config_manager(self):
        """ConfigManager の一時ファイルによる設定読み書き・バックアップ・プリセット適用をテスト"""
        test_yaml = "test_temp_config.yaml"
        if os.path.exists(test_yaml):
            os.remove(test_yaml)

        try:
            cm = ConfigManager(config_path=test_yaml)
            cfg = cm.load_config()
            self.assertIn("battery_system", cfg)
            self.assertIn("electricity_tariff", cfg)
            self.assertIn("fit_setting", cfg)
            self.assertIn("location", cfg)

            # プリセット適用テスト
            cm.apply_battery_preset("panasonic")
            cfg_p = cm.load_config()
            self.assertEqual(cfg_p["battery_system"]["manufacturer"], "panasonic")
            self.assertEqual(cfg_p["battery_system"]["protocol"], "echonet_udp")

            cm.apply_power_plan_preset("tepco", "smart_life")
            cfg_t = cm.load_config()
            self.assertEqual(cfg_t["electricity_tariff"]["company"], "tepco")
            self.assertEqual(cfg_t["electricity_tariff"]["night_start_hour"], 1)
            self.assertEqual(cfg_t["electricity_tariff"]["night_end_hour"], 6)

            # バックアップ
            bak = cm.backup_config()
            self.assertIsNotNone(bak)
            self.assertTrue(os.path.exists(bak))
            os.remove(bak)
        finally:
            if os.path.exists(test_yaml):
                os.remove(test_yaml)

    def test_network_scanner_subnet(self):
        """サブネット取得とスキャナー関数の健全性をテスト"""
        subnet, local_ip = network_scanner.get_local_subnet()
        self.assertIsNotNone(subnet)
        self.assertIsNotNone(local_ip)
        self.assertTrue(str(local_ip).startswith("192.168.") or str(local_ip).startswith("10.") or str(local_ip).startswith("172."))


if __name__ == "__main__":
    unittest.main()
