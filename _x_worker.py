"""
Playwrightワーカースクリプト（別プロセスで実行される）
専用の永続プロファイルを使い、headedモードでXニューストレンドを取得

login: headedブラウザを開いてXに手動ログイン → プロファイルに保存
fetch: 保存済みプロファイルでニューストレンドを取得（headed最小化）
"""

import io
import json
import re
import sys
from pathlib import Path

# Windows cp932 でエンコードできない文字の対策: stdout/stderr を UTF-8 に強制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BROWSER_DATA_DIR = str(Path(__file__).parent / ".x_browser_data")

# navigator.webdriver を隠すJSスニペット
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['ja-JP', 'ja', 'en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
"""

# Playwrightが自動追加するフラグのうち、ボット検出に使われるものを除外
STEALTH_IGNORE_ARGS = [
    "--enable-automation",
]

# ボット検出回避用の起動引数
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-component-update",
]


def _launch_context(pw, extra_args=None):
    """ボット検出を回避したブラウザコンテキストを起動"""
    args = STEALTH_ARGS.copy()
    if extra_args:
        args.extend(extra_args)

    context = pw.chromium.launch_persistent_context(
        BROWSER_DATA_DIR,
        headless=False,
        channel="chrome",
        locale="ja-JP",
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        ignore_default_args=STEALTH_IGNORE_ARGS,
        args=args,
    )

    # 全ページでステルスJSを注入
    context.add_init_script(STEALTH_JS)

    return context


def do_login():
    """headedブラウザを開いてユーザーにXへの手動ログインを促す"""
    from playwright.sync_api import sync_playwright

    data_dir = Path(BROWSER_DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = _launch_context(p)
        page = context.pages[0] if context.pages else context.new_page()

        # Xのログインページに移動
        page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=30000)

        print("ブラウザが開きました。Xにログインしてください。", file=sys.stderr)
        print("ログイン完了後、ホームタイムラインが表示されたらブラウザを閉じてください。", file=sys.stderr)

        # ユーザーがブラウザを閉じるまで待機（最大5分）
        try:
            page.wait_for_url("**/home**", timeout=300000)
            print("ログイン検出！セッションを保存しています...", file=sys.stderr)
            page.wait_for_timeout(3000)
        except Exception:
            pass

        context.close()

    print("セッション保存完了", file=sys.stderr)
    sys.exit(0)


def do_fetch():
    """保存済みプロファイルでXニューストレンドを取得"""
    from playwright.sync_api import sync_playwright

    data_dir = Path(BROWSER_DATA_DIR)
    if not data_dir.exists():
        print("プロファイルなし: 先にloginを実行してください", file=sys.stderr)
        sys.exit(1)

    with sync_playwright() as p:
        context = _launch_context(p, extra_args=["--window-position=-2000,-2000"])
        page = context.pages[0] if context.pages else context.new_page()

        # ニュースタブに移動
        try:
            page.goto(
                "https://x.com/explore/tabs/news",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as e:
            print(f"ページ遷移エラー: {e}", file=sys.stderr)
            context.close()
            sys.exit(1)

        # コンテンツ読み込み待ち
        page.wait_for_timeout(5000)

        # ログインウォールチェック
        url = page.url
        if "/login" in url or "/i/flow/login" in url:
            print("ログインウォール検出: 再ログインが必要です", file=sys.stderr)
            context.close()
            sys.exit(2)

        html = page.content()
        if "アカウントを作成" in html and "ログイン" in html and len(html) < 100000:
            print("ログインウォール検出(HTML): 再ログインが必要です", file=sys.stderr)
            context.close()
            sys.exit(2)

        # トレンド項目を抽出
        trends = []
        items = page.query_selector_all('[data-testid="cellInnerDiv"]')

        for item in items:
            try:
                text = item.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                title = ""
                post_count = ""
                category = ""
                time_ago = ""

                for line in lines:
                    count_match = re.search(r"([\d,]+)\s*件のポスト", line)
                    if count_match:
                        post_count = count_match.group(1).replace(",", "")
                        continue
                    if re.match(r"^\d+[時分秒日]", line) or "速報" in line:
                        time_ago = line
                        continue
                    cats = [
                        "ニュース",
                        "トレンド",
                        "スポーツ",
                        "エンターテイメント",
                        "ビジネス",
                        "金融",
                        "テクノロジー",
                        "政治",
                        "その他",
                    ]
                    if any(cat in line for cat in cats) and len(line) < 30:
                        category = line
                        continue
                    if line in ("もっと見る", "さらに表示", "Show more"):
                        continue
                    if len(line) > len(title) and len(line) > 3:
                        title = line

                if title and len(title) > 3:
                    item_data = {
                        "title": title,
                        "post_count": int(post_count) if post_count else 0,
                        "category": category,
                        "time_ago": time_ago,
                        "source": "X ニューストレンド",
                        "origin": "x_news",
                    }
                    if not any(t["title"] == title for t in trends):
                        trends.append(item_data)
            except Exception:
                continue

        context.close()

        if not trends:
            print("トレンド項目が0件でした", file=sys.stderr)
            sys.exit(1)

        trends.sort(key=lambda x: x["post_count"], reverse=True)
        print(json.dumps(trends, ensure_ascii=False))
        sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python _x_worker.py [login|fetch]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "login":
        do_login()
    elif cmd == "fetch":
        do_fetch()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
