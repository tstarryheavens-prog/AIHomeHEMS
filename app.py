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
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()

# ==========================================
# ⚡ SMART ENERGY OS (サイドバーシステム設定)
# ==========================================
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))
now_dt = datetime.now(JST)

# 手動オーバーライド状態の読み込み
override_active = False
override_mode_str = ""
override_time_left_str = ""

if os.path.exists("manual_override.json"):
    try:
        with open("manual_override.json", "r", encoding="utf-8") as f:
            ov_data = json.load(f)
        expire_dt = datetime.fromisoformat(ov_data["expire_at"])
        if now_dt < expire_dt:
            override_active = True
            override_mode = ov_data["override_mode"]
            override_mode_str = "強制充電 (0x42)" if override_mode == 0x42 else "強制待機 (0x44)"
            time_diff = expire_dt - now_dt
            mins = int(time_diff.total_seconds() / 60)
            override_time_left_str = f"残り {mins} 分"
        else:
            os.remove("manual_override.json")
    except Exception:
        pass

st.sidebar.title("⚡ AI HEMS OS v2.4")
try:
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except Exception:
    config = {}

broute_status = "🟢 有効" if config.get("broute", {}).get("enabled") else "🟡 シミュレーション"
nichicon_status = "🟢 有効 (192.168.2.12)" if config.get("nichicon", {}).get("enabled") else "🟡 シミュレーション"

st.sidebar.markdown(f"**位置情報**: `{config.get('location', {}).get('name', 'Nagoya')}`")
st.sidebar.markdown(f"**太陽光定格**: `{int(config.get('system', {}).get('pv_capacity_kw', 4))} kW`")
st.sidebar.markdown(f"**蓄電池容量**: `{config.get('system', {}).get('battery_capacity_kwh', 14.9)} kWh`")
st.sidebar.markdown(f"**ニチコンT5**: {nichicon_status}")
st.sidebar.markdown(f"**HEMS Web**: 🟢 ONLINE (192.168.2.23)")

st.sidebar.divider()

# 1. リアルタイム自動更新トグル
auto_refresh = st.sidebar.toggle("🔄 リアルタイム自動更新 (5秒)", value=True)

st.sidebar.divider()

# 2. ⚡ 緊急手動コントロール
st.sidebar.markdown("### ⚡ 緊急手動コントロール")
if override_active:
    st.sidebar.warning(f"⚠️ 一時手動介入中:\n{override_mode_str}\n({override_time_left_str})")
    if st.sidebar.button("🤖 AI自動制御に即時復帰", use_container_width=True):
        if os.path.exists("manual_override.json"):
            os.remove("manual_override.json")
        st.sidebar.success("AI自動制御へ復帰しました！")
        time.sleep(0.5)
        st.rerun()
else:
    st.sidebar.success("🤖 AI自動運転中")
    
    col_charge, col_standby = st.sidebar.columns(2)
    with col_charge:
        if st.sidebar.button("⚡ 充電 (1h)", use_container_width=True, help="1時間強制充電"):
            expire_at = (now_dt + timedelta(hours=1)).isoformat()
            with open("manual_override.json", "w", encoding="utf-8") as f:
                json.dump({"override_mode": 0x42, "expire_at": expire_at, "label": "手動1時間強制充電"}, f)
            st.sidebar.success("1h充電をセット！")
            time.sleep(0.5)
            st.rerun()
    with col_standby:
        if st.sidebar.button("⏸️ 待機 (3h)", use_container_width=True, help="3時間放電停止"):
            expire_at = (now_dt + timedelta(hours=3)).isoformat()
            with open("manual_override.json", "w", encoding="utf-8") as f:
                json.dump({"override_mode": 0x44, "expire_at": expire_at, "label": "手動3時間強制待機"}, f)
            st.sidebar.success("3h待機をセット！")
            time.sleep(0.5)
            st.rerun()

st.sidebar.divider()

# 3. 過去データ同期・抽出ボタン
st.sidebar.markdown("### 📥 過去データの同期・抽出操作")
if st.sidebar.button("📥 直近14日間の履歴データを同期", use_container_width=True):
    with st.sidebar.spinner("HEMS Web コントローラから直近14日分の履歴ログを取得中..."):
        count = fetch_hems_past_days_history(days=14)
        if count > 0:
            st.sidebar.success(f"直近 {count} 日分の履歴ログを同期しました！")
            time.sleep(0.8)
            st.rerun()
        else:
            st.sidebar.info("同期対象の新しい履歴ログはありません。")

if st.sidebar.button("⚡ 2016年〜全期間(約10年)履歴一括抽出", use_container_width=True):
    if start_bulk_extraction_async(start_year=2016, end_year=2026):
        st.sidebar.success("バックグラウンド履歴一括抽出を開始しました！画面上部に進捗が表示されます。")
        time.sleep(0.8)
        st.rerun()
    else:
        st.sidebar.warning("すでに履歴一括抽出タスクが実行中です。")



# ==========================================
# 🖥️ メインコンテンツ表示 (最上部に計画根拠バナーを配置)
# ==========================================
latest_sched = get_latest_schedule()
target_soc_val = 100
pv_est_val = 0
load_est_val = 0
reason_desc = "AI自動スケジュールが計算した最適値が適用されています。"

