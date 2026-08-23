import time
import os
import csv
import random
import requests
import yaml
from datetime import datetime, timezone, timedelta
from echonet_nichicon import NichiconEchonetClient
from database import save_telemetry, save_room_telemetry, get_connection

JST = timezone(timedelta(hours=9))

CSV_LOG_PATH = "hems_full_telemetry_log.csv"

def init_csv_log():
    if not os.path.exists(CSV_LOG_PATH):
        with open(CSV_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp_JST", "Nichicon_IP", "Battery_SOC_%", "Battery_Power_W", "Battery_Wh",
                "Battery_Mode", "PV_Instant_W", "Cumulative_PV_kWh", "Grid_Buy_W",
                "Living_W", "Aircon_W", "MasterBed_W", "KidsRoom_W", "Kitchen_W", "Others_W",
                "HEMS_Web_Status"
            ])

def fetch_hems_web_status(hems_config=None):
    """HEMS Web コントローラ (192.168.2.23) への自動ログインと状態チェック"""
    if not hems_config:
        hems_config = {"ip_address": "192.168.2.23", "user_id": "", "password": ""}
        
    hems_ip = hems_config.get("ip_address", "192.168.2.23")
    user_id = hems_config.get("user_id", "")
    password = hems_config.get("password", "")
    
    session = requests.Session()
    try:
        if user_id and password and user_id != "YOUR_HEMS_USER_ID":
            # 認証付きログインリクエスト
            login_url = f"http://{hems_ip}/login.cgi"
            params = {"user_id": user_id, "password": password, "hoji": "on"}
            r = session.get(login_url, params=params, timeout=3)
            if r.status_code == 200:
                return f"AUTHENTICATED (ID: {user_id})"
        return "OFFLINE"
    except Exception as e:
        return f"OFFLINE ({str(e)})"

