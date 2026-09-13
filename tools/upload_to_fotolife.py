#!/usr/bin/env python3
"""
はてなフォトライフ AtomPub 画像アップロードスクリプト

ローカル画像をはてなフォトライフにアップロードし、記事に埋め込めるURLを取得します。
"""

import os
import sys
import base64
from pathlib import Path
import xml.etree.ElementTree as ET
import requests
from hatena_publisher import load_env_config, generate_wsse_header

FOTOLIFE_POST_URL = "https://f.hatena.ne.jp/atom/post"

def upload_image(image_path: Path, title: str = None):
    config = load_env_config()
    username = config["hatena_id"]
    api_key = config["api_key"]
    if not username or not api_key:
        print("Error: HATENA_ID or HATENA_API_KEY missing.", file=sys.stderr)
        sys.exit(1)

    if not image_path.exists():
        print(f"Error: File {image_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    img_bytes = image_path.read_bytes()
    b64_data = base64.b64encode(img_bytes).decode("utf-8")
    
    mime_type = "image/jpeg"
    if image_path.suffix.lower() == ".png":
        mime_type = "image/png"
    elif image_path.suffix.lower() == ".gif":
        mime_type = "image/gif"

    img_title = title or image_path.stem

    xml_payload = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://purl.org/atom/ns#">
  <title>{img_title}</title>
  <content mode="base64" type="{mime_type}">{b64_data}</content>
  <dc:subject xmlns:dc="http://purl.org/dc/elements/1.1/">AIHomeHEMS</dc:subject>
</entry>
"""

    headers = {
        "X-WSSE": generate_wsse_header(username, api_key),
        "Content-Type": "application/xml",
    }

    print(f"📡 はてなフォトライフへアップロード中: {image_path.name}...")
    resp = requests.post(FOTOLIFE_POST_URL, data=xml_payload.encode("utf-8"), headers=headers, timeout=30)

    if resp.status_code == 201:
        root = ET.fromstring(resp.text)
        # 画像URLとhatena記法の抽出
        hatena_syntax = root.find("{http://purl.org/atom/ns#}hatena_syntax")
        syntax_text = hatena_syntax.text if hatena_syntax is not None else ""
        
        image_url = ""
        for link in root.findall("{http://purl.org/atom/ns#}link"):
            if link.attrib.get("rel") == "alternate":
                image_url = link.attrib.get("href")

        # 直リンク画像URL（hatena:imageurl等）
        img_src = ""
        img_elem = root.find("{http://purl.org/atom/ns#}imageurl")
        if img_elem is not None:
            img_src = img_elem.text
        if not img_src:
            img_src = image_url

        print(f"✅ アップロード成功！")
        print(f"  🔗 画像URL: {img_src}")
        print(f"  🔖 はてな記法: {syntax_text}")
        return {"image_url": img_src, "syntax": syntax_text}
    else:
        print(f"❌ アップロード失敗: HTTP {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 upload_to_fotolife.py <image_path> [title]")
        sys.exit(1)
    img = Path(sys.argv[1])
    t = sys.argv[2] if len(sys.argv) > 2 else None
    upload_image(img, t)
