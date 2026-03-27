#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  discord-claude-bot  —  Graceful shutdown (SIGTERM)
# ──────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")"

PIDFILE="bot.pid"
LOG="bot.log"

# ── Colors (disable if not TTY) ──────────────────────────────
if [ -t 1 ]; then
    BOLD='\033[1m' DIM='\033[2m' CYAN='\033[36m'
    GREEN='\033[32m' YELLOW='\033[33m' RED='\033[31m' RESET='\033[0m'
else
    BOLD='' DIM='' CYAN='' GREEN='' YELLOW='' RED='' RESET=''
fi

info()    { echo -e "  ${CYAN}›${RESET} $1"; }
success() { echo -e "  ${GREEN}✔${RESET} $1"; }
warn()    { echo -e "  ${YELLOW}▲${RESET} $1"; }

# ── Find and stop process ────────────────────────────────────
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        info "Sending SIGTERM to PID ${PID}..."
        kill "$PID"

        # Wait up to 10 seconds for graceful shutdown
        WAITED=0
        while ps -p "$PID" > /dev/null 2>&1 && [ "$WAITED" -lt 10 ]; do
            sleep 1
            WAITED=$((WAITED + 1))
        done

        if ps -p "$PID" > /dev/null 2>&1; then
            warn "Process did not exit after 10s — use ${CYAN}./kill.sh${RESET} to force"
        else
            rm -f "$PIDFILE"
            success "Bot stopped gracefully (PID: ${PID})"
            echo "$(date '+%Y-%m-%d %H:%M:%S') Bot stopped (PID: $PID)" >> "$LOG"
            ./notify.sh "🔴 봇이 종료되었습니다 (PID: ${PID})" &
        fi
    else
        rm -f "$PIDFILE"
        warn "Bot was not running (stale PID file removed)"
    fi
else
    # Fallback: search for process without PID file
    PID=$(pgrep -f "python main.py" | head -1 || true)
    if [ -n "$PID" ]; then
        info "Found bot without PID file (PID: ${PID})"
        kill "$PID"
        success "Bot stopped (PID: ${PID})"
        echo "$(date '+%Y-%m-%d %H:%M:%S') Bot stopped (PID: $PID)" >> "$LOG"
    else
        warn "Bot is not running"
    fi
fi
