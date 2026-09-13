import unittest
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

# tools ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from hatena_publisher import generate_wsse_header, build_entry_xml, parse_markdown_file, parse_entry_response

class TestHatenaPublisher(unittest.TestCase):
    def test_wsse_header_generation(self):
        header = generate_wsse_header("testuser", "testapikey")
        self.assertIn('UsernameToken Username="testuser"', header)
        self.assertIn('PasswordDigest="', header)
        self.assertIn('Nonce="', header)
        self.assertIn('Created="', header)

    def test_build_entry_xml(self):
        xml_bytes = build_entry_xml(
            title="テスト記事",
            content="これは本文です。\n```python\nprint('hello')\n```",
            categories=["HEMS", "蓄電池"],
            draft=True,
            username="testuser"
        )
        root = ET.fromstring(xml_bytes)
        self.assertEqual(root.find("{http://www.w3.org/2005/Atom}title").text, "テスト記事")
        self.assertEqual(root.find("{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name").text, "testuser")
        
        categories = [cat.attrib.get("term") for cat in root.findall("{http://www.w3.org/2005/Atom}category")]
        self.assertEqual(categories, ["HEMS", "蓄電池"])
        
        draft = root.find("{http://www.w3.org/2007/app}control/{http://www.w3.org/2007/app}draft")
        self.assertIsNotNone(draft)
        self.assertEqual(draft.text, "yes")

    def test_parse_entry_response(self):
        sample_response = """<?xml version="1.0" encoding="utf-8"?>
        <entry xmlns="http://www.w3.org/2005/Atom" xmlns:app="http://www.w3.org/2007/app">
          <id>tag:blog.hatena.ne.jp,2013:blog-sample-123456</id>
          <title>サンプルタイトル</title>
          <link rel="alternate" type="text/html" href="https://sample.hatenablog.com/entry/2026/09/13/120000" />
          <link rel="edit" href="https://blog.hatena.ne.jp/user/sample.hatenablog.com/atom/entry/123456" />
          <app:control>
            <app:draft>yes</app:draft>
          </app:control>
        </entry>
        """
        info = parse_entry_response(sample_response)
        self.assertEqual(info["title"], "サンプルタイトル")
        self.assertEqual(info["id"], "tag:blog.hatena.ne.jp,2013:blog-sample-123456")
        self.assertEqual(info["alternate_url"], "https://sample.hatenablog.com/entry/2026/09/13/120000")
        self.assertEqual(info["edit_url"], "https://blog.hatena.ne.jp/user/sample.hatenablog.com/atom/entry/123456")
        self.assertTrue(info["draft"])

if __name__ == "__main__":
    unittest.main()
