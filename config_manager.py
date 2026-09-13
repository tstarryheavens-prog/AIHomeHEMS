"""
config_manager.py - HEMSシステム設定マネージャー
config.yaml の安全な読み書き・更新・バリデーション・バックアップ機能を提供
"""

import os
import shutil
import yaml
from datetime import datetime
from typing import Dict, Any, Optional

from presets_jp import (
    BATTERY_MANUFACTURERS,
    POWER_COMPANIES,
    GRID_MEASUREMENT_SOURCES,
    JAPAN_LOCATIONS
)

DEFAULT_CONFIG_PATH = "config.yaml"
EXAMPLE_CONFIG_PATH = "config.example.yaml"


def get_default_config() -> Dict[str, Any]:
    """デフォルト設定構造を返却"""
    return {
        "battery_system": {
            "manufacturer": "nichicon",
            "name": "ニチコン (Nichicon ESS / V2H T5系)",
            "protocol": "echonet_tcp",
            "ip_address": "192.168.1.200",
            "port": 3610,
            "enabled": True,
            "battery_capacity_kwh": 14.9,
            "battery_max_soc": 100.0,
            "battery_min_soc": 20.0
        },
        "solar_pv": {
            "pv_capacity_kw": 4.0,
            "pv_efficiency": 0.85,
            "enabled": True
        },
        "grid_measurement": {
            "source": "hems_web",
            "name": "住宅用HEMSコントローラー (Web/CenteHTTPd)",
            "enabled": True
        },
        "hems_controller": {
            "ip_address": "192.168.1.100",
            "user_id": "",
            "password": "",
            "enabled": True
        },
        "route": {
            "enabled": False,
            "port": "COM3",
            "baudrate": 115200,
            "id": "",
            "password": ""
        },
        "electricity_tariff": {
            "company": "chuden",
            "plan": "smart_life_yorutoku",
            "name": "中部電力 スマートライフプラン【夜とく】",
            "night_start_hour": 21,
            "night_end_hour": 7,
            "optimal_charge_start_hour": 3,
            "optimal_charge_start_min": 0,
            "optimal_charge_end_hour": 6,
            "optimal_charge_end_min": 30,
            "night_rate_yen_kwh": 16.30,
            "day_rate_yen_kwh": 36.00
        },
        "fit_setting": {
            "fit_end_date": "2026-11-27",
            "pre_fit_sell_price": 31.0,
            "post_fit_sell_price": 8.5
        },
        "location": {
            "name": "東京都 (千代田区)",
            "latitude": 35.6812,
            "longitude": 139.7671
        },
        # 既存下位互換用セクション
        "nichicon": {
            "enabled": True,
            "ip_address": "192.168.1.200",
            "port": 3610
        },
        "system": {
            "battery_capacity_kwh": 14.9,
            "battery_max_soc": 100.0,
            "battery_min_soc": 20.0,
            "pv_capacity_kw": 4.0,
            "pv_efficiency": 0.85
        }
    }


