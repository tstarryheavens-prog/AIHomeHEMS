#!/usr/bin/env python3
"""
はてなブログ AtomPub API 投稿・管理スクリプト

機能:
  - Markdownファイル（フロントマター付き）からはてなブログへの自動投稿（下書き・公開）
  - デフォルトでHTML（type="text/html"）に自動レンダリングして送信（見たままモード／Markdownモード問わず完全対応）
  - 記事の更新 (PUT)
  - 記事一覧の取得・表示 (GET)
  - WSSE認証 / Basic認証両対応
"""

import os
import sys
import re
import argparse
import base64
import hashlib
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from pathlib import Path
import requests
import yaml
import markdown

# XML名前空間定義
ATOM_NS = "http://www.w3.org/2005/Atom"
APP_NS = "http://www.w3.org/2007/app"
NAMESPACES = {
    "atom": ATOM_NS,
    "app": APP_NS,
}


def load_env_config():
    """環境変数または .env, hatena_config.yaml から設定を読み込む"""
    config = {
        "hatena_id": os.environ.get("HATENA_ID"),
        "blog_id": os.environ.get("HATENA_BLOG_ID"),
        "api_key": os.environ.get("HATENA_API_KEY"),
        "default_draft": os.environ.get("HATENA_DEFAULT_DRAFT", "true").lower() in ("true", "1", "yes"),
        "auth_method": os.environ.get("HATENA_AUTH_METHOD", "wsse").lower(),
    }

    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k == "HATENA_ID" and not config["hatena_id"]:
                        config["hatena_id"] = v
                    elif k == "HATENA_BLOG_ID" and not config["blog_id"]:
                        config["blog_id"] = v
                    elif k == "HATENA_API_KEY" and not config["api_key"]:
                        config["api_key"] = v
                    elif k == "HATENA_DEFAULT_DRAFT":
                        config["default_draft"] = v.lower() in ("true", "1", "yes")

    yaml_path = Path("hatena_config.yaml")
    if yaml_path.exists():
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    config["hatena_id"] = config["hatena_id"] or data.get("hatena_id")
                    config["blog_id"] = config["blog_id"] or data.get("blog_id")
                    config["api_key"] = config["api_key"] or data.get("api_key")
                    if "default_draft" in data:
                        config["default_draft"] = bool(data["default_draft"])
        except Exception as e:
            print(f"Warning: Failed to parse hatena_config.yaml: {e}", file=sys.stderr)

    return config


def generate_wsse_header(username: str, api_key: str) -> str:
    """WSSE認証ヘッダーを生成"""
    nonce = os.urandom(20)
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sha = hashlib.sha1()
    sha.update(nonce + created.encode("utf-8") + api_key.encode("utf-8"))
    digest = base64.b64encode(sha.digest()).decode("utf-8")
    nonce_b64 = base64.b64encode(nonce).decode("utf-8")
    return f'UsernameToken Username="{username}", PasswordDigest="{digest}", Nonce="{nonce_b64}", Created="{created}"'


def get_auth_headers(config):
    """設定に応じた認証ヘッダーを返す"""
    username = config["hatena_id"]
    api_key = config["api_key"]
    if not username or not api_key:
        raise ValueError("HATENA_ID または HATENA_API_KEY が設定されていません。.env を確認してください。")

    if config["auth_method"] == "basic":
        b64_cred = base64.b64encode(f"{username}:{api_key}".encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {b64_cred}"}
    else:
        return {"X-WSSE": generate_wsse_header(username, api_key)}


def parse_markdown_file(file_path: Path):
    """フロントマター付きMarkdownファイルをパースする"""
    text = file_path.read_text(encoding="utf-8")
    metadata = {}
    content = text

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if match:
        raw_meta, content = match.groups()
        try:
            parsed_meta = yaml.safe_load(raw_meta)
            if isinstance(parsed_meta, dict):
                metadata = parsed_meta
        except Exception as e:
            print(f"Warning: YAML Frontmatter parse error: {e}", file=sys.stderr)
    else:
        first_line_match = re.match(r"^#\s+(.+)$", text.split("\n")[0])
        if first_line_match:
            metadata["title"] = first_line_match.group(1).strip()
            content = "\n".join(text.split("\n")[1:]).strip()

    title = metadata.get("title", file_path.stem)
    categories = metadata.get("category", metadata.get("categories", []))
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]
    draft = metadata.get("draft", None)

    return {
        "title": title,
        "categories": categories,
        "draft": draft,
        "content": content.strip(),
        "custom_url": metadata.get("custom_url", None)
    }


