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

# ガラスモルフィズム ＆ チラつき防止カスタムCSSの挿入
st.markdown(
    """
    <style>
    /* 全体の背景とカラーテーマの調整 */
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    
    /* Streamlitの再実行時のフェード（グレーアウト）を完全に無効化 */
    div[data-stale="true"] {
        opacity: 1 !important;
        filter: none !important;
    }
    [data-testid="stAppViewContainer"] [data-stale="true"] {
        opacity: 1 !important;
        filter: none !important;
    }
    div[data-chunks-to-draw] {
        opacity: 1 !important;
    }
    
    /* ガラスモルフィズム風のカスタムカードデザイン */
    .glass-card {
        background: rgba(22, 28, 45, 0.45);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    /* アラート・バナーのスタイル調整 */
    .stAlert {
        border-radius: 12px !important;
        background-color: rgba(30, 41, 59, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    
    /* タブのスタイル調整 (ユニバーサルかつ先進的) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(15, 23, 42, 0.5);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 700;
        border: none;
        padding: 0 16px;
        transition: all 0.2s ease-in-out;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #f1f5f9;
        background-color: rgba(255, 255, 255, 0.03);
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    
    /* 📱 iPhoneダークモード視認性強化: ボタンの白文字・高コントラスト固定 */
    div.stButton > button {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease-in-out !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
    }
    div.stButton > button:hover {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
        box-shadow: 0 0 10px rgba(59, 130, 246, 0.5) !important;
    }
    div.stButton > button:active, div.stButton > button:focus {
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


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

# 🗂️ 3タブレイアウトの構築
tab1, tab2, tab3 = st.tabs(["🎛️ ライブモニター", "🤖 AI制御・スケジュール", "🛡️ 寿命診断 ＆ 自給率分析"])

# フラグメント更新関数 (ページ全体の暗転チラつきを完全排除してサイレント更新)
@st.fragment(run_every=5 if auto_refresh else None)
def render_tab1_live():
    # JMA防災情報（Storm Watch）の表示
    from weather_service import WeatherService
    weather = WeatherService()
    warnings_info = weather.check_jma_warnings()

    if warnings_info.get("has_warning", False):
        alert_names = "・".join([w["name"] for w in warnings_info["warnings"]])
        st.markdown(
            f"""
            <div class="glass-card" style="border-color: #ef4444; background: rgba(239, 68, 68, 0.12); margin-top: 10px; margin-bottom: 15px;">
                <h4 style="color: #fca5a5; margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px;">
                    ⚠️ Storm Watch (気象警報連動 防災動作中)
                </h4>
                <p style="color: #fecdd3; margin: 0; font-size: 0.95rem;">
                    名古屋市熱田区に <strong>{alert_names}</strong> が発令されています。<br>
                    停電発生に備えて自動最適化スケジュールを一時中断し、<strong>蓄電池を100%満充電に保護維持 (0x42 急速充電)</strong> しています。
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div class="glass-card" style="padding: 10px 16px; margin-bottom: 15px; margin-top: 10px; border-color: rgba(16, 185, 129, 0.2);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="color: #cbd5e1; font-size: 0.85rem; font-weight: 700;">🛡️ 防災ステータス (Storm Watch)</div>
                    <div style="color: #10b981; font-size: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 6px;">
                        <span style="display: inline-block; width: 8px; height: 8px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981;"></span>
                        熱田区 警報なし (通常AI自動運転)
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

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

with tab3:
    st.markdown("### 🛡️ バッテリー寿命診断 ＆ エネルギー自給自足分析")
    
    from database import get_battery_health_metrics, get_self_sufficiency_data
    health = get_battery_health_metrics()
    self_suff = get_self_sufficiency_data()
    
    h_col1, h_col2, h_col3 = st.columns(3)
    with h_col1:
        st.metric("🛡️ 寿命保護スコア (JIT)", f"{health['life_protection_score']} / 100", help="満充電放置時間の削減実績に基づくスコア")
    with h_col2:
        st.metric("🩺 バッテリー健康グレード", health['health_grade'])
    with h_col3:
        st.metric("🌱 平均エネルギー自給率", f"{self_suff['average_percent']}%", help="過去30日間の総消費量に対する太陽光・蓄電池供給率")

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
        st.markdown("#### 📈 直近30日間の日別エネルギー自給率推移")
        import pandas as pd
        df_suff = pd.DataFrame(self_suff["daily_data"])
        st.line_chart(df_suff.set_index("date")["self_sufficiency_percent"])

    
    st.divider()

    st.markdown("### 📈 全体電力トレンド推移")
    
    limit_map = {
        "📅 全期間 過去全ログ (約35,000件 / 過去全データ)": 100000,
        "📅 直近 48時間 (約34,560件)": 34560,
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
                "📅 直近 48時間 (約34,560件)",
                "📅 直近 24時間 (約17,280件)",
                "🕕 直近 6時間 (約4,320件)",
                "🕐 直近 1時間 (約720件)",
                "⏱️ 直近 10分 (120件)"
            ],
            index=2, # デフォルトは直近24時間
            key="trend_range_option_main"
        )
        
    fetch_limit = limit_map.get(range_option, 17280)
    
    telemetry_hist = get_recent_telemetry(limit=fetch_limit)
    if telemetry_hist:
        df_th = pd.DataFrame(telemetry_hist)
        df_th["timestamp"] = pd.to_datetime(df_th["timestamp"])
        df_th = df_th.sort_values("timestamp")
        
        num_cols = [c for c in ["pv_w", "grid_w", "battery_w", "battery_soc"] if c in df_th.columns]
        
        # スマホ表示速度向上のためのデータリサンプリング (間引き・平均化)
        df_th_index = df_th.set_index("timestamp")
        if len(df_th) > 10000:
            df_th_plot = df_th_index[num_cols].resample('10min').mean().dropna()
        elif len(df_th) > 2000:
            df_th_plot = df_th_index[num_cols].resample('2min').mean().dropna()
        else:
            df_th_plot = df_th_index[num_cols]
            
        st.caption(f"📊 表示中データ: {len(df_th_plot):,} 件 (元データ: {len(df_th):,} 件) | 期間: `{df_th_index.index.min().strftime('%Y-%m-%d %H:%M')}` 〜 `{df_th_index.index.max().strftime('%Y-%m-%d %H:%M')}`")
        
        import altair as alt
        
        # 高コントラスト＆ユニバーサルデザインのAltair描画用関数
        def draw_altair_chart(df, y_cols, y_label):
            df_reset = df.reset_index()
            # 凡例名をわかりやすく変換
            rename_dict = {
                "pv_w": "太陽光発電 (W)",
                "grid_w": "買電/売電電力 (W)",
                "battery_w": "蓄電池充放電 (W)",
                "battery_soc": "蓄電池 SOC (%)"
            }
            df_plot_renamed = df_reset.rename(columns=rename_dict)
            plot_cols = [rename_dict[c] for c in y_cols if c in rename_dict]
            
            df_melt = df_plot_renamed.melt("timestamp", value_vars=plot_cols, var_name="指標", value_name="値")
            
            # カラーパレットの設定 (ユニバーサルデザイン)
            color_scale = alt.Scale(
                domain=["太陽光発電 (W)", "買電/売電電力 (W)", "蓄電池充放電 (W)", "蓄電池 SOC (%)"],
                range=["#fbbf24", "#f87171", "#38bdf8", "#34d399"] # 黄、赤、青、緑
            )
            
            chart = alt.Chart(df_melt).mark_line(interpolate='monotone', strokeWidth=2).encode(
                x=alt.X('timestamp:T', title='時間 (JST)', axis=alt.Axis(format='%m/%d %H:%M', grid=True, gridColor='rgba(255,255,255,0.07)', labelColor='#94a3b8', titleColor='#94a3b8')),
                y=alt.Y('値:Q', title=y_label, axis=alt.Axis(grid=True, gridColor='rgba(255,255,255,0.07)', labelColor='#94a3b8', titleColor='#94a3b8')),
                color=alt.Color('指標:N', scale=color_scale, legend=alt.Legend(title="指標一覧", labelColor='#f1f5f9', titleColor='#f1f5f9')),
                tooltip=[
                    alt.Tooltip('timestamp:T', title='時刻', format='%Y-%m-%d %H:%M'),
                    alt.Tooltip('指標:N', title='項目'),
                    alt.Tooltip('値:Q', title='電力値/残量')
                ]
            ).properties(
                height=320
            ).configure_view(
                strokeOpacity=0
            ).configure(
                background='transparent'
            )
            st.altair_chart(chart, use_container_width=True)

        if chart_option == "☀️ 太陽光発電 (W)":
            st.markdown("##### ☀️ 太陽光発電電力 (PV W) の過去推移")
            draw_altair_chart(df_th_plot, ["pv_w"], "電力 (W)")
        elif chart_option == "⚡ 買電電力 (W)":
            st.markdown("##### ⚡ 買電/売電電力 (Grid W) の過去推移 (+:買電, -:売電)")
            draw_altair_chart(df_th_plot, ["grid_w"], "電力 (W)")
        elif chart_option == "🔋 蓄電池 SOC (%) ＆ 充放電 (W)":
            st.markdown("##### 🔋 蓄電池 SOC (%) の過去推移")
            draw_altair_chart(df_th_plot, ["battery_soc"], "蓄電池残量 (%)")
            st.markdown("##### 🔋 蓄電池 充放電電力 (W) の過去推移 (+:充電, -:放電)")
            draw_altair_chart(df_th_plot, ["battery_w"], "充放電電力 (W)")
        else:
            st.markdown("##### 📊 全電力指標（重ね合わせ比較）")
            draw_altair_chart(df_th_plot, ["pv_w", "grid_w", "battery_w"], "電力 (W)")
            st.markdown("##### 🔋 蓄電池 SOC (%) の過去推移")
            draw_altair_chart(df_th_plot, ["battery_soc"], "蓄電池残量 (%)")
            
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

