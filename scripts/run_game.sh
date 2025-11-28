#!/bin/bash
#
# UECda ゲーム実行スクリプト
# Pythonサーバー + Pythonクライアント5台でゲームを実行
#
# 使い方:
#   ./scripts/run_game.sh [ゲーム数]
#
# 例:
#   ./scripts/run_game.sh       # デフォルト: 3ゲーム
#   ./scripts/run_game.sh 10    # 10ゲーム

set -e

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# 設定
NUM_GAMES=${1:-3}
PORT=42485
HOST=127.0.0.1

echo "=========================================="
echo "UECda Game Runner"
echo "=========================================="
echo "ゲーム数: $NUM_GAMES"
echo "ポート: $PORT"
echo ""

# サーバー起動
echo "サーバーを起動中..."
cd "$ROOT_DIR/uecda_server"
uv run python -m uecda_server.main --num-games "$NUM_GAMES" &
SERVER_PID=$!

# サーバーが起動するまで待機
sleep 2

# クライアント起動
echo "クライアントを起動中..."
cd "$ROOT_DIR/uecda_client"
for i in {0..4}; do
    uv run python -m uecda_client.main -H "$HOST" -p "$PORT" -n "Player$i" &
done

# 全プロセスの終了を待機
wait

echo ""
echo "=========================================="
echo "ゲーム終了"
echo "=========================================="