A8_DEFAULT_CONFIG_ID = "AiCzxW5LM9avBb8VJ393"


def inject_a8_ad_units(html_content: str, config_id: str = A8_DEFAULT_CONFIG_ID) -> str:
    """
    記事のデザインを邪魔せず、読者目線で自然かつクリック率（CTR）が最も高くなる
    適材適所の位置にA8広告マネージャーとスマートPR枠を自動注入する
    """
    # 1. 記事冒頭：ステマ規制（消費者庁ガイドライン）に完全準拠したスタイリッシュなPR表記バッジ
    pr_badge = (
        '<div style="font-size: 11px; color: #888888; text-align: right; margin-bottom: 14px; padding: 4px 6px; letter-spacing: 0.5px;">'
        '<span style="background: #eef1f4; border: 1px solid #d0d7de; border-radius: 4px; padding: 2px 6px; font-weight: bold; color: #57606a;">PR</span> '
        '当記事はアフィリエイト広告を含みます'
        '</div>\n'
    )

    # 2. 記事終盤（まとめ・次回予告直前）：読了後のアクション意欲が最も高い位置に配置する上品なスポンサー枠
    bottom_sponsor_box = (
        '\n<div class="a8-sponsor-box" style="margin: 36px 0 24px 0; padding: 20px 24px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.04);">'
        '<div style="font-size: 11px; font-weight: bold; color: #64748b; margin-bottom: 8px; letter-spacing: 1px; display: flex; align-items: center; gap: 6px;">'
        '<span>💡</span> SPONSORED LINK'
        '</div>'
        '<div style="font-size: 13.5px; color: #334155; line-height: 1.65;">'
        '卒FIT後の電気料金プラン見直し、太陽光発電・大容量蓄電池の導入費用シミュレーションや一括比較など、賢いエネルギー対策に役立つサービスをご紹介しています。'
        '</div>'
        '</div>\n'
        '<!-- A8.net Auto Link Manager -->'
        '<script src="//statics.a8.net/a8link/a8linkmgr.js"></script>\n'
        '<script>\n'
        '  a8linkmgr({\n'
        f'    "config_id": "{config_id}"\n'
        '  });\n'
        '</script>\n'
    )

    return pr_badge + html_content + bottom_sponsor_box


def convert_markdown_to_html(md_content: str, enable_ads: bool = True) -> str:
    """Markdownをはてなブログ用のリッチHTMLに変換"""
    html = markdown.markdown(
        md_content,
        extensions=[
            "fenced_code",
            "tables",
            "nl2br",
            "sane_lists"
        ]
    )
    if enable_ads:
        html = inject_a8_ad_units(html)
    return html


def build_entry_xml(title: str, content: str, categories: list, draft: bool, username: str = "", as_html: bool = True, enable_ads: bool = True) -> bytes:
    """Atom XMLのエントリ文字列を構築"""
    entry = ET.Element("entry", {
        "xmlns": ATOM_NS,
        "xmlns:app": APP_NS,
    })

    title_elem = ET.SubElement(entry, "title")
    title_elem.text = title

    if username:
        author_elem = ET.SubElement(entry, "author")
        name_elem = ET.SubElement(author_elem, "name")
        name_elem.text = username

    if as_html:
        html_body = convert_markdown_to_html(content, enable_ads=enable_ads)
        content_elem = ET.SubElement(entry, "content", {"type": "text/html"})
        content_elem.text = html_body
    else:
        content_elem = ET.SubElement(entry, "content", {"type": "text/x-markdown"})
        content_elem.text = content

    for cat in categories:
        ET.SubElement(entry, "category", {"term": str(cat)})

    control_elem = ET.SubElement(entry, f"{{{APP_NS}}}control")
    draft_elem = ET.SubElement(control_elem, f"{{{APP_NS}}}draft")
    draft_elem.text = "yes" if draft else "no"

    return ET.tostring(entry, encoding="utf-8", xml_declaration=True)


