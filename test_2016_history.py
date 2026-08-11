import requests
import yaml
import time
import json
import re

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

hems_conf = config.get('hems_controller', {})
ip = hems_conf.get('ip_address', '192.168.2.23')
user_id = hems_conf.get('user_id', '')
password = hems_conf.get('password', '')

session = requests.Session()
login_url = f'http://{ip}/login.cgi'
params = {'user_id': user_id, 'password': password, 'hoji': 'on', 'disp_url': ''}
session.get(login_url, params=params, timeout=5)

test_dates = ['20160101', '20160615', '20180101', '20200101', '20220101', '20240101']

import sys
sys.stdout.reconfigure(encoding='utf-8')

print('=== Testing Historical Data Retrieval from 2016 ===')
for d in test_dates:
    session.get(f'http://{ip}/onLoad_Notify?enter=/monitor1.html?hToday={d}', timeout=2)
    no_cache = int(time.time() * 1000)
    poll_url = f'http://{ip}/monitor1.html?hToday={d}&action=poll&cache={no_cache}'
    res = session.get(poll_url, timeout=3)
    res.encoding = 'shift_jis'
    match = re.search(r'\{.*\}', res.text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        disp = data.get("tEMonitorDate")
        cost = data.get("tEMonitorTodayright")
        self_suff = data.get("tEMonitorTodayleft")
        print(f"Date {d} -> Date Display: {disp}, Cost: Yen {cost}, Self Sufficiency: {self_suff}%")
