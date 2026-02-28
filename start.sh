#!/bin/bash
# すあし社長 Xポスト作成ツール 起動スクリプト（Mac/Linux/クラウド環境用）
#
# 使い方:
#   1. .env ファイルにAPIキーを設定（.env.example を参考）
#   2. ./start.sh を実行
#   3. ブラウザで http://localhost:8502 を開く

cd "$(dirname "$0")"

# 依存パッケージのインストール（初回のみ）
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "📦 依存パッケージをインストール中..."
    pip install -r requirements.txt
fi

echo "🚀 すあし社長 Xポスト作成ツールを起動します..."
echo "   ブラウザで http://localhost:8502 を開いてください"
echo ""
streamlit run app.py --server.port 8502 --server.headless true
