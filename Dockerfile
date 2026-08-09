FROM python:3.10-slim

# システムのタイムゾーンを日本時間(JST)に設定
ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# 依存関係をキャッシュするために requirements.txt を先にコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションソースをコピー
COPY . .

# 起動スクリプトに実行権限を付与
RUN chmod +x /app/entrypoint.sh

# Streamlitのデフォルトポート
EXPOSE 8501

ENTRYPOINT ["/app/entrypoint.sh"]
