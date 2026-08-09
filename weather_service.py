import requests
import yaml
from datetime import datetime, date

class WeatherService:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.lat = self.config["location"]["latitude"]
        self.lon = self.config["location"]["longitude"]
        self.pv_capacity_kw = self.config["system"]["pv_capacity_kw"]
        self.pv_efficiency = self.config["system"]["pv_efficiency"]

    def fetch_forecast(self):
        """
        Open-Meteo APIから時間ごとの日射量(shortwave_radiation: W/m2)と雲量(cloud_cover: %)を取得する
        """
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "hourly": "shortwave_radiation,cloud_cover,temperature_2m",
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
            
            result = []
            for t, rad, cloud in zip(times, radiations, clouds):
                # 日射量 W/m2 (標準1kW/m2での発電換算)
                # 推定瞬時電力(kW) = (日射量 / 1000 W/m2) * 定格容量(kW) * 総合効率
                rad_val = rad if rad is not None else 0.0
                est_pv_kw = (rad_val / 1000.0) * self.pv_capacity_kw * self.pv_efficiency
                
                result.append({
                    "forecast_time": t,
                    "shortwave_radiation": rad_val,
                    "cloud_cover": cloud if cloud is not None else 0,
                    "est_pv_kwh": round(est_pv_kw, 3) # 1時間あたりのkWh
                })
            return result
        except Exception as e:
            print(f"[WeatherService] Error fetching weather forecast: {e}")
            return self._generate_mock_forecast()

    def get_tomorrow_pv_estimate(self):
        """
        翌日の合計太陽光発電量(kWh)と時間ごとの予測データを計算する
        """
        forecasts = self.fetch_forecast()
        today_str = date.today().isoformat()
        
        tomorrow_forecasts = [
            item for item in forecasts 
            if not item["forecast_time"].startswith(today_str)
        ]
        
        total_kwh = sum(item["est_pv_kwh"] for item in tomorrow_forecasts)
        return {
            "date": "Tomorrow",
            "total_pv_kwh": round(total_kwh, 2),
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

if __name__ == "__main__":
    service = WeatherService()
    tomorrow_pv = service.get_tomorrow_pv_estimate()
    print(f"翌日の予測PV発電量: {tomorrow_pv['total_pv_kwh']} kWh")
