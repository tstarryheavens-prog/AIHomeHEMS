"""
presets_jp.py - 日本国内固有規格・主要メーカー・電力会社料金プランのプリセット定義モジュール
AI Home HEMS 汎用化レイヤー
"""

from typing import Dict, Any, List

# ----------------------------------------------------------------------
# 1. 蓄電池 / V2H 国内主要メーカープロファイル
# ----------------------------------------------------------------------
BATTERY_MANUFACTURERS: Dict[str, Dict[str, Any]] = {
    "nichicon": {
        "name": "ニチコン (Nichicon ESS / V2H T5系)",
        "protocol": "echonet_tcp",
        "default_port": 3610,
        "alt_port": 1369,
        "default_capacity_kwh": 14.9,
        "echonet_class": [0x02, 0x7D, 0x01],
        "solar_class": [0x02, 0x79, 0x01],
        "supports_timer_sync": True,
        "modes": {
            "auto": 0x45,       # 自家消費 (グリーン)
            "charge": 0x42,     # 強制充電
            "discharge": 0x43,  # 売電 / 放電
            "standby": 0x44     # 待機
        },
        "description": "国内V2H/家庭用蓄電池大手。TCP 3610/1369ポートによるECHONET Lite拡張通信に対応。"
    },
    "panasonic": {
        "name": "パナソニック (Panasonic 創蓄連携システム / Li-ion)",
        "protocol": "echonet_udp",
        "default_port": 3610,
        "alt_port": None,
        "default_capacity_kwh": 6.3,
        "echonet_class": [0x02, 0x7D, 0x01],
        "solar_class": [0x02, 0x79, 0x01],
        "supports_timer_sync": False,
        "modes": {
            "auto": 0x45,       # 経済モード / 環境モード
            "charge": 0x42,     # 強制充電
            "discharge": 0x43,  # 放電
            "standby": 0x44     # 待機
        },
        "description": "国内シェア上位。標準ECHONET Lite (UDP 3610) 準拠。AiSEG2連携対応。"
    },
    "omron": {
        "name": "オムロン (OMRON 住・産共用フレキシブル蓄電システム KPBP-A)",
        "protocol": "echonet_udp",
        "default_port": 3610,
        "alt_port": None,
        "default_capacity_kwh": 9.8,
        "echonet_class": [0x02, 0x7D, 0x01],
        "solar_class": [0x02, 0x79, 0x01],
        "supports_timer_sync": False,
        "modes": {
            "auto": 0x45,
            "charge": 0x42,
            "discharge": 0x43,
            "standby": 0x44
        },
        "description": "高信頼な国内蓄電システム。ECHONET Lite (UDP 3610) による標準制御に対応。"
    },
    "dia_tabuchi": {
        "name": "ダイヤゼブラ電機 / 旧田淵電機 (EneTelus)",
        "protocol": "echonet_udp",
        "default_port": 3610,
        "alt_port": None,
        "default_capacity_kwh": 9.9,
        "echonet_class": [0x02, 0x7D, 0x01],
        "solar_class": [0x02, 0x79, 0x01],
        "supports_timer_sync": False,
        "modes": {
            "auto": 0x45,
            "charge": 0x42,
            "discharge": 0x43,
            "standby": 0x44
        },
        "description": "ハイブリッド蓄電システムEneTelus。標準ECHONET Lite (UDP 3610) 対応。"
    },
    "sharp": {
        "name": "シャープ (SHARP クラウド蓄電池 / SUNVISTA)",
        "protocol": "echonet_udp",
        "default_port": 3610,
        "alt_port": None,
        "default_capacity_kwh": 6.5,
        "echonet_class": [0x02, 0x7D, 0x01],
        "solar_class": [0x02, 0x79, 0x01],
        "supports_timer_sync": False,
        "modes": {
            "auto": 0x45,
            "charge": 0x42,
            "discharge": 0x43,
            "standby": 0x44
        },
        "description": "住宅用太陽光・蓄電池大手。ECHONET Lite (UDP 3610) 対応。"
    },
    "kyocera": {
        "name": "京セラ (KYOCERA Enerezza / クレイ型蓄電池)",
        "protocol": "echonet_udp",
        "default_port": 3610,
        "alt_port": None,
        "default_capacity_kwh": 10.0,
        "echonet_class": [0x02, 0x7D, 0x01],
        "solar_class": [0x02, 0x79, 0x01],
        "supports_timer_sync": False,
        "modes": {
            "auto": 0x45,
            "charge": 0x42,
            "discharge": 0x43,
            "standby": 0x44
        },
        "description": "世界初のクレイ型リチウムイオン蓄電池。ECHONET Lite対応。"
    },
    "choshu": {
        "name": "長州産業 (Smart PV Multi / プレミアム蓄電)",
        "protocol": "echonet_udp",
        "default_port": 3610,
        "alt_port": None,
        "default_capacity_kwh": 9.8,
        "echonet_class": [0x02, 0x7D, 0x01],
        "solar_class": [0x02, 0x79, 0x01],
        "supports_timer_sync": False,
        "modes": {
            "auto": 0x45,
            "charge": 0x42,
            "discharge": 0x43,
            "standby": 0x44
        },
        "description": "国内ソーラー＆マルチ蓄電システム。オムロンOEM等ECHONET Lite準拠。"
    },
    "generic_echonet": {
        "name": "汎用 ECHONET Lite 規格蓄電池 (Class 0x027D)",
        "protocol": "echonet_udp",
        "default_port": 3610,
        "alt_port": None,
        "default_capacity_kwh": 10.0,
        "echonet_class": [0x02, 0x7D, 0x01],
        "solar_class": [0x02, 0x79, 0x01],
        "supports_timer_sync": False,
        "modes": {
            "auto": 0x45,
            "charge": 0x42,
            "discharge": 0x43,
            "standby": 0x44
        },
        "description": "エコーネットコンソーシアム規格の蓄電池標準プロファイル (UDP 3610)。"
    },
    "tesla": {
        "name": "テスラ (Tesla Powerwall - Local Gateway API)",
        "protocol": "http_api",
        "default_port": 443,
        "alt_port": 80,
        "default_capacity_kwh": 13.5,
        "echonet_class": None,
        "solar_class": None,
        "supports_timer_sync": False,
        "modes": {
            "auto": "self_consumption",
            "charge": "charge",
            "discharge": "discharge",
            "standby": "backup"
        },
        "description": "大容量蓄電池。テスラゲートウェイのLocal REST APIによるテレメトリ取得に対応。"
    },
    "simulation": {
        "name": "シミュレーション / デモモード (Mock Client)",
        "protocol": "mock",
        "default_port": 0,
        "alt_port": None,
        "default_capacity_kwh": 14.9,
        "echonet_class": None,
        "solar_class": None,
        "supports_timer_sync": True,
        "modes": {
            "auto": 0x45,
            "charge": 0x42,
            "discharge": 0x43,
            "standby": 0x44
        },
        "description": "実機なしで全機能を検証できるシミュレーションモード。"
    }
}


