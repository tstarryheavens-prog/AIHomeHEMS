# 🤝 AI Home HEMS コントリビューションガイド

AI Home HEMS プロジェクトへの貢献にご関心をお寄せいただき、誠にありがとうございます！
バグ報告、機能提案、ドキュメントの改善、プルリクエスト（PR）など、あらゆるコントリビューションを心より歓迎いたします。

---

## 📋 参加の基本ルール

本プロジェクトに参加される際は、[行動規範 (CODE_OF_CONDUCT.md)](CODE_OF_CONDUCT.md) を遵守いただくようお願いいたします。お互いを尊重し、友好的かつ生産的なコミュニティを築きましょう。

---

## 🐛 バグ報告と機能要望

### バグを報告する場合
1. [既存の Issues](https://github.com/tstarryheavens-prog/AIHomeHEMS/issues) で同様の問題が既に報告されていないかご確認ください。
2. 解決していない場合、**Bug Report テンプレート** を使用して新しい Issue を作成してください。
3. 以下の情報を含めていただくと迅速な調査・修正が可能になります：
   - 使用しているOSおよびPythonバージョン
   - 蓄電池メーカー・モデル名（例: ニチコン T5, パナソニック 創蓄連携, オムロン KPBP-A等）
   - 電力会社および料金プラン
   - 再現手順およびエラーログ（スタックトレース）
   - 個人情報（HEMSパスワード、Bルート認証情報、グローバルIP等）が含まれていないことをご確認ください。

### 新機能や対応機器を提案する場合
- **Feature Request テンプレート** を使用して Issue を作成してください。
- なぜその機能が必要か、どのような利用シナリオがあるかを具体的にご記入ください。

---

## 💻 開発環境のセットアップ

### 1. リポジトリのフォークとクローン
```bash
git clone https://github.com/<あなたのユーザー名>/AIHomeHEMS.git
cd AIHomeHEMS
```

### 2. Python仮想環境の構築
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 設定ファイルの準備
```bash
cp config.example.yaml config.yaml
```
実機がない環境でも、`config.yaml` の `battery_system.manufacturer` を `"simulation"` に設定することで、シミュレーションモードで全機能をテストできます。

### 4. アプリケーションの起動
```bash
streamlit run app.py
```

---

## 🧪 テストの実行

PRを提出する前に、必ずすべての単体テストを実行しパスすることを確認してください：

```bash
# 全テストの一括実行
python3 -m unittest discover tests

# 汎用化・国内規格テストの実行
python3 -m unittest tests/test_generalization.py
```

---

## 🚀 プルリクエスト（PR）の提出手順

1. `main` ブランチから新しいトピックブランチを作成します：
   ```bash
   git checkout -b feature/support-new-battery-model
   # または
   git checkout -b fix/udp-packet-timeout-issue
   ```
2. コードの修正を行い、必要に応じて `tests/` にテストケースを追加します。
3. コードスタイル（PEP 8）に準拠し、コミットメッセージは明確かつ簡潔に記述してください：
   - 例: `feat: Add Daikin heat-pump water heater ECHONET Lite profile`
   - 例: `fix: Handle socket timeout on ECHONET UDP multicast scan`
4. あなたのフォークにプッシュし、本リポジトリの `main` ブランチに向けてプルリクエストを作成します。
5. PRテンプレートの各項目を記入し、レビューをお待ちください。

---

## 🇯🇵 新しい蓄電池・ECHONET機器の追加方法

新しい国内メーカーや機器プロファイルを追加する場合は、[`presets_jp.py`](presets_jp.py) の `BATTERY_MANUFACTURERS` または `GRID_MEASUREMENT_SOURCES` に定義を追加し、[`universal_echonet.py`](universal_echonet.py) で必要に応じたプロトコルハンドラーを拡張してください。

皆さまからの素晴らしいコントリビューションを心よりお待ちしております！
