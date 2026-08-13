import yaml
from weather_service import WeatherService
from database import save_daily_schedule
from katene_importer import get_hourly_average_demand
from datetime import date, timedelta

class PostFitOptimizer:
    def __init__(self, config_path="config.yaml"):
        import os
        if os.path.isdir(config_path):
            config_path = os.path.join(config_path, "config.yaml") if os.path.exists(os.path.join(config_path, "config.yaml")) else "config.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            self.config = {}
        self.weather_service = WeatherService(config_path)
        sys_cfg = self.config.get("system", {})
        self.battery_capacity_kwh = sys_cfg.get("battery_capacity_kwh", 14.9)
        self.min_soc = sys_cfg.get("battery_min_soc", 20.0)
        self.max_soc = sys_cfg.get("battery_max_soc", 100.0)

    def calculate_optimal_schedule(self):
        """
        中部電力「スマートライフプラン【夜とく】」× FITカウントダウン × 天気予報連動の最得動的SOC調整
        """
        fit_end = date.fromisoformat(self.config.get("fit_setting", {}).get("fit_end_date", "2026-11-27"))
        today = date.today()
        is_fit_active = (today <= fit_end)
        days_until_fit_end = (fit_end - today).days

        tomorrow = today + timedelta(days=1)
        hourly_demand_profile = get_hourly_average_demand(target_month=tomorrow.month)
        est_load_kwh = sum(hourly_demand_profile)

        # 翌日気象・発電量予測
        tomorrow_pv_info = self.weather_service.get_tomorrow_pv_estimate()
        est_pv_kwh = tomorrow_pv_info.get("total_pv_kwh", 12.0)
        weather_condition = tomorrow_pv_info.get("condition", "cloudy") # clear, cloudy, rainy, storm

        if is_fit_active:
            # 💰 FIT期間中 (〜2026/11/27 売電31.0円/kWh)
            # 基本は夜間(16.3円)100%充電で売電利益を最大化。
            # ただし、翌日が台風/大雨警報(storm)の場合は100%防災モード維持。
            target_night_soc = 100.0
            sell_price = self.config.get("fit_setting", {}).get("pre_fit_sell_price", 31.0)
            diff_price = sell_price - 16.30
            
            reason = (
                f"【FIT高額売電モード (あと {days_until_fit_end} 日 / 売電単価 {sell_price}円/kWh)】\n"
                f"翌日予測PV: {est_pv_kwh:.1f} kWh ({weather_condition.upper()})。\n"
                f"夜間割安電力 (16.30円) で100%充電し、昼間太陽光を31円で全量売電することで、"
                f"1kWhあたり +{diff_price:.1f}円 の利ざや利益を追求します。"
            )
        else:
            # 🌿 卒FIT後 (2026/11/28〜 売電8.5円/kWh ＜ 買電36円/kWh)
            # 完全自家消費型動的充電アルゴリズム (気象連動)
            est_surplus_pv_kwh = max(0.0, est_pv_kwh - est_load_kwh)
            needed_battery_kwh_from_pv = min(self.battery_capacity_kwh, est_surplus_pv_kwh)
            needed_night_charge_kwh = max(0.0, self.battery_capacity_kwh - needed_battery_kwh_from_pv)

            base_target_soc = (needed_night_charge_kwh / self.battery_capacity_kwh) * 100.0

            # 天気予報データ連動の動的補正
            if weather_condition == "clear" or est_pv_kwh > 16:
                # 快晴: 深夜充電を極力抑えてPV受入スペースを空ける (20~40%)
                target_night_soc = min(base_target_soc, 35.0)
                weather_msg = f"☀️ 翌日快晴予測 ({est_pv_kwh:.1f}kWh)。太陽光余剰受入のため深夜充電を {target_night_soc:.0f}% に抑制。"
            elif weather_condition == "rainy" or est_pv_kwh < 6:
                # 大雨/荒天: PV期待できないため深夜最安帯で80〜95%充電
                target_night_soc = max(base_target_soc, 85.0)
                weather_msg = f"🌧️ 翌日雨天予測 ({est_pv_kwh:.1f}kWh)。昼間高額買電を避けるため深夜電力で {target_night_soc:.0f}% 急速充電。"
            else:
                # 曇り/標準
                target_night_soc = max(40.0, min(80.0, base_target_soc))
                weather_msg = f"⛅ 翌日標準発電予測 ({est_pv_kwh:.1f}kWh)。深夜充電 {target_night_soc:.0f}% とPV自家消費のハイブリッド運用。"

            target_night_soc = round(max(self.min_soc + 5.0, min(self.max_soc, target_night_soc)), 1)
            reason = f"【卒FIT完全自家消費モード】{weather_msg}"

        schedule_result = {
            "target_date": today.isoformat(),
            "is_fit_active": is_fit_active,
            "days_until_fit_end": days_until_fit_end,
            "fit_end_date": fit_end.isoformat(),
            "est_pv_kwh": est_pv_kwh,
            "est_load_kwh": est_load_kwh,
            "target_night_soc": target_night_soc,
            "weather_condition": weather_condition,
            "recommendation_reason": reason,
            "hourly_pv_prediction": tomorrow_pv_info.get("hourly", [])
        }

        save_daily_schedule(
            target_date=today.isoformat(),
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
