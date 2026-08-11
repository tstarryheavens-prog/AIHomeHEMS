import sys
import yaml
from database import get_connection

sys.stdout.reconfigure(encoding='utf-8')

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hems_daily_history ORDER BY date_str DESC LIMIT 15')
    rows = [dict(r) for r in cursor.fetchall()]
    print("=== Recent HEMS Extracted Energy Breakdown ===")
    for r in rows:
        d = r['date_str']
        buy = r.get('buy_kwh', 0)
        sale = r.get('sale_kwh', 0)
        pv = r.get('pv_kwh', 0)
        self_kwh = r.get('self_kwh', 0)
        cost = r.get('cost_yen', 0)
        print(f"Date: {d} | Buy: {buy} kWh | Sale: {sale} kWh | PV Gen: {pv} kWh | Self-Cons: {self_kwh} kWh | Cost: Yen {cost}")
