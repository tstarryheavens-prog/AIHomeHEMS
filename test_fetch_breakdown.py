import requests
import yaml
import sys
import json
import re
import time
from datetime import datetime, timedelta, timezone
from database import get_connection, now_jst

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

hems_conf = config.get("hems_controller", {})
ip = hems_conf.get("ip_address", "192.168.2.23")
user_id = hems_conf.get("user_id", "")
password = hems_conf.get("password", "")

session = requests.Session()
login_url = f"http://{ip}/login.cgi"
params = {"user_id": user_id, "password": password, "hoji": "on", "disp_url": ""}
session.get(login_url, params=params, timeout=5)

JST = timezone(timedelta(hours=9))
today = datetime.now(JST)

print("=== Fetching Daily Breakdown from HEMS Controller ===")
for i in range(14):
    target_date = today - timedelta(days=i)
    date_param = target_date.strftime("%Y%m%d")
    date_display = target_date.strftime("%Y-%m-%d")

    cost_val = 0.0
    sale_kwh = 0.0
    buy_kwh = 0.0

    try:
        # 1. monitor1.html (電気代)
        session.get(f"http://{ip}/onLoad_Notify?enter=/monitor1.html?hToday={date_param}", timeout=3)
        time.sleep(0.2)
        res1 = session.get(f"http://{ip}/monitor1.html?hToday={date_param}&action=poll", timeout=4)
        res1.encoding = 'shift_jis'

        if res1.status_code == 200 and "tEMonitorTodayright" in res1.text:
            m1 = re.search(r'\{.*\}', res1.text, re.DOTALL)
            if m1:
                d1 = json.loads(m1.group(0))
                cost_val = float(d1.get("tEMonitorTodayright", "0").replace(",", "").replace("¥", "").strip())
    except Exception as e:
        print(f"Error fetching cost for {date_display}: {e}")

    try:
        # 2. monitor2.html (売電 kWh ＆ 買電 kWh)
        session.get(f"http://{ip}/onLoad_Notify?enter=/monitor2.html?hToday={date_param}", timeout=3)
        time.sleep(0.2)
        res2 = session.get(f"http://{ip}/monitor2.html?hToday={date_param}&action=poll", timeout=4)
        res2.encoding = 'shift_jis'

        if res2.status_code == 200 and "tEMonitorTodayleft" in res2.text:
            m2 = re.search(r'\{.*\}', res2.text, re.DOTALL)
            if m2:
                d2 = json.loads(m2.group(0))
                sale_kwh = float(d2.get("tEMonitorTodayleft", "0").replace(",", "").strip())
                buy_kwh = float(d2.get("tEMonitorTodayright", "0").replace(",", "").strip())
    except Exception as e:
        print(f"Error fetching kwh for {date_display}: {e}")

    # 自家消費 ＝ 買電 ＋ 売電推計に基づく自家消費プロファイル
    pv_kwh = round(sale_kwh + (buy_kwh * 0.4), 1)
    self_kwh = round(pv_kwh - sale_kwh, 1)

    print(f"Date {date_display} -> 買電: {buy_kwh} kWh | 売電: {sale_kwh} kWh | 発電: {pv_kwh} kWh | 自家消費: {self_kwh} kWh | 電気代: Yen {cost_val}")

    if cost_val > 0 or buy_kwh > 0 or sale_kwh > 0:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO hems_daily_history 
                (date_str, cost_yen, load_kwh, buy_kwh, sale_kwh, pv_kwh, self_kwh, self_sufficiency_percent, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, ?)
            ''', (date_display, cost_val, buy_kwh, buy_kwh, sale_kwh, pv_kwh, self_kwh, now_jst()))
            conn.commit()

    time.sleep(0.3)

print("Successfully saved daily energy breakdown to database!")
