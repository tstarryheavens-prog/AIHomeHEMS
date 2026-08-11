FROM python:3.11-slim

# 日本時間(JST)のタイムゾーン設定およびビルド依存パッケージのインストール
ENV TZ=Asia/Tokyo
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションソースコードのコピー
COPY . /app

# スクリプトの実行権限確認
RUN chmod +x /app/entrypoint.sh

# Streamlit ポート露出
EXPOSE 8501

# コンテナ起動エントリーポイント
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
