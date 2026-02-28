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
from datetime import datetime
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
        "updated_at": datetime.now().isoformat(),
        "count": len(trends),
        "trends": trends,
    }
    CACHE_FILE.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {len(trends)}件のトレンドを保存しました → {CACHE_FILE.name}")
    print(f"   更新日時: {cache_data['updated_at']}")


def git_push():
    """キャッシュファイルをGitHubにプッシュ"""
    import os
    os.chdir(SCRIPT_DIR)  # リポジトリルートに移動

    try:
        # ステージング
        subprocess.run(
            ["git", "add", CACHE_FILE.name],
            check=True, capture_output=True, text=True,
        )

        # 変更があるか確認
        diff = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True,
        )
        if not diff.stdout.strip():
            print("ℹ️ 変更なし（前回と同じトレンド）。プッシュをスキップします")
            return

        # コミット
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"sync: X trends update {now}"],
            check=True, capture_output=True, text=True,
        )

        # プッシュ
        subprocess.run(
            ["git", "push"],
            check=True, capture_output=True, text=True,
        )
        print("✅ GitHubにプッシュしました")

    except subprocess.CalledProcessError as e:
        print(f"❌ Git操作に失敗しました: {e}")
        if e.stderr:
            print(f"   {e.stderr.strip()}")


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
