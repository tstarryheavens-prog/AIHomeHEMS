import yaml
from weather_service import WeatherService
from database import save_daily_schedule
from katene_importer import get_hourly_average_demand
from datetime import date

class PostFitOptimizer:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.weather_service = WeatherService(config_path)
        self.battery_capacity_kwh = self.config["system"]["battery_capacity_kwh"]
        self.min_soc = self.config["system"]["battery_min_soc"]
        self.max_soc = self.config["system"]["battery_max_soc"]

    def calculate_optimal_schedule(self):
        """
        中部電力「スマートライフプラン【夜とく】」× FIT期限(2026/11/29)対応の最得自動判定
        """
        # 1. FIT期限(2026-11-29)および単価の読み込み
        fit_end = date.fromisoformat(self.config.get("fit_setting", {}).get("fit_end_date", "2026-11-29"))
        today = date.today()
        is_fit_active = (today <= fit_end)
        
        # 2. 過去ログに基づく時間帯別平均消費電力プロファイル(24h)の取得
        hourly_demand_profile = get_hourly_average_demand()
        est_load_kwh = sum(hourly_demand_profile)
        
        # 3. 翌日太陽光予測発電量 (kWh) の取得
        tomorrow_pv_info = self.weather_service.get_tomorrow_pv_estimate()
        est_pv_kwh = tomorrow_pv_info["total_pv_kwh"]
        
        if is_fit_active:
            # 💰 FIT期間中 (〜2026/11/29): 売電単価 31円/kWh ＞ 深夜単価 16.30円/kWh
            # 最得戦略: 深夜(23-7時)に16.3円で100%充電し、昼間太陽光(31円)は全量売電＆昼間消費は蓄電池から供給
            target_night_soc = 100.0
            reason = (
                f"【FIT高額売電モード適用中 (〜2026/11/29まで 売電31.0円/kWh)】\n"
                f"中部電力「夜とく」の格安深夜電力(16.30円/kWh)で蓄電池を100%まで充電(0x42)。\n"
                f"昼間は太陽光発電(31円/kWh)を最大限売電(0x43 放電/売電優先)し、差額利益 (+14.7円/kWh) を最大化します。"
            )
        else:
            # 🌿 卒FIT後 (2026/11/30〜): 買電単価 36円/kWh ＞ 売電単価 8.5円/kWh
            # 最得戦略: 自家消費グリーンモード(0x45)優先。翌日PV余剰分だけ受入スペースを空けて深夜充電
            est_surplus_pv_kwh = max(0.0, est_pv_kwh - est_load_kwh)
            needed_battery_kwh_from_pv = min(self.battery_capacity_kwh, est_surplus_pv_kwh)
            needed_night_charge_kwh = max(0.0, self.battery_capacity_kwh - needed_battery_kwh_from_pv)
            
            target_night_soc = (needed_night_charge_kwh / self.battery_capacity_kwh) * 100.0
            target_night_soc = max(self.min_soc + 10.0, min(self.max_soc, target_night_soc))
            target_night_soc = round(target_night_soc, 1)

            if target_night_soc <= 30.0:
                reason = f"【卒FIT自家消費モード (2026/11/30以降)】翌日は快晴予測({est_pv_kwh}kWh)。PV余剰自家消費充電のため、深夜充電を抑制({target_night_soc}%)します。"
            elif target_night_soc >= 80.0:
                reason = f"【卒FIT自家消費モード (2026/11/30以降)】翌日は雨予測({est_pv_kwh}kWh)。深夜割安電力(16.30円)で蓄電池を十分充電({target_night_soc}%)します。"
            else:
                reason = f"【卒FIT自家消費モード (2026/11/30以降)】翌日は適度な発電予測({est_pv_kwh}kWh)。深夜充電({target_night_soc}%)と昼間PV自家消費(0x45)のハイブリッド運用を行います。"

        schedule_result = {
            "target_date": today.isoformat(),
            "is_fit_active": is_fit_active,
            "fit_end_date": fit_end.isoformat(),
            "est_pv_kwh": est_pv_kwh,
            "est_load_kwh": est_load_kwh,
            "target_night_soc": target_night_soc,
            "recommendation_reason": reason,
            "hourly_pv_prediction": tomorrow_pv_info["hourly"]
        }

        # DBに保存
        save_daily_schedule(
            target_date=date.today().isoformat(),
            target_night_soc=target_night_soc,
            est_pv_kwh=est_pv_kwh,
            est_load_kwh=est_load_kwh,
            details_dict=schedule_result
        )

        return schedule_result

if __name__ == "__main__":
    optimizer = PostFitOptimizer()
    plan = optimizer.calculate_optimal_schedule()
    print("=== 最適化スケジュール判定結果 ===")
    print(f"翌日予測PV発電量: {plan['est_pv_kwh']} kWh")
    print(f"推奨深夜充電目標SOC: {plan['target_night_soc']} %")
    print(f"制御方針: {plan['recommendation_reason']}")
