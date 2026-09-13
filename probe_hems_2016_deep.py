import requests
import yaml
import sys
import json
import re
import time

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

hems_conf = config.get("hems_controller", {})
ip = hems_conf.get("ip_address", "192.168.1.100")
user_id = hems_conf.get("user_id", "")
password = hems_conf.get("password", "")

session = requests.Session()
login_url = f"http://{ip}/login.cgi"
params = {"user_id": user_id, "password": password, "hoji": "on", "disp_url": ""}
res_login = session.get(login_url, params=params, timeout=5)
print(f"Login status: {res_login.status_code}")

print("\n=== 1. Probing CGI & CSV Download Endpoints on 192.168.1.100 ===")

cgi_candidates = [
    "/csv_down.cgi", "/csvdown.cgi", "/csv_export.cgi", "/dl_csv.cgi", "/download.cgi",
    "/data_down.cgi", "/history_down.cgi", "/log.cgi", "/backup.cgi", "/export.cgi",
    "/hems_log.csv", "/hems.csv", "/log.csv", "/data.csv", "/history.csv", "/monitor.csv",
    "/monitor_daily.csv", "/monitor_monthly.csv", "/hems_history.csv", "/dl.cgi",
    "/csv_download.cgi", "/csv.cgi", "/csv_down.html", "/data.cgi", "/save.cgi",
    "/history.cgi", "/log_down.cgi", "/monitor1_data.cgi", "/monitor_log.cgi",
    "/csv", "/download", "/export", "/log", "/data", "/history", "/backup",
    "/setting.html", "/sys_setting.html", "/maintenance.html", "/device.html"
]

found_endpoints = []

for cgi in cgi_candidates:
    try:
        r = session.get(f"http://{ip}{cgi}", timeout=2)
        if r.status_code in [200, 302, 401] and len(r.content) > 0:
            print(f"  [FOUND] {cgi} -> Status {r.status_code}, Length: {len(r.content)} bytes")
            found_endpoints.append((cgi, r.status_code, len(r.content)))
            if "csv" in cgi or "log" in cgi or "data" in cgi:
                print(f"    Content Excerpt: {r.text[:200]}")
    except Exception:
        pass
    time.sleep(0.05)

print("\n=== 2. Testing 2016-2024 Date Parameter Variations on monitor1, monitor2, monitor3 ===")

date_params_to_test = [
    # YYYYMMDD formats
    "20160101", "20160615", "20161231",
    "20180101", "20200101", "20220101", "20240101",
    # YYMMDD formats
    "160101", "180101", "200101", "220101", "240101",
    # YYYY-MM-DD formats
    "2016-01-01", "2018-01-01", "2020-01-01", "2022-01-01",
    # YYYYMM formats
    "201601", "201801", "202001", "202201", "202401"
]

param_names = ["hToday", "hDate", "hYear", "hMonth", "date", "year", "ym", "period"]

for page in ["/monitor1.html", "/monitor2.html", "/monitor3.html"]:
    print(f"\n--- Testing Page {page} ---")
    for d in ["20160101", "20160615", "20180101", "20200101", "20220101", "20240101"]:
        for pname in ["hToday", "hDate", "hYear", "hMonth", "date"]:
            try:
                session.get(f"http://{ip}/onLoad_Notify?enter={page}?{pname}={d}", timeout=2)
                no_cache = int(time.time() * 1000)
                poll_url = f"http://{ip}{page}?{pname}={d}&action=poll&cache={no_cache}"
                r = session.get(poll_url, timeout=2.5)
                r.encoding = 'shift_jis'

                if r.status_code == 200 and "{" in r.text:
                    match = re.search(r'\{.*\}', r.text, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                        disp = data.get("tEMonitorDate", "")
                        v1 = data.get("tEMonitorTodayleft", "0")
                        v2 = data.get("tEMonitorTodayright", "0")
                        if v1 != "0" or v2 != "0" or "16" in disp or "18" in disp or "20" in disp or "22" in disp:
                            print(f"  [VALID 2016 DATA] {page}?{pname}={d} -> Date Disp: '{disp}', Left: '{v1}', Right: '{v2}'")
            except Exception:
                pass
            time.sleep(0.05)

print("\n=== Deep Probing Complete ===")
