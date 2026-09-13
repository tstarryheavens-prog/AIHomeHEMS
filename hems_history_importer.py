import requests
import yaml
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from database import get_connection

JST = timezone(timedelta(hours=9))

def fetch_hems_past_days_history(days=30):
    """
    HEMS Webコントローラ(192.168.1.100)から過去N日間の電気代・自給率・消費電力量の履歴ログを自動収集しDB保存する
    """
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception:
        return 0

    hems_conf = config.get("hems_controller", {})
    ip = hems_conf.get("ip_address", "192.168.1.100")
    user_id = hems_conf.get("user_id", "")
    password = hems_conf.get("password", "")

    if not user_id or user_id == "YOUR_HEMS_USER_ID":
        print("[HEMS History Importer] User ID not configured in config.yaml.")
        return 0

    session = requests.Session()
    login_url = f"http://{ip}/login.cgi"
    params = {"user_id": user_id, "password": password, "hoji": "on", "disp_url": ""}
    
    try:
        login_res = session.get(login_url, params=params, timeout=4)
        if login_res.status_code != 200:
            print("[HEMS History Importer] Login failed.")
            return 0
    except Exception as e:
        print(f"[HEMS History Importer] Connection error: {e}")
        return 0

    # DBテーブル確保
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

    today = datetime.now(JST)
    records_saved = 0

    for i in range(days):
        target_date = today - timedelta(days=i)
        date_param = target_date.strftime("%Y%m%d")
        date_display = target_date.strftime("%Y-%m-%d")

        try:
            # 1. monitor1.html (電気代)
            session.get(f"http://{ip}/onLoad_Notify?enter=/monitor1.html?hToday={date_param}", timeout=2)
            no_cache = int(time.time() * 1000)
            poll_url = f"http://{ip}/monitor1.html?hToday={date_param}&action=poll&cache={no_cache}"
            res1 = session.get(poll_url, timeout=3)
            res1.encoding = 'shift_jis'

            cost_val = 0.0
            if res1.status_code == 200 and "tEMonitorTodayright" in res1.text:
                match1 = re.search(r'\{.*\}', res1.text, re.DOTALL)
                if match1:
                    d1 = json.loads(match1.group(0))
                    cost_val = float(d1.get("tEMonitorTodayright", "0").replace(",", ""))

            # 2. monitor2.html (売電 kWh ＆ 買電 kWh)
            session.get(f"http://{ip}/onLoad_Notify?enter=/monitor2.html?hToday={date_param}", timeout=2)
            poll_url2 = f"http://{ip}/monitor2.html?hToday={date_param}&action=poll&cache={no_cache}"
            res2 = session.get(poll_url2, timeout=3)
            res2.encoding = 'shift_jis'

            sale_kwh = 0.0
            buy_kwh = 0.0
            if res2.status_code == 200 and "tEMonitorTodayleft" in res2.text:
                match2 = re.search(r'\{.*\}', res2.text, re.DOTALL)
                if match2:
                    d2 = json.loads(match2.group(0))
                    sale_kwh = float(d2.get("tEMonitorTodayleft", "0").replace(",", ""))
                    buy_kwh = float(d2.get("tEMonitorTodayright", "0").replace(",", ""))

            pv_kwh = sale_kwh * 1.5 # 発電量概算
            self_kwh = max(0.0, pv_kwh - sale_kwh) # 自家消費

            if cost_val > 0 or buy_kwh > 0 or sale_kwh > 0:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO hems_daily_history 
                        (date_str, cost_yen, load_kwh, buy_kwh, sale_kwh, pv_kwh, self_kwh, self_sufficiency_percent, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, ?)
                    ''', (date_display, cost_val, buy_kwh, buy_kwh, sale_kwh, pv_kwh, self_kwh, datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                records_saved += 1
        except Exception:
            pass

    print(f"[HEMS History Importer] Successfully fetched and stored {records_saved} days of historical records from HEMS!")
    return records_saved

from database import get_connection, get_hems_daily_history

if __name__ == "__main__":
    count = fetch_hems_past_days_history(days=14)
    records = get_hems_daily_history()
    print("HEMS Daily History Records:", records)
