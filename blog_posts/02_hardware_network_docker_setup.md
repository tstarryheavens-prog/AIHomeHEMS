---
title: "【ハードウェア設計】ニチコン蓄電池・HEMS・ASUSTOR NASの宅内LAN配線とDocker常時稼働基盤の構築【第2回】"
category:
  - 自作HEMS
  - Docker
  - NAS
  - ネットワーク
  - ASUSTOR
draft: false
---

「自作HEMSを作りたいけど、蓄電池やHEMSってどうやってネットワークに繋がってるの？」  
「PCを24時間つけっぱなしにするのは電気代の無駄だし、どこで動かせばいいの？」

前回は2026年卒FITの危機と「AIHomeHEMS」の全体像をお話ししましたが、今回は**物理レイヤー（ハードウェア配線・IP設計・NAS常時稼働基盤）**をガッツリ掘り下げていきます！

ソフトを作る前に、土台となるインフラがグラグラだと、謎の通信タイムアウトやデータ欠落に泣かされることになります。  
我が家で実際に構築した**「止まらない宅内HEMSネットワーク」**と**Docker Composeの完全設定**を全公開します！

ソースコードはこちら（GitHub公開中）👇  
👉 **[GitHub リポジトリ: AIHomeHEMS](https://github.com/tstarryheavens-prog/AIHomeHEMS)**

<br>

---

<br>

## 🔌 1. 宅内HEMSの物理配線図：Wi-Fiは使わず「有線LAN」一択！

まず結論から言います。  
**HEMSコントローラや蓄電池、サーバー（NAS）の接続には、絶対にWi-Fiを使ってはいけません。100%有線LANで配線してください！**

無線LANは電子レンジや障害物でパケットロスが発生しやすく、UDPで蓄電池と通信する際にタイムアウトが頻発します。秒単位の常時監視ロギングを行うシステムにおいて、ネットワークの不安定さは致命傷です。

我が家の物理配線図がこちらです：

<br>

<p align="center">
  <img src="https://cdn-ak.f.st-hatena.com/images/fotolife/c/corestation/20260913/20260913004645.jpg" alt="AIHomeHEMS ネットワーク・物理構成図（日本語解説）" style="max-width:100%; height:auto; border-radius:12px; box-shadow: 0 8px 24px rgba(0,0,0,0.12);">
</p>

<br>

```
   ┌────────────────────────────────────────────────────────┐
   │                    ホームゲートウェイ / ルーター         │
   │                      (192.168.1.1)                     │
   └───────────────────────────┬────────────────────────────┘
                               │ (Cat6 有線LAN)
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │             スイッチングハブ (ギガビット対応)             │
   └───┬───────────────────────┬────────────────────────┬───┘
       │                       │                        │
       ▼ (有線LAN)             ▼ (有線LAN)              ▼ (有線LAN)
 ┌───────────────┐     ┌───────────────┐        ┌───────────────┐
 │ ニチコン蓄電池 │     │ HEMS Web端末  │        │  ASUSTOR NAS  │
 │ (14.9kWh / T5)│     │  (CenteHTTPd) │        │   (AS3102T)   │
 │ 192.168.1.200 │     │ 192.168.1.100 │        │ 192.168.1.50  │
 └───────────────┘     └───────────────┘        └───────┬───────┘
                                                        │ Docker
                                                        ▼
                                                ┌───────────────┐
                                                │   AIHomeHEMS  │
                                                │ (ポート: 8501) │
                                                └───────────────┘
```

<br>

すべての機器をギガビット対応スイッチングハブに集約し、ルーター側のDHCP固定割り当て（MACアドレスバインド）で**IPアドレスを完全に固定**しています。

- 🔋 **ニチコン蓄電池**: `192.168.1.200`（UDPポート: 3610 / ECHONET Lite）
- 📟 **HEMSコントローラ**: `192.168.1.100`（HTTPポート: 80 / Web管理画面）
- 🖥️ **ASUSTOR NAS**: `192.168.1.50`（Streamlitダッシュボード: 8501）

<br>

---

<br>

## 🐳 2. 常時稼働サーバーに「ASUSTOR NAS」を選んだ理由

自作HEMSを動かすハードウェアの選定ですが、候補としては以下の3つがありました：

1. **Raspberry Pi 4 / 5**: 定番だが、microSDカードの書き込み寿命が秒単位ロギングに耐えられない（SSD化が必要でコストがかさむ）。
2. **余っているWindows PC / Mac mini**: 消費電力が20W〜50Wあり、常時稼働させると電気代削減のためのシステムなのに本末転倒。
3. **ASUSTOR NAS (AS3102T)**: 省電力（アイドル時約10W）、RAID1ミラーリングでHDD障害に強い、Docker（Portainer）が最初から動く！

結論として、**24時間365日常に稼働している自宅のNAS（ASUSTOR）にDockerで相乗りさせる**のが圧倒的コスパ＆省エネでした！

<br>

---

<br>

## 📄 3. 実践！Docker Compose 設定ファイルの中身

NAS上で動かすための `docker-compose.yml` です。  
データの永続化とホストネットワークの扱いがキモになります。

<br>

```yaml
version: '3.8'

services:
  ai-hems:
    build: .
    container_name: ai-home-hems
    restart: unless-stopped
    network_mode: "host"
    environment:
      - TZ=Asia/Tokyo
      - PYTHONUNBUFFERED=1
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
    ports:
      - "8501:8501"
```

<br>

### 💡 ここだけは押さえたい重要ポイント！

#### ① `network_mode: "host"` の指定
ここが最大のハマりポイントです！  
ニチコン蓄電池とやり取りする「ECHONET Lite」は、**UDPポート 3610** を使ったソケット通信を行います。また、機器探索時にはUDPブロードキャスト（またはマルチキャスト `224.0.23.0`）を使用します。  
Dockerのデフォルトのブリッジネットワークだとブロードキャスト電文が透過せず、蓄電池との通信に失敗することがあります。  
ホストのネットワークスタックをそのまま共有する `network_mode: "host"` を指定することで、NAS本体と同一のLANセグメントから直接蓄電池を叩けるようになります！

#### ② `restart: unless-stopped` で自動復旧
停電からの復電時や、NAS本体のファームウェア更新による再起動後も、人間が何もしなくてもコンテナが自動で立ち上がって監視を再開してくれます。

#### ③ タイムゾーン `TZ=Asia/Tokyo`
これを忘れるとコンテナ内がUTC（世界協定時）になり、時系列データベースのログや電気料金の「21:00〜7:00深夜割引」の計算が9時間ズレて大混乱します（笑）。必ず指定しておきましょう！

<br>

---

<br>

## 📦 4. Dockerfile の設計

Python 3.12 スリムイメージをベースにした軽量で堅牢な `Dockerfile` です。

<br>

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 必要なシステムパッケージをインストール（ヘルスチェックやタイムゾーン用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 依存ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードの配置
COPY . .

# 起動スクリプトの実行権限付与
RUN chmod +x entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["./entrypoint.sh"]
```

<br>

### 🚀 起動スクリプト（entrypoint.sh）でロガーとUIを同時起動
HEMSは「秒単位でデータを収集する常時デーモン」と「人間がブラウザで見るダッシュボード（Streamlit）」の2つの顔を持っています。  
`entrypoint.sh` でバックグラウンドロガーを立ち上げつつ、フォアグラウンドでStreamlitを立ち上げる設計にしています。

<br>

```bash
#!/bin/bash
set -e

echo "🚀 [AIHomeHEMS] 常時監視ロガースレッドを起動中..."
python3 scheduler.py &

echo "🌐 [AIHomeHEMS] Streamlit UIサーバーを起動中 (ポート 8501)..."
exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

<br>

---

<br>

## 🛠️ 5. 動作確認：コンテナを起動してみる

NASのSSHターミナルから以下のコマンドを一発叩くだけで、ビルドと起動が完了します。

<br>

```bash
# コンテナのビルドとバックグラウンド起動
docker compose up -d --build

# 起動ログの確認
docker compose logs -f
```

<br>

起動後、同じWi-Fiに繋がったiPhoneやPCのブラウザから `http://192.168.1.50:8501` にアクセスすれば、爆速でダッシュボードの初期画面が立ち上がります！

<br>

---

<br>

## 📢 まとめ＆次回予告

今回は、自作HEMSを支える物理ネットワーク設計と、ASUSTOR NAS上でのDocker常時稼働基盤の構築手順を詳しく解説しました！

インフラの準備が整ったので、次回はいよいよ核心部分！  
**「蓄電池と話すための共通規格『ECHONET Lite』のプロトコル仕様と、ニチコンT5系のバイナリ電文構造」**をディープに解剖していきます！

ECHONET Liteの仕様書は数千ページあって初見だと頭が痛くなりますが、蓄電池の制御に必要なエッセンスだけをギュッと凝縮して分かりやすく図解します。お楽しみに！
