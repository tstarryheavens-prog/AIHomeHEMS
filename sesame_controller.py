import datetime
import base64
import requests
import json
import yaml
import os

try:
    from Crypto.Hash import CMAC
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

def load_sesame_config(config_path="config.yaml"):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("sesame", {})
    except Exception:
        return {}

def save_sesame_config(api_key, uuid, secret_key, config_path="config.yaml"):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if "sesame" not in config:
            config["sesame"] = {}
        config["sesame"]["api_key"] = api_key
        config["sesame"]["uuid"] = uuid
        config["sesame"]["secret_key"] = secret_key
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
        return True
    except Exception as e:
        print(f"[Sesame] Error saving config: {e}")
        return False

def generate_sesame_sign(secret_key_hex):
    """
    CANDY HOUSE SESAME Web API v3 の AES-CMAC 署名を生成する
    """
    if not HAS_CRYPTO:
        return None
    try:
        ts = int(datetime.datetime.now().timestamp())
        message = ts.to_bytes(4, byteorder='little')
        message = message.hex()[2:8]
        cmac = CMAC.new(bytes.fromhex(secret_key_hex.strip()), ciphermod=AES)
        cmac.update(bytes.fromhex(message))
        return cmac.hexdigest()
    except Exception as e:
        print(f"[Sesame] Error generating sign: {e}")
        return None

def get_sesame_status(api_key=None, uuid=None):
    """セサミの現在の施錠・解錠状態・バッテリー残量を取得する"""
    conf = load_sesame_config()
    api_key = api_key or conf.get("api_key")
    uuid = uuid or conf.get("uuid")

    if not api_key or not uuid:
        return {"success": False, "error": "APIキーまたはUUIDが未設定です"}

    url = f"https://app.candyhouse.co/api/sesame2/{uuid}"
    headers = {"x-api-key": api_key}

    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            # locked: True/False, battery: %, responsive: bool
            return {
                "success": True,
                "locked": data.get("locked", False),
                "battery": data.get("batteryPercentage", 100),
                "responsive": data.get("responsive", True),
                "raw": data
            }
        else:
            return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def control_sesame_lock(action="toggle", api_key=None, uuid=None, secret_key=None, history_tag="HomeHEMS"):
    """
    セサミを施錠 (lock: 82) または 解錠 (unlock: 83) または トグル (toggle: 88) する
    """
    conf = load_sesame_config()
    api_key = api_key or conf.get("api_key")
    uuid = uuid or conf.get("uuid")
    secret_key = secret_key or conf.get("secret_key")

    if not api_key or not uuid:
        return {"success": False, "error": "API Key または UUID が設定されていません。"}

    if not secret_key:
        return {
            "success": False, 
            "error": "Secret Key (秘密鍵/QRコード由来のHEX鍵) が未設定です。SESAME Web API v3 では秘密鍵による署名が必須です。"
        }

    # cmd: 82=lock(施錠), 83=unlock(解錠), 88=toggle(切替)
    cmd_map = {
        "lock": 82,
        "unlock": 83,
        "toggle": 88
    }
    cmd = cmd_map.get(action.lower(), 88)

    sign = generate_sesame_sign(secret_key)
    if not sign:
        return {"success": False, "error": "署名生成に失敗しました (Secret Keyのフォーマット確認またはpycryptodome確認)。"}

    url = f"https://app.candyhouse.co/api/sesame2/{uuid}/cmd"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    body = {
        "cmd": cmd,
        "history": base64.b64encode(history_tag.encode("utf-8")).decode("utf-8"),
        "sign": sign
    }

    try:
        res = requests.post(url, data=json.dumps(body), headers=headers, timeout=8)
        if res.status_code in [200, 204]:
            return {"success": True, "action": action, "status_code": res.status_code}
        else:
            return {"success": False, "error": f"APIエラー (HTTP {res.status_code}): {res.text}"}
    except Exception as e:
        return {"success": False, "error": f"通信エラー: {e}"}
