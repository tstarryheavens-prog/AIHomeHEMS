import pandas as pd
import sqlite3
import os
import yaml
from database import get_connection

def import_katene_csv(file_path):
    """
    カテエネ（中部電力）やHEMS書き出し等、各種電力会社のCSVログを判定してDBインポートする
    対応カラム例:
    - DATE, 日時, 日付, 時間
    - USE, BUY, 使用量, 消費量, kWh
    - USE_CHARGE, 電気代, 料金, 金額
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"ファイルが見つかりません: {file_path}"}

    try:
        # ディレクトリ・単価情報のロード
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            unit_price = config.get("tariff", {}).get("daytime_rate", 31.0)
        except Exception:
            unit_price = 31.0

        # エンコーディング対応 (Shift_JIS / UTF-8)
        try:
            df = pd.read_csv(file_path, encoding="shift_jis")
        except Exception:
            df = pd.read_csv(file_path, encoding="utf-8")

        cols = list(df.columns)
        cols_upper = [str(c).upper().strip() for c in cols]
        
        # 1. 日付カラム検出 (DATE, 日時, 日付, TIME, 年月)
        date_col = None
        for i, c in enumerate(cols_upper):
            if any(k in c for k in ["DATE", "日", "時", "TIME", "年月"]):
                date_col = cols[i]
                break

        # 2. 電力(kWh)カラム検出 (USE, BUY, KWH, 使用, 量, 電力, VALUE, CONS)
        kwh_col = None
        # 優先順位: 'USE', 'BUY', 'KWH', '使用量'
        for prio in ["USE", "BUY", "KWH", "使用量", "消費量", "使用電力量"]:
            for i, c in enumerate(cols_upper):
                if prio in c and "CHARGE" not in c and "CO2" not in c and "MONEY" not in c:
                    kwh_col = cols[i]
                    break
            if kwh_col:
                break
        
        if not kwh_col:
            for i, c in enumerate(cols_upper):
                if any(k in c for k in ["USE", "BUY", "KWH", "使用", "量", "電力", "VALUE", "CONS"]) and "CHARGE" not in c:
                    kwh_col = cols[i]
                    break

        if not date_col or not kwh_col:
            return {"success": False, "error": f"CSVの列名を解析できませんでした。検出列: {cols}"}

        # 3. 電気代(円)カラム検出 (USE_CHARGE, CHARGE, 料金, 電気代, 金額)
        cost_col = None
        for i, c in enumerate(cols_upper):
            if any(k in c for k in ["USE_CHARGE", "CHARGE", "料金", "電気代", "金額", "COST"]):
                cost_col = cols[i]
                break

        df['parsed_time'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=['parsed_time'])
        df['hour'] = df['parsed_time'].dt.hour
        df['date_str'] = df['parsed_time'].dt.strftime("%Y-%m-%d")
        df['year_month'] = df['parsed_time'].dt.strftime("%Y-%m")
        df['kwh'] = pd.to_numeric(df[kwh_col].astype(str).str.replace(",", ""), errors='coerce').fillna(0.0)

        if cost_col:
            df['cost_yen'] = pd.to_numeric(df[cost_col].astype(str).str.replace(",", "").str.replace("¥", ""), errors='coerce').fillna(0.0)
        else:
            df['cost_yen'] = df['kwh'] * unit_price

        total_rows = len(df)
        if total_rows == 0:
            return {"success": False, "error": "有効なデータ行が見つかりませんでした。"}

        min_date = df['date_str'].min()
        max_date = df['date_str'].max()
        total_kwh = float(df['kwh'].sum())
        total_cost = float(df['cost_yen'].sum())

        with get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. historical_load テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historical_load (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME UNIQUE,
                    hour INTEGER,
                    load_kwh REAL
                )
            ''')
            for _, row in df.iterrows():
                t_str = row['parsed_time'].strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute('''
                    INSERT OR REPLACE INTO historical_load (timestamp, hour, load_kwh)
                    VALUES (?, ?, ?)
                ''', (t_str, row['hour'], row['kwh']))

            # 2. hems_daily_history (日別合計kWh & 日別電気代)
            daily_df = df.groupby('date_str').agg({'kwh': 'sum', 'cost_yen': 'sum'}).reset_index()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hems_daily_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_str TEXT UNIQUE,
                    cost_yen REAL,
                    load_kwh REAL DEFAULT 0.0,
                    self_sufficiency_percent REAL,
                    fetched_at DATETIME
                )
            ''')
            for _, drow in daily_df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO hems_daily_history (date_str, cost_yen, load_kwh, self_sufficiency_percent, fetched_at)
                    VALUES (?, ?, ?, 0.0, CURRENT_TIMESTAMP)
                ''', (drow['date_str'], round(float(drow['cost_yen']), 1), round(float(drow['kwh']), 2)))

            # 3. hems_monthly_history (月別合計kWh & 月別電気代)
            monthly_df = df.groupby('year_month').agg({'kwh': 'sum', 'cost_yen': 'sum'}).reset_index()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hems_monthly_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year_month TEXT UNIQUE,
                    cost_yen REAL,
                    load_kwh REAL DEFAULT 0.0,
                    self_sufficiency_percent REAL,
                    fetched_at DATETIME
                )
            ''')
            for _, mrow in monthly_df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO hems_monthly_history (year_month, cost_yen, load_kwh, self_sufficiency_percent, fetched_at)
                    VALUES (?, ?, ?, 0.0, CURRENT_TIMESTAMP)
                ''', (mrow['year_month'], round(float(mrow['cost_yen']), 1), round(float(mrow['kwh']), 2)))

            conn.commit()

        return {
            "success": True,
            "total_rows": total_rows,
            "start_date": min_date,
            "end_date": max_date,
            "total_kwh": round(total_kwh, 2),
            "est_cost_yen": round(total_cost, 0),
            "error": None
        }

    except Exception as e:
        return {"success": False, "error": f"CSVインポートエラー: {e}"}

def get_historical_load_summary():
    """DB内の historical_load レコード件数と日付範囲、総消費電力量を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_load'")
        if not cursor.fetchone():
            return {"count": 0, "start_date": "-", "end_date": "-", "total_kwh": 0.0}

        cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp), SUM(load_kwh) FROM historical_load")
        row = cursor.fetchone()
        if row and row[0] > 0:
            return {
                "count": row[0],
                "start_date": str(row[1]).split(" ")[0] if row[1] else "-",
                "end_date": str(row[2]).split(" ")[0] if row[2] else "-",
                "total_kwh": round(row[3], 2) if row[3] else 0.0
            }
        return {"count": 0, "start_date": "-", "end_date": "-", "total_kwh": 0.0}

def get_hourly_average_demand():
    """過去ログデータから時間帯(0時〜23時)ごとの平均消費電力量(kWh)を算出する"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historical_load'")
        if not cursor.fetchone():
            default_hourly = [0.3, 0.25, 0.25, 0.25, 0.3, 0.4, 0.6, 0.7, 0.5, 0.4, 0.4, 0.5,
                              0.5, 0.4, 0.4, 0.5, 0.6, 0.8, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4]
            return default_hourly
        
        cursor.execute('''
            SELECT hour, AVG(load_kwh) as avg_kwh
            FROM historical_load
            GROUP BY hour
            ORDER BY hour ASC
        ''')
        rows = cursor.fetchall()
        if not rows:
            return [0.5] * 24
        
        avg_profile = [row['avg_kwh'] for row in rows]
        return avg_profile

if __name__ == "__main__":
    summary = get_historical_load_summary()
    print("Historical Load Summary:", summary)
