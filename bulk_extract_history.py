import requests
import yaml
import sqlite3
import time
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from database import get_connection

JST = timezone(timedelta(hours=9))

class BulkExtractionProgress:
    def __init__(self):
        self.is_running = False
        self.total_days = 0
        self.processed_days = 0
        self.extracted_records = 0
        self.current_date_str = ""
        self.error_message = ""
        self.start_time = None
        self.completed_time = None

    def to_dict(self):
        pct = (self.processed_days / self.total_days * 100.0) if self.total_days > 0 else 0.0
        return {
            "is_running": self.is_running,
            "total_days": self.total_days,
            "processed_days": self.processed_days,
            "extracted_records": self.extracted_records,
            "progress_percent": round(pct, 1),
            "current_date_str": self.current_date_str,
            "error_message": self.error_message
        }

_progress = BulkExtractionProgress()

def get_bulk_extraction_status():
    return _progress.to_dict()

def _run_bulk_extraction_worker(start_year, end_year):
    global _progress
    _progress.is_running = True
    _progress.processed_days = 0
    _progress.extracted_records = 0
    _progress.error_message = ""
    _progress.start_time = datetime.now(JST)

    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        _progress.error_message = f"Config load error: {e}"
        _progress.is_running = False
        return

    hems_conf = config.get("hems_controller", {})
    ip = hems_conf.get("ip_address", "192.168.2.23")
    user_id = hems_conf.get("user_id", "")
    password = hems_conf.get("password", "")

    session = requests.Session()
    login_url = f"http://{ip}/login.cgi"
    params = {"user_id": user_id, "password": password, "hoji": "on", "disp_url": ""}
    
    try:
        res_login = session.get(login_url, params=params, timeout=5)
        if res_login.status_code != 200:
            _progress.error_message = "HEMS Web ログインに失敗しました"
            _progress.is_running = False
            return
    except Exception as e:
        _progress.error_message = f"接続エラー: {e}"
        _progress.is_running = False
        return

    # DBテーブルの初期化
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hems_daily_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str TEXT UNIQUE,
                cost_yen REAL,
                self_sufficiency_percent REAL,
                fetched_at DATETIME
            )
        ''')
        conn.commit()

    start_date = datetime(start_year, 1, 1, tzinfo=JST)
    today = datetime.now(JST)
    _progress.total_days = (today - start_date).days + 1

    for day_idx in range(_progress.total_days):
        current_date = start_date + timedelta(days=day_idx)
        date_param = current_date.strftime("%Y%m%d")
        date_display = current_date.strftime("%Y-%m-%d")
        _progress.current_date_str = date_display
        _progress.processed_days = day_idx + 1

        try:
            session.get(f"http://{ip}/onLoad_Notify?enter=/monitor1.html?hToday={date_param}", timeout=2)
            no_cache = int(time.time() * 1000)
            poll_url = f"http://{ip}/monitor1.html?hToday={date_param}&action=poll&cache={no_cache}"
            res = session.get(poll_url, timeout=2.5)
            res.encoding = 'shift_jis'

            if res.status_code == 200 and "tEMonitorTodayright" in res.text:
                match = re.search(r'\{.*\}', res.text, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    cost_val = float(data.get("tEMonitorTodayright", "0").replace(",", ""))
                    self_suff_val = float(data.get("tEMonitorTodayleft", "0"))

                    if cost_val > 0:
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT OR REPLACE INTO hems_daily_history (date_str, cost_yen, self_sufficiency_percent, fetched_at)
                                VALUES (?, ?, ?, ?)
                            ''', (date_display, cost_val, self_suff_val, datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                        _progress.extracted_records += 1
        except Exception:
            pass

    # 月別履歴データ(2016年〜2026年)も全自動抽出・保存
    try:
        from hems_monthly_importer import extract_all_monthly_history_from_2016
        extract_all_monthly_history_from_2016()
    except Exception:
        pass

    _progress.is_running = False
    _progress.completed_time = datetime.now(JST)

def start_bulk_extraction_async(start_year=2016, end_year=2026):
    global _progress
    if _progress.is_running:
        return False
    t = threading.Thread(target=_run_bulk_extraction_worker, args=(start_year, end_year), daemon=True)
    t.start()
    return True

if __name__ == "__main__":
    start_bulk_extraction_async()
    while _progress.is_running:
        print("Status:", get_bulk_extraction_status())
        time.sleep(2)
