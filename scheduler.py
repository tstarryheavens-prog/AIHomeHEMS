import time
import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from broute_collector import BRouteCollector
from echonet_nichicon import NichiconEchonetClient, EPC_BATTERY_MODE
from optimizer import PostFitOptimizer
import database

class HEMSController:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        database.init_db()
        
        b_conf = self.config.get("broute", {})
        n_conf = self.config.get("nichicon", {})
        
        self.broute = BRouteCollector(
            port=b_conf.get("port", "COM3"),
            broute_id=b_conf.get("id", ""),
            broute_pass=b_conf.get("password", ""),
            enabled=b_conf.get("enabled", False)
        )
        
        self.nichicon = NichiconEchonetClient(
            ip_address=n_conf.get("ip_address", "192.168.1.100"),
            enabled=n_conf.get("enabled", False)
        )
        
        self.optimizer = PostFitOptimizer(config_path)
        self.scheduler = BackgroundScheduler()

    def collect_telemetry_job(self):
        """30秒ごとにBルートとニチコン蓄電池のリアルタイムデータを収集・保存"""
        b_data = self.broute.read_instantaneous_power()
        n_data = self.nichicon.get_battery_info()
        
        grid_w = b_data.get("grid_w", 0)
        soc = n_data.get("soc", 50)
        battery_w = n_data.get("power_w", 0)
        mode = n_data.get("mode", "AUTO")
        
        # PV瞬時W計算 (簡略化)
        pv_w = max(0, -grid_w + battery_w) if grid_w < 0 else 0
        
        database.save_telemetry(grid_w, pv_w, battery_w, soc, mode)
        # print(f"[Telemetry] Grid:{grid_w}W, SOC:{soc}%, Batt:{battery_w}W")

    def run_daily_optimization_job(self):
        """毎日23:00に翌日の充電計画を作成し、必要に応じてニチコンの運転モードを切替"""
        print("[Scheduler] Running daily post-FIT optimization...")
        plan = self.optimizer.calculate_optimal_schedule()
        target_soc = plan["target_night_soc"]
        
        # 目標SOCが高ければ深夜充電モード(0x42)へ、低ければ自動モード(0x45)へ
        if target_soc > 50.0:
            print(f"[Scheduler] Switching Nichicon ESS to MIDNIGHT CHARGE mode (Target SOC: {target_soc}%)")
            self.nichicon.set_battery_mode(0x42) # 充電
        else:
            print(f"[Scheduler] Keeping Nichicon ESS in AUTO PV-PRIORITY mode (Target SOC: {target_soc}%)")
            self.nichicon.set_battery_mode(0x45) # 自動

    def start(self):
        self.broute.connect()
        # 30秒周期のデータ収集
        self.scheduler.add_job(self.collect_telemetry_job, 'interval', seconds=30)
        # 毎日23:00の計画最適化実行
        self.scheduler.add_job(self.run_daily_optimization_job, 'cron', hour=23, minute=0)
        
        # 起動時に即時1回最適化を実行しておく
        self.run_daily_optimization_job()
        
        self.scheduler.start()
        print("[HEMSController] Scheduler started successfully.")

if __name__ == "__main__":
    controller = HEMSController()
    controller.start()
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        controller.scheduler.shutdown()
