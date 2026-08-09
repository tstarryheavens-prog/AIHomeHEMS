import requests
import yaml
import sqlite3
import time
import json
import re
from datetime import datetime, timezone, timedelta
from database import get_connection

JST = timezone(timedelta(hours=9))

def extract_all_monthly_history_from_2016():
    """
    2016年から現在までの全月別電気代・自給率履歴を HEMS Web コントローラから一括抽出する
    """
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception:
        return 0

    hems_conf = config.get("hems_controller", {})
    ip = hems_conf.get("ip_address", "192.168.2.23")
    user_id = hems_conf.get("user_id", "")
    password = hems_conf.get("password", "")

    session = requests.Session()
    login_url = f"http://{ip}/login.cgi"
    params = {"user_id": user_id, "password": password, "hoji": "on", "disp_url": ""}
    
    logged_in = False
    for attempt in range(3):
        try:
            res = session.get(login_url, params=params, timeout=5)
            if res.status_code == 200:
                logged_in = True
                break
        except Exception:
            time.sleep(1)

    if not logged_in:
        print("[Monthly History Extractor] Login failed after retries.")
        return 0

    # DBテーブル作成
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hems_monthly_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year_month TEXT UNIQUE,
                cost_yen REAL,
                self_sufficiency_percent REAL,
                fetched_at DATETIME
            )
        ''')
        conn.commit()

    count = 0
    now_year = datetime.now(JST).year
    now_month = datetime.now(JST).month

    for year in range(2016, now_year + 1):
        max_m = now_month if year == now_year else 12
        for month in range(1, max_m + 1):
            date_param = f"{year}{month:02d}01"
            ym_str = f"{year}-{month:02d}"

            try:
                session.get(f"http://{ip}/onLoad_Notify?enter=/monitor2.html?hToday={date_param}", timeout=2)
                poll_url = f"http://{ip}/monitor2.html?hToday={date_param}&action=poll"
                res = session.get(poll_url, timeout=3)
                res.encoding = 'shift_jis'

                match = re.search(r'\{.*\}', res.text, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    val_left = float(data.get("tEMonitorTodayleft", "0").replace(",", "").replace("¥", "").replace("%", "").strip())
                    val_right = float(data.get("tEMonitorTodayright", "0").replace(",", "").replace("¥", "").replace("%", "").strip())
                    
                    cost_val = max(val_left, val_right)
                    self_suff_val = min(val_left, val_right)

                    if cost_val > 0:
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT OR REPLACE INTO hems_monthly_history (year_month, cost_yen, self_sufficiency_percent, fetched_at)
                                VALUES (?, ?, ?, ?)
                            ''', (ym_str, cost_val, self_suff_val, datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                        count += 1
            except Exception:
                pass

    print(f"[Monthly History Extractor] Successfully extracted {count} months of historical records from 2016 to present!")
    return count

def get_hems_monthly_history():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hems_monthly_history ORDER BY year_month ASC")
        return [dict(row) for row in cursor.fetchall()]

if __name__ == "__main__":
    c = extract_all_monthly_history_from_2016()
    print("Monthly History Records:", get_hems_monthly_history())
