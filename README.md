# ⚡ AI Home HEMS - 汎用次世代スマートエネルギーOS

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![ECHONET Lite](https://img.shields.io/badge/ECHONET_Lite-Certified_Spec-green.svg)](https://echonet.jp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI Home HEMS** は、日本国内の家庭用蓄電池・太陽光発電（PV）・スマートメーター（Bルート）・HEMS分電盤を統合制御し、電気代の最小化と非常時バックアップを自律的に両立する**オープンソースのスマートエネルギーOS**です。

ECHONET Lite規格（一般社団法人エコーネットコンソーシアム）に準拠し、国内主要メーカー各社の蓄電池・V2H、全国10大電力会社の深夜割引プラン・市場連動プランに対応。宅内ネットワークの**自動スキャン機能**と**Web GUIプルダウン個別設定**により、どなたでも簡単に導入できます。

---

## 🌟 主な特徴

### 1. 🔍 宅内スマート機器 自動スキャン (Auto-Discovery)
- **ECHONET Lite UDPマルチキャスト (`224.0.23.0:3610`)** とサブネット高速ポート走査を統合。
- 宅内LANに存在する蓄電池、太陽光パワコン、スマート電力量メータ、エコキュート（給湯器）、エアコン、HEMSコントローラーを自動探索。
- 検出結果から「🔋 蓄電池として登録」「🔌 HEMSとして登録」を**ワンクリックで設定に即時反映**。

### 2. 🇯🇵 日本国内規格 ＆ 国内主要メーカーのプルダウン選択対応
- **蓄電池 / V2H メーカープロファイル内蔵**:
  - **ニチコン (Nichicon)**: ESS / V2H T5系 (独自TCP 3610/1369ポート、ハードウェアタイマー同期対応)
  - **パナソニック (Panasonic)**: 創蓄連携システム / Li-ion蓄電池 (標準ECHONET Lite UDP 3610)
  - **オムロン (OMRON)**: 住・産共用フレキシブル蓄電システム KPBP-A系 (UDP 3610)
  - **ダイヤゼブラ電機 / 旧田淵電機**: ハイブリッド蓄電システム EneTelus (UDP 3610)
  - **シャープ (SHARP)**: クラウド蓄電池 / SUNVISTA JH-WBシリーズ (UDP 3610)
  - **京セラ (KYOCERA)**: クレイ型蓄電池 Enerezza (UDP 3610)
  - **長州産業**: Smart PV Multi (UDP 3610)
  - **テスラ (Tesla)**: Powerwall (Local Gateway REST API)
  - **汎用 ECHONET Lite 規格蓄電池**: クラス 0x027D (UDP 3610)
  - **シミュレーションモード**: 実機がない環境でも全UIとAIアルゴリズムを完全検証可能
- **買電・売電（系統電力）取得方式**:
  - 住宅用HEMS Webコントローラー (CenteHTTPd / パナホーム / パナソニックAiSEG系)
  - 電力会社スマートメーター Bルート直接通信 (Wi-SUNドングル ROHM BP35A1等)
  - ECHONET Lite 低圧スマート電力量メータ (Class 0x0288)
  - 蓄電池・パワコン内蔵 CTセンサー計測値
  - シミュレーション

### 3. ⚡ 全国10大電力会社 ＆ 新電力プランのプリセット
- **東京電力 (TEPCO)**: スマートライフプラン、夜トク8、夜トク12、従量電灯B
- **中部電力ミライズ**: スマートライフプラン【夜とく】、Eライフプラン、ポイントプラン
- **関西電力 (KEPCO)**: はぴｅタイムＲ、従量電灯A
- **東北電力 / 九州電力 / 中国電力 / 四国電力 / 北陸電力 / 北海道電力 / 沖縄電力** のオール電化・深夜割引プラン
- **市場連動型プラン (JEPX連動)**: Looopでんき、オクトパスエナジー等のダイナミックプライシング
- **カスタム自由設定**: ご自宅の契約単価や時間帯を手動でミリ単位調整可能

### 4. 🤖 AI気象予測 × JIT充放電 最適化制御
- **気象庁API ＆ Open-Meteo 日射量予測連携**: 翌日の発電予測量とご家庭の過去消費傾向から深夜充電SOC目標値を自動算出。
- **JIT (Just-In-Time) 充電**: 100%満充電の維持時間を極小化するため、起床直前の早朝 (例: 03:00〜06:30) にピンポイントで急速充電し、蓄電池の化学的寿命を最大化。
- **FIT / 卒FIT自動切り替え**: 満了日を基準に、FIT期間中（夕方強固売電）と卒FIT後（完全自家消費グリーン優先）のアルゴリズムを自律切り替え。
- **Storm Watch (気象警報連動 防災モード)**: 気象庁の大雨・暴風・大雪警報が発令された場合、直ちに満充電バックアップモード (0x42) に自動突入。

### 5. 🎛️ リッチな統合ダッシュボード (Streamlit)
- リアルタイムエネルギーフロー・アニメーション
- 各部屋別電力消費の内訳円グラフ（Living, Aircon, Kitchen, etc.）
- 月別・年別の売買電収支明細、電気代削減効果レポート
- 宅内IoTカメラ (ATOMCam等) のリアルタイムストリーミング監視

---

## 🚀 クイックスタート

### 動作環境
- Python 3.9 以上
- Windows / macOS / Linux / Raspberry Pi / Docker (NAS / Synology / ASUSTOR等)

### 1. リポジトリのクローンと依存パッケージのインストール
```bash
git clone https://github.com/your-org/HomeHEMS.git
cd HomeHEMS
pip install -r requirements.txt
```

### 2. アプリケーションの起動
```bash
streamlit run app.py
```
ブラウザが自動的に開き、`http://localhost:8501` にダッシュボードが表示されます。

---

## ⚙️ 初期セットアップ（わずか3ステップ）

1. 画面上部の **「⚙️ システム設定・汎用化」** タブを開きます。
2. **「🔍 宅内ネットワークを自動スキャンする」** をクリック。
   - 発見された機器リストから、ご自宅の蓄電池やHEMSコントローラーをワンクリックで反映します。
3. **「⚡ 電力会社 ＆ 電気料金プラン設定」** でご契約の電力会社とプランを選択し、**「💾 設定を保存して即時反映する」** を押すだけで完了です！

設定は自動的に `config.yaml` に暗号化・安全書き込みされ、バックグラウンドの監視ロガーやAI制御デーモンに即座に同期されます。

---

## 📁 主要ファイル構成

```
├── app.py                     # Streamlit 統合Webダッシュボード (5タブ構成)
├── presets_jp.py              # 日本国内規格・国内メーカー・電力プランプリセット定義
├── universal_echonet.py       # 国内全メーカー対応 ECHONET Lite 汎用通信クライアント
├── network_scanner.py         # ECHONET Liteマルチキャスト＆ポート探索スキャナー
├── config_manager.py          # 設定ファイル管理・バリデーション・バックアップ
├── hems_logger.py             # 定期データ取得 ＆ AI最適充放電スケジューラー
├── optimizer.py               # 機械学習・天気予報連動の翌日充放電最適化エンジン
├── weather_service.py         # 気象庁警報API (Storm Watch) ＆ Open-Meteo日射量予測
├── broute_collector.py        # Wi-SUN Bルート直接通信モジュール (BP35A1等)
├── database.py                # SQLite (hems.db) 時系列テレメトリ・履歴ストレージ
├── config.example.yaml        # 設定ファイル テンプレート
└── README.md                  # 本ドキュメント
```

---

## 🛡️ ライセンス

本プロジェクトは [MIT License](LICENSE) のもとで公開されています。商用・非商用問わず自由にご利用・改変いただけます。
