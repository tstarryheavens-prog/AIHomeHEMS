#!/usr/bin/env python3
"""
セキュリティ＆個人情報チェッカー

ブログ記事やコミット対象ファイルに、機密情報や個人情報（住所、実IP、パスワード、認証キー、実機ID等）
が含まれていないかを検査します。
"""

import os
import sys
import re
from pathlib import Path

# チェック対象の機密パターン
SENSITIVE_PATTERNS = {
    "HEMS実機ID": re.compile(r"E4D[0-9A-Z]{6}", re.IGNORECASE),
    "実機認証パスワード": re.compile(r"password:\s*[\"']?0320[\"']?", re.IGNORECASE),
    "特定地域・住所": re.compile(r"熱田区|伝馬", re.IGNORECASE),
    "特定緯度経度": re.compile(r"35\.1206|136\.9092"),
    "ローカル実IP (192.168.2.x)": re.compile(r"192\.168\.2\.\d+"),
    "はてなAPIキー露出": re.compile(r"sq927s291n"),
    "Gitea/内部Git認証情報": re.compile(r"Kapichan|tononon:"),
}

EXCLUDE_DIRS = {".git", "__pycache__", "tests", ".pytest_cache"}
EXCLUDE_FILES = {"config.yaml", ".env", "hems.db", "hems_data_log.csv", "hems_full_telemetry_log.csv", "security_check.py"}

def check_file(file_path: Path):
    violations = []
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in SENSITIVE_PATTERNS.items():
                if pattern.search(line):
                    violations.append((line_no, name, line.strip()))
    except Exception as e:
        pass
    return violations

def main():
    target_dir = Path(".")
    has_violation = False

    print("🛡️ 個人情報・機密情報セキュリティチェックを実行中...\n")

    # blog_posts と tools, docs, 主要スクリプトを重点検査
    scanned_files = 0
    for root, dirs, files in os.walk(target_dir):
        # 除外ディレクトリのスキップ
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for f in files:
            if f in EXCLUDE_FILES or f.startswith("."):
                continue
            if not f.endswith((".py", ".md", ".yaml", ".yml", ".json", ".sh", ".txt")):
                continue

            file_path = Path(root) / f
            violations = check_file(file_path)
            scanned_files += 1

            if violations:
                has_violation = True
                print(f"⚠️ 【警告】機密情報を検出: {file_path}")
                for line_no, name, line in violations:
                    # ログでの二次露出を防ぐため一部マスク
                    masked_line = line[:60] + "..." if len(line) > 60 else line
                    print(f"   行 {line_no} [{name}]: {masked_line}")
                print()

    print(f"✅ スキャン完了: {scanned_files} ファイルを検査しました。")
    if has_violation:
        print("\n❌ 機密情報が残っています！修正してからGitHubへのプッシュやブログ公開を行ってください。")
        sys.exit(1)
    else:
        print("\n🎉 機密情報・個人情報の露出は検出されませんでした！安全です。")

if __name__ == "__main__":
    main()
