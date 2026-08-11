@echo off
chcp 65001 > nul
echo ========================================================
echo  ⚡ SMART ENERGY OS (AI HEMS Controller) 起動ランチャー
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Pythonがインストールされていません。
    echo 🌐 https://www.python.org/downloads/ より Python 3.10 以降をインストールしてください。
    echo ⚠️ ※ インストール時に必ず「Add python.exe to PATH」にチェックを入れてください。
    pause
    exit /b
)

echo 📦 依存ライブラリをインストール・検証中...
pip install -r requirements.txt

echo.
echo 🚀 HEMS システムを起動します...
echo 🌐 アクセスURL: http://localhost:8501
echo.
python -m streamlit run app.py --server.port=8501

pause
