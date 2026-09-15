#!/bin/bash
set -e

echo "========================================================"
echo " ⚡ Starting AI SMART ENERGY CONTROLLER Container"
echo "========================================================"

# 1. データベースの初期化
echo "📦 Initializing Database..."
python3 -c "import database; database.init_db()"

# 2. バックグラウンドデータ収集＆最適化スケジューラの起動 (死活監視・自動再起動付き)
echo "🚀 Starting Background Scheduler (with auto-restart watchdog)..."
(
    while true; do
        python3 scheduler.py
        echo "⚠️ [Watchdog] scheduler.py exited! Restarting in 5 seconds..."
        sleep 5
    done
) &

# 3. Streamlit Web UI の起動 (フォアグラウンド)
echo "🌐 Starting Streamlit UI on port 8501..."
exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
