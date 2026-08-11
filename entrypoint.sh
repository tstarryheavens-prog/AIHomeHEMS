#!/bin/bash
set -e

echo "========================================================"
echo " ⚡ Starting AI SMART ENERGY CONTROLLER Container"
echo "========================================================"

# 1. データベースの初期化
echo "📦 Initializing Database..."
python3 -c "import database; database.init_db()"

# 2. バックグラウンドデータ収集＆最適化スケジューラの起動
echo "🚀 Starting Background Scheduler..."
python3 scheduler.py &

# 3. Streamlit Web UI の起動 (フォアグラウンド)
echo "🌐 Starting Streamlit UI on port 8501..."
exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
