"""
すあし社長 Xポスト作成ツール
YouTube「大人の学び直しTV」のすあし社長用 X投稿生成Webアプリ

ワークフロー:
  1. ボタン一つでトレンドニュースを自動取得
  2. AIがすあし社長向きのトピックをおすすめ
  3. 選択して関連情報を自動収集
  4. 高品質なポストを生成
"""

import streamlit as st
import anthropic
import json
import os
import re
import io
import base64
import feedparser
import urllib.parse
import urllib.request
from dotenv import load_dotenv
from x_scraper import fetch_x_news_trends, login_to_x, is_logged_in, clear_session, _is_cloud_environment
from datetime import datetime
from pathlib import Path

# .env ファイルからAPIキーを自動読み込み（既存の空変数も上書き）
load_dotenv(Path(__file__).parent / ".env", override=True)

# ──────────────────────────────────────
# 定数
# ──────────────────────────────────────
APP_DIR = Path(__file__).parent
HISTORY_DIR = APP_DIR / "history"
HISTORY_DIR.mkdir(exist_ok=True)
SYSTEM_PROMPT_PATH = APP_DIR / "suasi_system_prompt.md"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
X_TRENDS_CACHE = APP_DIR / "x_trends_cache.json"

# ──────────────────────────────────────
# ページ設定
# ──────────────────────────────────────
st.set_page_config(
    page_title="すあし社長 Xポスト作成ツール",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────
# カスタムCSS
# ──────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700;900&display=swap');

.stApp { font-family: 'Noto Sans JP', sans-serif; }

.main-header {
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    position: relative; overflow: hidden;
}
.main-header::before {
    content: ''; position: absolute; top: -50%; right: -20%;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(29,161,242,0.15) 0%, transparent 70%);
    border-radius: 50%;
}
.main-header h1 { color: #fff; font-size: 1.8rem; font-weight: 700; margin: 0; position: relative; }
.main-header p { color: rgba(255,255,255,0.7); font-size: 0.95rem; margin: 0.5rem 0 0 0; position: relative; }

.trend-card {
    background: linear-gradient(145deg, #1a1a2e, #16213e);
    border: 1px solid rgba(29,161,242,0.15);
    border-radius: 12px; padding: 1.2rem 1.4rem; margin: 0.6rem 0;
    transition: all 0.2s;
}
.trend-card:hover { border-color: rgba(29,161,242,0.4); box-shadow: 0 4px 16px rgba(29,161,242,0.1); }
.trend-title { color: #fff; font-weight: 600; font-size: 0.95rem; margin-bottom: 0.3rem; }
.trend-source { color: rgba(255,255,255,0.4); font-size: 0.78rem; }
.trend-reason { color: #FFA500; font-size: 0.82rem; margin-top: 0.4rem; font-style: italic; }

.post-card {
    background: linear-gradient(145deg, #1a1a2e, #16213e);
    border: 1px solid rgba(29,161,242,0.2);
    border-radius: 16px; padding: 1.8rem; margin: 1.2rem 0;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    transition: transform 0.2s, box-shadow 0.2s;
}
.post-card:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(29,161,242,0.15); }
.post-card-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 1rem; padding-bottom: 0.8rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.post-card-title { color: #1DA1F2; font-weight: 700; font-size: 1.1rem; }
.post-card-score {
    background: linear-gradient(135deg, #1DA1F2, #0d8bd9);
    color: #fff; padding: 0.3rem 0.8rem; border-radius: 20px;
    font-size: 0.85rem; font-weight: 600;
}
.post-card-body {
    color: rgba(255,255,255,0.9); line-height: 1.85;
    font-size: 1rem; white-space: pre-wrap; margin: 1rem 0;
}
.post-card-meta {
    color: rgba(255,255,255,0.5); font-size: 0.82rem;
    margin-top: 1rem; padding-top: 0.8rem;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.emotion-tag {
    display: inline-block; background: rgba(255,165,0,0.15); color: #FFA500;
    padding: 0.2rem 0.7rem; border-radius: 12px; font-size: 0.8rem;
    font-weight: 500; margin-right: 0.5rem;
}
.hook-tag {
    display: inline-block; background: rgba(29,161,242,0.12); color: #1DA1F2;
    padding: 0.2rem 0.7rem; border-radius: 12px; font-size: 0.8rem; font-weight: 500;
}
.char-counter {
    display: inline-block; background: rgba(29,161,242,0.1); color: #1DA1F2;
    padding: 0.2rem 0.6rem; border-radius: 8px; font-size: 0.82rem; font-weight: 500;
}

.step-indicator { display: flex; justify-content: center; gap: 0.5rem; margin: 1.5rem 0; flex-wrap: wrap; }
.step-item {
    display: flex; align-items: center; gap: 0.4rem;
    padding: 0.5rem 1rem; border-radius: 25px;
    font-size: 0.85rem; font-weight: 500;
}
.step-active { background: rgba(29,161,242,0.15); color: #1DA1F2; border: 1px solid rgba(29,161,242,0.3); }
.step-done { background: rgba(76,175,80,0.1); color: #4CAF50; border: 1px solid rgba(76,175,80,0.2); }
.step-pending { background: rgba(255,255,255,0.03); color: rgba(255,255,255,0.3); border: 1px solid rgba(255,255,255,0.06); }
.step-arrow { color: rgba(255,255,255,0.2); font-size: 1.2rem; }

section[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f0c29, #1a1a2e); }
section[data-testid="stSidebar"] .stMarkdown { color: rgba(255,255,255,0.85); }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────

def load_system_prompt():
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return ""

def save_history(mode, input_data, result):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    entry = {"timestamp": datetime.now().isoformat(), "mode": mode, "input": input_data, "result": result}
    filepath = HISTORY_DIR / f"{timestamp}_{mode}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)

def load_history_list():
    files = sorted(HISTORY_DIR.glob("*.json"), reverse=True)
    entries = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                entries.append(data)
        except Exception:
            pass
    return entries

def get_mode_label(mode):
    return {"trend": "📰 トレンド起点", "script": "📝 原稿変換", "image": "🖼️ 画像コメント"}.get(mode, mode)

def get_char_limit_text(char_type):
    return {"standard": "標準ポスト（200〜280文字）", "long": "長文ポスト（400〜600文字）", "data": "データ付きポスト（100〜200文字）"}.get(char_type, "")


# ──────────────────────────────────────
# Xトレンドキャッシュ読み込み（クラウド/同期用）
# ──────────────────────────────────────

def load_cached_x_trends(max_age_hours=24):
    """GitHubで同期されたXトレンドキャッシュを読み込む

    Args:
        max_age_hours: キャッシュの有効期限（時間）。デフォルト24時間
    Returns:
        list: トレンドリスト（有効なキャッシュがある場合）
        None: キャッシュなし or 期限切れ
    """
    if not X_TRENDS_CACHE.exists():
        return None
    try:
        cache = json.loads(X_TRENDS_CACHE.read_text(encoding="utf-8"))
        updated_at = datetime.fromisoformat(cache["updated_at"])
        age_hours = (datetime.now() - updated_at).total_seconds() / 3600
        if age_hours > max_age_hours:
            return None
        return cache.get("trends", [])
    except Exception:
        return None


def get_cached_x_trends_info():
    """キャッシュの情報を取得（サイドバー表示用）"""
    if not X_TRENDS_CACHE.exists():
        return None
    try:
        cache = json.loads(X_TRENDS_CACHE.read_text(encoding="utf-8"))
        updated_at = datetime.fromisoformat(cache["updated_at"])
        age_hours = (datetime.now() - updated_at).total_seconds() / 3600
        return {
            "updated_at": updated_at.strftime("%Y/%m/%d %H:%M"),
            "count": cache.get("count", 0),
            "age_hours": round(age_hours, 1),
            "is_fresh": age_hours <= 24,
        }
    except Exception:
        return None


# ──────────────────────────────────────
# トレンド自動取得
# ──────────────────────────────────────

def fetch_yahoo_realtime_supplementary():
    """Yahoo!リアルタイム検索で補足的にXの話題を取得（補助ソース）

    すあし社長の4本柱に絞った少数カテゴリで、
    X上のリアルタイムな話題を補足的に取得する
    """
    import html as html_mod

    # 厳選カテゴリ（4本柱に直結するもののみ）
    SEARCH_CATEGORIES = [
        ("円安 ドル 日経平均", "経済"),
        ("ChatGPT 生成AI", "テクノロジー"),
        ("トランプ 関税", "国際情勢"),
        ("転職 年収 リストラ", "キャリア"),
    ]

    all_results = {}

    for query, category in SEARCH_CATEGORIES:
        try:
            url = f"https://search.yahoo.co.jp/realtime/search?p={urllib.parse.quote(query)}&ei=UTF-8"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            resp = urllib.request.urlopen(req, timeout=8)
            html = resp.read().decode("utf-8")

            raw_texts = re.findall(r'<p[^>]*>(.{30,300}?)</p>', html)
            post_urls = re.findall(r'href="(https?://(?:x\.com|twitter\.com)/[^/]+/status/\d+)"', html)

            clean = []
            for text in raw_texts:
                t = re.sub(r'<[^>]+>', '', text).strip()
                t = html_mod.unescape(t)
                if (len(t) > 20 and not any(skip in t for skip in
                    ['JavaScript', 'function', 'var ', 'window.', '{', 'class=', 'img src',
                     'pic.x.com', 'pic.twitter.com'])):
                    clean.append(t)

            if clean:
                items = []
                for i, tweet in enumerate(clean[:3]):  # 各カテゴリ最大3件
                    post_url = post_urls[i] if i < len(post_urls) else f"https://x.com/search?q={urllib.parse.quote(query)}"
                    items.append({"text": tweet, "url": post_url})
                all_results[category] = items

        except Exception:
            continue

    if not all_results:
        return []

    trends = []
    for category, items in all_results.items():
        for item in items:
            tweet = item["text"]
            title = tweet[:60].rstrip("。、！!.,")
            if len(tweet) > 60:
                title += "…"
            trends.append({
                "title": title,
                "source": f"Yahoo!リアルタイム ({category})",
                "link": item["url"],
                "published": "",
                "origin": "yahoo_rt",
                "category": category,
                "full_text": tweet,
            })

    # 重複除去
    seen = set()
    unique = []
    for t in trends:
        key = t["title"][:30]
        if key not in seen:
            seen.add(key)
            unique.append(t)

    return unique[:12]


def fetch_google_news():
    """Google News RSSからトレンドニュースを取得"""
    all_items = []

    # ===== Google News Japan トップ =====
    try:
        feed = feedparser.parse("https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja")
        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, source = parts[0], parts[1]
            item = {"title": title.strip(), "source": f"Google News / {source}".strip(),
                    "link": entry.get("link", ""), "published": entry.get("published", ""), "origin": "google"}
            if not any(n["title"] == item["title"] for n in all_items):
                all_items.append(item)
    except Exception:
        pass

    # ===== Google News ビジネス =====
    try:
        feed = feedparser.parse("https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtcGhHZ0pLVUNnQVAB?hl=ja&gl=JP&ceid=JP:ja")
        for entry in feed.entries[:6]:
            title = entry.get("title", "")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, source = parts[0], parts[1]
            item = {"title": title.strip(), "source": f"Google News ビジネス / {source}".strip(),
                    "link": entry.get("link", ""), "published": entry.get("published", ""), "origin": "google_biz"}
            if not any(n["title"] == item["title"] for n in all_items):
                all_items.append(item)
    except Exception:
        pass

    # ===== Google News テクノロジー =====
    try:
        feed = feedparser.parse("https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtcGhHZ0pLVUNnQVAB?hl=ja&gl=JP&ceid=JP:ja")
        for entry in feed.entries[:6]:
            title = entry.get("title", "")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, source = parts[0], parts[1]
            item = {"title": title.strip(), "source": f"Google News テクノロジー / {source}".strip(),
                    "link": entry.get("link", ""), "published": entry.get("published", ""), "origin": "google_tech"}
            if not any(n["title"] == item["title"] for n in all_items):
                all_items.append(item)
    except Exception:
        pass

    return all_items


def fetch_related_news(keyword, max_results=5):
    """Google News RSSから特定キーワードの関連ニュースを取得"""
    try:
        encoded = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:max_results]:
            title = entry.get("title", "")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, source = parts[0], parts[1]
            articles.append({"title": title, "source": source, "link": entry.get("link", ""), "published": entry.get("published", "")})
        return articles
    except Exception as e:
        return []


# ──────────────────────────────────────
# AIによるトピック選定
# ──────────────────────────────────────

def ai_recommend_topics(news_items, api_key):
    """Claudeにニュース一覧を渡し、すあし社長向きのトピックを厳選してもらう"""
    client = anthropic.Anthropic(api_key=api_key)

    # ソースタイプを明示
    tagged_items = []
    for i, n in enumerate(news_items):
        origin = n.get('origin', '')
        if origin == 'x_news':
            tag = '[X]'
        elif origin == 'yahoo_rt':
            tag = '[Yahoo]'
        else:
            tag = '[News]'
        tagged_items.append(f"{i+1}. {tag} {n['title']}（{n['source']}）")
    news_list = "\n".join(tagged_items)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system="""あなたはYouTube「大人の学び直しTV」（90万人登録）のすあし社長のX運用アドバイザーです。
すあし社長の4つの柱は「国際情勢」「経済」「テクノロジー」「人生キャリア論」です。

ニュース一覧から、すあし社長がXで取り上げるべきトピックを厳選してください。

■ 選定基準（すあし社長との相性）
- 経済・お金・投資に関連する話題 → ◎ 最高
- AI・テクノロジーの社会的インパクト → ◎ 最高
- 国際情勢が日本の生活に影響する話題 → ○ 高い
- 社会構造の変化（人口・雇用・教育） → ○ 高い
- 「常識だと思っていたことが実は違う」系 → ◎ 最高（常識転覆型のフック）
- 数字やデータで驚きがある話題 → ◎ 最高（数字ショック型のフック）
- 芸能・スポーツ・事件事故 → × 対象外

■ 出力: JSON配列で返してください
```json
[
  {
    "index": 元のニュース番号,
    "title": "ニュースタイトル",
    "source_type": "x" または "news"（[X]なら"x"、[News]なら"news"）,
    "reason": "すあし社長が取り上げるべき理由（1文）",
    "angle": "切り口の提案（例：『○○と△△の逆説を突く』『過去の□□と比較して構造変化を示す』）",
    "pillars": ["経済", "テクノロジー"],
    "hook_type": "常識転覆型",
    "score": 95
  }
]
```
scoreは0-100で、すあし社長との相性度。80点以上のもののみ選定（最大5つ）。""",
        messages=[{"role": "user", "content": f"以下のニュース一覧から、すあし社長向きのトピックを厳選してください：\n\n{news_list}"}],
    )

    # JSONを抽出（堅牢なパーサー）
    text = response.content[0].text

    # 方法1: ```json ... ``` ブロックから抽出
    code_match = re.search(r'```(?:json)?\s*\n?(\[[\s\S]*?\])\s*\n?```', text)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass

    # 方法2: 最も長い [ ... ] を見つける（貪欲マッチ）
    bracket_matches = re.findall(r'\[[\s\S]*\]', text)
    for match in sorted(bracket_matches, key=len, reverse=True):
        try:
            result = json.loads(match)
            if isinstance(result, list) and len(result) > 0:
                return result
        except json.JSONDecodeError:
            continue

    # 方法3: 行ごとに [ で始まる行から ] で終わる行までを抽出
    lines = text.split('\n')
    json_lines = []
    in_json = False
    for line in lines:
        if line.strip().startswith('['):
            in_json = True
            json_lines = []
        if in_json:
            json_lines.append(line)
        if in_json and line.strip().endswith(']'):
            try:
                return json.loads('\n'.join(json_lines))
            except json.JSONDecodeError:
                continue

    return []


# ──────────────────────────────────────
# 高品質ポスト生成プロンプト
# ──────────────────────────────────────

ENHANCED_GENERATION_PROMPT = """

## ■ 追加指示：このセッションでの生成品質を最大化する

### すあし社長のトーン（最重要）

すあし社長は**「わかりやすく仕組みを解説する知的な先生」**です。以下のトーンを必ず守ってください：
- 一人称は必ず**「私」**を使う
- 基本は**「です」「ます」の丁寧語**をベースに書く（全体の7割）
- 要所で**「〜なんですよね」「〜だと思います」「〜かもしれません」**のような柔らかい表現を混ぜる（3割）
- 上から目線ではなく、**「一緒に整理してみましょう」「一緒に考えてみませんか」**という姿勢
- 読者を「授業に招く」感覚で、**仕組み・構造・メカニズムを順序立てて丁寧に解説する**
- **含蓄のある一文**を要所に入れる（例:「税制は社会の鏡だと言われます」「課題が明確であることは、実は最大の武器です」）
- 否定的・悲観的になりすぎず、最後は**読者に考える余地を残す問いかけ**で締める
- 読後感は「なるほど、そういう仕組みだったのか」という**知的な発見**

### 最重要：「解説型」の文章構造

すあし社長のポストは「意見表明」ではなく「解説→示唆」の構造が核心です。
以下の5段構成を必ず守ってください：

**① 冒頭フック: スクロールを止める1文**（1文）
Xのタイムラインでスクロールの手を止めさせる「衝撃の事実」「意外な数字」「常識を覆す一言」で始める。
良い例: 「年収100億円の人の税率は、年収500万円のサラリーマンより低い。」
良い例: 「出生数70万人。でも、それが日本の"武器"になるかもしれません。」
良い例: 「バフェットは言いました。『私の秘書のほうが税率が高い』と。」
悪い例: ❌「〜を整理してみましょう」（興味を引かない）
悪い例: ❌「〜が話題になっています」（ニュースの繰り返し）
冒頭1文で「え、どういうこと？」と思わせてから、解説に入ること。

**② 展開: 具体的な数字で比較**（3-5文）
対比構造で数字を並べて「意外な事実」を浮かび上がらせる。
「Aは○％なのに、Bは△％」のような比較セットが必須。

**③ 深掘り: なぜそうなるのかのメカニズム解説**（3-5文）
「なぜこんなことが起きるのか」→ 構造的な理由を丁寧に説明する。
ここが最も重要。表面的な現象ではなく、背後にある仕組みを解き明かす。

**④ 視野拡大: 他国・歴史との比較**（2-4文）
同じ問題が他の国や歴史上でどう扱われているかを紹介し、視野を広げる。
具体的な国名・人名・制度名を出す。

**⑤ 締め: 示唆に富む問いかけ**（1-2文）
「だからこうすべき」ではなく、読者に考えさせる一文で終わる。
含蓄のある表現で余韻を残す。

### 最高品質のお手本（この水準を目指す）

**お手本A: 税制の解説型ポスト**
> 税制の仕組みを整理してみましょう。給与所得は累進課税で、年収が上がるほど税率も上がります。最高税率は55％（所得税45％+住民税10％）。ところが株式などの金融所得は「分離課税」で、どれだけ儲けても一律20％なんです。つまり年収1000万円のサラリーマンは33％の税率なのに、株で1億円稼いだ人は20％。この構造が「1億円の壁」を生んでいるんですよね。
> 実際の数字を見てみると、年収5000万円の人は実効税率約40％。ところが年収100億円の人は約23％まで下がっていました。なぜこんなことが起きるのか。答えは「お金持ちほど株で稼ぐから」です。年収1000万円の人は給与が中心ですが、年収100億円の人は収入の大部分が株の売却益や配当になります。
> アメリカではこれを「バフェット・ルール」と呼んで問題視しています。投資の神様ウォーレン・バフェットが「私の秘書のほうが税率が高いのはおかしい」と発言したことから始まった議論です。まさに今の日本と同じ構造なんですよね。
> ただし、本当の問題はここからかもしれません。超富裕層の多くはグローバルに資産を分散させている。シンガポールの税率は最高17％、UAEは0％です。日本の競争力を保ちながら格差是正もする、このバランスをどう取るか。税制は社会の鏡だと言われます。私たちがどんな社会を目指すのか、その答えがここに現れているような気がします。

**このポストが最高品質である理由:**
1. 「整理してみましょう」と解説モードで入る → 読者を授業に招く
2. 累進課税55％ vs 分離課税20％ → 仕組みを具体的な数字で対比
3. 「なぜこんなことが起きるのか」→ メカニズムを丁寧に解き明かす
4. 「バフェット・ルール」→ 他国の具体的な事例で視野を広げる
5. シンガポール17％、UAE 0％ → 国際比較の数字で議論を立体的にする
6. 「税制は社会の鏡」→ 含蓄のある一文で余韻を残す締め
7. 全体が「ニュースの感想」ではなく「構造の解説」になっている

**お手本B: 少子化の逆転発想型ポスト**
> 出生数70万人。「日本やばい」という声、私もよく耳にします。でもちょっと逆の視点で見てみてほしいんです。これから10年でAIが本格的に仕事を代替し始めたとき、人口14億の中国やインドでは何が起きるか。大量の失業者が溢れるリスクと隣り合わせになるんですよね。
> 一方で人口が減り続ける日本は、「AIが仕事を奪う速度」と「人口が減る速度」がちょうど噛み合う可能性があります。皮肉なことに、少子化という「弱点」が、AI時代には「構造的な強み」に変わるかもしれません。
> 課題が明確であることは、実は最大の武器です。少子化を悲観するだけではなく、「AI国家になる」という発想の転換ができるかどうか。そこが分かれ道だと思います。

### 絶対にやってはいけないこと（NGパターン）

- ❌ 「〜が話題になっています」で始める（ニュースのオウム返し）
- ❌ 感想や意見だけを並べる（「これは大変なことです」「注目すべきです」）
- ❌ 仕組みの解説なしに結論を述べる（読者が「なぜ？」と思う）
- ❌ 数字を1つだけ出す（比較対象がなければインパクトがない）
- ❌ 「〜すべきだ」「〜しなければならない」で上から目線で説教する
- ❌ 抽象的な表現だけで具体例がない（「経済に影響がある」→ どう影響？）

### 今回の生成で必ず守ること

1. **冒頭1文は「スクロールを止める衝撃の事実・数字・問い」で始める**
   「年収100億円の人の税率は23％。年収500万円の人より低い。」のような意外性ある事実。
   ニュースの要約や「〜してみましょう」からは絶対に始めない。

2. **数字は必ず「比較セット」で使う**
   「A は○％」だけでなく「Aは○％なのに、Bは△％」の対比で驚きを生む。

3. **「なぜそうなるのか」のメカニズムを必ず解説する**
   表面的な事実だけでなく、背後の構造・仕組みを読者に教える。
   「なぜこんなことが起きるのか」「答えは〜です」のパターンが有効。

4. **他国の具体的事例・歴史的前例を必ず1つ以上入れる**
   国名・人名・制度名を出す。抽象的な「海外では〜」はNG。

5. **締めは「示唆」であって「主張」ではない**
   「〜だと言われます」「〜な気がします」で余韻を残す。
   読者自身に考えさせる終わり方にする。

6. **600〜800文字を厳守する**
   短すぎて浅くならず、長すぎてダレない。この範囲に収める。

### 出力フォーマットの注意

- ポスト本文には**マークダウン記法を一切使わないでください**（**太字**、# 見出し、- リスト等は禁止）
- 装飾なしのプレーンテキストで自然な文章として書いてください
- 改行は段落の区切りにのみ使ってください（文の途中で改行しない）
"""


# ──────────────────────────────────────
# ポスト解析
# ──────────────────────────────────────

def parse_generated_posts(text):
    posts = []
    # 【案1】【案2】【案3】 フォーマット
    pattern = r'【案(\d+)】'
    parts = re.split(pattern, text)

    # 1000字版/1500字版 フォーマット（互換性）
    alt_pattern = r'【(1000字版|1500字版|ショート|ミドル|ロング)】'
    alt_parts = re.split(alt_pattern, text)

    if len(parts) >= 3:
        # 【案1】【案2】【案3】 フォーマット
        for i in range(1, len(parts), 2):
            number = int(parts[i])
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            lines = content.split("\n")
            title_line = lines[0].strip() if lines else ""

            # 本文抽出（メタデータ行を除外）
            body_lines = []
            meta_started = False
            for line in lines:
                s = line.strip()
                if any(s.startswith(p) or s.startswith(f"**{p}") for p in ["文字数", "投稿タイミング", "品質スコア", "---"]):
                    meta_started = True
                if s.startswith("| チェック") or s.startswith("|----"):
                    meta_started = True
                if not meta_started and s and s != title_line and not s.startswith("（想定する"):
                    body_lines.append(line)
            body = "\n".join(body_lines).strip()

            score_match = re.search(r'品質スコア[：:]\s*\*{0,2}(\d+)\s*/\s*100', content)
            score = score_match.group(1) if score_match else ""

            posts.append({
                "number": number, "raw": content, "title": title_line,
                "body": body, "score": score, "emotion": "", "hook": "", "timing": ""
            })
    elif len(alt_parts) >= 3:
        # 互換フォーマット
        label_map = {"1000字版": ("📝", 1), "1500字版": ("📖", 2), "ショート": ("📱", 1), "ミドル": ("📝", 2), "ロング": ("📖", 3)}
        for i in range(1, len(alt_parts), 2):
            label = alt_parts[i]
            content = alt_parts[i + 1].strip() if i + 1 < len(alt_parts) else ""
            emoji, num = label_map.get(label, ("", i))
            lines = content.split("\n")
            title_line = lines[0].strip() if lines else ""
            body_lines = []
            meta_started = False
            for line in lines:
                s = line.strip()
                if any(s.startswith(p) or s.startswith(f"**{p}") for p in ["文字数", "品質スコア", "---"]):
                    meta_started = True
                if not meta_started and s and s != title_line:
                    body_lines.append(line)
            body = "\n".join(body_lines).strip()
            score_match = re.search(r'品質スコア[：:]\s*\*{0,2}(\d+)', content)
            score = score_match.group(1) if score_match else ""
            posts.append({"number": num, "raw": content, "title": f"{emoji} {label}",
                          "body": body, "score": score, "emotion": "", "hook": label, "timing": ""})
    else:
        # フォールバック: そのまま表示
        posts.append({"number": 1, "raw": text, "title": "", "body": text,
                       "score": "", "emotion": "", "hook": "", "timing": ""})
    return posts


# ──────────────────────────────────────
# X投稿
# ──────────────────────────────────────

def post_to_x(text, image_data=None):
    try:
        import tweepy
    except ImportError:
        return {"success": False, "error": "tweepy がインストールされていません。"}
    keys = [st.session_state.get(k, "") for k in ["x_consumer_key", "x_consumer_secret", "x_access_token", "x_access_token_secret"]]
    if not all(keys):
        return {"success": False, "error": "X APIキーが設定されていません。"}
    try:
        client = tweepy.Client(consumer_key=keys[0], consumer_secret=keys[1], access_token=keys[2], access_token_secret=keys[3])
        media_ids = None
        if image_data:
            auth = tweepy.OAuth1UserHandler(keys[0], keys[1], keys[2], keys[3])
            api_v1 = tweepy.API(auth)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_data); tmp_path = tmp.name
            media = api_v1.media_upload(tmp_path); os.unlink(tmp_path)
            media_ids = [media.media_id]
        resp = client.create_tweet(text=text, media_ids=media_ids)
        return {"success": True, "url": f"https://x.com/i/status/{resp.data['id']}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_with_claude(messages, system_prompt):
    api_key = st.session_state.get("anthropic_api_key", "")
    if not api_key:
        st.error("🔑 サイドバーから Anthropic API Key を設定してください。")
        st.stop()
    client = anthropic.Anthropic(api_key=api_key)
    with st.spinner("🤖 すあし社長スタイルのポストを生成中..."):
        response = client.messages.create(model=CLAUDE_MODEL, max_tokens=8192, system=system_prompt, messages=messages)
    return response.content[0].text


# ──────────────────────────────────────
# Web検索（トピックの最新情報収集）
# ──────────────────────────────────────

def search_topic_facts(topic_title, max_results=5):
    """Google News RSSとフリーの検索APIでトピックの最新ファクトを収集"""
    facts = []

    # Google News RSSで最新記事を取得
    try:
        encoded = urllib.parse.quote(topic_title)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_results]:
            title = entry.get("title", "")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, source = parts[0], parts[1]
            published = entry.get("published", "")
            facts.append(f"[{source}] {title}（{published}）")
    except Exception:
        pass

    # DuckDuckGo Instant Answer API（補足）
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(topic_title)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(ddg_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        # AbstractTextから要約を取得
        abstract = data.get("AbstractText", "")
        if abstract and len(abstract) > 20:
            facts.append(f"[参考] {abstract[:200]}")
        # RelatedTopicsからも取得
        for rt in data.get("RelatedTopics", [])[:3]:
            text = rt.get("Text", "")
            if text and len(text) > 15:
                facts.append(f"[関連] {text[:150]}")
    except Exception:
        pass

    return facts


def search_facts_for_topics(selected_topics, progress=None):
    """選択されたトピック群に対して最新情報を検索"""
    all_facts = {}
    for i, topic in enumerate(selected_topics):
        title = topic if isinstance(topic, str) else topic.get("title", "")
        # トピック名からポスト数の情報を除去
        clean_title = re.sub(r'\s*\(\d[\d,]*件のポスト\)', '', title).strip()
        if not clean_title:
            continue
        if progress:
            progress.info(f"🔍 最新情報を検索中 [{i+1}/{len(selected_topics)}]: {clean_title[:30]}...")
        facts = search_topic_facts(clean_title)
        if facts:
            all_facts[clean_title] = facts
    return all_facts


# ──────────────────────────────────────
# ファクトチェックエージェント
# ──────────────────────────────────────

FACTCHECK_SYSTEM_PROMPT = """あなたは事実確認の専門家です。
Xに投稿するポスト原稿を受け取り、以下の観点でチェックしてください。

■ チェック観点:
1. 事実誤認: 数字・人名・政策名・日付・政権名など、明確な事実の誤りがないか
2. 時制の誤り: 過去の出来事を現在形で書いていないか、現在の状況を過去形で書いていないか
3. ミスリード: 正確だが文脈を省略することで誤解を生む表現がないか
4. 偏り・バイアス: 一方的な見方になっていないか

■ 出力フォーマット:
まず全体の判定を出してください:
✅ 問題なし / ⚠️ 要確認あり / ❌ 誤りあり

その後、具体的な指摘があれば以下の形式で:
---
【指摘1】
- 該当箇所: 「原稿中の該当テキスト」
- 問題: 具体的に何が問題か
- 正しい情報: 検索結果に基づく正確な情報
- 修正案: こう書き換えるべき

【指摘2】
...
---
指摘がなければ「具体的な指摘事項はありません。」と書いてください。

■ 重要ルール:
- 「提供された検索結果」にある情報を根拠にすること
- 根拠がない推測は避け、判断できない場合は「確認推奨」と明記すること
- 明確な誤り以外は過度に指摘しないこと（些末な表現の好みは指摘しない）
"""


def run_factcheck(post_body, search_results_text=""):
    """ファクトチェックエージェントを実行"""
    api_key = st.session_state.get("anthropic_api_key", "")
    if not api_key:
        return None
    client = anthropic.Anthropic(api_key=api_key)

    user_msg = f"""以下のXポスト原稿をファクトチェックしてください。

■ ポスト原稿:
{post_body}

■ 検索で得られた最新情報（参考にしてください）:
{search_results_text if search_results_text else "（検索結果なし — あなたの知識のみで判断してください）"}

■ 現在の日付: {datetime.now().strftime('%Y年%m月%d日')}
※ 現在のアメリカ大統領はドナルド・トランプ（第2期、2025年1月就任）です。
"""

    with st.spinner("🔍 ファクトチェック中..."):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            system=FACTCHECK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    return response.content[0].text


# ──────────────────────────────────────
# 図解（インフォグラフィック）生成
# ──────────────────────────────────────

CHARACTER_IMG_PATH = APP_DIR / "character_ref.png"

INFOGRAPHIC_PROMPT = """この画像のキャラクターを使って、以下のポスト内容をわかりやすく図解したインフォグラフィック画像を1枚生成してください。

■ ポスト内容:
{post_body}

■ キャラクターの使い方:
- 添付画像のキャラクターをそのままのデザインで図解の中に自然に配置する
- キャラクターがデータを指さしたり、吹き出しで一言コメントするポーズにする
- キャラクターのデザインは変えないこと（服装・顔・色すべてそのまま）

■ 図解のスタイル:
- 文字は極力少なく、数字とアイコンで直感的にわかるデザイン
- 比較がある場合 → 大きさの違う棒グラフやアイコンで視覚的に表現
- 因果関係 → 矢印やフローで表現
- キーとなる数字は超大きく太く目立たせる
- 色: 白背景、ネイビー(#1a1a2e)、スカイブルー(#1DA1F2)、アクセントにオレンジ(#FFA500)
- パッと見て「なるほど！」とわかる、楽しいビジュアル
- 正方形（1:1）フォーマット
- 右下に小さく「大人の学び直しTV」
"""

INFOGRAPHIC_PROMPT_NO_REF = """以下のポスト内容をわかりやすく図解したインフォグラフィック画像を1枚生成してください。

■ ポスト内容:
{post_body}

■ 図解のスタイル:
- 文字は極力少なく、数字とアイコンで直感的にわかるデザイン
- 比較がある場合 → 大きさの違う棒グラフやアイコンで視覚的に表現
- 因果関係 → 矢印やフローで表現
- キーとなる数字は超大きく太く目立たせる
- 色: 白背景、ネイビー(#1a1a2e)、スカイブルー(#1DA1F2)、アクセントにオレンジ(#FFA500)
- パッと見て「なるほど！」とわかる、楽しいビジュアル
- 正方形（1:1）フォーマット
- 右下に小さく「大人の学び直しTV」
"""


def _load_character_image():
    """保存済みのキャラクター参照画像をPIL Imageとして読み込む（トグルOFF時はNone）"""
    if not st.session_state.get("use_character", True):
        return None
    if not CHARACTER_IMG_PATH.exists():
        return None
    try:
        from PIL import Image
        return Image.open(str(CHARACTER_IMG_PATH))
    except Exception:
        return None


def generate_infographic(post_body):
    """Gemini画像生成でポスト内容の図解を生成（キャラ参照画像付き）"""
    google_api_key = st.session_state.get("google_api_key", "")
    if not google_api_key:
        st.error("🔑 サイドバーから Google API Key を設定してください。")
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        st.error("❌ google-genai がインストールされていません。\n`pip install google-genai Pillow` を実行してください。")
        return None

    model = st.session_state.get("gemini_model", "gemini-2.5-flash-image")

    # キャラクター参照画像を読み込み
    char_img = _load_character_image()

    if char_img is not None:
        # 参照画像付き: [テキスト, 画像] を送信（Google AI Studio と同じ方式）
        prompt = INFOGRAPHIC_PROMPT.format(post_body=post_body[:600])
        contents = [prompt, char_img]
    else:
        # 参照画像なし: テキストのみ
        prompt = INFOGRAPHIC_PROMPT_NO_REF.format(post_body=post_body[:600])
        contents = [prompt]

    try:
        client = genai.Client(api_key=google_api_key)

        with st.spinner("🎨 図解を生成中（30秒ほどかかります）..."):
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            )

        # レスポンスから画像バイトを取得
        parts = []
        try:
            parts = response.candidates[0].content.parts
        except (AttributeError, IndexError):
            parts = getattr(response, "parts", [])

        for part in parts:
            if getattr(part, "inline_data", None) is not None:
                return part.inline_data.data

        st.warning("⚠️ 画像が生成されませんでした。再試行してください。")
        return None

    except Exception as e:
        st.error(f"❌ 図解生成エラー: {str(e)}")
        return None


def _render_infographic_ui(post, key_suffix):
    """図解生成ボタンと画像表示のUIを描画"""
    infographic_key = f"infographic_{key_suffix}"
    has_google_key = bool(st.session_state.get("google_api_key"))

    if not has_google_key:
        return  # Google APIキー未設定時は何も表示しない

    # 既に生成済みの場合は表示
    if st.session_state.get(infographic_key):
        img_bytes = st.session_state[infographic_key]
        st.image(img_bytes, caption="📊 生成された図解", use_container_width=True)
        col_dl, col_regen = st.columns(2)
        with col_dl:
            st.download_button(
                "💾 図解をダウンロード",
                data=img_bytes,
                file_name=f"infographic_{key_suffix}.png",
                mime="image/png",
                key=f"dl_img_{key_suffix}",
                use_container_width=True,
            )
        with col_regen:
            if st.button("🔄 図解を再生成", key=f"regen_img_{key_suffix}", use_container_width=True):
                img_data = generate_infographic(post["body"])
                if img_data:
                    st.session_state[infographic_key] = img_data
                    st.rerun()
    else:
        # 生成ボタン
        if st.button("🎨 この内容の図解を生成", key=f"gen_img_{key_suffix}", use_container_width=True):
            img_data = generate_infographic(post["body"])
            if img_data:
                st.session_state[infographic_key] = img_data
                st.rerun()


# ──────────────────────────────────────
# 結果表示 + 個別修正フロー
# ──────────────────────────────────────

def _render_post_card(post, key_prefix="", is_selected=False):
    """ポストカードをStreamlitネイティブ部品でレンダリング"""
    border = is_selected
    with st.container(border=True):
        # ヘッダー行: タイトル + スコア
        score_str = f"　`{post['score']}/100`" if post.get("score") else ""
        st.markdown(f"**【案{post['number']}】{post['title']}**{score_str}")
        # 本文
        st.markdown(post["body"])
        # 文字数
        st.caption(f"📏 {len(post['body'])}文字")


def display_generated_results(result_text, key_prefix=""):
    """生成結果を表示し、案選択 → 個別修正の繰り返しフローを提供"""
    posts = parse_generated_posts(result_text)
    x_ok = all(st.session_state.get(k) for k in ["x_consumer_key", "x_consumer_secret", "x_access_token", "x_access_token_secret"])

    # 修正履歴がある場合のキー
    revision_key = f"{key_prefix}_revision"
    selected_key = f"{key_prefix}_selected_post"

    # ── 修正済みの最新版があれば、それを表示 ──
    if st.session_state.get(revision_key):
        revision = st.session_state[revision_key]
        st.markdown("#### ✏️ 修正版")

        revised_post = revision["post"]
        _render_post_card(revised_post, key_prefix=key_prefix, is_selected=True)

        k = f"{key_prefix}_revised"
        col_copy, col_post, col_back = st.columns(3)
        with col_copy:
            with st.popover("📋 コピー", use_container_width=True):
                st.text_area("コピー用", value=revised_post["body"], height=300, key=f"cp_{k}")
        with col_post:
            if x_ok:
                with st.popover("🐦 投稿", use_container_width=True):
                    st.warning("⚠️ Xに投稿します。")
                    st.text_area("内容", value=revised_post["body"], height=150, key=f"pv_{k}", disabled=True)
                    if st.button("✅ 確定して投稿", key=f"cf_{k}", type="primary"):
                        r = post_to_x(revised_post["body"])
                        if r["success"]:
                            st.success(f"✅ [見る]({r['url']})")
                        else:
                            st.error(f"❌ {r['error']}")
            else:
                st.caption("🔒 X API未設定")
        with col_back:
            if st.button("🔙 3案に戻る", key=f"back_{key_prefix}", use_container_width=True):
                st.session_state.pop(revision_key, None)
                st.session_state.pop(selected_key, None)
                st.rerun()

        # 図解生成
        _render_infographic_ui(revised_post, f"{key_prefix}_revised")

        # ファクトチェック結果
        fc = revision.get("factcheck")
        if fc:
            with st.expander("🔍 ファクトチェック結果", expanded=True):
                st.markdown(fc)

        # さらに修正
        st.markdown("---")
        st.markdown("##### 🔄 さらに修正する")
        further_instruction = st.text_area(
            "修正指示",
            height=80,
            placeholder="例: もう少し短く、冒頭をもっとインパクトのある数字にして...",
            key=f"further_{key_prefix}",
        )
        if st.button("🔄 この案をさらに修正", type="primary", use_container_width=True, key=f"revise_again_{key_prefix}"):
            if further_instruction.strip():
                _do_revision(revised_post, further_instruction, key_prefix)
            else:
                st.warning("修正指示を入力してください。")

        # 修正履歴
        history = revision.get("history", [])
        if history:
            with st.expander(f"📜 修正履歴（{len(history)}回）"):
                for i, h in enumerate(history):
                    st.caption(f"**{i+1}回目:** {h['instruction']}")

        return  # 修正版表示時は3案を隠す

    # ── 3案を表示 ──
    for post in posts:
        _render_post_card(post, key_prefix=key_prefix)

        k = f"{key_prefix}_{post['number']}"
        col_select, col_copy, col_post_btn = st.columns(3)
        with col_select:
            if st.button(f"✏️ この案を選んで修正", key=f"sel_{k}", use_container_width=True):
                st.session_state[selected_key] = post
                st.rerun()
        with col_copy:
            with st.popover("📋 コピー", use_container_width=True):
                st.text_area("コピー用", value=post["body"], height=300, key=f"cp_{k}")
        with col_post_btn:
            if x_ok:
                with st.popover("🐦 投稿", use_container_width=True):
                    st.warning("⚠️ Xに投稿します。")
                    st.text_area("内容", value=post["body"], height=150, key=f"pv_{k}", disabled=True)
                    if st.button("✅ 確定して投稿", key=f"cf_{k}", type="primary"):
                        r = post_to_x(post["body"])
                        if r["success"]:
                            st.success(f"✅ [見る]({r['url']})")
                        else:
                            st.error(f"❌ {r['error']}")
            else:
                st.caption("🔒 X API未設定")

        # 図解生成
        _render_infographic_ui(post, f"{key_prefix}_{post['number']}")

    # ── 案が選択されたら修正指示入力を表示 ──
    if st.session_state.get(selected_key):
        sel = st.session_state[selected_key]
        st.markdown("---")
        st.markdown(f"#### ✏️ 【案{sel['number']}】を修正")
        st.info(f"選択中: **{sel['title']}**（{len(sel['body'])}文字）")

        revision_instruction = st.text_area(
            "修正指示を入力",
            height=100,
            placeholder="例: もっと前向きに、冒頭の数字を変えて、最後に行動を促す一言を追加...",
            key=f"rev_inst_{key_prefix}",
        )
        col_go, col_cancel = st.columns(2)
        with col_go:
            if st.button("🤖 修正版を生成", type="primary", use_container_width=True, key=f"go_rev_{key_prefix}"):
                if revision_instruction.strip():
                    _do_revision(sel, revision_instruction, key_prefix)
                else:
                    st.warning("修正指示を入力してください。")
        with col_cancel:
            if st.button("❌ キャンセル", use_container_width=True, key=f"cancel_rev_{key_prefix}"):
                st.session_state.pop(selected_key, None)
                st.rerun()

    with st.expander("📄 生成全文（デバッグ用）"):
        st.text(result_text)


def _do_revision(original_post, instruction, key_prefix):
    """選択された案に対して修正を実行"""
    system_prompt = load_system_prompt() + ENHANCED_GENERATION_PROMPT

    msg = f"""以下のXポストを、修正指示に従って修正してください。

■ 元のポスト（案{original_post['number']}）:
{original_post['body']}

■ 修正指示:
{instruction}

■ ルール:
- 修正指示に忠実に従ってください
- すあし社長の「解説型」トーンを維持してください（仕組みの解説 → 数字の比較 → メカニズムの解明 → 他国比較 → 示唆で締め）
- 修正後のポストのみを出力してください（タイトルや案番号は不要）
- 600〜800文字を目安にしてください
- マークダウン記法は使わないでください（太字、見出し、リスト等は禁止）
"""
    result = generate_with_claude(
        messages=[{"role": "user", "content": msg}],
        system_prompt=system_prompt,
    )

    # 修正後テキストをクリーンアップ
    body = result.strip()

    # ファクトチェック
    fc_result = run_factcheck(body)

    # 修正履歴を保持
    revision_key = f"{key_prefix}_revision"
    prev = st.session_state.get(revision_key)
    history = prev["history"].copy() if prev else []
    history.append({"instruction": instruction, "before": original_post["body"]})

    revised_post = {
        "number": original_post["number"],
        "title": original_post.get("title", "").replace("（修正版）", "") + "（修正版）",
        "body": body,
        "score": "",
        "emotion": "",
        "hook": "",
        "timing": "",
        "raw": body,
    }

    st.session_state[revision_key] = {
        "post": revised_post,
        "history": history,
        "factcheck": fc_result,
    }
    st.session_state.pop(f"{key_prefix}_selected_post", None)
    st.rerun()


# ──────────────────────────────────────
# サイドバー
# ──────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔑 API設定")
    if "anthropic_api_key" not in st.session_state:
        st.session_state.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    ak = st.text_input("Anthropic API Key", value=st.session_state.anthropic_api_key, type="password")
    st.session_state.anthropic_api_key = ak
    if ak: st.success("✅ 接続済み")
    else: st.warning("⚠️ APIキーを入力")

    st.markdown("---")
    st.markdown("## 🎨 図解生成 (Gemini)")
    if "google_api_key" not in st.session_state:
        st.session_state.google_api_key = os.environ.get("GOOGLE_API_KEY", "")
    gk = st.text_input("Google API Key", value=st.session_state.google_api_key, type="password", key="gak")
    st.session_state.google_api_key = gk
    if gk:
        st.success("✅ 接続済み")
    else:
        st.caption("💡 図解生成にはGoogle APIキーが必要")
    gemini_model_options = {
        "gemini-2.5-flash-image（安定・高速）": "gemini-2.5-flash-image",
        "gemini-3.1-flash-image-preview（最新Flash）": "gemini-3.1-flash-image-preview",
        "gemini-3-pro-image-preview（最高品質Pro）": "gemini-3-pro-image-preview",
    }
    gemini_label = st.selectbox(
        "図解モデル",
        options=list(gemini_model_options.keys()),
        index=0,
        key="gemini_model_select",
    )
    st.session_state.gemini_model = gemini_model_options[gemini_label]

    # キャラクター参照画像（トグル式）
    if CHARACTER_IMG_PATH.exists():
        use_char = st.checkbox("🧑‍💼 すあし社長キャラを図解に使う", value=True, key="use_char_img")
        st.session_state.use_character = use_char
        if use_char:
            st.image(str(CHARACTER_IMG_PATH), width=60)
            with st.expander("キャラ画像を変更", expanded=False):
                char_upload = st.file_uploader(
                    "新しい画像に差し替え",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="char_img_replace",
                )
                if char_upload is not None:
                    CHARACTER_IMG_PATH.write_bytes(char_upload.read())
                    st.success("✅ 差し替え完了")
                    st.rerun()
    else:
        st.session_state.use_character = False
        char_upload = st.file_uploader(
            "🧑‍💼 すあし社長キャラ画像",
            type=["png", "jpg", "jpeg", "webp"],
            key="char_img_upload",
        )
        if char_upload is not None:
            CHARACTER_IMG_PATH.write_bytes(char_upload.read())
            st.success("✅ キャラ画像を保存しました！")
            st.rerun()
        st.caption("💡 図解にすあし社長キャラを組み込めます")

    st.markdown("---")
    with st.expander("🐦 X API設定（任意）", expanded=False):
        st.session_state.x_consumer_key = st.text_input("Consumer Key", type="password", key="xck")
        st.session_state.x_consumer_secret = st.text_input("Consumer Secret", type="password", key="xcs")
        st.session_state.x_access_token = st.text_input("Access Token", type="password", key="xat")
        st.session_state.x_access_token_secret = st.text_input("Access Token Secret", type="password", key="xats")

    st.markdown("---")
    st.markdown("## 🔍 Xトレンド取得")

    # キャッシュ情報を表示（全環境共通）
    cache_info = get_cached_x_trends_info()
    if cache_info:
        if cache_info["is_fresh"]:
            st.success(f"📦 同期キャッシュ: {cache_info['count']}件\n\n更新: {cache_info['updated_at']}（{cache_info['age_hours']}時間前）")
        else:
            st.warning(f"📦 キャッシュ期限切れ（{cache_info['age_hours']}時間前）\n\nWindows PCで sync_x_trends.bat を実行してください")

    if _is_cloud_environment():
        if not cache_info:
            st.info("☁️ クラウド環境ではXトレンドはキャッシュ同期で動作します\n\nWindows PCで sync_x_trends.bat を実行すると、Xトレンドが取得できます")
        st.caption("Google News + Yahoo!リアルタイム検索は常時利用可能")
    else:
        if is_logged_in():
            st.success("✅ Xセッション保存済み")
            st.caption("ニュースタブからポスト数付きで取得します")
        else:
            if not cache_info:
                st.info("💡 ブラウザが開くのでXにログインしてください")
        col_login, col_clear = st.columns([3, 1])
        with col_login:
            if st.button("🔗 Xにログイン" if not is_logged_in() else "🔄 再ログイン", key="x_login_btn", use_container_width=True):
                with st.spinner("ブラウザを起動中... Xにログインしてください"):
                    result = login_to_x()
                if result:
                    st.success("✅ ログイン完了！セッション保存済み")
                    st.rerun()
                else:
                    st.error("❌ ログインに失敗しました。再試行してください")
        with col_clear:
            if is_logged_in():
                if st.button("🗑️", key="x_clear_btn", help="セッション削除"):
                    clear_session()
                    st.rerun()

    st.markdown("---")
    st.markdown("## 📝 生成モード")
    st.caption("同じテーマで切り口を変えた3パターンを生成")
    st.markdown("各600〜800文字 × 3案")

    st.markdown("---")
    st.markdown("## 📜 履歴")
    hist = load_history_list()
    if not hist: st.caption("まだ履歴なし")
    else:
        st.caption(f"{len(hist)}件")
        for i, e in enumerate(hist[:15]):
            ts = datetime.fromisoformat(e["timestamp"])
            inp = e.get("input", {})
            summary = ""
            if isinstance(inp, dict):
                for k in ["selected_topics", "script", "description"]:
                    v = inp.get(k, "")
                    if v:
                        summary = ", ".join(v[:2]) if isinstance(v, list) else str(v)[:25]
                        break
            if st.button(f"{ts.strftime('%m/%d %H:%M')} {get_mode_label(e['mode'])}\n{summary}", key=f"h_{i}", use_container_width=True):
                st.session_state.view_history = e


# ──────────────────────────────────────
# ヘッダー
# ──────────────────────────────────────

st.markdown("""
<div class="main-header">
    <h1>🐦 すあし社長 Xポスト作成ツール</h1>
    <p>ボタン一つでトレンドを取得 → AIがおすすめトピックを提案 → 高品質ポストを自動生成</p>
</div>
""", unsafe_allow_html=True)

# 履歴表示
if st.session_state.get("view_history"):
    entry = st.session_state.view_history
    ts = datetime.fromisoformat(entry["timestamp"])
    if st.button("← 戻る"):
        st.session_state.view_history = None; st.rerun()
    st.markdown(f"**📜 {ts.strftime('%Y/%m/%d %H:%M')} — {get_mode_label(entry['mode'])}**")
    with st.expander("📥 入力"): st.json(entry.get("input", {}))
    st.markdown(entry.get("result", "")); st.stop()


# ──────────────────────────────────────
# メイン: タブ
# ──────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["📰 トレンド起点（メイン）", "📝 原稿変換", "🖼️ 画像コメント"])

# ──────────────────────────────────────
# タブ1: トレンド起点
# ──────────────────────────────────────
with tab1:
    step = st.session_state.get("trend_step", 1)
    cls = {1: ["step-active","step-pending","step-pending"],
           2: ["step-done","step-active","step-pending"],
           3: ["step-done","step-done","step-active"]}
    c = cls.get(step, cls[1])
    st.markdown(f"""
<div class="step-indicator">
    <span class="step-item {c[0]}">① トレンド取得 & AI選定</span>
    <span class="step-arrow">→</span>
    <span class="step-item {c[1]}">② トピック確認 & 選択</span>
    <span class="step-arrow">→</span>
    <span class="step-item {c[2]}">③ ポスト生成</span>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ── STEP 1: 自動取得 ──
    st.markdown("### ① トレンドニュースを取得")
    st.caption("ボタンを押すだけで、今のトレンドニュースを自動取得し、すあし社長向きのトピックをAIが厳選します。")

    col_fetch, col_manual = st.columns([2, 1])
    with col_fetch:
        fetch_clicked = st.button("🔍 今のトレンドを取得して分析する", type="primary", use_container_width=True, key="fetch_btn")
    with col_manual:
        with st.popover("✏️ 手動入力"):
            manual_input = st.text_area("トピックを1行ずつ", height=100, placeholder="少子化\nAI規制\n円安", key="manual_in")
            if st.button("追加", key="add_manual"):
                if manual_input.strip():
                    manual_topics = [l.strip() for l in manual_input.strip().split("\n") if l.strip()]
                    st.session_state.manual_topics = manual_topics
                    st.rerun()

    if fetch_clicked:
        if not st.session_state.get("anthropic_api_key"):
            st.error("🔑 APIキーを設定してください")
        else:
            # 前回の結果をクリア
            for key in ["ai_recommendations", "x_trend_items", "related_news", "raw_news", "trend_step"]:
                if key in st.session_state:
                    del st.session_state[key]

            # ===== トレンド取得（優先度順） =====
            progress = st.empty()

            # ── 1. Xニューストレンド（メイン） ──
            x_news_items = []
            x_login_warning = None

            # クラウド環境: GitHubで同期されたキャッシュから読み込み
            cached_trends = load_cached_x_trends(max_age_hours=24)
            if cached_trends:
                progress.info("📱 【1/3】Xトレンドをキャッシュから読み込み中...")
                for item in cached_trends:
                    count_str = f" ({item['post_count']:,}件のポスト)" if item.get('post_count') else ""
                    x_news_items.append({
                        "title": item["title"] + count_str,
                        "source": "X ニューストレンド（同期）",
                        "link": f"https://x.com/search?q={urllib.parse.quote(item['title'])}",
                        "published": item.get("time_ago", ""),
                        "origin": "x_news",
                        "post_count": item.get("post_count", 0),
                    })
                progress.info(f"✅ Xニュース（キャッシュ）: {len(x_news_items)}件")
            elif is_logged_in():
                # ローカル環境: Playwrightで直接取得
                progress.info("📱 【1/3】Xのニュースタブからトレンドを取得中...")
                x_news = fetch_x_news_trends()
                if x_news == "login_required":
                    x_login_warning = "⚠️ Xのセッションが切れています。サイドバーから再ログインしてください"
                elif x_news and isinstance(x_news, list):
                    for item in x_news:
                        count_str = f" ({item['post_count']:,}件のポスト)" if item['post_count'] else ""
                        x_news_items.append({
                            "title": item["title"] + count_str,
                            "source": "X ニューストレンド",
                            "link": f"https://x.com/search?q={urllib.parse.quote(item['title'])}",
                            "published": item.get("time_ago", ""),
                            "origin": "x_news",
                            "post_count": item.get("post_count", 0),
                        })
                    progress.info(f"✅ Xニュース: {len(x_news_items)}件取得")
                else:
                    x_login_warning = "⚠️ Xニュース取得失敗。サイドバーから再ログインを試してください"
            else:
                x_login_warning = "💡 サイドバーからXにログインすると、Xニューストレンドも取得できます"

            # ── 2. Google News（世の中のトレンド） ──
            progress.info("📰 【2/3】Google Newsからトレンドを取得中...")
            google_items = fetch_google_news()

            # ── 3. Yahoo!リアルタイム検索（補足） ──
            progress.info("🔍 【3/3】Yahoo!リアルタイム検索で補足情報を取得中...")
            yahoo_items = fetch_yahoo_realtime_supplementary()

            # 取得状況を表示
            counts = []
            if x_news_items:
                counts.append(f"🐦 Xニュース {len(x_news_items)}件")
            if google_items:
                counts.append(f"📰 Google News {len(google_items)}件")
            if yahoo_items:
                counts.append(f"🔍 Yahoo!補足 {len(yahoo_items)}件")
            progress.info(f"✅ 取得完了: {' + '.join(counts)}" if counts else "⚠️ トレンドを取得できませんでした")

            if x_login_warning:
                st.warning(x_login_warning)

            # セッションに保存
            st.session_state.x_trend_items = x_news_items
            st.session_state.yahoo_items = yahoo_items

            all_items = x_news_items + google_items + yahoo_items
            if not all_items:
                st.error("ニュースの取得に失敗しました。インターネット接続を確認してください。")
            else:
                st.session_state.raw_news = all_items

                # AIにはGoogle Newsのみ送信して選定
                if google_items:
                    progress.info("🤖 Google Newsからすあし社長向きのトピックをAIが選定中...")
                    try:
                        recommendations = ai_recommend_topics(google_items, st.session_state.anthropic_api_key)
                    except Exception as e:
                        recommendations = []
                        st.error(f"AI選定エラー: {str(e)}")
                else:
                    recommendations = []

                if recommendations:
                    st.session_state.ai_recommendations = recommendations
                    # 関連ニュースも先に取得
                    progress.info("📰 関連ニュースを収集中...")
                    related = {}
                    for rec in recommendations:
                        keyword = rec.get("title", "")[:20]
                        articles = fetch_related_news(keyword, max_results=3)
                        related[rec["title"]] = articles
                    st.session_state.related_news = related
                    progress.empty()
                    st.session_state.trend_step = 2
                    st.rerun()
                else:
                    progress.empty()
                    # Xトレンド or Yahoo補足があればそれだけで表示
                    if x_news_items or yahoo_items:
                        st.session_state.trend_step = 2
                        st.session_state.related_news = {}
                        st.rerun()
                    else:
                        # フォールバック: AI選定が失敗しても生データを表示
                        st.warning("⚠️ AI選定が失敗しましたが、取得したトレンドを直接表示します。")
                        fallback_recs = []
                        for item in google_items[:10]:
                            fallback_recs.append({
                                "title": item["title"],
                                "reason": item.get("source", ""),
                                "angle": "直接取得（AI選定スキップ）",
                                "pillars": [],
                                "hook_type": "",
                                "score": 70,
                            })
                        if fallback_recs:
                            st.session_state.ai_recommendations = fallback_recs
                            st.session_state.related_news = {}
                            st.session_state.trend_step = 2
                            st.rerun()

    # ── STEP 2: トピック選択 ──
    has_x = bool(st.session_state.get("x_trend_items"))
    has_ai = bool(st.session_state.get("ai_recommendations"))
    has_yahoo = bool(st.session_state.get("yahoo_items"))

    if has_x or has_ai or has_yahoo:
        st.markdown("---")
        st.markdown("### ② トピックを選択")
        st.caption("ポストにしたいトピックにチェックを入れてください。")

        selected = []
        rec_idx = 0

        # 手動トピック
        if st.session_state.get("manual_topics"):
            st.markdown("**✏️ 手動追加トピック:**")
            for j, mt in enumerate(st.session_state.manual_topics):
                if st.checkbox(f"✏️ {mt}", key=f"manual_{j}", value=True):
                    selected.append({"title": mt, "angle": "手動入力", "pillars": [], "hook_type": ""})

        # ── 🐦 Xニューストレンド（メイン） ──
        if has_x:
            x_items = st.session_state.x_trend_items
            st.markdown(f"#### 🐦 Xニューストレンド（{len(x_items)}件）")
            st.caption("Xの「話題を検索」→ ニュースタブから取得。今X上で最も話題になっているニュースです。")

            for item in x_items:
                label = f"🐦 {item['title']}"
                checked = st.checkbox(label, key=f"x_news_{rec_idx}", value=False)
                if checked:
                    selected.append({
                        "title": item["title"],
                        "angle": "Xニューストレンド",
                        "pillars": [],
                        "hook_type": "トレンド起点",
                        "score": 90,
                    })
                rec_idx += 1

        # ── 🌐 世の中のトレンド（AI選定） ──
        if has_ai:
            recs = st.session_state.ai_recommendations
            st.markdown(f"#### 🌐 世の中のトレンド（AI厳選 {len(recs)}件）")
            st.caption("Google Newsからすあし社長向きのトピックをAIが厳選。")

            def _show_rec(rec, idx, default_checked=False):
                """推薦カードを表示して選択状態を返す"""
                pillars_str = " × ".join(rec.get("pillars", []))
                hook_str = rec.get("hook_type", "")
                score = rec.get("score", 0)
                if score >= 90: badge = "🔥"
                elif score >= 80: badge = "⭐"
                else: badge = "📌"
                checked = st.checkbox(f"{badge} **{rec['title']}**", key=f"rec_{idx}", value=default_checked)
                st.markdown(f"""<div class="trend-card">
    <div class="trend-title">{rec['title']}</div>
    <div class="trend-source">🏷️ {pillars_str}　｜　🎣 {hook_str}　｜　📊 相性度: {score}/100</div>
    <div class="trend-reason">💡 {rec.get('angle', '')}</div>
</div>""", unsafe_allow_html=True)
                rel = st.session_state.get("related_news", {}).get(rec["title"], [])
                if rel:
                    with st.expander(f"📰 関連ニュース ({len(rel)}件)", expanded=False):
                        for art in rel:
                            st.caption(f"• {art['title']}（{art['source']}）")
                return checked

            first_ai_idx = rec_idx
            for rec in recs:
                if _show_rec(rec, rec_idx, default_checked=(rec_idx == first_ai_idx and not has_x)):
                    selected.append(rec)
                rec_idx += 1

        # ── 🔍 Yahoo!リアルタイム補足 ──
        if has_yahoo:
            yahoo_items = st.session_state.yahoo_items
            with st.expander(f"🔍 Yahoo!リアルタイム補足（{len(yahoo_items)}件）", expanded=False):
                st.caption("Yahoo!リアルタイム検索からの補足情報。X上で今話題のポストを参考にできます。")

                categories = {}
                for item in yahoo_items:
                    cat = item.get("category", "その他")
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(item)

                for cat, items in categories.items():
                    st.markdown(f"**{cat}**")
                    for item in items:
                        label = f"🔍 {item['title']}"
                        checked = st.checkbox(label, key=f"yahoo_{rec_idx}", value=False)
                        if item.get("full_text") and item["full_text"] != item["title"]:
                            st.caption(f"💬 {item['full_text'][:120]}")
                        if checked:
                            selected.append({
                                "title": item["title"],
                                "angle": f"Yahoo!リアルタイム（{cat}）",
                                "pillars": [],
                                "hook_type": "トレンド起点",
                                "score": 70,
                                "full_text": item.get("full_text", ""),
                            })
                        rec_idx += 1

        # 追加コンテキスト
        extra = st.text_area("📌 追加コンテキスト（任意）", height=80,
            placeholder="関連する原稿や追加情報...", key="trend_extra")

        # 修正指示
        modify_instruction = st.text_area("✏️ 修正指示（任意）", height=80,
            placeholder="例: もっと前向きに、若者向けの語り口で、米国との比較を入れて...", key="trend_modify")

        if selected:
            if st.button("🤖 すあし社長スタイルのポストを生成", type="primary", use_container_width=True, key="gen_btn"):
                system_prompt = load_system_prompt()
                gen_progress = st.empty()

                # ── STEP A: 選択トピックの最新情報をWeb検索 ──
                gen_progress.info("🔍 選択トピックの最新情報をWeb検索中...")
                topic_facts = search_facts_for_topics(selected, progress=gen_progress)

                # 選択トピックの情報を構築（検索結果付き）
                topics_context = ""
                for s in selected:
                    topics_context += f"\n### トピック: {s['title']}\n"
                    if s.get("angle"):
                        topics_context += f"- 切り口: {s['angle']}\n"
                    if s.get("pillars"):
                        topics_context += f"- 柱の組合せ: {' × '.join(s['pillars'])}\n"
                    if s.get("hook_type"):
                        topics_context += f"- フック型: {s['hook_type']}\n"
                    # 関連ニュース
                    rel = st.session_state.get("related_news", {}).get(s["title"], [])
                    if rel:
                        topics_context += "- 関連ニュース:\n"
                        for art in rel:
                            topics_context += f"  - {art['title']}（{art['source']}）\n"
                    # Web検索結果を追加
                    clean_title = re.sub(r'\s*\(\d[\d,]*件のポスト\)', '', s['title']).strip()
                    facts = topic_facts.get(clean_title, [])
                    if facts:
                        topics_context += "- 最新のWeb検索結果（事実確認用）:\n"
                        for fact in facts:
                            topics_context += f"  - {fact}\n"

                # ── STEP B: ポスト生成 ──
                gen_progress.info("🤖 すあし社長スタイルのポストを生成中...")
                user_msg = f"""以下のトピックについて、すあし社長スタイルのXポストを3案生成してください。
各案600〜800文字で、それぞれ異なる切り口で仕組み・構造を解説するスタイルにしてください。

■ 生成する3案（各600〜800文字）:
【案1】仕組み解説型 — テーマの基本構造を整理して「なぜそうなるのか」を解き明かす
【案2】国際比較型 — 他国の事例と比較して日本の状況を立体的に見せる
【案3】逆説・発見型 — 「一見〜だが、実は〜」という意外な構造を提示する

■ 選定されたトピック:
{topics_context}

■ 重要な指示（必ず守ること）:
- 「ニュースの感想」ではなく「仕組み・構造の解説」として書くこと
- 冒頭は「〜を整理してみましょう」「〜の構造はこうなっています」等の解説導入で始める
- 具体的な数字は必ず比較セットで使う（「Aは○％なのに、Bは△％」）
- 「なぜそうなるのか」のメカニズムを必ず解説すること
- 他国の具体的な国名・人名・制度名を入れること
- 締めは主張ではなく、示唆・問いかけで余韻を残すこと
- 「最新のWeb検索結果」の情報を必ず参照し、事実に基づいた正確な記述にすること
- 現在の米国大統領はドナルド・トランプ（第2期、2025年1月就任）です
- 人名・政権名・数値などの事実情報は検索結果に基づき正確に記述すること
"""
                if extra.strip():
                    user_msg += f"\n■ 追加コンテキスト:\n{extra}\n"
                if modify_instruction.strip():
                    user_msg += f"\n■ 修正指示（これを最優先で反映してください）:\n{modify_instruction}\n"

                enhanced_system = system_prompt + ENHANCED_GENERATION_PROMPT
                result = generate_with_claude(
                    messages=[{"role": "user", "content": user_msg}],
                    system_prompt=enhanced_system,
                )

                # ── STEP C: ファクトチェック ──
                gen_progress.info("🔍 ファクトチェック中...")
                # 各案を解析してファクトチェック
                posts = parse_generated_posts(result)
                all_search_text = ""
                for facts_list in topic_facts.values():
                    all_search_text += "\n".join(facts_list) + "\n"

                fc_results = {}
                for post in posts:
                    fc = run_factcheck(post["body"], all_search_text)
                    if fc:
                        fc_results[post["number"]] = fc

                gen_progress.empty()
                st.session_state.trend_result = result
                st.session_state.trend_factcheck = fc_results
                st.session_state.trend_step = 3
                save_history("trend", {
                    "selected_topics": [s["title"] for s in selected],
                    "angles": [s.get("angle", "") for s in selected],
                    "extra": extra,
                }, result)
                st.rerun()

    # ── STEP 3: 結果 ──
    if st.session_state.get("trend_result") and st.session_state.get("trend_step", 1) >= 3:
        st.markdown("---")
        st.markdown("### ③ ✨ 生成結果")
        display_generated_results(st.session_state.trend_result, "trend")

        # ファクトチェック結果を表示
        fc_results = st.session_state.get("trend_factcheck", {})
        if fc_results:
            with st.expander("🔍 ファクトチェック結果", expanded=True):
                for num, fc_text in fc_results.items():
                    st.markdown(f"**案{num}:**")
                    st.markdown(fc_text)
                    st.markdown("---")

        c1, c2 = st.columns(2)
        _trend_clear_keys = [
            "trend_result", "ai_recommendations", "raw_news", "related_news",
            "trend_step", "manual_topics", "x_trend_items", "yahoo_items",
            "trend_revision", "trend_selected_post", "trend_factcheck",
        ]
        # 図解のセッションも削除
        for sk in list(st.session_state.keys()):
            if sk.startswith("infographic_trend_"):
                _trend_clear_keys.append(sk)
        with c1:
            if st.button("🗑️ クリア", key="cl_t"):
                for k in _trend_clear_keys:
                    st.session_state.pop(k, None)
                st.rerun()
        with c2:
            if st.button("🔄 新しいトレンド", key="new_t"):
                for k in _trend_clear_keys:
                    st.session_state.pop(k, None)
                st.rerun()


# ──────────────────────────────────────
# タブ2: 原稿変換
# ──────────────────────────────────────
with tab2:
    st.markdown("#### YouTube原稿からXポストを生成")
    script_text = st.text_area("📄 原稿テキスト", height=250, placeholder="YouTube動画の原稿をここに...", key="s_in")
    script_ctx = st.text_area("📌 追加コンテキスト（任意）", height=80, placeholder="関連ニュース等...", key="s_ctx")
    if st.button("▶ 生成する", key="g_s", type="primary", use_container_width=True):
        if not script_text.strip():
            st.warning("原稿を入力してください。")
        else:
            sp = load_system_prompt() + ENHANCED_GENERATION_PROMPT
            msg = f"""以下のYouTube原稿をベースに、すあし社長スタイルのXポストを3案生成してください。
それぞれ600〜800文字で、切り口やフックを変えてバリエーションを付けてください。
品質スコアが最大になるよう意識してください。

【案1】切り口A（600〜800文字）
【案2】切り口B（600〜800文字）
【案3】切り口C（600〜800文字）

■ 原稿:
{script_text}
"""
            if script_ctx.strip(): msg += f"\n■ 追加コンテキスト:\n{script_ctx}\n"
            result = generate_with_claude([{"role": "user", "content": msg}], sp)
            # ファクトチェック
            posts = parse_generated_posts(result)
            fc_results = {}
            for post in posts:
                fc = run_factcheck(post["body"])
                if fc:
                    fc_results[post["number"]] = fc
            st.session_state.script_result = result
            st.session_state.script_factcheck = fc_results
            save_history("script", {"script": script_text[:200], "context": script_ctx}, result)
    if st.session_state.get("script_result"):
        st.markdown("---"); st.markdown("## ✨ 生成結果")
        display_generated_results(st.session_state.script_result, "scr")
        fc_results = st.session_state.get("script_factcheck", {})
        if fc_results:
            with st.expander("🔍 ファクトチェック結果", expanded=True):
                for num, fc_text in fc_results.items():
                    st.markdown(f"**案{num}:**")
                    st.markdown(fc_text)
                    st.markdown("---")
        if st.button("🗑️ クリア", key="cl_s"):
            clear_keys = ["script_result", "scr_revision", "scr_selected_post", "script_factcheck"]
            for sk in list(st.session_state.keys()):
                if sk.startswith("infographic_scr_"):
                    clear_keys.append(sk)
            for k in clear_keys:
                st.session_state.pop(k, None)
            st.rerun()


# ──────────────────────────────────────
# タブ3: 画像コメント
# ──────────────────────────────────────
with tab3:
    st.markdown("#### 画像にすあし社長スタイルのコメント")
    img = st.file_uploader("🖼️ 画像", type=["png","jpg","jpeg","gif","webp"], key="img_up")
    if img: st.image(img, caption=img.name, width=400)
    img_desc = st.text_area("📌 説明（任意）", height=80, placeholder="背景や文脈...", key="img_d")
    if st.button("▶ コメント生成", key="g_i", type="primary", use_container_width=True):
        if not img:
            st.warning("画像をアップロードしてください。")
        else:
            sp = load_system_prompt() + ENHANCED_GENERATION_PROMPT
            img_bytes = img.read(); img.seek(0)
            img_b64 = base64.b64encode(img_bytes).decode()
            ext = img.name.rsplit(".",1)[-1].lower()
            mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","gif":"image/gif","webp":"image/webp"}.get(ext,"image/png")
            desc = f"\n■ 説明:\n{img_desc}\n" if img_desc.strip() else ""
            content = [
                {"type": "text", "text": f"""以下の画像について、すあし社長スタイルのXポストを3案生成してください。
それぞれ600〜800文字で、切り口を変えてバリエーションを付けてください。

【案1】切り口A（600〜800文字）
【案2】切り口B（600〜800文字）
【案3】切り口C（600〜800文字）
{desc}
画像添付前提のポストにしてください。"""},
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": img_b64}},
            ]
            result = generate_with_claude([{"role": "user", "content": content}], sp)
            # ファクトチェック
            posts = parse_generated_posts(result)
            fc_results = {}
            for post in posts:
                fc = run_factcheck(post["body"])
                if fc:
                    fc_results[post["number"]] = fc
            st.session_state.image_result = result
            st.session_state.image_factcheck = fc_results
            save_history("image", {"image_name": img.name, "desc": img_desc}, result)
    if st.session_state.get("image_result"):
        st.markdown("---"); st.markdown("## ✨ 生成結果")
        display_generated_results(st.session_state.image_result, "img")
        fc_results = st.session_state.get("image_factcheck", {})
        if fc_results:
            with st.expander("🔍 ファクトチェック結果", expanded=True):
                for num, fc_text in fc_results.items():
                    st.markdown(f"**案{num}:**")
                    st.markdown(fc_text)
                    st.markdown("---")
        if st.button("🗑️ クリア", key="cl_i"):
            clear_keys = ["image_result", "img_revision", "img_selected_post", "image_factcheck"]
            for sk in list(st.session_state.keys()):
                if sk.startswith("infographic_img_"):
                    clear_keys.append(sk)
            for k in clear_keys:
                st.session_state.pop(k, None)
            st.rerun()
