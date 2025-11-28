#!/bin/bash
# Test script: Python server with C clients
# Usage: ./scripts/test_with_c_clients.sh [num_games] [options]
#
# Examples:
#   ./scripts/test_with_c_clients.sh           # Run with default 100 games
#   ./scripts/test_with_c_clients.sh 10        # Run 10 games
#   ./scripts/test_with_c_clients.sh 5 -v      # Run 5 games with verbose output

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
C_CLIENT_DIR="${PROJECT_DIR}/../tndhm_devkit_c-20221111/client"

# Default values
NUM_GAMES="${1:-100}"
shift 2>/dev/null || true
EXTRA_ARGS="$@"

HOST="127.0.0.1"
PORT="42485"

# Check if C client exists
if [ ! -f "$C_CLIENT_DIR/client" ]; then
    echo "Error: C client not found at $C_CLIENT_DIR/client"
    echo "Please build the C client first:"
    echo "  cd $C_CLIENT_DIR && make"
    exit 1
fi

echo "==================================="
echo "UECda Integration Test"
echo "==================================="
echo "Server: Python (uecda_server)"
echo "Client: C (tndhm_devkit)"
echo "Games: $NUM_GAMES"
echo "==================================="
echo

# Start Python server in background
cd "$PROJECT_DIR"
uv run python -m uecda_server.main --num-games "$NUM_GAMES" $EXTRA_ARGS &
SERVER_PID=$!

# Wait for server to start
sleep 2

# Check if server started successfully
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "Error: Server failed to start"
    exit 1
fi

echo "Server started (PID: $SERVER_PID)"
echo "Connecting 5 C clients..."
echo

# Start 5 C clients
CLIENT_PIDS=()
for i in {0..4}; do
    "$C_CLIENT_DIR/client" -h "$HOST" -p "$PORT" -n "Client$i" &
    CLIENT_PIDS+=($!)
done

# Wait for all clients to finish
for pid in "${CLIENT_PIDS[@]}"; do
    wait $pid 2>/dev/null || true
done

# Wait for server to finish
wait $SERVER_PID 2>/dev/null || true

echo
echo "Test completed!"
