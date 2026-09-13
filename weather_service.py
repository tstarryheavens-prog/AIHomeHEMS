import requests
import yaml
from datetime import datetime, date

class WeatherService:
    def __init__(self, config_path="config.yaml"):
        import os
        if os.path.isdir(config_path):
            config_path = os.path.join(config_path, "config.yaml") if os.path.exists(os.path.join(config_path, "config.yaml")) else "config.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            self.config = {}
        
        loc = self.config.get("location", {})
        sys_cfg = self.config.get("system", {})
        self.lat = loc.get("latitude", 35.6812)
        self.lon = loc.get("longitude", 139.7671)
        self.pv_capacity_kw = sys_cfg.get("pv_capacity_kw", 4.0)
        self.pv_efficiency = sys_cfg.get("pv_efficiency", 0.85)

    def fetch_forecast(self):
        """
        Open-Meteo APIから時間ごとの日射量(shortwave_radiation: W/m2)、雲量(cloud_cover: %)、天気コード(weather_code)を取得する
        """
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "hourly": "shortwave_radiation,cloud_cover,temperature_2m,weather_code,precipitation_probability",
            "timezone": "Asia/Tokyo",
            "forecast_days": 2
        }
        
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            radiations = hourly.get("shortwave_radiation", [])
            clouds = hourly.get("cloud_cover", [])
            codes = hourly.get("weather_code", [])
            precips = hourly.get("precipitation_probability", [])
            
            result = []
            for t, rad, cloud, code, precip in zip(times, radiations, clouds, codes, precips):
                # 日射量 W/m2 (標準1kW/m2での発電換算)
                # 推定瞬時電力(kW) = (日射量 / 1000 W/m2) * 定格容量(kW) * 総合効率
                rad_val = rad if rad is not None else 0.0
                est_pv_kw = (rad_val / 1000.0) * self.pv_capacity_kw * self.pv_efficiency
                
                result.append({
                    "forecast_time": t,
                    "shortwave_radiation": rad_val,
                    "cloud_cover": cloud if cloud is not None else 0,
                    "weather_code": code if code is not None else 0,
                    "precipitation_probability": precip if precip is not None else 0,
                    "est_pv_kwh": round(est_pv_kw, 3) # 1時間あたりのkWh
                })
            return result
        except Exception as e:
            print(f"[WeatherService] Error fetching weather forecast: {e}")
            return self._generate_mock_forecast()

    def get_tomorrow_pv_estimate(self):
        """
        翌日の合計太陽光発電量(kWh)、時間ごとの予測、および正確な天気状態(晴れ・曇り・雨・快晴)を計算する
        """
        forecasts = self.fetch_forecast()
        today_str = date.today().isoformat()
        
        tomorrow_forecasts = [
            item for item in forecasts 
            if not item["forecast_time"].startswith(today_str)
        ]
        
        total_kwh = sum(item["est_pv_kwh"] for item in tomorrow_forecasts)

        # 昼間時間帯 (06:00〜18:00) の天気コードと雲量から総合判定
        daylight_items = [
            f for f in tomorrow_forecasts 
            if 6 <= int(f["forecast_time"].split("T")[1].split(":")[0]) <= 18
        ]
        
        if daylight_items:
            avg_cloud = sum(f["cloud_cover"] for f in daylight_items) / len(daylight_items)
            codes = [f.get("weather_code", 0) for f in daylight_items]
            has_rain = any(c in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99] for c in codes)
            has_storm = any(c in [95, 96, 99] for c in codes)
            
            if has_storm:
                condition = "storm"
                condition_label = "⚡ 警報・雷雨"
            elif has_rain:
                condition = "rainy"
                condition_label = "🌧️ 雨天"
            elif avg_cloud < 25 or total_kwh > 18.0:
                condition = "clear"
                condition_label = "☀️ 快晴・日照良好"
            elif avg_cloud < 60 or total_kwh > 12.0:
                condition = "sunny_cloudy"
                condition_label = "⛅ 晴れ時々曇り"
            else:
                condition = "cloudy"
                condition_label = "☁️ 曇り"
        else:
            condition = "clear" if total_kwh > 15.0 else "cloudy"
            condition_label = "☀️ 晴れ" if total_kwh > 15.0 else "☁️ 曇り"

        return {
            "date": "Tomorrow",
            "total_pv_kwh": round(total_kwh, 2),
            "condition": condition,
            "condition_label": condition_label,
            "hourly": tomorrow_forecasts
        }

    def _generate_mock_forecast(self):
        """オフライン時またはAPIエラー時のダミー予測"""
        result = []
        now_date = date.today().isoformat()
        for h in range(48):
            hour = h % 24
            # 簡易ベルカーブ（日中6時〜18時に日射量発生）
            if 6 <= hour <= 18:
                rad = 600 * (1 - ((hour - 12) / 6) ** 2)
            else:
                rad = 0.0
            est_pv_kw = (rad / 1000.0) * self.pv_capacity_kw * self.pv_efficiency
            result.append({
                "forecast_time": f"{now_date}T{hour:02d}:00",
                "shortwave_radiation": round(rad, 1),
                "cloud_cover": 20,
                "est_pv_kwh": round(est_pv_kw, 3)
            })
        return result

    def check_jma_warnings(self):
        """
        気象庁の警報情報APIから、名古屋市(2310000)の現在の警報発表状況を取得する
        警報（特別警報含む）が発表されている場合は詳細な情報を返す
        """
        url = "https://www.jma.go.jp/bosai/warning/data/warning/230000.json"
        
        # 警報コードと名前のマッピング
        jma_codes = {
            "32": "暴風警報", "33": "大雨警報", "35": "暴風警報", "36": "大雪警報",
            "37": "暴風雪警報", "38": "波浪警報", "40": "高潮警報",
            "53": "大雨特別警報", "55": "暴風特別警報", "56": "大雪特別警報",
            "57": "暴風雪特別警報", "58": "波浪特別警報", "60": "高潮特別警報"
        }
        
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            nagoya_code = "2310000"
            area_types = data.get("areaTypes", [])
            
            active_alerts = []
            for at in area_types:
                areas = at.get("areas", [])
                for area in areas:
                    if area.get("code") == nagoya_code:
                        warnings = area.get("warnings", [])
                        for w in warnings:
                            code = w.get("code")
                            status = w.get("status")
                            if code and status in ["発表", "継続"]:
                                try:
                                    code_val = int(code)
                                    # 32番台以上は警報・特別警報レベル (31以下の注意報等は除外)
                                    if code_val >= 32:
                                        alert_name = jma_codes.get(code, f"その他警報 (コード: {code})")
                                        active_alerts.append({
                                            "code": code,
                                            "name": alert_name,
                                            "status": status
                                        })
                                except ValueError:
                                    pass
            
            return {
                "has_warning": len(active_alerts) > 0,
                "warnings": active_alerts,
                "status": "active" if len(active_alerts) > 0 else "clear",
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            print(f"[WeatherService] Error checking JMA warnings: {e}")
            return {
                "has_warning": False,
                "warnings": [],
                "status": "error",
                "error_msg": str(e),
                "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

if __name__ == "__main__":
    service = WeatherService()
    tomorrow_pv = service.get_tomorrow_pv_estimate()
    print(f"翌日の予測PV発電量: {tomorrow_pv['total_pv_kwh']} kWh")
