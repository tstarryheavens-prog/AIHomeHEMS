#!/bin/bash

echo "========================================================"
echo "⚡ Checking and installing python dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "⚡ Initializing database..."
python3 -c "import database; database.init_db()"

# バックグラウンドスケジューラを起動
echo "⚡ Starting HEMS background scheduler..."
python3 -u scheduler.py &


# Streamlit を起動 (0.0.0.0でバインドして外部アクセスを許可)
echo "⚡ Starting Streamlit UI on port 8501..."
python3 -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0

