"""
version.py - AIHomeHEMS システムバージョン管理モジュール
システム全体（UI、サイドバー、ヘッダー、ログ、API等）のバージョン表記を一元管理します。
"""

__version__ = "2.5.0"
APP_VERSION = f"v{__version__}"
RELEASE_DATE = "2026-09-15"
RELEASE_CODENAME = "Universal Smart HEMS & Auto-Discovery"

def get_version_info():
    return {
        "version": __version__,
        "version_str": APP_VERSION,
        "release_date": RELEASE_DATE,
        "codename": RELEASE_CODENAME,
        "display_badge": f"⚡ AI HEMS OS {APP_VERSION}"
    }