if latest_sched:
    target_soc_val = int(round(latest_sched.get('target_night_soc', 100)))
    pv_est_val = int(round(latest_sched.get('est_pv_kwh', 0)))
    load_est_val = int(round(latest_sched.get('est_load_kwh', 0)))
    
    if pv_est_val > 15:
        reason_desc = (
            f"翌日予想発電量 {pv_est_val}kWh。<br>"
            f"十分な日照予測のため、深夜充電を {target_soc_val}% に抑制。<br>"
            f"太陽光余剰充電枠を確保。"
        )
    elif pv_est_val < 5:
        reason_desc = (
            f"翌日予想発電量 {pv_est_val}kWh。<br>"
            f"日中の不足電力を補うため、深夜最安料金帯に {target_soc_val}% 急速充電。<br>"
            f"昼間の買電量を最小化。"
        )
    else:
        reason_desc = (
            f"翌日予想発電量 {pv_est_val}kWh、予想消費量 {load_est_val}kWh。<br>"
            f"充放電バランスと経済効果を最大化する深夜充電目標 {target_soc_val}% を算定。"
        )

st.markdown(
    f"""
    <div class="glass-card" style="padding: 10px 14px; margin-bottom: 12px; border-color: rgba(59, 130, 246, 0.3); background: rgba(15, 23, 42, 0.75);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="color:#60a5fa; font-weight:800; font-size:0.9rem;">🤖 AI最適化予測・充電計画</span>
            <span style="font-size:0.75rem; background:#1e3a8a; padding:2px 8px; border-radius:4px; color:#93c5fd; font-weight:700; border:1px solid #3b82f6;">v2.4 OS</span>
        </div>
        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:6px; text-align:center;">
            <div>
                <div style="font-size:0.7rem; color:#cbd5e1;">今夜の目標SOC</div>
                <div style="font-size:1.2rem; font-weight:900; color:#34d399;">{target_soc_val} %</div>
            </div>
            <div>
                <div style="font-size:0.7rem; color:#cbd5e1;">翌日予想発電</div>
                <div style="font-size:1.2rem; font-weight:900; color:#fbbf24;">{pv_est_val} kWh</div>
            </div>
            <div>
                <div style="font-size:0.7rem; color:#cbd5e1;">翌日予想消費</div>
                <div style="font-size:1.2rem; font-weight:900; color:#60a5fa;">{load_est_val} kWh</div>
            </div>
        </div>
        <div style="font-size:0.78rem; color:#ffffff; line-height:1.45; font-weight:600;">
            {reason_desc}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ガラスモルフィズム ＆ チラつき防止カスタムCSS of 挿入
st.markdown(
    """
    <style>
    /* 全体の背景とカラーテーマの調整 */
    .stApp {
        background-color: #0b0f19;
        color: #ffffff;
    }
    
    /* Streamlitヘッダーの透過とボタン高可視性確保 */
    header[data-testid="stHeader"] {
        background-color: rgba(11, 15, 25, 0.8) !important;
        backdrop-filter: blur(8px) !important;
    }
    
    /* 📱 サイドバー開閉アイコンボタンの視認性・浮き彫り化 (暗闇で絶対に消えないデザイン) */
    button[data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarHeader"] button,
    [data-testid="stHeader"] button {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border: 2px solid #3b82f6 !important;
        border-radius: 8px !important;
        box-shadow: 0 0 12px rgba(59, 130, 246, 0.5) !important;
    }
    button[data-testid="stSidebarCollapseButton"]:hover,
    [data-testid="stSidebarHeader"] button:hover {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
    }
    button[data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarHeader"] button svg {
        fill: #ffffff !important;
        color: #ffffff !important;
        stroke: #ffffff !important;
    }

    /* 📱 サイドバー全体の高コントラスト背景・文字色固定 */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important; /* 濃紺 */
        border-right: 1px solid rgba(59, 130, 246, 0.3) !important;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important; /* 文字をすべて純白に固定して背景と同化するのを完全防止 */
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #38bdf8 !important; /* 見出しは鮮やかなアイスブルー */
        font-weight: 800 !important;
    }
    [data-testid="stSidebar"] code {
        background-color: #1e293b !important;
        color: #fbbf24 !important; /* コード・強調数値は黄色 */
        border: 1px solid #3b82f6 !important;
    }
    
    /* 📱 全画面文字視認性徹底保証 */
    .stMarkdown, .stText, p, span, div, label, li {
        color: #f8fafc !important;
    }
    small, .stCaption {
        color: #cbd5e1 !important;
    }
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
    [data-testid="stMetricLabel"] {
        color: #cbd5e1 !important;
    }

    /* 再実行時のフェード（グレーアウト）無効化 */
    div[data-stale="true"], [data-testid="stAppViewContainer"] [data-stale="true"], div[data-chunks-to-draw] {
        opacity: 1 !important;
        filter: none !important;
    }
    
    /* ガラスモルフィズム風のカスタムカードデザイン */
    .glass-card {
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
    }
    
    /* タブのスタイル調整 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(15, 23, 42, 0.7);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 8px;
        color: #cbd5e1 !important;
        font-weight: 700;
        border: none;
        padding: 0 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    }
    
    /* 📱 ボタンの高コントラスト・はっきり視認できるスタイル */
    div.stButton > button, [data-testid="stSidebar"] button {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border: 2px solid #3b82f6 !important;
        border-radius: 8px !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
    }
    div.stButton > button:hover, [data-testid="stSidebar"] button:hover {
        background-color: #2563eb !important;
        color: #ffffff !important;
        box-shadow: 0 0 12px rgba(37, 99, 235, 0.8) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)






# バックグラウンド過去ログ一括抽出の進捗表示
bulk_status = get_bulk_extraction_status()
if bulk_status["is_running"]:
    st.warning("⚡ **バックグラウンドにて2016年からの全期間(約10年分)履歴ログを一括抽出・同期中...**")
    progress_val = float(bulk_status["progress_percent"]) / 100.0
    st.progress(min(1.0, max(0.0, progress_val)))
    st.info(
        f"📊 **進行状況**: {bulk_status['processed_days']} / {bulk_status['total_days']} 日 "
        f"({bulk_status['progress_percent']}%) | **現在取得日**: `{bulk_status['current_date_str']}` | "
        f"**取得レコード数**: {bulk_status['extracted_records']} 件"
    )
elif bulk_status["processed_days"] > 0 and bulk_status["processed_days"] == bulk_status["total_days"]:
    st.success(f"✅ 2016年からの全期間 ({bulk_status['extracted_records']}日分) の履歴ログの一括抽出・DB保存が完了しました！")


# 🗂️ 3タブレイアウトの構築
tab1, tab2, tab3 = st.tabs(["🎛️ ライブモニター", "🤖 AI制御・スケジュール", "🛡️ 寿命診断 ＆ 自給率分析"])

# フラグメント更新関数 (ページ全体の暗転チラつきを完全排除してサイレント更新)
@st.fragment(run_every=5 if auto_refresh else None)
def render_tab1_live():
    # JMA防災情報（Storm Watch）の表示
    from weather_service import WeatherService
    weather = WeatherService()
    warnings_info = weather.check_jma_warnings()

    # 適用スケジュールの動的判定
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now_dt_live = datetime.now(JST)
    now_hour_live = now_dt_live.hour
    now_minute_live = now_dt_live.minute
    
    # 経済設定読み込み
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception:
        cfg = {}
    fit_end_str_live = cfg.get("fit_setting", {}).get("fit_end_date", "2026-11-27")
    try:
        fit_end_date_live = datetime.strptime(fit_end_str_live, "%Y-%m-%d").date()
    except Exception:
        fit_end_date_live = datetime(2026, 11, 27).date()
    is_fit_active_live = (now_dt_live.date() <= fit_end_date_live)
    
    # スケジュール説明文の構築
    is_yorytoku_night_live = (now_hour_live >= 21 or now_hour_live < 7)
    is_jit_live = (3 <= now_hour_live < 6) or (now_hour_live == 6 and now_minute_live <= 30)
    
    latest_sched_live = get_latest_schedule()
    target_soc_val_live = 100
    if latest_sched_live:
        target_soc_val_live = int(round(latest_sched_live.get('target_night_soc', 100)))

    if override_active:
        sched_desc = f"⚠️ 一時手動制御中: {override_mode_str} ({override_time_left_str}) ➔ スケジュール一時保留中"
        status_bg = "rgba(245, 158, 11, 0.12)"
        status_border = "rgba(245, 158, 11, 0.35)"
        status_color = "#f59e0b"
    elif warnings_info.get("has_warning", False):
        alert_names = "・".join([w["name"] for w in warnings_info["warnings"]])
        sched_desc = f"⚠️ Storm Watch警報発令中 ({alert_names}) ➔ 蓄電池満充電維持 (0x42)"
        status_bg = "rgba(239, 68, 68, 0.12)"
        status_border = "#ef4444"
        status_color = "#fca5a5"
    else:
        status_bg = "rgba(16, 185, 129, 0.08)"
        status_border = "rgba(16, 185, 129, 0.15)"
        status_color = "#34d399"
        if is_yorytoku_night_live:
            if is_jit_live:
                sched_desc = f"⚡ 夜間JIT急速充電中 (夜とく: 16.3円 / 急速充電 0x42 / 目標: {target_soc_val_live}%) [03:00-06:30]"
            else:
                sched_desc = f"⏸️ 夜間待機中 (系統電力優先買電 / 蓄電池放電停止ガード 0x44) [21:00-07:00]"
        else:
            sched_desc = f"💰 昼間自動運転中 (太陽光自家消費/売電優先) [07:00-21:00]"

    st.markdown(
        f"""
        <div style="background: {status_bg}; border: 1px solid {status_border}; border-radius: 8px; padding: 6px 12px; margin-bottom: 8px; font-size:0.78rem; color:{status_color}; font-weight:700;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span>🛡️ 運転ステータス: {sched_desc}</span>
                <span style="display:inline-block; width:6px; height:6px; background-color:{'#f59e0b' if override_active else ('#ef4444' if warnings_info.get('has_warning', False) else '#10b981')}; border-radius:50%; box-shadow:0 0 6px {'#f59e0b' if override_active else ('#ef4444' if warnings_info.get('has_warning', False) else '#10b981')};"></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    latest_log = poll_and_log_all_data()

    pv_w_int = int(round(latest_log.get('pv_w', 0)))
    grid_w_int = int(round(latest_log.get('grid_w', 0)))
    battery_w_int = int(round(latest_log.get('battery_w', 0)))
    soc_int = int(round(latest_log.get('battery_soc', 50)))
    cum_pv_int = int(round(latest_log.get('cum_pv_kwh', 0)))

    # 小数表現の作成
    pv_kw = round(pv_w_int / 1000.0, 2)
    grid_kw = round(grid_w_int / 1000.0, 2)
    battery_kw = round(battery_w_int / 1000.0, 2)

    # 家庭内負荷計算 (W) ➔ PV発電 - 系統電力(売電は負) - 蓄電池電力(充電は正)
    house_w_int = max(0, pv_w_int - grid_w_int - battery_w_int)
    house_kw = round(house_w_int / 1000.0, 2)

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
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 8px 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        max-height: 240px;
        overflow: hidden;
    }}
    .hems-header {{
        display: flex;
        justify-content: space-between;
        font-size: 0.75rem;
        color: #94a3b8;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 4px;
        margin-bottom: 8px;
        font-weight: 600;
    }}
    .flow-grid {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
    }}
    .flow-card {{
        background: rgba(30, 41, 59, 0.85);
        border: 1px solid #475569;
        border-radius: 10px;
        padding: 6px 10px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }}
    .pv-card {{ border-color: #f59e0b; box-shadow: 0 0 10px rgba(245, 158, 11, 0.2); grid-column: 2; }}
    .grid-card {{ border-color: {'#ef4444' if grid_w_int > 0 else '#10b981'}; box-shadow: 0 0 10px {'rgba(239, 68, 68, 0.2)' if grid_w_int > 0 else 'rgba(16, 185, 129, 0.2)'}; grid-column: 1; grid-row: 2; }}
    .house-card {{ border-color: #60a5fa; background: rgba(30, 58, 138, 0.4); box-shadow: 0 0 15px rgba(96, 165, 250, 0.3); grid-column: 2; grid-row: 2; }}
    .bat-card {{ border-color: #38bdf8; box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); grid-column: 3; grid-row: 2; }}

    .card-title {{ font-size: 0.72rem; font-weight: 700; color: #cbd5e1; margin-bottom: 2px; }}
    .card-val {{ font-size: 1.15rem; font-weight: 900; margin: 1px 0; }}
    .card-sub {{ font-size: 0.68rem; font-weight: 600; color: #94a3b8; }}

    @media (max-width: 600px) {{
        .hems-container {{ padding: 6px 8px; border-radius: 10px; max-height: 220px; }}
        .hems-header {{ font-size: 0.7rem; margin-bottom: 6px; }}
        .flow-grid {{ grid-template-columns: 1fr 1fr; gap: 6px; }}
        .pv-card {{ grid-column: 1; grid-row: 1; }}
        .house-card {{ grid-column: 2; grid-row: 1; }}
        .bat-card {{ grid-column: 1; grid-row: 2; }}
        .grid-card {{ grid-column: 2; grid-row: 2; }}
        .flow-card {{ padding: 4px 6px; border-radius: 8px; }}
        .card-title {{ font-size: 0.65rem; }}
        .card-val {{ font-size: 1.05rem; }}
        .card-sub {{ font-size: 0.62rem; }}
    }}
    </style>
    </head>
    <body>

    <div class="hems-container">
        <div class="hems-header">
            <div>🏠 <strong>スマートホーム HEMS コントローラ</strong></div>
            <div>⏱️ {latest_log.get('timestamp', '')}</div>
        </div>
        
        <div class="flow-grid">
            <div class="flow-card pv-card">
                <div class="card-title">☀️ 太陽光発電システム</div>
                <div class="card-val" style="color: #fbbf24;">{pv_kw} <span style="font-size:0.8rem;">kW</span></div>
                <div class="card-sub">({pv_w_int:,} W) | 累積: {cum_pv_int:,} kWh</div>
            </div>

            <div class="flow-card grid-card">
                <div class="card-title">⚡ 電力会社 (送電線)</div>
                <div class="card-val" style="color: {'#ef4444' if grid_w_int > 0 else '#10b981'};">{grid_kw} <span style="font-size:0.8rem;">kW</span></div>
                <div class="card-sub">{'🔴 買電中' if grid_w_int > 0 else ('🟢 売電中' if grid_w_int < 0 else '⚡ 系統平衡')} ({grid_w_int:,} W)</div>
            </div>

            <div class="flow-card house-card">
                <div style="font-size:1.1rem; margin-bottom: 1px;">🏡</div>
                <div class="card-title" style="color:#93c5fd;">消費 (家庭負荷)</div>
                <div class="card-val" style="color: #60a5fa;">{house_kw} <span style="font-size:0.8rem;">kW</span></div>
                <div class="card-sub">({house_w_int:,} W)</div>
            </div>

            <div class="flow-card bat-card">
                <div class="card-title">🔋 蓄電池 (ニチコンT5)</div>
                <div class="card-val" style="color: #38bdf8;">{soc_int} <span style="font-size:0.8rem;">%</span> ({battery_kw} kW)</div>
                <div class="card-sub">{'⚡ 充電中' if battery_w_int > 50 else ('🔋 放電中' if battery_w_int < -50 else '⏸️ 待機中')} ({battery_w_int:,} W)</div>
            </div>
        </div>
    </div>

    </body>
    </html>
    """

    components.html(html_hems_flow, height=230)

    # ==========================================
    # 📈 全電力トレンド推移 (スマホバグ出し用に上部配置)
    # ==========================================
    st.markdown("##### 📈 全電力トレンド推移 (過去48時間等)")
    
    # 1. グラフ用の描画エリアを先に定義（表示が上になる）
    chart_area = st.container()
    
    # 2. グラフ選択コントロール用の表示エリアを定義（表示が下になる）
    control_area = st.container()
    
    limit_map = {
        "📅 全期間 過去全ログ (約35,000件)": 100000,
        "📅 直近 48時間 (約34,560件)": 34560,
        "📅 直近 24時間 (約17,280件)": 17280,
        "🕕 直近 6時間 (約4,320件)": 4320,
        "🕐 直近 1時間 (約720件)": 720
    }
    
    with control_area:
        tr_col1, tr_col2 = st.columns([1.5, 1])
        with tr_col1:
            chart_option = st.radio(
                "グラフ指標:",
                ["☀️ 太陽光発電 (W)", "⚡ 買電電力 (W)", "🔋 蓄電池 SOC (%) ＆ 充放電 (W)", "📊 全項目重ね合わせ比較"],
                index=3,
                horizontal=True,
                key="live_chart_option",
                label_visibility="collapsed"
            )
        with tr_col2:
            range_option = st.selectbox(
                "期間:",
                [
                    "📅 全期間 過去全ログ (約35,000件)",
                    "📅 直近 48時間 (約34,560件)",
                    "📅 直近 24時間 (約17,280件)",
                    "🕕 直近 6時間 (約4,320件)",
                    "🕐 直近 1時間 (約720件)"
                ],
                index=1, # 初期表示を直近48時間に設定！
                key="live_range_option",
                label_visibility="collapsed"
            )
        
    fetch_limit = limit_map.get(range_option, 34560)
    telemetry_hist = get_recent_telemetry(limit=fetch_limit)
    
    with chart_area:
        if telemetry_hist:
            df_th = pd.DataFrame(telemetry_hist)
            df_th["timestamp"] = pd.to_datetime(df_th["timestamp"])
            df_th = df_th.sort_values("timestamp")
            num_cols = [c for c in ["pv_w", "grid_w", "battery_w", "battery_soc"] if c in df_th.columns]
            
            df_th_index = df_th.set_index("timestamp")
            if len(df_th) > 10000:
                df_th_plot = df_th_index[num_cols].resample('10min').mean().dropna()
            elif len(df_th) > 2000:
                df_th_plot = df_th_index[num_cols].resample('2min').mean().dropna()
            else:
                df_th_plot = df_th_index[num_cols]
                
            import altair as alt
            
            def draw_altair_chart_compact(df, y_cols, y_label):
                df_reset = df.reset_index()
                rename_dict = {
                    "pv_w": "太陽光発電 (W)",
                    "grid_w": "買電/売電 (W)",
                    "battery_w": "蓄電池充放電 (W)",
                    "battery_soc": "蓄電池 SOC (%)"
                }
                
                # モバイル文字色用 (明るい色)
                text_color = '#e2e8f0'
                grid_color = 'rgba(255,255,255,0.06)'
                
                color_scale = alt.Scale(
                    domain=["太陽光発電 (W)", "買電/売電 (W)", "蓄電池充放電 (W)", "蓄電池 SOC (%)"],
                    range=["#fbbf24", "#f87171", "#38bdf8", "#10b981"]
                )
                
                # もしSOCと電力が混在している（全項目重ね合わせ）場合、左右2軸に分離する
                if "battery_soc" in y_cols and len(y_cols) > 1:
                    power_vars = [c for c in ["pv_w", "grid_w", "battery_w"] if c in y_cols]
                    plot_power_cols = [rename_dict[c] for c in power_vars]
                    
                    df_plot_renamed = df_reset.rename(columns=rename_dict)
                    
                    # 1. 電力用 (左軸 - W)
                    df_melt_pow = df_plot_renamed.melt("timestamp", value_vars=plot_power_cols, var_name="指標", value_name="電力")
                    power_chart = alt.Chart(df_melt_pow).mark_line(interpolate='monotone', strokeWidth=1.5).encode(
                        x=alt.X('timestamp:T', title=None, axis=alt.Axis(format='%m/%d %H:%M', grid=True, gridColor=grid_color, labelColor=text_color)),
                        y=alt.Y('電力:Q', title='電力 (W)', axis=alt.Axis(grid=True, gridColor=grid_color, labelColor=text_color, titleColor=text_color)),
                        color=alt.Color('指標:N', scale=color_scale, legend=alt.Legend(title=None, labelColor=text_color, direction='horizontal', orient='bottom'))
                    )
                    
                    # 2. SOC用 (右軸 - %)
                    df_melt_soc = df_plot_renamed.melt("timestamp", value_vars=["蓄電池 SOC (%)"], var_name="指標", value_name="残量")
                    soc_chart = alt.Chart(df_melt_soc).mark_line(interpolate='monotone', strokeWidth=2.2, strokeDash=[4, 3]).encode(
                        x=alt.X('timestamp:T'),
                        y=alt.Y('残量:Q', title='残量 (%)', scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(grid=False, labelColor='#10b981', titleColor='#10b981')),
                        color=alt.Color('指標:N', scale=color_scale, legend=alt.Legend(title=None, labelColor=text_color, direction='horizontal', orient='bottom'))
                    )
                    
                    chart = alt.layer(power_chart, soc_chart).resolve_scale(
                        y='independent'
                    ).properties(
                        height=180
                    ).configure_view(
                        strokeOpacity=0
                    ).configure(
                        background='transparent'
                    )
                else:
                    # 通常の1軸グラフ
                    plot_cols = [rename_dict[c] for c in y_cols if c in rename_dict]
                    df_plot_renamed = df_reset.rename(columns=rename_dict)
                    df_melt = df_plot_renamed.melt("timestamp", value_vars=plot_cols, var_name="指標", value_name="値")
                    
                    chart = alt.Chart(df_melt).mark_line(interpolate='monotone', strokeWidth=1.5).encode(
                        x=alt.X('timestamp:T', title=None, axis=alt.Axis(format='%m/%d %H:%M', grid=True, gridColor=grid_color, labelColor=text_color)),
                        y=alt.Y('値:Q', title=y_label, axis=alt.Axis(grid=True, gridColor=grid_color, labelColor=text_color, titleColor=text_color)),
                        color=alt.Color('指標:N', scale=color_scale, legend=alt.Legend(title=None, labelColor=text_color, direction='horizontal', orient='bottom')),
                        tooltip=[
                            alt.Tooltip('timestamp:T', title='時刻', format='%m/%d %H:%M'),
                            alt.Tooltip('指標:N', title='項目'),
                            alt.Tooltip('値:Q', title='値')
                        ]
                    ).properties(
                        height=180
                    ).configure_view(
                        strokeOpacity=0
                    ).configure(
                        background='transparent'
                    )
                
                st.altair_chart(chart, use_container_width=True)
    
            if chart_option == "☀️ 太陽光発電 (W)":
                draw_altair_chart_compact(df_th_plot, ["pv_w"], "W")
            elif chart_option == "⚡ 買電電力 (W)":
                draw_altair_chart_compact(df_th_plot, ["grid_w"], "W")
            elif chart_option == "🔋 蓄電池 SOC (%) ＆ 充放電 (W)":
                draw_altair_chart_compact(df_th_plot, ["battery_soc"], "%")
                draw_altair_chart_compact(df_th_plot, ["battery_w"], "W")
            else:
                draw_altair_chart_compact(df_th_plot, ["pv_w", "grid_w", "battery_w", "battery_soc"], "W")
    
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

with tab1:
    render_tab1_live()

with tab2:
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
        st.markdown("#### 🤖 翌日AI最適化予測 ＆ 全自動スケジュール")
        if latest_sched:
            details = json.loads(latest_sched.get("details_json", "{}"))
            target_soc_val = int(round(latest_sched.get('target_night_soc', 100)))
            pv_est_val = int(round(latest_sched.get('est_pv_kwh', 0)))
            load_est_val = int(round(latest_sched.get('est_load_kwh', 0)))
            
            m_c1, m_c2, m_c3 = st.columns(3)
            m_c1.metric("自動充電目標 (今夜)", f"{target_soc_val} %", help="中部電力「夜とく」16.30円/kWh時間帯に充電する目標値")
            m_c2.metric("翌日予想 発電量", f"{pv_est_val} kWh")
            m_c3.metric("翌日予想 消費量", f"{load_est_val} kWh")
            
            st.success(
                f"🤖 **AI全自動制御が有効化されています**\n\n"
                f"・**動作予定**: 深夜 JIT 充電帯 (03:00〜06:30) に、夜間最安電力を **{target_soc_val}%** まで自動的に充電し、"
                f"それ以外の深夜オフピーク時間は放電を停止(系統優先)させます。昼間時間帯は自動で自家消費/売電運転に移行します。\n"
                f"・**次回自動更新**: 本日 21:00 頃に翌日の最新天気予報を反映して再計算されます。"
            )
        else:
            st.info("🤖 AI自動スケジュール生成中... 本日夜に最適充電計画が反映されます。")


with tab3:
    st.markdown("### 🛡️ バッテリー寿命診断 ＆ エネルギー自給自足分析")
    
    from database import get_battery_health_metrics, get_self_sufficiency_data
    health = get_battery_health_metrics()
    self_suff = get_self_sufficiency_data()
    
    # 蓄電池の生涯総サイクル数 ＆ 推定SOHの計算
    cum_charge_kwh = batt_sys_info.get("cum_charge_kwh", 0) if batt_sys_info else 0
    cum_discharge_kwh = batt_sys_info.get("cum_discharge_kwh", 0) if batt_sys_info else 0
    
    if cum_charge_kwh > 0:
        total_cycles = (cum_charge_kwh + cum_discharge_kwh) / 2.0 / 11.1
    else:
        # 実機から取得できなかった場合の稼働日数ベース推定（1日約0.75サイクル）
        total_cycles = health['total_telemetry_days'] * 0.75
        
    total_cycles = max(1.0, total_cycles)
    
    # 推定SOH (State of Health) 劣化計算モデル (ニチコンT5サイクル特性に基づく概算)
    # ニチコンの仕様上、6000サイクル以上で容量60%以上維持。
    # 1サイクルあたり 0.005%〜0.007% の容量劣化と、経年劣化を加算
    calendar_loss = health['total_telemetry_days'] * (3.0 / 365.0) # 年間約3.0%の経年劣化
    cycle_loss = total_cycles * 0.005
    est_soh = max(70.0, min(100.0, 100.0 - calendar_loss - cycle_loss))
    
    h_col1, h_col2, h_col3 = st.columns(3)
    with h_col1:
        st.metric("🩺 バッテリー健康度 (SOH)", f"{est_soh:.2f} %", help="出荷時を100%とした時の現在の容量維持率の推定値")
    with h_col2:
        st.metric("🔄 生涯総サイクル数", f"{int(round(total_cycles)):,} 回", help="定格容量分の充放電を1サイクルとした総カウント数")
    with h_col3:
        st.metric("🛡️ 寿命保護スコア (JIT)", f"{health['life_protection_score']} / 100", help="AI満充電放置時間の削減実績に基づく保護スコア")

    # ==========================================
    # 🌲 経済効果 ＆ エコ貢献度統計 (直近30日の実績)
    # ==========================================
    st.markdown("#### 🌲 直近30日間のエネマネ経済効果 ＆ エコ削減貢献度")
    h_history_30 = get_hems_daily_history(limit=30, filter_zero=True)
    self_kwh_sum = 0
    buy_kwh_sum = 0
    sale_kwh_sum = 0
    if h_history_30:
        self_kwh_sum = sum([r.get("self_kwh", 0) or 0 for r in h_history_30])
        buy_kwh_sum = sum([r.get("buy_kwh", 0) or 0 for r in h_history_30])
        sale_kwh_sum = sum([r.get("sale_kwh", 0) or 0 for r in h_history_30])
    
    co2_kg = self_kwh_sum * 0.435
    sugi_trees = co2_kg / 14.0
    
    # 2026-11-27までのFIT判定
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now_dt_check = datetime.now(JST)
    fit_end_str_check = config.get("fit_setting", {}).get("fit_end_date", "2026-11-27")
    try:
        fit_end_date_check = datetime.strptime(fit_end_str_check, "%Y-%m-%d").date()
    except Exception:
        fit_end_date_check = datetime(2026, 11, 27).date()
    fit_end_check = datetime(fit_end_date_check.year, fit_end_date_check.month, fit_end_date_check.day, 23, 59, 59, tzinfo=JST)
    is_fit_active_check = (now_dt_check <= fit_end_check)

    # 経済削減効果：太陽光の自家消費節約(36円単価) ＋ 深夜充電した電力の昼間放電による利益(利ざや14.7円)
    solar_savings = self_kwh_sum * 36.0
    arbitrage_savings = (buy_kwh_sum * 0.8) * (31.0 - 16.30) if is_fit_active_check else 0
    total_savings = solar_savings + arbitrage_savings

    eco_col1, eco_col2, eco_col3 = st.columns(3)
    with eco_col1:
        st.metric("💰 今月の削減経済効果 (概算)", f"¥{int(round(total_savings)):,}", help="太陽光自家消費分(買電削減) ＋ 夜間充電利ざやによる節約の合計額")
    with eco_col2:
        st.metric("📉 CO2排出削減量", f"{co2_kg:.1f} kg-CO2", help="太陽光自家消費により削減された二酸化炭素排出量")
    with eco_col3:
        st.metric("🌲 杉の木換算本数", f"{sugi_trees:.1f} 本", help="削減したCO2を杉の木(1本年14kg吸収)に換算した際の本数")

    st.markdown(
        f"""
        <div class="glass-card" style="margin-top: 10px; margin-bottom: 20px;">
            <h5 style="color: #60a5fa; margin: 0 0 10px 0;">📊 蓄電池延命・保護レポート</h5>
            <p style="margin: 0; font-size: 0.95rem; line-height: 1.6;">
                朝の利用直前にピンポイント満充電を行う「JIT(Just In Time)急速充電窓」制御により、<br>
                1日あたり平均 <strong>{health['saved_hours_per_day']} 時間</strong> の満充電放置時間を削減できています。<br>
                これにより、高電圧放置によるバッテリー内部の劣化を抑制し、長期間 of 寿命維持を強力にサポートしています。<br>
                <small style="color: #94a3b8;">※ 集計対象ログ日数: {health['total_telemetry_days']} 日</small>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # ==========================================
    # 🩺 ニチコン詳細診断 (マニア向けECHONET Lite詳細情報)
    # ==========================================
    st.markdown("#### 🔌 ニチコンT5 蓄電池システム・詳細診断 (マニア向け)")
    with st.expander("🩺 ECHONET Lite デバイス生データ ＆ システム内部状態", expanded=False):
        if batt_sys_info:
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                st.markdown("**🔋 蓄電デバイス状態 (Class 0x027D)**")
                st.write(f"・**接続IP / Port**: `{config.get('nichicon', {}).get('ip_address', '192.168.2.12')}:{config.get('nichicon', {}).get('port', 3610)}`")
                st.write(f"・**動作モード (EPC 0xDA)**: `{batt_sys_info.get('mode', 'UNKNOWN')}`")
                st.write(f"・**現在の蓄電SOC (EPC 0xE7)**: `{batt_sys_info.get('soc', 0)} %`")
                st.write(f"・**現在の残容量Wh (EPC 0xE2)**: `{batt_sys_info.get('battery_wh', 0):,} Wh`")
                st.write(f"・**定格充電能力 (EPC 0xD0)**: `5,900 W` (実機設定値)")
                st.write(f"・**定格放電能力 (EPC 0xD1)**: `5,900 W` (実機設定値)")
            with d_col2:
                st.markdown("**📊 累積充放電電力 / 太陽光統計**")
                st.write(f"・**瞬時充放電電力 (EPC 0xD3)**: `{batt_sys_info.get('power_w', 0):,} W` (+:充電, -:放電)")
                st.write(f"・**累積充電電力量 (EPC 0xE5)**: `{batt_sys_info.get('cum_charge_kwh', 0):,} kWh` (寿命累計)")
                st.write(f"・**累積放電電力量 (EPC 0xE4)**: `{batt_sys_info.get('cum_discharge_kwh', 0):,} kWh` (寿命累計)")
                st.write(f"・**太陽光瞬時発電 (EPC 0xE0)**: `{batt_sys_info.get('pv_w', 0):,} W`")
                st.write(f"・**太陽光累積発電 (EPC 0xE1)**: `{batt_sys_info.get('cum_pv_kwh', 0):,} kWh` (累計)")
        else:
            st.warning("蓄電池とのECHONET Lite通信が遮断されているか、シミュレーションモードのため詳細情報を取得できません。")

    if self_suff["daily_data"]:
        df_suff = pd.DataFrame(self_suff["daily_data"])
        if "self_sufficiency_percent" in df_suff.columns and df_suff["self_sufficiency_percent"].sum() > 0:
            st.markdown("#### 📈 直近30日間の日別エネルギー自給率推移 (%)")
            import altair as alt
            chart_suff = alt.Chart(df_suff).mark_area(
                color='rgba(52, 211, 153, 0.15)',
                line={'color': '#34d399', 'strokeWidth': 1.8},
                interpolate='monotone'
            ).encode(
                x=alt.X('date:T', title=None, axis=alt.Axis(format='%m/%d', grid=True, gridColor='rgba(255,255,255,0.06)', labelColor='#cbd5e1')),
                y=alt.Y('self_sufficiency_percent:Q', title=None, scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(grid=True, gridColor='rgba(255,255,255,0.06)', labelColor='#cbd5e1')),
                tooltip=[
                    alt.Tooltip('date:T', title='日付', format='%Y/%m/%d'),
                    alt.Tooltip('self_sufficiency_percent:Q', title='自給率 (%)')
                ]
            ).properties(
                height=110
            ).configure_view(
                strokeOpacity=0
            ).configure(
                background='transparent'
            )
            st.altair_chart(chart_suff, use_container_width=True)
        else:
            st.info("💡 **自給率推移**: 日別履歴ログがまだ十分に取得されていません。サイドバーの「直近14日間の履歴データを同期」を実行すると推移が表示されます。")

    


    
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
            st.info("※ 有効な日別データが見つかりません。左側サイドバーの「直近14日間の履歴データを同期」ボタンを押すか、過去CSVを取り込んでください。")
            
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
            
        else:
            st.info("※ 月別履歴データが読み込まれていません。左側サイドバー of 「2016年〜全期間」ボタンを押すか、CSVを取り込んでください。")
            
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

# ==========================================
# ⚙️ メイン画面下部フォールバック操作パネル (サイドバーが開けない環境用)
# ==========================================
st.divider()
with st.expander("⚙️ システム手動操作・同期（サイドバーが開けない場合）", expanded=False):
    st.markdown("##### ⚡ 緊急手動コントロール")
    if override_active:
        st.warning(f"⚠️ 一時手動介入中: {override_mode_str} ({override_time_left_str})")
        if st.button("🤖 AI自動制御に復帰", key="fb_restore_btn", use_container_width=True):
            if os.path.exists("manual_override.json"):
                os.remove("manual_override.json")
            st.success("AI自動制御へ復帰しました！")
            time.sleep(0.5)
            st.rerun()
    else:
        st.success("🤖 AI自動運転中 (手動介入なし)")
        fb_c1, fb_c2 = st.columns(2)
        with fb_c1:
            if st.button("⚡ 充電 (1h)", key="fb_charge_btn", use_container_width=True):
                expire_at = (now_dt + timedelta(hours=1)).isoformat()
                with open("manual_override.json", "w", encoding="utf-8") as f:
                    json.dump({"override_mode": 0x42, "expire_at": expire_at, "label": "手動1時間強制充電"}, f)
                st.success("1h充電をセット！")
                time.sleep(0.5)
                st.rerun()
        with fb_c2:
            if st.button("⏸️ 待機 (3h)", key="fb_standby_btn", use_container_width=True):
                expire_at = (now_dt + timedelta(hours=3)).isoformat()
                with open("manual_override.json", "w", encoding="utf-8") as f:
                    json.dump({"override_mode": 0x44, "expire_at": expire_at, "label": "手動3時間強制待機"}, f)
                st.success("3h待機をセット！")
                time.sleep(0.5)
                st.rerun()
                
    st.divider()
    st.markdown("##### 📥 過去データの同期")
    if st.button("📥 直近14日間の履歴データを同期", key="fb_sync_btn", use_container_width=True):
        with st.spinner("HEMS Web コントローラから直近14日分の履歴ログを取得中..."):
            count = fetch_hems_past_days_history(days=14)
            if count > 0:
                st.success(f"直近 {count} 日分の履歴ログを同期しました！")
                time.sleep(0.8)
                st.rerun()
            else:
                st.info("同期対象の新しい履歴ログはありません。")


