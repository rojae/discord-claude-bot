#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  discord-claude-bot  —  Start (background)
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
fail()    { echo -e "  ${RED}✖${RESET} $1"; exit 1; }

# ── Pre-flight checks ────────────────────────────────────────
if [ ! -d ".venv" ]; then
    fail "Virtual environment not found. Run ${BOLD}./install.sh${RESET} first."
fi

if [ ! -f ".env" ]; then
    fail ".env not found. Run ${BOLD}./install.sh${RESET} first."
fi

# Check for duplicate instance
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        warn "Bot is already running (PID: ${OLD_PID})"
        info "Use ${CYAN}./status.sh${RESET} to check or ${CYAN}./stop.sh${RESET} to restart"
        exit 1
    else
        rm -f "$PIDFILE"
        info "Removed stale PID file"
    fi
fi

# ── Activate venv ─────────────────────────────────────────────
# shellcheck disable=SC1091
source .venv/bin/activate

# ── Start bot ─────────────────────────────────────────────────
echo -e "${BOLD}  Starting discord-claude-bot...${RESET}"

echo "$(date '+%Y-%m-%d %H:%M:%S') Bot starting..." >> "$LOG"
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT
nohup .venv/bin/python main.py >> "$LOG" 2>&1 &
BOT_PID=$!
echo "$BOT_PID" > "$PIDFILE"

# Brief wait to check immediate crash
sleep 1
if ps -p "$BOT_PID" > /dev/null 2>&1; then
    success "Bot started (PID: ${BOT_PID})"
    info "Logs: ${DIM}tail -f ${LOG}${RESET}"
    echo "$(date '+%Y-%m-%d %H:%M:%S') Bot started (PID: $BOT_PID)" >> "$LOG"
    ./notify.sh "🟢 봇이 시작되었습니다 (PID: ${BOT_PID})" &
else
    rm -f "$PIDFILE"
    fail "Bot crashed immediately. Check ${BOLD}${LOG}${RESET} for details."
fi