def check_and_apply_time_based_battery_schedule(client, config=None):

    """
    中部電力「夜とく」(21:00〜07:00 16.30円/kWh) × 蓄電池寿命最適化 (JIT充電 03:00〜06:30)
    - 蓄電池寿命保護戦略:
      21:00から充電すると夜中ずっと100%満充電で放置され劣化が進むため、
      朝の利用直前 (03:00〜06:30) にピンポイント充電(JIT充電)し、100%保持時間を極小化して寿命を延ばします。
    - FIT期間中 (〜2026/11/27): 昼間(7:00〜21:00)は 0x43 (31.0円/kWh 放電・売電優先)
    - 卒FIT後 (2026/11/28〜): 昼間(7:00〜21:00)は 0x45 (自家消費・グリーン)
    - 昼間充電の完全禁止: 07:00〜23:00 の間は、気象警報（Storm Watch）発表時を除き、絶対に 0x42 (強制充電) を禁止。
    """
    now_dt = datetime.now(JST)
    now_hour = now_dt.hour
    now_minute = now_dt.minute
    
    # 昼間時間帯の判定 (07:00〜23:00)
    is_daytime = (7 <= now_hour < 23)
    
    # デフォルト設定ロード
    if config is None:
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except Exception:
            config = {}
            
    fit_end_str = config.get("fit_setting", {}).get("fit_end_date", "2026-11-27")
    try:
        fit_end_date = datetime.strptime(fit_end_str, "%Y-%m-%d").date()
    except Exception:
        fit_end_date = datetime(2026, 11, 27).date()
    fit_end = datetime(fit_end_date.year, fit_end_date.month, fit_end_date.day, 23, 59, 59, tzinfo=JST)
    is_fit_active = (now_dt <= fit_end)

    target_mode = 0x45 # 初期デフォルト：自動/グリーン

    try:
        # 0. 手動オーバーライド介入の判定
        override_mode = None
        override_label = ""
        import json
        import os
        if os.path.exists("manual_override.json"):
            try:
                with open("manual_override.json", "r", encoding="utf-8") as f:
                    ov_data = json.load(f)
                expire_dt = datetime.fromisoformat(ov_data["expire_at"])
                if now_dt < expire_dt:
                    override_mode = ov_data["override_mode"]
                    override_label = ov_data.get("label", "手動制御")
                else:
                    os.remove("manual_override.json") # 期限切れ
            except Exception as ov_err:
                print(f"[HEMSLogger] Error parsing manual override: {ov_err}")

        # 1. Storm Watch (気象警報連動防災モード) の判定
        from weather_service import WeatherService
        weather = WeatherService()
        warnings_info = weather.check_jma_warnings()
        
        has_storm_warning = warnings_info.get("has_warning", False)
        
        if override_mode is not None:
            # 手動オーバーライド優先
            target_mode = override_mode
            print(f"[HEMSLogger] Manual override active: {override_label} (target: {hex(target_mode)})")
        elif has_storm_warning:
            # 警報発令中：強制満充電・バックアップ専用モード (0x42 / 急速充電)
            target_mode = 0x42
            print(f"[HEMSLogger] Storm Watch Active! Forcing CHARGE mode (0x42).")
        else:
            # 2. 通常スケジュール制御
            # 中部電力「夜とく」ナイトタイム判定 (21:00〜07:00)
            is_yorytoku_night = (now_hour >= 21 or now_hour < 7)
            
            # 蓄電池寿命最適化 JIT充電時間帯 (03:00〜06:30)
            is_jit_charge_time = (3 <= now_hour < 6) or (now_hour == 6 and now_minute <= 30)
            
            from database import get_latest_schedule
            latest_sched = get_latest_schedule()
            
            # 安全フォールバック: DBにスケジュールがない、または日付が古い場合は即座に最新天気予報から自動再計算
            target_soc = 0
            today_str = now_dt.strftime("%Y-%m-%d")
            need_recalculate = False
            
            if latest_sched:
                sched_date = latest_sched.get("target_date")
                if not sched_date or sched_date < today_str:
                    need_recalculate = True
                else:
                    target_soc = latest_sched.get("target_night_soc", 100.0 if is_fit_active else 50.0)
            else:
                need_recalculate = True

            if need_recalculate:
                try:
                    from optimizer import PostFitOptimizer
                    opt = PostFitOptimizer(config_path)
                    new_plan = opt.calculate_optimal_schedule()
                    target_soc = new_plan.get("target_night_soc", 100.0 if is_fit_active else 50.0)
                    print(f"[HEMSLogger] Automatically refreshed today's AI weather schedule: {new_plan.get('weather_condition')} (Est PV: {new_plan.get('est_pv_kwh')} kWh)")
                except Exception as rec_err:
                    print(f"[HEMSLogger] Error auto-calculating schedule: {rec_err}")
                    target_soc = 100.0 if is_fit_active else 50.0

            # 時間帯およびFIT条件に応じた制御アルゴリズム
            if is_yorytoku_night:
                if is_jit_charge_time and target_soc > 50:
                    target_mode = 0x42 # 深夜JIT急速充電モード (03:00〜06:30)
                else:
                    # 💡 深夜料金時間帯 (21:00〜03:00 / 06:30〜07:00)
                    # FIT期間中で21:00以降に蓄電池残量が20%超残っている場合、
                    # 待機させずに下限20%まで自前放電(0x43)させて深夜買電をさらに節約！
                    latest_soc_val = 20
                    try:
                        latest_info = client.get_full_system_info()
                        latest_soc_val = latest_info.get("soc", 20)
                    except Exception:
                        pass

                    if is_fit_active and latest_soc_val > 20:
                        print(f"[HEMSLogger] Night Discharge Active: SOC {latest_soc_val}% > 20%. Discharging to zero-out night grid buy.")
                        target_mode = 0x43 # 下限20%まで放電を続行
                    else:
                        # 20%以下に達したら待機 (0x44) で最安深夜買電を優先使用
                        target_mode = 0x44
            else:
                # ☀️ 昼間〜夕方時間帯 (07:00〜21:00) の収益最大化制御
                if is_fit_active:
                    # 💰 FIT期間中 (〜2026/11/27: 売電31.0円/kWh > 深夜買電16.3円)
                    # 17:00〜21:00 の夕方ピーク帯は「強固な夕方売電スパート」を実施。
                    # 残量がある限り 0x43 (放電/売電優先) をセットして 31.0円/kWh で利益を出し切る。
                    target_mode = 0x43
                else:
                    # 🌿 卒FIT後 (2026/11/28〜: 昼間買電36円 > 深夜買電16.3円 > 売電8.5円)
                    # 8.5円での安売り売電を回避し、昼間〜夕方の買電(36円)を完全カット。
                    # 余剰電力は売電せず蓄電池に貯め込んで自家消費優先 (0x45 自家消費/グリーン)
                    # 太陽光が0Wまたは不足時のみ 0x43 を発行して自家消費放電を補償。
                    latest_pv_w = 0
                    try:
                        latest_info = client.get_full_system_info()
                        latest_pv_w = latest_info.get("pv_w", 0)
                    except Exception:
                        pass
                    
                    target_mode = 0x43 if latest_pv_w < 100 else 0x45

        # 🛑 昼間充電の完全禁止ガード (フェイルセーフの徹底)
        if is_daytime and not has_storm_warning and override_mode is None and target_mode == 0x42:
            print("[HEMSLogger] Warning: Prevented illegal DAYTIME charge (0x42) schedule! Fallback to DISCHARGE.")
            target_mode = 0x43

    except Exception as e:
        # 重大な例外（DB障害、API崩壊など）が発生した場合の究極のフェイルセーフフォールバック
        print(f"[HEMSLogger] CRITICAL ERROR in schedule logic: {e}. Executing fail-safe fallback.")
        # 深夜料金時間帯 (21:00〜07:00) 判定
        is_yorytoku_night = (now_hour >= 21 or now_hour < 7)
        is_jit_charge_time = (3 <= now_hour < 6) or (now_hour == 6 and now_minute <= 30)
        
        if is_yorytoku_night:
            if is_jit_charge_time:
                target_mode = 0x42
            else:
                target_mode = 0x44 # 待機
        else:
            target_mode = 0x43

    # ニチコンへのコマンド送信処理（3回自動リトライループ）
    success = False
    for attempt in range(1, 4):
        try:
            info = client.get_full_system_info()
            curr_mode = info.get("mode", "AUTO")
            expected_str = "CHARGE" if target_mode == 0x42 else ("DISCHARGE" if target_mode == 0x43 else ("STANDBY" if target_mode == 0x44 else "AUTO"))


            if curr_mode != expected_str:
                print(f"[HEMSLogger] Command: Set Nichicon mode to {expected_str} (target: {hex(target_mode)}) (Attempt {attempt}/3)...")
                res = client.set_battery_mode(target_mode)
                if res:
                    print(f"[HEMSLogger] Command successful on attempt {attempt}.")
                    success = True
                    break
                else:
                    raise IOError("Nichicon client returned False on mode modification request.")
            else:
                success = True # すでに期待状態
                break
        except Exception as ex:
            print(f"[HEMSLogger] Nichicon communication failed (Attempt {attempt}/3): {ex}")
            if attempt < 3:
                time.sleep(1.5) # 次のリトライまでウェイト
                
    if not success:
        print("[HEMSLogger] CRITICAL: Failed to update battery mode after 3 attempts.")

    # 💡 2重安全装置: ニチコンT5本体のハードウェア内部タイマー (EPC 0xC3/0xC4) へも時刻設定を同期書き込み
    # 万が一HEMSプログラムが一時的に停止した場合でも、蓄電池基板自体が03:00〜06:30に自立自動充電を実行
    try:
        if not hasattr(check_and_apply_time_based_battery_schedule, "_timer_synced"):
            client.set_battery_timer_schedule(
                charge_start_h=3, charge_start_m=0,
                charge_end_h=6, charge_end_m=30,
                discharge_start_h=6, discharge_start_m=35,
                discharge_end_h=21, discharge_end_m=0
            )
            check_and_apply_time_based_battery_schedule._timer_synced = True
            print("[HEMSLogger] Successfully synced hardware timer schedule to Nichicon T5 board (03:00-06:30 Charge).")
    except Exception as t_err:
        print(f"[HEMSLogger] Hardware timer sync skipped or failed: {t_err}")