# ----------------------------------------------------------------------
# 2. 買電・売電（系統電力）取得方式プリセット
# ----------------------------------------------------------------------
GRID_MEASUREMENT_SOURCES: Dict[str, Dict[str, Any]] = {
    "hems_web": {
        "name": "住宅用HEMSコントローラー (Web/CenteHTTPd / パナホーム等)",
        "protocol": "http_scrape",
        "default_ip": "192.168.1.100",
        "requires_auth": True,
        "description": "HEMS分電盤・コントローラーのWeb管理画面から買電・売電・各部屋回路電力をリアルタイム取得。"
    },
    "broute": {
        "name": "スマートメーター Bルート直接通信 (Wi-SUNドングル BP35A1等)",
        "protocol": "serial_wisun",
        "default_port": "COM3",
        "requires_auth": True,
        "description": "電力会社スマートメーターとWi-SUN USBドングルでPANA認証直接通信。高精度・高頻度取得。"
    },
    "echonet_smartmeter": {
        "name": "LAN内 ECHONET Lite スマート電力量メータ (Class 0x0288)",
        "protocol": "echonet_udp",
        "default_port": 3610,
        "requires_auth": False,
        "description": "LAN上のECHONET Lite低圧スマート電力量メータから瞬時電力(EPC 0xE7)を取得。"
    },
    "battery_internal_ct": {
        "name": "蓄電池/パワコン内蔵 CTセンサー計測値 (ECHONET経由)",
        "protocol": "echonet_ct",
        "default_port": 3610,
        "requires_auth": False,
        "description": "蓄電池システム側で系統買電・売電を計測している場合にその値を参照。"
    },
    "simulation": {
        "name": "シミュレーション (Mock Grid)",
        "protocol": "mock",
        "default_port": 0,
        "requires_auth": False,
        "description": "時間帯に応じたリアルな生活パターン買電・売電をシミュレート。"
    }
}


