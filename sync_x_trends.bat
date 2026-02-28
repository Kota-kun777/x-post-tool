@echo off
chcp 65001 >nul
REM ============================================
REM Xニューストレンド同期バッチ（Windows用）
REM
REM 使い方:
REM   1. ダブルクリックで実行
REM   2. Xトレンドを取得 → x_trends_cache.json に保存
REM   3. 自動的にGitHub にコミット＆プッシュ
REM
REM タスクスケジューラで定期実行（例: 毎朝8時）:
REM   プログラム: cmd.exe
REM   引数: /c "C:\...\sync_x_trends.bat"
REM   開始: このファイルのフォルダパス
REM ============================================

cd /d "%~dp0"

echo ==========================================
echo   X トレンド同期ツール
echo ==========================================
echo.

REM トレンド取得 & GitHubプッシュ
python sync_x_trends.py --push

echo.
echo 完了しました。5秒後にウィンドウを閉じます...
timeout /t 5 >nul