def parse_entry_response(xml_text: str):
    """レスポンスXMLから公開URL、Edit URL、エントリID等を抽出"""
    try:
        root = ET.fromstring(xml_text)
        info = {
            "title": "",
            "id": "",
            "edit_url": "",
            "alternate_url": "",
            "published": "",
            "updated": "",
            "draft": False,
        }

        title = root.find("atom:title", NAMESPACES)
        if title is not None:
            info["title"] = title.text or ""

        entry_id = root.find("atom:id", NAMESPACES)
        if entry_id is not None:
            info["id"] = entry_id.text or ""

        for link in root.findall("atom:link", NAMESPACES):
            rel = link.attrib.get("rel")
            href = link.attrib.get("href")
            if rel == "edit":
                info["edit_url"] = href
            elif rel == "alternate":
                info["alternate_url"] = href

        published = root.find("atom:published", NAMESPACES)
        if published is not None:
            info["published"] = published.text or ""

        updated = root.find("atom:updated", NAMESPACES)
        if updated is not None:
            info["updated"] = updated.text or ""

        control = root.find("app:control", NAMESPACES)
        if control is not None:
            draft_elem = control.find("app:draft", NAMESPACES)
            if draft_elem is not None and draft_elem.text == "yes":
                info["draft"] = True

        return info
    except Exception as e:
        return {"raw": xml_text, "error": str(e)}


