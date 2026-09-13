import requests
import yaml

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

hems_ip = config.get('hems_controller', {}).get('ip_address', '192.168.1.100')
user_id = config.get('hems_controller', {}).get('user_id', '')
password = config.get('hems_controller', {}).get('password', '')

session = requests.Session()
session.get(f'http://{hems_ip}/login.cgi', params={'user_id': user_id, 'password': password, 'hoji': 'on'}, timeout=3)

pages = ['advice.html', 'check.html', 'cost.html', 'monitor1.html', 'notice.html', 'phvev.html', 'ringhome.html', 'setting.html', 'config.html', 'batt.html']
for p in pages:
    r = session.get(f'http://{hems_ip}/{p}', timeout=2)
    print(f"{p}: status {r.status_code}, len {len(r.text)}")
