"""
Windows PC用: Xニューストレンドを取得してJSONキャッシュに保存 → GitHubに同期

使い方:
  1. Windows PCでXにログイン済みの状態で実行
  2. python sync_x_trends.py
  3. x_trends_cache.json が生成/更新される
  4. --push オプションで自動的にGitHub にコミット＆プッシュ

定期実行: sync_x_trends.bat をタスクスケジューラに登録すると自動化できます
"""

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta

# 日本時間 (JST = UTC+9)
JST = timezone(timedelta(hours=9))
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CACHE_FILE = SCRIPT_DIR / "x_trends_cache.json"
WORKER_SCRIPT = SCRIPT_DIR / "_x_worker.py"


def fetch_trends():
    """_x_worker.py を呼び出してXトレンドを取得"""
    try:
        result = subprocess.run(
            [sys.executable, str(WORKER_SCRIPT), "fetch"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
        elif result.returncode == 2:
            print("❌ Xのセッションが切れています。先にログインしてください:")
            print("   python _x_worker.py login")
            return None
        else:
            print(f"❌ トレンド取得失敗 (exit code: {result.returncode})")
            if result.stderr:
                print(f"   {result.stderr.strip()}")
            return None
    except subprocess.TimeoutExpired:
        print("❌ タイムアウト: トレンド取得に時間がかかりすぎました")
        return None
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


def save_cache(trends):
    """トレンドをJSONキャッシュファイルに保存"""
    cache_data = {
        "updated_at": datetime.now(JST).isoformat(),
        "count": len(trends),
        "trends": trends,
    }
    CACHE_FILE.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {len(trends)}件のトレンドを保存しました → {CACHE_FILE.name}")
    print(f"   更新日時: {cache_data['updated_at']}")


def git_push():
    """キャッシュファイルをGitHub API経由でx-post-toolリポジトリに直接プッシュ"""
    import os
    import base64
    import urllib.request

    REPO = "Kota-kun777/x-post-tool"
    FILE_PATH = "x_trends_cache.json"
    API_URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

    # GitHubトークンを取得（gh CLI の認証を利用）
    try:
        token_result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=10,
        )
        token = token_result.stdout.strip()
        if not token:
            print("❌ GitHubトークンが取得できません。gh auth login を実行してください")
            return
    except Exception as e:
        print(f"❌ gh CLIエラー: {e}")
        return

    try:
        # 1. 既存ファイルのSHAを取得（更新に必要）
        req = urllib.request.Request(API_URL, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "x-post-tool-sync",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            existing = json.loads(resp.read().decode("utf-8"))
            sha = existing["sha"]

        # 2. ファイル内容をBase64エンコード
        content = CACHE_FILE.read_text(encoding="utf-8")
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")

        # 3. GitHub API でファイルを更新
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
        payload = json.dumps({
            "message": f"sync: X trends update {now}",
            "content": content_b64,
            "sha": sha,
        }).encode("utf-8")

        req = urllib.request.Request(API_URL, data=payload, method="PUT", headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "x-post-tool-sync",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                print("✅ x-post-tool リポジトリにプッシュしました")
            else:
                print(f"⚠️ レスポンス: {resp.status}")

    except urllib.error.HTTPError as e:
        print(f"❌ GitHub APIエラー: {e.code} {e.reason}")
        if e.code == 422:
            print("   （内容が前回と同じ可能性があります）")
    except Exception as e:
        print(f"❌ プッシュ失敗: {e}")

    # AI_Workspace リポジトリにもプッシュ（ローカルgit）
    try:
        os.chdir(SCRIPT_DIR)
        subprocess.run(["git", "add", CACHE_FILE.name], capture_output=True, text=True)
        diff = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True)
        if diff.stdout.strip():
            now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
            subprocess.run(
                ["git", "commit", "-m", f"sync: X trends update {now}"],
                capture_output=True, text=True,
            )
            subprocess.run(["git", "push"], capture_output=True, text=True)
            print("✅ AI_Workspace リポジトリにもプッシュしました")
    except Exception:
        pass  # AI_Workspace側は失敗しても問題ない


def main():
    print("=" * 50)
    print("🐦 X ニューストレンド同期ツール")
    print("=" * 50)

    trends = fetch_trends()
    if not trends:
        print("\n⚠️ トレンドを取得できませんでした")
        sys.exit(1)

    save_cache(trends)

    # --push オプションでGitHubにプッシュ
    if "--push" in sys.argv:
        print("\n📤 GitHubにプッシュ中...")
        git_push()

    print("\n✨ 完了！")


if __name__ == "__main__":
    main()
