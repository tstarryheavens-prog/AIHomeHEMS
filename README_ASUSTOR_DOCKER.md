# ⚡ ASUSTOR NAS (AS3102T) 常時稼働 ＆ iPhone 17 Pro Max アクセスガイド

本ドキュメントでは、作成した Docker 環境を **ASUSTOR NAS AS3102T** にデプロイし、**iPhone 17 Pro Max** からいつでもアクセスできるようにする手順を解説します。

---

## 📁 1. ASUSTOR NAS へのファイル転送

1. NAS の共有フォルダ内に作業用ディレクトリを作成します（例: `/volume1/Docker/hems`）。
2. 本プロジェクトのファイル一式（特に以下）をすべて作成したフォルダへコピーします。
   - `app.py`
   - `scheduler.py`
   - `database.py`
   - `broute_collector.py`
   - `echonet_nichicon.py`
   - `optimizer.py`
   - `weather_service.py`
   - `hems_logger.py`
   - `hems_history_importer.py`
   - `bulk_extract_history.py`
   - `config.yaml`
   - `requirements.txt`
   - `Dockerfile`
   - `docker-compose.yml`
   - `entrypoint.sh`
   - `hems.db`（既存データベースがある場合）

---

## 🚀 2. Docker コンテナの起動手順

### 方法 A: ADM Portainer / Docker App を使用する場合（UI操作）
1. ASUSTOR ADM にログインし、**App Central** から **Portainer**（または Docker / Container Center）をインストールして起動します。
2. Portainer の **Stacks** メニューから `Add stack` を選択します。
3. 名前を `ai-hems` とし、`docker-compose.yml` の内容を貼り付けるか、ファイルアップロードします。
4. **Deploy the stack** をクリックするとビルドと起動が開始されます。

### 方法 B: SSH ターミナルからコマンド起動する場合
1. ASUSTOR ADM の **設定** ＞ **ターミナル** で SSH を有効にします。
2. PCのターミナルから NAS に SSH 接続します：
   ```bash
   ssh admin@<NASのIPアドレス>
   ```
3. プロジェクトフォルダに移動し、コンテナをビルド・起動します：
   ```bash
   cd /volume1/Docker/hems
   docker compose up -d --build
   ```

---

## 📱 3. iPhone 17 Pro Max からのアクセス設定

### ① 自宅 Wi-Fi 接続時
Safari または Chrome から以下のURLを開きます：
```http
http://<NASのIPアドレス>:8501
```
*(例: http://192.168.2.100:8501)*

### ② 外出先（4G/5G通信）からの安全なアクセス (Tailscale推奨)
ルーターのポート開放不要で最もセキュアな **Tailscale (VPN)** の利用をお勧めします。

1. **ASUSTOR NAS に Tailscale を導入**:
   - ADM の **App Central** で `Tailscale` を検索してインストールします。
   - アプリを開き、Tailscale アカウントでログインして NAS をネットワークに追加します。
2. **iPhone に Tailscale を導入**:
   - App Store から `Tailscale` アプリをインストールします。
   - NAS と同じアカウントでログインし、VPN 接続を ON にします。
3. **iPhone からアクセス**:
   - Tailscale 管理画面で表示される NAS の Tailscale IP（例: `100.115.x.y`）を使ってアクセスします：
     ```http
     http://100.115.x.y:8501
     ```

### ③ iPhone のホーム画面にアプリ（PWA風）として登録する
1. iPhone の Safari で上記 URL を開きます。
2. 画面下部の **共有ボタン**（四角と上矢印のアイコン）をタップします。
3. **「ホーム画面に追加」** を選択し、名前を「AI SMART ENERGY」などに設定して保存します。
4. ホーム画面に専用アイコンが生成され、ワンタップでフルスクリーン風にシステムを起動できます。

---

## ⚙️ 4. ログ確認・管理コマンド

* **コンテナの稼働ログ確認**:
  ```bash
  docker logs -f ai-hems-controller
  ```
* **コンテナの再起動**:
  ```bash
  docker compose restart
  ```
* **コンテナの停止**:
  ```bash
  docker compose down
  ```
