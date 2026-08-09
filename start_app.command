#!/bin/bash
cd "$(dirname "$0")"

echo "========================================================"
echo " ⚡ SMART ENERGY OS (AI HEMS Controller) for macOS"
echo "========================================================"
echo ""

if ! command -v python3 &> /dev/null
then
    echo "❌ Python3 が見つかりませんでした。"
    echo "🌐 https://www.python.org/downloads/ または Homebrew (brew install python3) より導入してください。"
    read -p "Enterキーを押して終了..."
    exit 1
fi

echo "📦 依存ライブラリの自動インストール・検証中..."
python3 -m pip install -r requirements.txt

echo ""
echo "🚀 HEMS システムを起動します..."
echo "🌐 アクセスURL: http://localhost:8501"
echo ""
python3 -m streamlit run app.py --server.port=8501