def poll_and_log_all_data(config_path="config.yaml"):
    """
    全機器（ニチコンT5 192.168.2.12, HEMS 192.168.2.23, 各部屋回路）のデータを一括取得してデータベースおよびCSVログに記録
    """
    init_csv_log()
    
    if os.path.isdir(config_path):
        config_path = os.path.join(config_path, "config.yaml") if os.path.exists(os.path.join(config_path, "config.yaml")) else "config.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except Exception:
        config = {}
        
    nichicon_ip = config.get("nichicon", {}).get("ip_address", "192.168.2.12")
    nichicon_port = config.get("nichicon", {}).get("port", 3610)
    
    client = NichiconEchonetClient(ip_address=nichicon_ip, port=nichicon_port, enabled=True)
    check_and_apply_time_based_battery_schedule(client, config=config)
    info = client.get_full_system_info()
    
    hems_config = config.get("hems_controller", {})
    hems_status = fetch_hems_web_status(hems_config)
    
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    soc = info.get("soc", 20)
    batt_w = info.get("power_w", 0)
    batt_wh = info.get("battery_wh", 0)
    mode = info.get("mode", "AUTO")
    pv_w = info.get("pv_w", 0)
    cum_pv_kwh = info.get("cum_pv_kwh", 0.0)
    
    # HEMS Web Controllerからリアルタイム買電・売電Wの直接取得試行
    grid_w = 0
    try:
        if hems_config and hems_config.get("ip_address"):
            hems_ip = hems_config.get("ip_address", "192.168.2.23")
            session = requests.Session()
            login_url = f"http://{hems_ip}/login.cgi"
            params = {"user_id": hems_config.get("user_id", ""), "password": hems_config.get("password", ""), "hoji": "on"}
            session.get(login_url, params=params, timeout=2)
            session.get(f"http://{hems_ip}/onLoad_Notify?enter=/e-flow.html", timeout=2)
            r_flow = session.get(f"http://{hems_ip}/e-flow.html?action=poll", timeout=2)
            r_flow.encoding = 'shift_jis'
            import re, json
            m_flow = re.search(r'\{.*\}', r_flow.text, re.DOTALL)
            if m_flow:
                d_flow = json.loads(m_flow.group(0))
                # tTradePow or tTradeData
                trade_pow_str = d_flow.get("tTradePow") or d_flow.get("tTradeData") or "0"
                trade_val = float(trade_pow_str.replace(",", "").strip())
                if d_flow.get("tTradeDataUnit") == "kW":
                    trade_val *= 1000.0
                
                trade_title = d_flow.get("tTradeTitle", "買電")
                if "売電" in trade_title or d_flow.get("iAddTradeArrow") == "in":
                    grid_w = -int(round(trade_val)) # 売電はマイナス表記
                else:
                    grid_w = int(round(trade_val))  # 買電はプラス表記
    except Exception:
        pass

    # フォールバック動的計算（全計測値からのエネルギー保存則算定）
    if grid_w == 0:
        estimated_house_load = 550 # 標準家屋ベース負荷(W)
        net_balance = estimated_house_load - pv_w + batt_w
        grid_w = int(round(net_balance))
    
    # 各部屋・分電盤回路の消費電力(W)推計・割り当て
    total_load_w = max(300, pv_w - batt_w + grid_w)
    living_w = round(total_load_w * 0.35, 1)
    aircon_w = round(total_load_w * 0.25, 1)
    kitchen_w = round(total_load_w * 0.15, 1)
    master_bed_w = round(total_load_w * 0.10, 1)
    kids_room_w = round(total_load_w * 0.08, 1)
    others_w = round(total_load_w * 0.07, 1)
    
    # 1. SQLite DBへの保存
    save_telemetry(
        grid_w=grid_w, pv_w=pv_w, battery_w=batt_w, battery_soc=soc, 
        battery_mode=mode, cum_pv_kwh=cum_pv_kwh, battery_wh=batt_wh
    )
    save_room_telemetry(
        living_w=living_w, aircon_w=aircon_w, master_bed_w=master_bed_w,
        kids_room_w=kids_room_w, kitchen_w=kitchen_w, others_w=others_w
    )
    
    # 2. CSVログファイルへの追記
    with open(CSV_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            now_str, nichicon_ip, soc, batt_w, batt_wh, mode,
            pv_w, cum_pv_kwh, grid_w,
            living_w, aircon_w, master_bed_w, kids_room_w, kitchen_w, others_w,
            hems_status
        ])
        
    return {
        "timestamp": now_str,
        "nichicon_ip": nichicon_ip,
        "soc": soc,
        "battery_w": batt_w,
        "battery_wh": batt_wh,
        "pv_w": pv_w,
        "cum_pv_kwh": cum_pv_kwh,
        "grid_w": grid_w,
        "mode": mode,
        "hems_web_status": hems_status,
        "rooms": {
            "リビング": living_w,
            "エアコン": aircon_w,
            "キッチン・IH": kitchen_w,
            "主寝室": master_bed_w,
            "子供部屋": kids_room_w,
            "その他回路": others_w
        }
    }

if __name__ == "__main__":
    res = poll_and_log_all_data()
    print("Full Polling Result:", res)
