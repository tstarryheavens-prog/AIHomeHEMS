"""
scheduler.py - バックグラウンド常時稼働データ収集 ＆ AI最適化スケジューラー
Dockerコンテナ常時稼働時（NAS等）にバックグラウンドで30秒周期のテレメトリ収集と
毎日のAI充電計画最適化を実行します。
"""

import time
import os
from apscheduler.schedulers.background import BackgroundScheduler
from hems_logger import poll_and_log_all_data
from optimizer import PostFitOptimizer
import database

class HEMSController:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        database.init_db()
        self.optimizer = PostFitOptimizer(config_path)
        self.scheduler = BackgroundScheduler()

    def collect_telemetry_job(self):
        """30秒ごとに全機器（蓄電池, HEMS Web, 各部屋回路）のリアルタイムデータを一括収集・保存"""
        try:
            res = poll_and_log_all_data(self.config_path)
            # print(f"[Telemetry] Saved: Grid={res.get('grid_w')}W, PV={res.get('pv_w')}W, Batt={res.get('battery_w')}W, SOC={res.get('soc')}%")
        except Exception as e:
            print(f"[Scheduler] Error collecting telemetry: {e}")

    def run_daily_optimization_job(self):
        """毎日23:00に翌日の充電計画を作成し、DBへ保存"""
        print("[Scheduler] Running daily post-FIT AI optimization...")
        try:
            plan = self.optimizer.calculate_optimal_schedule()
            target_soc = plan.get("target_night_soc", 50.0)
            print(f"[Scheduler] AI Optimization completed. Target Night SOC: {target_soc}% (Weather: {plan.get('weather_condition')})")
        except Exception as e:
            print(f"[Scheduler] Error during daily optimization: {e}")

    def start(self):
        # 起動時に即時1回テレメトリ取得 (失敗してもスケジューラ登録を妨げない)
        print("[HEMSController] Initializing telemetry poll...")
        try:
            self.collect_telemetry_job()
        except Exception as ex:
            print(f"[HEMSController] Initial telemetry poll failed (will retry in schedule): {ex}")

        # 30秒周期のデータ収集ジョブ登録
        self.scheduler.add_job(self.collect_telemetry_job, 'interval', seconds=30, id="telemetry_job", replace_existing=True)

        # 毎日23:00の計画最適化ジョブ登録
        self.scheduler.add_job(self.run_daily_optimization_job, 'cron', hour=23, minute=0, id="optimization_job", replace_existing=True)

        # 起動時に即時1回最適化も計算 (安全実行)
        try:
            self.run_daily_optimization_job()
        except Exception as ex:
            print(f"[HEMSController] Initial optimization calculation skipped: {ex}")

        self.scheduler.start()
        print("[HEMSController] Background Scheduler started successfully (30s interval).")

if __name__ == "__main__":
    controller = HEMSController()
    controller.start()
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        controller.scheduler.shutdown()
        print("[HEMSController] Scheduler stopped.")
