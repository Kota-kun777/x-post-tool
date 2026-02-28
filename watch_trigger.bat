@echo off
chcp 65001 >nul
REM ============================================
REM Xトレンド同期 トリガー監視（Windows用）
REM
REM Streamlit Cloudのボタンからの同期リクエストを
REM 自動検出して実行します。
REM
REM 使い方:
REM   ダブルクリックで起動 → 常駐監視モード
REM   Ctrl+C で停止
REM
REM タスクスケジューラでPC起動時に自動起動:
REM   トリガー: ログオン時
REM   プログラム: cmd.exe
REM   引数: /c "C:\...\watch_trigger.bat"
REM   開始: このファイルのフォルダパス
REM ============================================

cd /d "%~dp0"

echo ==========================================
echo   X トレンド同期 - トリガー監視モード
echo ==========================================
echo.
echo Streamlit Cloud からのリクエストを待機中...
echo Ctrl+C で停止できます
echo.

python watch_trigger.py

echo.
pause