# ----------------------------------------------------------------------
# 3. 日本国内電力会社 ＆ 料金プランプリセット
# ----------------------------------------------------------------------
POWER_COMPANIES: Dict[str, Dict[str, Any]] = {
    "chuden": {
        "name": "中部電力ミライズ",
        "plans": {
            "smart_life_yorutoku": {
                "name": "スマートライフプラン【夜とく】(21時〜7時割安)",
                "night_start_hour": 21,
                "night_end_hour": 7,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 6,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 16.30,
                "day_rate_yen_kwh": 36.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "深夜21時〜翌7時までが16.30円。JIT最適充電は電池寿命最大化のため03:00〜06:30推奨。"
            },
            "smart_life": {
                "name": "スマートライフプラン (22時〜8時割安)",
                "night_start_hour": 22,
                "night_end_hour": 8,
                "optimal_charge_start_hour": 4,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 7,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 16.30,
                "day_rate_yen_kwh": 36.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "深夜22時〜翌8時まで割安。朝型ライフスタイル向け。"
            },
            "e_life": {
                "name": "Eライフプラン (3時間帯電灯)",
                "night_start_hour": 23,
                "night_end_hour": 7,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 30,
                "optimal_charge_end_hour": 6,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 16.50,
                "day_rate_yen_kwh": 38.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "夜間23時〜7時割安プラン。"
            },
            "standard": {
                "name": "従量電灯B / おとくプラン (一律従量制)",
                "night_start_hour": 0,
                "night_end_hour": 0,
                "optimal_charge_start_hour": 1,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 5,
                "optimal_charge_end_min": 0,
                "night_rate_yen_kwh": 30.00,
                "day_rate_yen_kwh": 30.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "時間帯別料金のない標準プラン。"
            }
        }
    },
    "tepco": {
        "name": "東京電力エナジーパートナー (TEPCO)",
        "plans": {
            "smart_life": {
                "name": "スマートライフプラン (午前1時〜午前6時割安)",
                "night_start_hour": 1,
                "night_end_hour": 6,
                "optimal_charge_start_hour": 2,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 5,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 17.78,
                "day_rate_yen_kwh": 35.76,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "オール電化・蓄電池向け。午前1時〜6時が割安ナイトタイム。"
            },
            "yorutoku8": {
                "name": "夜トク8 (午後11時〜午前7時割安)",
                "night_start_hour": 23,
                "night_end_hour": 7,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 6,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 20.74,
                "day_rate_yen_kwh": 32.74,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "夜間8時間割安プラン。"
            },
            "yorutoku12": {
                "name": "夜トク12 (午後9時〜午前9時割安)",
                "night_start_hour": 21,
                "night_end_hour": 9,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 7,
                "optimal_charge_end_min": 0,
                "night_rate_yen_kwh": 22.55,
                "day_rate_yen_kwh": 34.39,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "夜間12時間のロング割安プラン。"
            },
            "standard_b": {
                "name": "従量電灯B / スタンダードS (通常プラン)",
                "night_start_hour": 0,
                "night_end_hour": 0,
                "optimal_charge_start_hour": 1,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 5,
                "optimal_charge_end_min": 0,
                "night_rate_yen_kwh": 30.00,
                "day_rate_yen_kwh": 30.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "時間帯別料金のない標準従量プラン。"
            }
        }
    },
    "kepco": {
        "name": "関西電力 (KEPCO)",
        "plans": {
            "hapi_e_time_r": {
                "name": "はぴｅタイムＲ (午後11時〜午前7時割安)",
                "night_start_hour": 23,
                "night_end_hour": 7,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 6,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 15.20,
                "day_rate_yen_kwh": 31.43,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "関西エリア定番のオール電化プラン。深夜15.20円と非常に安価。"
            },
            "standard_a": {
                "name": "従量電灯A (通常プラン)",
                "night_start_hour": 0,
                "night_end_hour": 0,
                "optimal_charge_start_hour": 1,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 5,
                "optimal_charge_end_min": 0,
                "night_rate_yen_kwh": 26.00,
                "day_rate_yen_kwh": 26.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "時間帯料金のない標準プラン。"
            }
        }
    },
    "tohoku": {
        "name": "東北電力",
        "plans": {
            "yorisou_night8": {
                "name": "よりそう＋ナイト8 (午後11時〜午前7時割安)",
                "night_start_hour": 23,
                "night_end_hour": 7,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 6,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 17.50,
                "day_rate_yen_kwh": 38.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 9.0,
                "description": "東北エリアの夜間8時間割安プラン。"
            },
            "yorisou_night10": {
                "name": "よりそう＋ナイト10 (午後10時〜午前8時割安)",
                "night_start_hour": 22,
                "night_end_hour": 8,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 30,
                "optimal_charge_end_hour": 7,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 18.20,
                "day_rate_yen_kwh": 36.50,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 9.0,
                "description": "夜間10時間割安プラン。"
            }
        }
    },
    "kyushu": {
        "name": "九州電力",
        "plans": {
            "denka_night": {
                "name": "電化でナイト・セレクト (午後10時〜午前8時割安)",
                "night_start_hour": 22,
                "night_end_hour": 8,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 30,
                "optimal_charge_end_hour": 7,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 16.20,
                "day_rate_yen_kwh": 30.50,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 7.0,
                "description": "九州エリアのオール電化プラン。"
            }
        }
    },
    "chugoku": {
        "name": "中国電力",
        "plans": {
            "denka_style": {
                "name": "電化Styleコース (午後11時〜午前8時割安)",
                "night_start_hour": 23,
                "night_end_hour": 8,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 30,
                "optimal_charge_end_hour": 7,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 17.80,
                "day_rate_yen_kwh": 35.20,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 7.15,
                "description": "中国エリアの夜間割安プラン。"
            }
        }
    },
    "shikoku": {
        "name": "四国電力",
        "plans": {
            "denka_e_plan": {
                "name": "でんかｅプラン (午後11時〜午前7時割安)",
                "night_start_hour": 23,
                "night_end_hour": 7,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 6,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 17.10,
                "day_rate_yen_kwh": 36.80,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 7.0,
                "description": "四国エリアのオール電化プラン。"
            }
        }
    },
    "hokuriku": {
        "name": "北陸電力",
        "plans": {
            "kutsurogi_night12": {
                "name": "くつろぎナイト12 (午後8時〜午前8時割安)",
                "night_start_hour": 20,
                "night_end_hour": 8,
                "optimal_charge_start_hour": 2,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 6,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 18.50,
                "day_rate_yen_kwh": 35.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.0,
                "description": "北陸エリアの12時間ロング夜間プラン。"
            }
        }
    },
    "hokkaido": {
        "name": "北海道電力",
        "plans": {
            "enetoku_smart": {
                "name": "エネとくスマートプラン (午後10時〜午前8時割安)",
                "night_start_hour": 22,
                "night_end_hour": 8,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 30,
                "optimal_charge_end_hour": 7,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 20.50,
                "day_rate_yen_kwh": 41.20,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.0,
                "description": "北海道エリアの時間帯別プラン。"
            }
        }
    },
    "new_power": {
        "name": "新電力 / 市場連動型 (Looop, オクトパス等)",
        "plans": {
            "market_dynamic": {
                "name": "市場連動型プラン (JEPXスポット価格連動)",
                "night_start_hour": 0,
                "night_end_hour": 6,
                "optimal_charge_start_hour": 2,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 5,
                "optimal_charge_end_min": 0,
                "night_rate_yen_kwh": 14.00,
                "day_rate_yen_kwh": 38.00,
                "pre_fit_sell_price": 20.0,
                "post_fit_sell_price": 10.0,
                "description": "JEPX市場価格に応じて単価が変動する先進プラン。AIによる最適充放電に最適。"
            },
            "custom": {
                "name": "カスタム自由設定 (手動入力)",
                "night_start_hour": 23,
                "night_end_hour": 7,
                "optimal_charge_start_hour": 3,
                "optimal_charge_start_min": 0,
                "optimal_charge_end_hour": 6,
                "optimal_charge_end_min": 30,
                "night_rate_yen_kwh": 18.00,
                "day_rate_yen_kwh": 35.00,
                "pre_fit_sell_price": 31.0,
                "post_fit_sell_price": 8.5,
                "description": "ご自身の電力会社プランに合わせて各項目を手動設定できます。"
            }
        }
    }
}