class ConfigManager:
    """設定ファイルのロード・更新・安全な書き込みを統括するクラス"""

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """config.yamlが存在しない場合は config.example.yaml から複製、またはデフォルト作成"""
        if not os.path.exists(self.config_path):
            if os.path.exists(EXAMPLE_CONFIG_PATH):
                shutil.copy(EXAMPLE_CONFIG_PATH, self.config_path)
            else:
                self.save_config(get_default_config())

    def load_config(self) -> Dict[str, Any]:
        """設定を安全にロードし、不足キーをデフォルト値で補完"""
        self._ensure_config_exists()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[ConfigManager] Error reading {self.config_path}: {e}")
            cfg = {}

        defaults = get_default_config()

        # 既存形式 (nichicon, system) から新形式 (battery_system, solar_pv) への正規化補完
        if "battery_system" not in cfg:
            cfg["battery_system"] = {}
            if "nichicon" in cfg:
                cfg["battery_system"]["manufacturer"] = "nichicon"
                cfg["battery_system"]["ip_address"] = cfg["nichicon"].get("ip_address", "192.168.1.200")
                cfg["battery_system"]["port"] = cfg["nichicon"].get("port", 3610)
                cfg["battery_system"]["enabled"] = cfg["nichicon"].get("enabled", True)
                cfg["battery_system"]["protocol"] = "echonet_tcp"
            if "system" in cfg:
                cfg["battery_system"]["battery_capacity_kwh"] = cfg["system"].get("battery_capacity_kwh", 14.9)
                cfg["battery_system"]["battery_max_soc"] = cfg["system"].get("battery_max_soc", 100.0)
                cfg["battery_system"]["battery_min_soc"] = cfg["system"].get("battery_min_soc", 20.0)

        if "solar_pv" not in cfg and "system" in cfg:
            cfg["solar_pv"] = {
                "pv_capacity_kw": cfg["system"].get("pv_capacity_kw", 4.0),
                "pv_efficiency": cfg["system"].get("pv_efficiency", 0.85),
                "enabled": True
            }

        if "grid_measurement" not in cfg:
            cfg["grid_measurement"] = {
                "source": "hems_web" if cfg.get("hems_controller", {}).get("enabled") else "simulation",
                "name": "住宅用HEMSコントローラー (Web/CenteHTTPd)",
                "enabled": True
            }

        # 再帰的マージ
        def merge_dict(target, default):
            for k, v in default.items():
                if k not in target:
                    target[k] = v
                elif isinstance(v, dict) and isinstance(target[k], dict):
                    merge_dict(target[k], v)

        merge_dict(cfg, defaults)
        return cfg

    def backup_config(self) -> Optional[str]:
        """設定ファイルのタイムスタンプ付きバックアップを作成"""
        if not os.path.exists(self.config_path):
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{self.config_path}.bak_{ts}"
        try:
            shutil.copy(self.config_path, backup_filename)
            return backup_filename
        except Exception as e:
            print(f"[ConfigManager] Backup failed: {e}")
            return None

    def save_config(self, new_config: Dict[str, Any]) -> bool:
        """設定を安全にAtomic書き込みで保存"""
        self.backup_config()

        # 既存形式との下位互換性フィールドを自動同期
        bat = new_config.get("battery_system", {})
        sol = new_config.get("solar_pv", {})

        new_config["nichicon"] = {
            "enabled": bat.get("enabled", True),
            "ip_address": bat.get("ip_address", "192.168.1.200"),
            "port": bat.get("port", 3610)
        }

        new_config["system"] = {
            "battery_capacity_kwh": bat.get("battery_capacity_kwh", 14.9),
            "battery_max_soc": bat.get("battery_max_soc", 100.0),
            "battery_min_soc": bat.get("battery_min_soc", 20.0),
            "pv_capacity_kw": sol.get("pv_capacity_kw", 4.0),
            "pv_efficiency": sol.get("pv_efficiency", 0.85)
        }

        temp_file = f"{self.config_path}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                yaml.dump(new_config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            os.replace(temp_file, self.config_path)
            return True
        except Exception as e:
            print(f"[ConfigManager] Error saving {self.config_path}: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    def apply_battery_preset(self, manufacturer_id: str):
        """メーカーIDに基づいて蓄電池の通信設定をプリセット適用"""
        cfg = self.load_config()
        mfg = BATTERY_MANUFACTURERS.get(manufacturer_id)
        if not mfg:
            return False

        cfg["battery_system"]["manufacturer"] = manufacturer_id
        cfg["battery_system"]["name"] = mfg["name"]
        cfg["battery_system"]["protocol"] = mfg["protocol"]
        cfg["battery_system"]["port"] = mfg["default_port"]
        cfg["battery_system"]["battery_capacity_kwh"] = mfg.get("default_capacity_kwh", 10.0)
        return self.save_config(cfg)

    def apply_power_plan_preset(self, company_id: str, plan_id: str):
        """電力会社・プランIDに基づいて料金設定をプリセット適用"""
        cfg = self.load_config()
        comp = POWER_COMPANIES.get(company_id)
        if not comp:
            return False
        plan = comp["plans"].get(plan_id)
        if not plan:
            return False

        cfg["electricity_tariff"]["company"] = company_id
        cfg["electricity_tariff"]["plan"] = plan_id
        cfg["electricity_tariff"]["name"] = f"{comp['name']} {plan['name']}"
        cfg["electricity_tariff"]["night_start_hour"] = plan["night_start_hour"]
        cfg["electricity_tariff"]["night_end_hour"] = plan["night_end_hour"]
        cfg["electricity_tariff"]["optimal_charge_start_hour"] = plan["optimal_charge_start_hour"]
        cfg["electricity_tariff"]["optimal_charge_start_min"] = plan["optimal_charge_start_min"]
        cfg["electricity_tariff"]["optimal_charge_end_hour"] = plan["optimal_charge_end_hour"]
        cfg["electricity_tariff"]["optimal_charge_end_min"] = plan["optimal_charge_end_min"]
        cfg["electricity_tariff"]["night_rate_yen_kwh"] = plan["night_rate_yen_kwh"]
        cfg["electricity_tariff"]["day_rate_yen_kwh"] = plan["day_rate_yen_kwh"]

        if "pre_fit_sell_price" in plan:
            cfg["fit_setting"]["pre_fit_sell_price"] = plan["pre_fit_sell_price"]
        if "post_fit_sell_price" in plan:
            cfg["fit_setting"]["post_fit_sell_price"] = plan["post_fit_sell_price"]

        return self.save_config(cfg)

    def apply_location_preset(self, location_id: str):
        """地域IDに基づいて緯度経度・地域名をプリセット適用"""
        cfg = self.load_config()
        loc = JAPAN_LOCATIONS.get(location_id)
        if not loc:
            return False

        cfg["location"]["name"] = loc["name"]
        cfg["location"]["latitude"] = loc["lat"]
        cfg["location"]["longitude"] = loc["lon"]
        return self.save_config(cfg)


# シングルトンインスタンスヘルパー
_manager = None
def get_config_manager() -> ConfigManager:
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager
