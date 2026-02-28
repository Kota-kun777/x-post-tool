"""
X (Twitter) ニューストレンド スクレイパー
Playwrightを別プロセスで実行してStreamlitとの互換性を確保

初回: ブラウザが開くのでXにログインしてください（セッションが保存されます）
2回目以降: 保存されたセッションでheadedモード取得（ウィンドウは画面外に配置）

注意: クラウド環境（MacBook/スマホのブラウザ版）ではPlaywright/ブラウザが使えないため、
      Xトレンド取得機能は無効化され、Google News/Yahoo!のみで動作します。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BROWSER_DATA_DIR = Path(__file__).parent / ".x_browser_data"
_WORKER_SCRIPT = Path(__file__).parent / "_x_worker.py"


def _is_cloud_environment():
    """クラウド環境（ブラウザ版Claude Code等）かどうかを判定"""
    # クラウド環境の特徴: DISPLAYが無い、またはheadlessサーバー
    if os.environ.get("CLOUD_ENVIRONMENT") == "1":
        return True
    # Linuxでディスプレイがない場合はクラウド環境と判定
    if sys.platform == "linux" and not os.environ.get("DISPLAY"):
        return True
    return False


def is_logged_in():
    """セッションが保存済みか確認"""
    if _is_cloud_environment():
        return False
    return BROWSER_DATA_DIR.exists() and any(BROWSER_DATA_DIR.iterdir())


def login_to_x():
    """別プロセスでブラウザを開いてXにログイン（headedモード）"""
    if _is_cloud_environment():
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(_WORKER_SCRIPT), "login"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=360,
        )
        return result.returncode == 0
    except Exception:
        return False


def clear_session():
    """保存済みセッションを削除"""
    import shutil

    if BROWSER_DATA_DIR.exists():
        shutil.rmtree(BROWSER_DATA_DIR, ignore_errors=True)


def fetch_x_news_trends():
    """別プロセスでXのニューストレンドを取得

    Returns:
        list: トレンドリスト（成功時）
        None: 取得失敗時
        "login_required": セッション切れの場合
    """
    if _is_cloud_environment():
        return None
    if not is_logged_in():
        return "login_required"
    try:
        result = subprocess.run(
            [sys.executable, str(_WORKER_SCRIPT), "fetch"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
        elif result.returncode == 2:
            # ログインウォール検出 → セッション切れ
            return "login_required"
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    return None