def post_entry(file_path: Path, force_draft=None, force_publish=False, raw_markdown=False, no_ads=False):
    """Markdownファイルを投稿する"""
    config = load_env_config()
    if not config["hatena_id"] or not config["blog_id"] or not config["api_key"]:
        print("❌ エラー: はてなブログの認証情報が見つかりません。", file=sys.stderr)
        sys.exit(1)

    parsed = parse_markdown_file(file_path)

    if force_publish:
        draft = False
    elif force_draft is not None:
        draft = force_draft
    elif parsed["draft"] is not None:
        draft = parsed["draft"]
    else:
        draft = config["default_draft"]

    as_html = not raw_markdown
    xml_data = build_entry_xml(
        title=parsed["title"],
        content=parsed["content"],
        categories=parsed["categories"],
        draft=draft,
        username=config["hatena_id"],
        as_html=as_html,
        enable_ads=not no_ads,
    )

    url = f"https://blog.hatena.ne.jp/{config['hatena_id']}/{config['blog_id']}/atom/entry"
    headers = get_auth_headers(config)
    headers["Content-Type"] = "application/xml"

    print(f"📡 投稿中: {parsed['title']} (形式: {'HTML変換' if as_html else '生Markdown'}, 広告: {'ON' if not no_ads else 'OFF'}, 下書き: {'はい' if draft else 'いいえ'})...")
    resp = requests.post(url, data=xml_data, headers=headers, timeout=15)

    if resp.status_code == 201:
        entry_info = parse_entry_response(resp.text)
        print("✅ 投稿成功！")
        print(f"  📌 タイトル: {entry_info.get('title')}")
        print(f"  📝 状態: {'下書き' if entry_info.get('draft') else '公開中'}")
        print(f"  🔗 記事URL: {entry_info.get('alternate_url')}")
        print(f"  ⚙️ 編集URL: {entry_info.get('edit_url')}")
        return entry_info
    else:
        print(f"❌ 投稿失敗: HTTP {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)


def update_entry(edit_url_or_id: str, file_path: Path, force_draft=None, force_publish=False, raw_markdown=False, no_ads=False):
    """既存エントリを更新する"""
    config = load_env_config()
    parsed = parse_markdown_file(file_path)

    if force_publish:
        draft = False
    elif force_draft is not None:
        draft = force_draft
    elif parsed["draft"] is not None:
        draft = parsed["draft"]
    else:
        draft = config["default_draft"]

    as_html = not raw_markdown
    xml_data = build_entry_xml(
        title=parsed["title"],
        content=parsed["content"],
        categories=parsed["categories"],
        draft=draft,
        username=config["hatena_id"],
        as_html=as_html,
        enable_ads=not no_ads,
    )

    if edit_url_or_id.startswith("http"):
        url = edit_url_or_id
    else:
        url = f"https://blog.hatena.ne.jp/{config['hatena_id']}/{config['blog_id']}/atom/entry/{edit_url_or_id}"

    headers = get_auth_headers(config)
    headers["Content-Type"] = "application/xml"

    print(f"🔄 更新中: {parsed['title']} (形式: {'HTML変換' if as_html else '生Markdown'}, 広告: {'ON' if not no_ads else 'OFF'})...")
    resp = requests.put(url, data=xml_data, headers=headers, timeout=15)

    if resp.status_code == 200:
        entry_info = parse_entry_response(resp.text)
        print("✅ 更新成功！")
        print(f"  📌 タイトル: {entry_info.get('title')}")
        print(f"  🔗 記事URL: {entry_info.get('alternate_url')}")
        return entry_info
    else:
        print(f"❌ 更新失敗: HTTP {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)


def list_entries():
    """最近の記事一覧を取得"""
    config = load_env_config()
    if not config["hatena_id"] or not config["blog_id"] or not config["api_key"]:
        print("❌ エラー: はてなブログの認証情報が見つかりません。", file=sys.stderr)
        sys.exit(1)

    url = f"https://blog.hatena.ne.jp/{config['hatena_id']}/{config['blog_id']}/atom/entry"
    headers = get_auth_headers(config)

    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        print(f"❌ 取得失敗: HTTP {resp.status_code}", file=sys.stderr)
        sys.exit(1)

    root = ET.fromstring(resp.text)
    entries = root.findall("atom:entry", NAMESPACES)
    print(f"\n📚 記事一覧 ({len(entries)} 件表示):")
    print("-" * 80)
    for entry in entries:
        title = entry.find("atom:title", NAMESPACES)
        title_text = title.text if title is not None else "(無題)"
        
        alt_link = ""
        edit_link = ""
        for link in entry.findall("atom:link", NAMESPACES):
            rel = link.attrib.get("rel")
            if rel == "alternate":
                alt_link = link.attrib.get("href")
            elif rel == "edit":
                edit_link = link.attrib.get("href")

        control = entry.find("app:control", NAMESPACES)
        is_draft = False
        if control is not None:
            draft_elem = control.find("app:draft", NAMESPACES)
            if draft_elem is not None and draft_elem.text == "yes":
                is_draft = True

        status = "【下書き】" if is_draft else "【公開中】"
        print(f"{status} {title_text}")
        print(f"   公開URL: {alt_link}")
        print(f"   編集URL: {edit_link}\n")


def main():
    parser = argparse.ArgumentParser(description="はてなブログ AtomPub 記事投稿・管理ツール")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # post command
    post_parser = subparsers.add_parser("post", help="Markdownファイルを新規投稿する")
    post_parser.add_argument("file", type=Path, help="投稿するMarkdownファイルパス")
    post_parser.add_argument("--draft", action="store_true", help="下書きとして投稿（デフォルト）")
    post_parser.add_argument("--publish", action="store_true", help="直接公開して投稿")
    post_parser.add_argument("--raw-markdown", action="store_true", help="HTML変換せず生のMarkdownとして投稿")
    post_parser.add_argument("--no-ads", action="store_true", help="A8自動リンク・PR枠の注入を無効化")

    # update command
    update_parser = subparsers.add_parser("update", help="既存エントリを更新する")
    update_parser.add_argument("entry", type=str, help="更新対象のエントリIDまたはEdit URL")
    update_parser.add_argument("file", type=Path, help="更新するMarkdownファイルパス")
    update_parser.add_argument("--draft", action="store_true", help="下書き状態のまま更新")
    update_parser.add_argument("--publish", action="store_true", help="公開して更新")
    update_parser.add_argument("--raw-markdown", action="store_true", help="HTML変換せず生のMarkdownとして更新")
    update_parser.add_argument("--no-ads", action="store_true", help="A8自動リンク・PR枠の注入を無効化")

    # list command
    subparsers.add_parser("list", help="最近の記事一覧を表示する")

    args = parser.parse_args()

    if args.command == "post":
        post_entry(args.file, force_draft=True if args.draft else None, force_publish=args.publish, raw_markdown=args.raw_markdown, no_ads=args.no_ads)
    elif args.command == "update":
        update_entry(args.entry, args.file, force_draft=True if args.draft else None, force_publish=args.publish, raw_markdown=args.raw_markdown, no_ads=args.no_ads)
    elif args.command == "list":
        list_entries()


if __name__ == "__main__":
    main()
