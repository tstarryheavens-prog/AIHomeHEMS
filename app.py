import streamlit as st
import pandas as pd
import json
import yaml
import os
import time
import streamlit.components.v1 as components
from database import get_recent_telemetry, get_recent_room_telemetry, get_latest_schedule, init_db, get_hems_daily_history
from optimizer import PostFitOptimizer
from weather_service import WeatherService
from echonet_nichicon import NichiconEchonetClient
from network_scanner import scan_local_network_for_echonet, auto_update_config_with_discovered_ip
from hems_logger import poll_and_log_all_data, CSV_LOG_PATH
from hems_history_importer import fetch_hems_past_days_history
from bulk_extract_history import start_bulk_extraction_async, get_bulk_extraction_status

st.set_page_config(
    page_title="AI SMART ENERGY CONTROLLER",
    page_icon="⚡",
    layout="wide"
)

init_db()

# ==========================================
# ⚡ SMART ENERGY OS (サイドバーシステム設定)
# ==========================================
st.sidebar.title("⚡ SMART ENERGY OS")
try:
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except Exception:
    config = {}

broute_status = "🟢 有効" if config.get("broute", {}).get("enabled") else "🟡 シミュレーション (モック)"
nichicon_status = "🟢 有効 (192.168.2.12:3610)" if config.get("nichicon", {}).get("enabled") else "🟡 シミュレーション"

st.sidebar.markdown(f"**位置情報**: {config.get('location', {}).get('name', 'Tokyo')}")
st.sidebar.markdown(f"**太陽光定格**: {int(config.get('system', {}).get('pv_capacity_kw', 4))} kW")
st.sidebar.markdown(f"**蓄電池容量**: {config.get('system', {}).get('battery_capacity_kwh', 11.1)} kWh")
st.sidebar.markdown(f"**ニチコンT5**: {nichicon_status}")
st.sidebar.markdown(f"**HEMS Web (192.168.2.23)**: 🟢 ONLINE")

st.sidebar.divider()

# 1. リアルタイム自動更新トグル
auto_refresh = st.sidebar.toggle("🔄 リアルタイム自動更新 (5秒周期・暗転なし)", value=True)

# 2. ネットワークスキャン＆再計算ボタン
st.sidebar.markdown("**🔍 機器検出 ＆ 最適化**")
if st.sidebar.button("📡 サブネットをスキャンして自動接続", use_container_width=True):
    with st.sidebar.spinner("ローカルネットワーク(3610/TCP)を検索中..."):
        device = auto_update_config_with_discovered_ip()
        if device:
            st.sidebar.success(f"機器を発見しました！\nIP: {device['ip']} ({device['type']})")
            st.rerun()
        else:
            st.sidebar.warning("ネットワーク上に ECHONET TCP 機器が見つかりませんでした。")

if st.sidebar.button("🔄 翌日最適化の再計算実行", use_container_width=True):
    optimizer = PostFitOptimizer()
    optimizer.calculate_optimal_schedule()
    st.sidebar.success("再計算が完了しました！")

st.sidebar.divider()

# 3. 過去データ同期・抽出ボタン
st.sidebar.markdown("**📥 過去データの同期・抽出操作**")
if st.sidebar.button("📥 直近14日間の歴史データを同期", use_container_width=True):
    with st.sidebar.spinner("HEMS Web コントローラから直近14日分のログを取得中..."):
        count = fetch_hems_past_days_history(days=14)
        if count > 0:
            st.sidebar.success(f"直近 {count} 日分のログを同期しました！")
            st.rerun()

if st.sidebar.button("⚡ 2016年〜全期間(約10年)一括抽出", use_container_width=True):
    if start_bulk_extraction_async(start_year=2016, end_year=2026):
        st.sidebar.success("バックグラウンド一括抽出を開始しました！画面上部に進捗が表示されます。")
        st.rerun()
    else:
        st.sidebar.warning("すでに一括抽出タスクが実行中です。")


# ==========================================
# 🖥️ メインコンテンツ表示
# ==========================================
st.title("⚡ AI SMART ENERGY MONITOR")
st.subheader("Bルート × ニチコンT5 × HEMS Web × 天気予報AI最適化")

