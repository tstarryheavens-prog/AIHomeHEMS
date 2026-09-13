# 📝 はてなブログ自動生成＆投稿ガイド (AIHomeHEMS)

本ドキュメントでは、AI（Antigravity）と Python ツールを活用して、はてなブログへ「AIHomeHEMS」の開発顛末記や実装解説記事を自動生成・投稿する手順を解説します。

---

## ⚙️ 1. はてなブログ API の初期設定

1. **`.env` ファイルを作成**
   リポジトリのルートに `.env` を作成します（`.gitignore` に登録されているため Git にはコミットされません）。

   ```bash
   cp .env.example .env
   ```

2. **認証情報を入力**
   `.env` を開き、はてなブログの情報を入力します：

   ```env
   HATENA_ID=あなたのHatenaID
   HATENA_BLOG_ID=あなたのブログID.hatenablog.com
   HATENA_API_KEY=あなたのAtomPubAPIキー
   HATENA_DEFAULT_DRAFT=true
   ```

   > 💡 **AtomPub APIキーの確認方法**:
   > はてなブログ管理画面 ＞ **[設定]** ＞ **[詳細設定]** ＞ ページ下部の **[AtomPub]** 欄に記載されています。

---

## 🤖 2. AI（Antigravity）に記事を自動生成してもらう方法

チャットで以下のように話しかけるだけで、実際のソースコードを引用しながら高品質な記事 Markdown ファイルが自動生成されます。

### 指示プロンプト例
- `「第2回のECHONET Lite通信の記事を生成して」`
- `「第3回のリバースエンジニアリングの記事を書いて」`
- `「できた記事を下書きとしてはてなブログに投稿して」`

AI は `blog_posts/` ディレクトリ内にフロントマター付きの Markdown ファイル（例: `blog_posts/02_echonet_lite_nichicon_udp.md`）を作成します。

---

## 🚀 3. コマンドでのはてなブログ投稿・管理

投稿スクリプト `tools/hatena_publisher.py` を使って、コマンドラインから直接操作できます。

### ① 記事を下書きとして新規投稿（安全・推奨）
```bash
python3 tools/hatena_publisher.py post blog_posts/01_intro_fit_hems_overview.md
```
※ はてなブログ管理画面でプレビューを確認し、問題なければ管理画面で公開できます。

### ② 直接公開して投稿
```bash
python3 tools/hatena_publisher.py post blog_posts/01_intro_fit_hems_overview.md --publish
```

### ③ 既存の記事を更新
```bash
# 編集URLまたはエントリIDを指定
python3 tools/hatena_publisher.py update <エントリIDまたはEditURL> blog_posts/01_intro_fit_hems_overview.md
```

### ④ 最近の記事一覧を確認
```bash
python3 tools/hatena_publisher.py list
```

---

## 📚 4. 連載シリーズの構成一覧

| 回 | テーマ | 主なトピック / ソースコード |
|:---:|:---|:---|
| **第1回** | プロジェクト始動【顛末記】 | 卒FIT対策（31円→8.5円）、全体構成図、`config.yaml` |
| **第2回** | ECHONET Lite通信編 | ニチコン蓄電池（T5系）とUDP通信、EPC解析 (`echonet_nichicon.py`) |
| **第3回** | リバースエンジニアリング編 | HEMSコントローラWeb画面のスクレイピング・Cookie認証 (`hems_logger.py`) |
| **第4回** | データ基盤・時系列ロガー編 | SQLite WALモード、マルチスレッド常時監視 (`database.py`, `scheduler.py`) |
| **第5回** | AI最適化・気象連動編 | Open-Meteo日射量予測×電気料金プランの最適夜間充電 (`optimizer.py`) |
| **第6回** | UI・iPhone最適化編 | Streamlit×Altairによるモバイルダッシュボード設計 (`app.py`) |
| **第7回** | スマートホーム連携編 | Sesameスマートロック連携と宅内ネットワークスキャン (`sesame_controller.py`) |
| **第8回** | 常時運用・インフラ編 | ASUSTOR NAS (Docker Compose) による24時間運用 (`docker-compose.yml`) |

---

## 🐙 5. GitHub リポジトリへのプッシュ

ブログ生成ツールや記事 Markdown も含めて GitHub (`https://github.com/tstarryheavens-prog/AIHomeHEMS.git`) に同期する場合：

```bash
git add tools/ blog_posts/ docs/ tests/ .gitignore .env.example
git commit -m "feat: add automated Hatena Blog post generation and episode 1"
git push github main
```
