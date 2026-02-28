"""
Windows PC用: Streamlit Cloudからのトリガーを監視して自動同期

使い方:
  1. python watch_trigger.py         ← 常駐監視（2分おきにチェック）
  2. python watch_trigger.py --once   ← 1回だけチェックして終了

仕組み:
  - GitHub上の _trigger_sync.json を定期チェック
  - status が "pending" なら sync_x_trends.py を実行
  - 完了後 status を "completed" に更新してプッシュ
"""

import json
import subprocess
import sys
import time
import os
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
TRIGGER_FILE = SCRIPT_DIR / "_trigger_sync.json"
SYNC_SCRIPT = SCRIPT_DIR / "sync_x_trends.py"
CHECK_INTERVAL = 120  # 2分


def git_pull():
    """最新のトリガーファイルを取得"""
    try:
        os.chdir(str(SCRIPT_DIR))
        result = subprocess.run(
            ["git", "pull", "--quiet"],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  git pull エラー: {e}")
        return False


def check_trigger():
    """トリガーファイルを確認"""
    if not TRIGGER_FILE.exists():
        return None
    try:
        return json.loads(TRIGGER_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_sync():
    """sync_x_trends.py --push を実行"""
    print("  📡 Xトレンド取得 & GitHubプッシュ中...")
    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--push"],
        timeout=120,
    )
    return result.returncode == 0


def update_trigger_completed():
    """トリガーを completed に更新してプッシュ"""
    trigger = {
        "status": "completed",
        "completed_at": datetime.now().isoformat(),
    }
    TRIGGER_FILE.write_text(
        json.dumps(trigger, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    os.chdir(str(SCRIPT_DIR))
    try:
        subprocess.run(
            ["git", "add", TRIGGER_FILE.name],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "trigger: sync completed"],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push"],
            check=True, capture_output=True, text=True,
        )
        print("  ✅ ステータス更新をプッシュしました")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ ステータス更新のプッシュに失敗: {e}")


def check_and_sync():
    """1回のチェック & 同期サイクル"""
    # 最新を取得
    git_pull()

    # トリガー確認
    trigger = check_trigger()
    if not trigger or trigger.get("status") != "pending":
        return False

    requested = trigger.get("requested_at", "不明")
    print(f"\n{'='*50}")
    print(f"🔔 同期リクエスト検出！")
    print(f"   リクエスト時刻: {requested}")
    print(f"{'='*50}")

    # 同期実行
    ok = run_sync()

    if ok:
        # ステータス更新
        update_trigger_completed()
        print(f"\n✅ 同期完了！Streamlit Cloudに反映されます")
    else:
        print(f"\n❌ 同期に失敗しました")

    return ok


def main():
    once = "--once" in sys.argv

    print("=" * 50)
    print("👀 Xトレンド同期 トリガー監視")
    print("=" * 50)

    if once:
        print("モード: 1回チェック")
        print()
        check_and_sync()
        return

    print(f"モード: 常駐監視（{CHECK_INTERVAL}秒おき）")
    print("停止: Ctrl+C")
    print()

    while True:
        try:
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] チェック中...", end="", flush=True)

            if check_and_sync():
                print()  # 同期実行時は改行済み
            else:
                print(" 待機中")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n停止しました")
            break
        except Exception as e:
            print(f"\n  エラー: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