# ----------------------------------------------------------------------
# 4. 国内主要都市・都道府県 緯度経度プリセット
# ----------------------------------------------------------------------
JAPAN_LOCATIONS: Dict[str, Dict[str, Any]] = {
    "tokyo": {"name": "東京都 (東京・千代田区)", "lat": 35.6812, "lon": 139.7671},
    "nagoya": {"name": "愛知県 (名古屋市)", "lat": 35.1815, "lon": 136.9066},
    "osaka": {"name": "大阪府 (大阪市)", "lat": 34.6937, "lon": 135.5023},
    "yokohama": {"name": "神奈川県 (横浜市)", "lat": 35.4437, "lon": 139.6380},
    "sapporo": {"name": "北海道 (札幌市)", "lat": 43.0642, "lon": 141.3469},
    "sendai": {"name": "宮城県 (仙台市)", "lat": 38.2682, "lon": 140.8694},
    "niigata": {"name": "新潟県 (新潟市)", "lat": 37.9022, "lon": 139.0232},
    "kanazawa": {"name": "石川県 (金沢市)", "lat": 36.5947, "lon": 136.6256},
    "kyoto": {"name": "京都府 (京都市)", "lat": 35.0116, "lon": 135.7681},
    "kobe": {"name": "兵庫県 (神戸市)", "lat": 34.6901, "lon": 135.1955},
    "hiroshima": {"name": "広島県 (広島市)", "lat": 34.3853, "lon": 132.4553},
    "takamatsu": {"name": "香川県 (高松市)", "lat": 34.3401, "lon": 134.0433},
    "matsuyama": {"name": "愛媛県 (松山市)", "lat": 33.8417, "lon": 132.7661},
    "fukuoka": {"name": "福岡県 (福岡市)", "lat": 33.5904, "lon": 130.4017},
    "kumamoto": {"name": "熊本県 (熊本市)", "lat": 32.7898, "lon": 130.7417},
    "kagoshima": {"name": "鹿児島県 (鹿児島市)", "lat": 31.5966, "lon": 130.5571},
    "naha": {"name": "沖縄県 (那覇市)", "lat": 26.2124, "lon": 127.6809},
}


def get_supported_manufacturers() -> List[Dict[str, str]]:
    """UI用: メーカー選択リストを返却"""
    return [{"id": k, "name": v["name"]} for k, v in BATTERY_MANUFACTURERS.items()]

def get_supported_companies() -> List[Dict[str, str]]:
    """UI用: 電力会社選択リストを返却"""
    return [{"id": k, "name": v["name"]} for k, v in POWER_COMPANIES.items()]

def get_plans_for_company(company_id: str) -> List[Dict[str, Any]]:
    """指定電力会社のプラン一覧を返却"""
    comp = POWER_COMPANIES.get(company_id, POWER_COMPANIES["chuden"])
    return [{"id": k, "name": v["name"], **v} for k, v in comp["plans"].items()]

def get_grid_sources() -> List[Dict[str, str]]:
    """UI用: 系統電力取得元リストを返却"""
    return [{"id": k, "name": v["name"], "description": v["description"]} for k, v in GRID_MEASUREMENT_SOURCES.items()]

def get_location_presets() -> List[Dict[str, Any]]:
    """UI用: 地域プリセット一覧を返却"""
    return [{"id": k, "name": v["name"], "lat": v["lat"], "lon": v["lon"]} for k, v in JAPAN_LOCATIONS.items()]
