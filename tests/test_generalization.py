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