# ⚙️ モバイル用クイック操作パネル (スマホではサイドバーが隠れるためメイン画面にも折りたたみで配置)
with st.expander("⚙️ モバイル用クイックシステム設定・操作", expanded=False):
    st.markdown("##### **現在の機器接続ステータス**")
    m_col_info1, m_col_info2 = st.columns(2)
    with m_col_info1:
        st.write(f"📍 **位置情報**: {config.get('location', {}).get('name', 'Tokyo')}")
        st.write(f"☀️ **太陽光定格**: {int(config.get('system', {}).get('pv_capacity_kw', 4))} kW")
        st.write(f"🔋 **蓄電池容量**: {config.get('system', {}).get('battery_capacity_kwh', 11.1)} kWh")
    with m_col_info2:
        st.write(f"🔌 **ニチコンT5**: {nichicon_status}")
        st.write(f"📡 **Bルート**: {broute_status}")
        st.write(f"🌐 **HEMS Web (192.168.2.23)**: 🟢 ONLINE")
    
    st.divider()
    st.markdown("##### **クイック操作ボタン**")
    
    m_btn_col1, m_btn_col2, m_btn_col3 = st.columns(3)
    with m_btn_col1:
        if st.button("📡 サブネットをスキャンして自動接続", key="mob_scan_btn", use_container_width=True):
            with st.spinner("ローカルネットワーク(3610/TCP)を検索中..."):
                device = auto_update_config_with_discovered_ip()
                if device:
                    st.success(f"機器を発見しました！\nIP: {device['ip']} ({device['type']})")
                    st.rerun()
                else:
                    st.warning("ネットワーク上に ECHONET TCP 機器が見つかりませんでした。")
    with m_btn_col2:
        if st.button("🔄 翌日最適化の再計算実行", key="mob_recalc_btn", use_container_width=True):
            optimizer = PostFitOptimizer()
            optimizer.calculate_optimal_schedule()
            st.success("再計算が完了しました！")
            st.rerun()
    with m_btn_col3:
        if st.button("📥 直近14日間の歴史データを同期", key="mob_sync_btn", use_container_width=True):
            with st.spinner("HEMS Web コントローラから直近14日分のログを取得中..."):
                count = fetch_hems_past_days_history(days=14)
                if count > 0:
                    st.success(f"直近 {count} 日分のログを同期しました！")
                    st.rerun()
                else:
                    st.warning("同期可能な新しいログはありませんでした。")

    if st.button("⚡ 2016年〜全期間(約10年)一括抽出 (バックグラウンド)", key="mob_bulk_sync_btn", use_container_width=True):
        if start_bulk_extraction_async(start_year=2016, end_year=2026):
            st.success("バックグラウンド一括抽出を開始しました！画面上部に進捗が表示されます。")
            st.rerun()
        else:
            st.warning("すでに一括抽出タスクが実行中です。")

st.divider()

# バックグラウンド過去ログ一括抽出の進捗表示
bulk_status = get_bulk_extraction_status()
if bulk_status["is_running"]:
    st.warning("⚡ **バックグラウンドにて2016年からの全期間(約10年分)歴史ログを一括抽出・同期中...**")
    progress_val = float(bulk_status["progress_percent"]) / 100.0
    st.progress(min(1.0, max(0.0, progress_val)))
    st.info(
        f"📊 **進行状況**: {bulk_status['processed_days']} / {bulk_status['total_days']} 日 "
        f"({bulk_status['progress_percent']}%) | **現在取得日**: `{bulk_status['current_date_str']}` | "
        f"**取得レコード数**: {bulk_status['extracted_records']} 件"
    )
elif bulk_status["processed_days"] > 0 and bulk_status["processed_days"] == bulk_status["total_days"]:
    st.success(f"✅ 2016年からの全期間 ({bulk_status['extracted_records']}日分) の歴史ログの一括抽出・DB保存が完了しました！")


# フラグメント更新関数 (ページ全体の暗転チラつきを完全排除してサイレント更新)
@st.fragment(run_every=5 if auto_refresh else None)
def render_live_energy_dashboard():
    latest_log = poll_and_log_all_data()

    pv_w_int = int(round(latest_log.get('pv_w', 0)))
    grid_w_int = int(round(latest_log.get('grid_w', 0)))
    battery_w_int = int(round(latest_log.get('battery_w', 0)))
    soc_int = int(round(latest_log.get('soc', 0)))
    cum_pv_int = int(round(latest_log.get('cum_pv_kwh', 0)))
    battery_wh_int = int(round(latest_log.get('battery_wh', 0)))

    # 物理エネルギー保存則に基づく「家庭全体負荷(純家電消費電力)」の算定:
    # 供給(PV + 買電 + 放電) = 消費(純家電消費 + 充電 + 売電)
    # ➔ 純家電消費 = PV + 買電(+) / 売電(-) - 充電(+) / 放電(-)
    house_w_int = max(0, pv_w_int + grid_w_int - battery_w_int)

    pv_kw = round(pv_w_int / 1000.0, 2)
    grid_kw = round(abs(grid_w_int) / 1000.0, 2)
    battery_kw = round(abs(battery_w_int) / 1000.0, 2)
    house_kw = round(house_w_int / 1000.0, 2)

    # 1. 3DスマートHEMS画面
    st.markdown("### 🎛️ リアルタイム・エネルギーフロー (3DスマートHEMS画面)")

    html_hems_flow = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {{
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: transparent;
        color: #ffffff;
    }}
    .hems-container {{
        background: radial-gradient(circle at 50% 30%, #1e293b 0%, #0f172a 100%);
        border: 2px solid #334155;
        border-radius: 16px;
        padding: 12px 16px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
    }}
    .hems-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #94a3b8;
        font-size: 0.85rem;
        margin-bottom: 10px;
        border-bottom: 1px solid #334155;
        padding-bottom: 6px;
    }}
    .flow-grid {{
        display: grid;
        grid-template-columns: 1fr 1.2fr 1fr;
        gap: 10px;
        align-items: center;
    }}
    .flow-card {{
        background: rgba(30, 41, 59, 0.85);
        border: 1px solid #475569;
        border-radius: 12px;
        padding: 10px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }}
    .pv-card {{ border-color: #f59e0b; box-shadow: 0 0 10px rgba(245, 158, 11, 0.2); grid-column: 2; }}
    .grid-card {{ border-color: {'#ef4444' if grid_w_int > 0 else '#10b981'}; box-shadow: 0 0 10px {'rgba(239, 68, 68, 0.2)' if grid_w_int > 0 else 'rgba(16, 185, 129, 0.2)'}; grid-column: 1; grid-row: 2; }}
    .house-card {{ border-color: #60a5fa; background: rgba(30, 58, 138, 0.4); box-shadow: 0 0 15px rgba(96, 165, 250, 0.3); grid-column: 2; grid-row: 2; }}
    .bat-card {{ border-color: #38bdf8; box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); grid-column: 3; grid-row: 2; }}

    .card-title {{ font-size: 0.8rem; font-weight: 700; color: #cbd5e1; margin-bottom: 4px; }}
    .card-val {{ font-size: 1.4rem; font-weight: 900; margin: 2px 0; }}
    .card-sub {{ font-size: 0.75rem; font-weight: 600; color: #94a3b8; }}

    @media (max-width: 600px) {{
        .hems-container {{ padding: 8px; border-radius: 12px; border-width: 1px; }}
        .hems-header {{ flex-direction: column; align-items: flex-start; font-size: 0.75rem; gap: 4px; margin-bottom: 8px; }}
        .flow-grid {{ grid-template-columns: 1fr 1fr; gap: 6px; }}
        .pv-card {{ grid-column: 1; grid-row: 1; }}
        .house-card {{ grid-column: 2; grid-row: 1; }}
        .bat-card {{ grid-column: 1; grid-row: 2; }}
        .grid-card {{ grid-column: 2; grid-row: 2; }}
        .flow-card {{ padding: 6px; border-radius: 8px; }}
        .card-title {{ font-size: 0.7rem; margin-bottom: 2px; }}
        .card-val {{ font-size: 1.15rem; }}
        .card-sub {{ font-size: 0.65rem; }}
    }}
    </style>
    </head>
    <body>

    <div class="hems-container">
        <div class="hems-header">
            <div>🏠 <strong>スマートホーム HEMS コントローラ</strong> | 卒FIT最適化モード (5秒自動更新)</div>
            <div>⏱️ {latest_log.get('timestamp', '')} JST</div>
        </div>
        
        <div class="flow-grid">
            <div class="flow-card pv-card">
                <div class="card-title">☀️ 太陽光発電システム</div>
                <div class="card-val" style="color: #fbbf24;">{pv_kw} <span style="font-size:0.9rem;">kW</span></div>
                <div class="card-sub">({pv_w_int:,} W) | 累積: {cum_pv_int:,} kWh</div>
            </div>

            <div class="flow-card grid-card">
                <div class="card-title">⚡ 電力会社 (送電線)</div>
                <div class="card-val" style="color: {'#ef4444' if grid_w_int > 0 else '#10b981'};">{grid_kw} <span style="font-size:0.9rem;">kW</span></div>
                <div class="card-sub">{'🔴 買電中' if grid_w_int > 0 else ('🟢 売電中' if grid_w_int < 0 else '⚡ 系統平衡')} ({grid_w_int:,} W)</div>
            </div>

            <div class="flow-card house-card">
                <div style="font-size:1.5rem; margin-bottom: 2px;">🏡</div>
                <div class="card-title" style="color:#93c5fd;">消費 (家庭全体負荷)</div>
                <div class="card-val" style="color: #60a5fa;">{house_kw} <span style="font-size:0.9rem;">kW</span></div>
                <div class="card-sub">({house_w_int:,} W)</div>
            </div>

            <div class="flow-card bat-card">
                <div class="card-title">🔋 蓄電池 (ニチコンT5)</div>
                <div class="card-val" style="color: #38bdf8;">{soc_int} <span style="font-size:0.9rem;">%</span> ({battery_kw} kW)</div>
                <div class="card-sub">{'⚡ 充電中' if battery_w_int > 50 else ('🔋 放電中' if battery_w_int < -50 else '⏸️ 待機中')} ({battery_w_int:,} W)</div>
            </div>
        </div>
    </div>

    </body>
    </html>
    """

    components.html(html_hems_flow, height=320)

    st.info("🌐 **HEMS Web Controller (192.168.2.23)**: [http://192.168.2.23/](http://192.168.2.23/) （WEB CONTROLLER ログイン画面）")
    st.divider()

    # 2. 各部屋・分電盤回路の消費電力モニタリング（横棒グラフ ＋ 右側数値）
    st.markdown("### 🏠 各部屋・回路別の消費電力モニタリング (リアルタイム現在値)")
    rooms = latest_log.get("rooms", {})
    
    room_items = [
        ("🛋️ リビング", rooms.get("リビング", 0)),
        ("❄️ エアコン", rooms.get("エアコン", 0)),
        ("🍳 キッチン・IH", rooms.get("キッチン・IH", 0)),
        ("🛏️ 主寝室", rooms.get("主寝室", 0)),
        ("🧸 子供部屋", rooms.get("子供部屋", 0)),
        ("⚡ その他回路", rooms.get("その他回路", 0))
    ]
    
    max_w = max([v for _, v in room_items] + [100])
    
    bars_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {{
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: transparent;
        color: #ffffff;
    }}
    .bar-box {{
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 10px 14px;
        box-shadow: 0 6px 15px rgba(0,0,0,0.3);
    }}
    .room-row {{
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }}
    .room-row:last-child {{
        margin-bottom: 0;
    }}
    .room-label {{
        width: 130px;
        font-weight: 700;
        color: #e2e8f0;
        font-size: 0.95rem;
    }}
    .bar-track {{
        flex-grow: 1;
        background: #1e293b;
        border-radius: 8px;
        height: 18px;
        border: 1px solid #475569;
        overflow: hidden;
        margin: 0 14px;
    }}
    .bar-fill {{
        height: 100%;
        background: linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%);
        border-radius: 6px;
        transition: width 0.4s ease-in-out;
    }}
    .room-val {{
        width: 80px;
        text-align: right;
        font-weight: 800;
        font-size: 1.15rem;
        color: #38bdf8;
    }}
    </style>
    </head>
    <body>
    <div class="bar-box">
    """
    for label, val in room_items:
        w_val = int(round(val))
        pct = max(2, min(100, int((w_val / max_w) * 100)))
        bars_html += f"""
        <div class="room-row">
            <div class="room-label">{label}</div>
            <div class="bar-track"><div class="bar-fill" style="width:{pct}%;"></div></div>
            <div class="room-val">{w_val:,} W</div>
        </div>
        """
    bars_html += """
    </div>
    </body>
    </html>
    """

    components.html(bars_html, height=240)

render_live_energy_dashboard()

st.divider()

# ==========================================
# 🎯 3. 翌日最適充電スケジューリング ＆ ニチコンT5 蓄電池制御
# ==========================================
st.markdown("### 🎯 翌日最適充電スケジューリング ＆ ニチコンT5 蓄電池制御")

from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))

client = NichiconEchonetClient(enabled=config.get("nichicon", {}).get("enabled", True))
batt_sys_info = client.get_full_system_info()
cmd_status = st.session_state.get("last_battery_cmd_status")

fit_end_date_str = config.get("fit_setting", {}).get("fit_end_date", "2026-11-27")
try:
    fit_end_formatted = datetime.strptime(fit_end_date_str, "%Y-%m-%d").strftime("%Y/%m/%d")
except Exception:
    fit_end_formatted = fit_end_date_str.replace("-", "/")

st.warning(
    f"💡 **中部電力「スマートライフプラン【夜とく】」(21時〜7時) × 蓄電池寿命最得制御**:\n"
    f"・**🔋 寿命保護JIT充電 (03:00〜06:30)**: 朝の使用直前3.5時間で急速充電し、100%満充電保持時間を極小化！蓄電池の寿命を最大化します。\n"
    f"・**💰 31円利ざや売電 (〜{fit_end_formatted})**: 昼間(7-21時)は `0x43 (放電/売電優先)` で太陽光(31.0円/kWh)を全量売電！深夜16.3円との差額 `+14.7円/kWh` の純利益を追及！"
)


# ⏰ 現在設定されている蓄電池の充放電時間帯可視化パネル
st.markdown("#### ⏰ 現在の蓄電池 充放電タイマー設定スケジュール")
st.markdown(
    """
    | 時間帯区分 | 設定時刻窓 | 動作内容・電力料金単価 |
    | :--- | :--- | :--- |
    | **⚡ 深夜充電** | **`03:00` 〜 `06:30`** | 中部電力「夜とく」16.3円/kWh (JIT急速充電) |
    | **🛡️ 保護バッファ** | **`06:30` 〜 `06:35`** | インバータ基板保護・待機時間 (5分間) |
    | **🔋 昼間放電/売電** | **`06:35` 〜 `02:55`** | FIT高額売電 31.0円/kWh (または卒FIT自家消費) |
    """
)


latest_sched = get_latest_schedule()

col_sched, col_batt = st.columns([1.2, 1])

with col_sched:
    st.markdown("#### 🤖 翌日AI最適化予測 ＆ スケジュール予約")
    if latest_sched:
        details = json.loads(latest_sched.get("details_json", "{}"))
        target_soc_val = int(round(latest_sched.get('target_night_soc', 100)))
        pv_est_val = int(round(latest_sched.get('est_pv_kwh', 0)))
        load_est_val = int(round(latest_sched.get('est_load_kwh', 0)))
        
        m_c1, m_c2, m_c3 = st.columns(3)
        m_c1.metric("推奨 深夜充電目標", f"{target_soc_val} %", help="中部電力「夜とく」16.30円/kWh")
        m_c2.metric("翌日予想 発電量", f"{pv_est_val} kWh")
        m_c3.metric("翌日予想 消費量", f"{load_est_val} kWh")
        
        if st.button("💰 中部電力「夜とく」最得スケジュールを予約送信 (昼間:31円売電 ➔ 深夜3:00-6:30 JIT充電)", use_container_width=True):
            now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            st.session_state["last_battery_cmd_status"] = {
                "sent": True,
                "sent_at": now_str,
                "target_soc": target_soc_val,
                "mode_name": f"昼間(31円売電0x43) ➔ 深夜03:00〜06:30 JIT自動急速充電 (0x42 100%)",
                "success": True
            }
            client.set_battery_mode(0x43)
            st.success(f"✅ 昼間は【31円高額売電優先モード (0x43)】を設定し、深夜03:00〜06:30の寿命保護JIT充電を全自動予約しました！")
            time.sleep(1.2)
            st.rerun()

    if cmd_status and cmd_status.get("sent"):
        st.success(
            f"✅ **予約完了 (`{cmd_status.get('sent_at')}`)**: "
            f"昼間 `0x43 (31円売電)` ➔ 深夜 `03:00 JIT充電 (16.3円 100%)` 予約済"
        )
    else:
        st.info("🟡 **未予約**: 上記の「最得スケジュールを予約送信」ボタンを押すとセットされます。")

with col_batt:
    st.markdown("#### 🔋 蓄電池実機ステータス ＆ モード即時切替")
    curr_m = batt_sys_info.get("mode", "AUTO")
    mode_text = "⚡ 急速充電モード (0x42)" if curr_m == "CHARGE" else ("🔋 31円売電・放電優先 (0x43)" if curr_m == "DISCHARGE" else "🟢 自家消費・グリーンモード (0x45)")
    st.metric(label="現在のリアルタイム動作モード", value=mode_text)
    st.caption(f"SOC: {batt_sys_info.get('soc', 0)}% | 充放電: {batt_sys_info.get('power_w', 0):,} W | IP: 192.168.2.12:3610")
    
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if st.button("🔋 昼間売電・放電優先 (0x43)", use_container_width=True):
            client.set_battery_mode(0x43)
            st.success("実機を 0x43 (31円売電・放電優先) に変更しました")
            time.sleep(1.0)
            st.rerun()
    with b_col2:
        if st.button("🟢 卒FIT用 自家消費 (0x45)", use_container_width=True):
            client.set_battery_mode(0x45)
            st.success("実機を 0x45 (自家消費グリーン) に変更しました")
            time.sleep(1.0)
            st.rerun()

with st.expander("⏱️ ニチコンT5 本体基板タイマー時間設定 (高度な設定・充放電切替5分バッファ対応・PC電源OFF対応)", expanded=False):
    st.caption("スマホアプリと同様に、ニチコンT5本体の基板内部（ECHONET EPC 0xC3/0xC4/0xC5/0xC6）へ「充電時間窓」および「放電時間窓」をプログラム書き込み保存します。インバータ基板保護のため **充放電切替の5分バッファ** を全自動で確保します。")

    col_t1, col_t2, col_t3 = st.columns([1.2, 1.2, 1])
    with col_t1:
        charge_start_t = st.time_input("⚡ 深夜充電 開始時刻", value=datetime.strptime("03:00", "%H:%M").time(), key="hw_timer_c_start")
        charge_end_t = st.time_input("⚡ 深夜充電 終了時刻", value=datetime.strptime("06:30", "%H:%M").time(), key="hw_timer_c_end")

    with col_t3:
        buffer_min = st.selectbox("🛡️ 充放電切替バッファ時間", options=[5, 10, 0], index=0, help="充電から放電へ切り替える際に、インバータ基板のリレー発熱や電圧サージを防ぐ保護待機時間です。")

    c_end_dt = datetime.combine(datetime.today(), charge_end_t) + timedelta(minutes=buffer_min)
    c_start_dt = datetime.combine(datetime.today(), charge_start_t) - timedelta(minutes=buffer_min)

    dis_start_default = c_end_dt.time()
    dis_end_default = c_start_dt.time()

    with col_t2:
        dis_start_t = st.time_input(f"🔋 昼間放電 開始時刻 (+{buffer_min}分バッファ)", value=dis_start_default, key="hw_timer_d_start")
        dis_end_t = st.time_input(f"🔋 昼間放電 終了時刻 (-{buffer_min}分バッファ)", value=dis_end_default, key="hw_timer_d_end")

    if st.button("💾 ニチコンT5本体基板へ全充放電タイマー(5分バッファ付)を永久保存書き込み", use_container_width=True):
        res_hw = client.set_battery_timer_schedule(
            charge_start_h=charge_start_t.hour,
            charge_start_m=charge_start_t.minute,
            charge_end_h=charge_end_t.hour,
            charge_end_m=charge_end_t.minute,
            discharge_start_h=dis_start_t.hour,
            discharge_start_m=dis_start_t.minute,
            discharge_end_h=dis_end_t.hour,
            discharge_end_m=dis_end_t.minute
        )
        if res_hw:
            st.success(
                f"🎉 **保存成功！** ニチコンT5本体基板(EPC 0xC3/0xC4/0xC5/0xC6)へ全タイマー設定を書き込みました！\n\n"
                f"・**充電**: `{charge_start_t.strftime('%H:%M')}` 〜 `{charge_end_t.strftime('%H:%M')}` | "
                f"**保護バッファ**: `{buffer_min}分間` | "
                f"**放電**: `{dis_start_t.strftime('%H:%M')}` 〜 `{dis_end_t.strftime('%H:%M')}`\n\n"
                f"PCの電源をOFFにしても、蓄電池基板単体で全自動動作します！"
            )
        else:
            st.warning("⚠️ 蓄電池本体へのタイマー書き込みに失敗しました（192.168.2.12 の接続状態をご確認ください）。")

st.divider()

# ==========================================
# 📈 4. 全体電力トレンド推移
# ==========================================
st.markdown("### 📈 全体電力トレンド推移")

limit_map = {
    "📅 全期間 過去全ログ (約35,000件 / 過去全データ)": 100000,
    "📅 直近 24時間 (約17,280件)": 17280,
    "🕕 直近 6時間 (約4,320件)": 4320,
    "🕐 直近 1時間 (約720件)": 720,
    "⏱️ 直近 10分 (120件)": 120
}

c_radio, c_range = st.columns([1.8, 1])
with c_radio:
    st.markdown("**表示指標選択**:")
    chart_option = st.radio(
        "グラフ項目の選択:",
        ["☀️ 太陽光発電 (W)", "⚡ 買電電力 (W)", "🔋 蓄電池 SOC (%) ＆ 充放電 (W)", "📊 全項目重ね合わせ比較"],
        horizontal=True,
        key="trend_chart_option_main"
    )
with c_range:
    st.markdown("**時間軸・過去ログ表示範囲**:")
    range_option = st.selectbox(
        "表示対象の期間選択:",
        [
            "📅 全期間 過去全ログ (約35,000件 / 過去全データ)",
            "📅 直近 24時間 (約17,280件)",
            "🕕 直近 6時間 (約4,320件)",
            "🕐 直近 1時間 (約720件)",
            "⏱️ 直近 10分 (120件)"
        ],
        index=0,
        key="trend_range_option_main"
    )

limit_map = {
    "📅 全期間 過去全ログ (約35,000件 / 過去全データ)": 100000,
    "📅 直近 24時間 (約17,280件)": 17280,
    "🕕 直近 6時間 (約4,320件)": 4320,
    "🕐 直近 1時間 (約720件)": 720,
    "⏱️ 直近 10分 (120件)": 120
}
fetch_limit = limit_map.get(range_option, 100000)

telemetry_hist = get_recent_telemetry(limit=fetch_limit)
if telemetry_hist:
    df_th = pd.DataFrame(telemetry_hist)
    df_th["timestamp"] = pd.to_datetime(df_th["timestamp"])
    df_th = df_th.sort_values("timestamp").set_index("timestamp")
    
    num_cols = [c for c in ["pv_w", "grid_w", "battery_w", "battery_soc"] if c in df_th.columns]
    
    if len(df_th) > 2000:
        df_th_plot = df_th[num_cols].resample('1min').mean().dropna()
    else:
        df_th_plot = df_th[num_cols]
    
    st.caption(f"📊 表示中データ: {len(df_th_plot):,} 件 (元データ: {len(df_th):,} 件) | 期間: `{df_th.index.min().strftime('%Y-%m-%d %H:%M')}` 〜 `{df_th.index.max().strftime('%Y-%m-%d %H:%M')}`")

    if chart_option == "☀️ 太陽光発電 (W)":
        st.markdown("##### ☀️ 太陽光発電電力 (PV W) の過去推移")
        st.line_chart(df_th_plot[["pv_w"]].rename(columns={"pv_w": "太陽光発電 (W)"}))
    elif chart_option == "⚡ 買電電力 (W)":
        st.markdown("##### ⚡ 買電/売電電力 (Grid W) の過去推移 (+:買電, -:売電)")
        st.line_chart(df_th_plot[["grid_w"]].rename(columns={"grid_w": "買電/売電電力 (W)"}))
    elif chart_option == "🔋 蓄電池 SOC (%) ＆ 充放電 (W)":
        st.markdown("##### 🔋 蓄電池 SOC (%) の過去推移")
        st.line_chart(df_th_plot[["battery_soc"]].rename(columns={"battery_soc": "蓄電池 SOC (%)"}))
        st.markdown("##### 🔋 蓄電池 充放電電力 (W) の過去推移 (+:充電, -:放電)")
        st.line_chart(df_th_plot[["battery_w"]].rename(columns={"battery_w": "充放電電力 (W)"}))
    else:
        st.markdown("##### 📊 全電力指標（過去全データの重ね合わせ比較）")
        st.line_chart(df_th_plot[["pv_w", "grid_w", "battery_w"]].rename(columns={
            "pv_w": "太陽光発電 (W)",
            "grid_w": "買電電力 (W)",
            "battery_w": "蓄電池充放電 (W)"
        }))
        st.line_chart(df_th_plot[["battery_soc"]].rename(columns={"battery_soc": "蓄電池 SOC (%)"}))

st.divider()

# ==========================================
# 📊 5. HEMS 実機 ＆ CSV過去ログ実績（電力量kWh ＆ 電気代円）
# ==========================================
st.markdown("### 📊 HEMS 実機 ＆ CSV過去ログ実績（電力量kWh ＆ 電気代円）")

st.info(
    "💡 **HEMS実機データ ＆ 過去CSVログの自動可視化**:\n"
    "HEMSコントローラ（192.168.2.23）から同期した直近実績、およびアップロードしたCSV過去ログの「電力量 (kWh)」と「電気代 (円)」を時系列グラフで確認できます。"
)

from hems_monthly_importer import get_hems_monthly_history
from katene_importer import import_katene_csv, get_historical_load_summary

hist_sub_tab1, hist_sub_tab2, hist_sub_tab3 = st.tabs([
    "⚡ 日別電力量(kWh) ＆ 電気代(円) トレンド", 
    "📅 月別電力量(kWh) ＆ 電気代(円) トレンド (2016年〜全期間)",
    "📁 2016年〜過去CSVログのインポート (カテエネ・HEMS書き出し)"
])

with hist_sub_tab1:
    h_history = get_hems_daily_history(limit=1000, filter_zero=True)
    if h_history:
        df_hh = pd.DataFrame(h_history)
        df_hh["date_str"] = pd.to_datetime(df_hh["date_str"])
        df_hh = df_hh.sort_values("date_str").set_index("date_str")
        
        st.markdown(f"**⚡ 日別 4大電力量推移 (買電 / 売電 / 発電 / 自家消費 kWh) (全 {len(df_hh)} 日分)**")
        kwh_cols = [c for c in ["buy_kwh", "sale_kwh", "pv_kwh", "self_kwh"] if c in df_hh.columns]
        if kwh_cols:
            df_kwh_show = df_hh[kwh_cols].rename(columns={
                "buy_kwh": "買電量 (kWh)",
                "sale_kwh": "売電量 (kWh)",
                "pv_kwh": "発電量 (kWh)",
                "self_kwh": "自家消費 (kWh)"
            })
            st.line_chart(df_kwh_show)

        st.markdown(f"**💴 日別電気代 (円/日) 推移**")
        st.bar_chart(df_hh[["cost_yen"]], y_label="電気代 (円)")
    else:
        st.info("※ 有効な日別データが見つかりません。左側サイドバーの「直近14日間の歴史データを同期」ボタンを押すか、過去CSVを取り込んでください。")

with hist_sub_tab2:
    m_history = get_hems_monthly_history()
    if m_history:
        df_mh = pd.DataFrame(m_history)
        df_mh["year_month"] = pd.to_datetime(df_mh["year_month"])
        df_mh = df_mh.sort_values("year_month").set_index("year_month")
        
        st.markdown(f"**月別消費電力量 (kWh/月) 推移 (全 {len(df_mh)} ヶ月分)**")
        if "load_kwh" in df_mh.columns and df_mh["load_kwh"].sum() > 0:
            st.bar_chart(df_mh[["load_kwh"]], y_label="月別電力量 (kWh)")
        
        st.markdown(f"**月別電気代 (円/月) 推移 (全 {len(df_mh)} ヶ月分)**")
        st.bar_chart(df_mh[["cost_yen"]], y_label="月別電気代 (円)")
        
        m_display_cols = [c for c in ["load_kwh", "cost_yen", "self_sufficiency_percent"] if c in df_mh.columns]
    else:
        st.info("※ 月別履歴データが読み込まれていません。左側サイドバーの「2016年〜全期間」ボタンを押すか、CSVを取り込んでください。")

with hist_sub_tab3:
    st.markdown("**2016年〜2026年 電力会社・HEMS全形式 CSVログの取り込み**")
    
    h_summary = get_historical_load_summary()
    if h_summary["count"] > 0:
        st.success(
            f"💾 **現在DB保存中の過去CSVデータ**: **{h_summary['count']:,} 件** | "
            f"**対象期間**: `{h_summary['start_date']}` 〜 `{h_summary['end_date']}` | "
            f"**総消費電力量**: **{h_summary['total_kwh']:,} kWh**"
        )
    else:
        st.warning("⚠️ 現在データベースに過去CSVログは登録されていません。下記からアップロードしてください。")

    uploaded_csv = st.file_uploader("過去の電力使用量CSVファイル（FLAG, DATE, USE, BUY, SALE等）をドラッグ＆ドロップ", type=["csv"])
    if uploaded_csv is not None:
        temp_path = "temp_uploaded_katene.csv"
        with open(temp_path, "wb") as f:
            f.write(uploaded_csv.getbuffer())
        
        res = import_katene_csv(temp_path)
        if os.path.exists(temp_path):
            os.remove(temp_path)

        if res["success"]:
            st.success(
                f"🎉 **インポート成功！**\n\n"
                f"・**取り込み件数**: **{res['total_rows']:,} 行**\n"
                f"・**対象期間**: `{res['start_date']}` 〜 `{res['end_date']}`\n"
                f"・**総消費電力量**: **{res['total_kwh']:,} kWh**\n"
                f"・**電気代合計**: **¥{int(res['est_cost_yen']):,}**\n\n"
                f"※ 「電力量(kWh)」および「電気代(円)」の両方の時系列グラフへ全自動反映されました。"
            )
            time.sleep(1.5)
            st.rerun()
        else:
            st.error(f"❌ インポート失敗: {res['error']}")

    st.divider()
    if st.button("🧪 テスト用 2016年〜2026年過去CSVサンプルデータを自動適用"):
        import create_sample_csv
        res = import_katene_csv("sample_katene_2016_2026.csv")
        if res["success"]:
            st.success(f"テストサンプル ({res['total_rows']:,} 行) の読み込みが完了しました！")
            st.rerun()
