#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  discord-claude-bot  —  Force kill (SIGKILL)
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

# ── Find and force kill ──────────────────────────────────────
KILLED=false

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -9 "$PID" 2>/dev/null || true
        success "Force killed PID ${PID}"
        KILLED=true
    else
        info "PID ${PID} was not running"
    fi
    rm -f "$PIDFILE"
fi

# Also check for any orphaned processes
ORPHANS=$(pgrep -f "python main.py" || true)
if [ -n "$ORPHANS" ]; then
    for PID in $ORPHANS; do
        kill -9 "$PID" 2>/dev/null || true
        success "Force killed orphan PID ${PID}"
        KILLED=true
    done
fi

if [ "$KILLED" = true ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Bot force killed" >> "$LOG"
else
    warn "Bot is not running"
fi
