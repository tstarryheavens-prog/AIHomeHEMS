import requests
import yaml
import re

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

hems_ip = config.get('hems_controller', {}).get('ip_address', '192.168.2.23')
user_id = config.get('hems_controller', {}).get('user_id', '')
password = config.get('hems_controller', {}).get('password', '')

session = requests.Session()
r_login = session.get(f'http://{hems_ip}/login.cgi', params={'user_id': user_id, 'password': password, 'hoji': 'on'}, timeout=3)

r = session.get(f'http://{hems_ip}/e-flow.html', timeout=2)
r.encoding = 'shift_jis'

print("=== Found Links and Forms ===")
links = re.findall(r'(?:href|src|action)=["\']?([^"\' >]+)', r.text)
for l in sorted(set(links)):
    print(l)

# Let's search for any HTML files or CGIs in index
r_menu = session.get(f'http://{hems_ip}/e-menu.html', timeout=2)
r_menu.encoding = 'shift_jis'
print("=== e-menu.html links ===")
links_m = re.findall(r'(?:href|src|action)=["\']?([^"\' >]+)', r_menu.text)
for l in sorted(set(links_m)):
    print(l)
