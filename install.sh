#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  discord-claude-bot  —  Installation Script
# ──────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

# ── Cleanup trap ──────────────────────────────────────────────
cleanup() {
    rm -f .env.bak .env.tmp 2>/dev/null
}
trap cleanup EXIT

# ── Colors (disable if not TTY) ───────────────────────────────
if [ -t 1 ]; then
    BOLD='\033[1m'
    DIM='\033[2m'
    CYAN='\033[36m'
    GREEN='\033[32m'
    YELLOW='\033[33m'
    RED='\033[31m'
    MAGENTA='\033[35m'
    RESET='\033[0m'
else
    BOLD='' DIM='' CYAN='' GREEN='' YELLOW='' RED='' MAGENTA='' RESET=''
fi

# ── Helpers ───────────────────────────────────────────────────
info()    { echo -e "  ${CYAN}›${RESET} $1"; }
success() { echo -e "  ${GREEN}✔${RESET} $1"; }
warn()    { echo -e "  ${YELLOW}▲${RESET} $1"; }
fail()    { echo -e "  ${RED}✖${RESET} $1"; exit 1; }
ask()     { echo -en "  ${MAGENTA}?${RESET} $1"; }

# Portable sed in-place (macOS & Linux)
sed_i() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# Set .env value safely (handles special chars in values)
set_env() {
    local key="$1" value="$2" file="${3:-.env}"
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        # Use awk to avoid sed delimiter issues with paths/tokens
        awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k{$2=v}1' "$file" > .env.tmp && mv .env.tmp "$file"
    else
        echo "${key}=${value}" >> "$file"
    fi
}

# ── Banner ────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║                                              ║"
echo "  ║   discord-claude-bot  installer              ║"
echo "  ║                                              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${RESET}"

# ──────────────────────────────────────────────────────────────
#  Step 1: Python version check
# ──────────────────────────────────────────────────────────────
echo -e "${BOLD}  Step 1/5  ${DIM}Python version check${RESET}"

PYTHON=""
PYTHON_VER=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>/dev/null || true)
        major=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
        if [ "$major" -ge 3 ] 2>/dev/null && [ "$minor" -ge 11 ] 2>/dev/null; then
            PYTHON="$cmd"
            PYTHON_VER="$ver"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.11+ is required. Install it first:
       macOS:   brew install python@3.13
       Ubuntu:  sudo apt install python3.13 python3.13-venv
       Fedora:  sudo dnf install python3.13
       Windows: https://www.python.org/downloads/"
fi

# Check venv module is available
if ! $PYTHON -c "import venv" &>/dev/null; then
    fail "Python venv module not found. Install it:
       Ubuntu/Debian: sudo apt install python${PYTHON_VER}-venv
       Fedora:        sudo dnf install python3-libs"
fi

success "Found ${PYTHON} (${PYTHON_VER}) at $(command -v "$PYTHON")"

# ──────────────────────────────────────────────────────────────
#  Step 2: Virtual environment
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  Step 2/5  ${DIM}Virtual environment${RESET}"

RECREATE_VENV=false

if [ -d ".venv" ]; then
    # Check existing venv Python version
    VENV_PYTHON=".venv/bin/python"
    if [ -x "$VENV_PYTHON" ]; then
        VENV_VER=$("$VENV_PYTHON" -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>/dev/null || echo "unknown")
        if [ "$VENV_VER" != "$PYTHON_VER" ]; then
            warn "Version mismatch: .venv has Python ${VENV_VER}, system has ${PYTHON_VER}"
            ask "Recreate with Python ${PYTHON_VER}? [Y/n] "
            read -r answer
            if [[ ! "$answer" =~ ^[Nn]$ ]]; then
                RECREATE_VENV=true
            fi
        else
            success "Existing .venv matches Python ${PYTHON_VER}"
        fi
    else
        warn "Existing .venv is broken (no python binary)"
        RECREATE_VENV=true
    fi

    if [ "$RECREATE_VENV" = false ]; then
        ask "Recreate virtual environment? [y/N] "
        read -r answer
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            RECREATE_VENV=true
        fi
    fi

    if [ "$RECREATE_VENV" = true ]; then
        rm -rf .venv
        info "Removed old .venv"
    fi
fi

if [ ! -d ".venv" ]; then
    info "Creating virtual environment with ${PYTHON}..."
    if ! $PYTHON -m venv .venv; then
        fail "Failed to create virtual environment. Check Python installation."
    fi
    success "Virtual environment created (.venv/)"
fi

# Activate
# shellcheck disable=SC1091
source .venv/bin/activate
success "Activated .venv ($(python --version 2>&1))"

# ──────────────────────────────────────────────────────────────
#  Step 3: Install dependencies
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  Step 3/5  ${DIM}Install dependencies${RESET}"

info "Upgrading pip..."
if ! pip install --upgrade pip --quiet 2>&1; then
    warn "pip upgrade failed, continuing with existing version"
fi

info "Installing packages from pyproject.toml..."
if ! pip install -e . 2>&1 | tail -1; then
    fail "Package installation failed. Check pyproject.toml and network connection."
fi

# Verify each core dependency
echo ""
MISSING_DEPS=()
for pkg in "discord.py" "pydantic" "pydantic-settings" "python-dotenv"; do
    pkg_ver=$(pip show "$pkg" 2>/dev/null | grep "^Version:" | awk '{print $2}')
    if [ -n "$pkg_ver" ]; then
        echo -e "    ${GREEN}✔${RESET} ${DIM}${pkg} ${pkg_ver}${RESET}"
    else
        echo -e "    ${RED}✖${RESET} ${DIM}${pkg} — NOT INSTALLED${RESET}"
        MISSING_DEPS+=("$pkg")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    fail "Missing dependencies: ${MISSING_DEPS[*]}"
fi
success "All dependencies verified"

# ──────────────────────────────────────────────────────────────
#  Step 4: Setup .env
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  Step 4/5  ${DIM}Environment configuration${RESET}"

SKIP_ENV=false

if [ ! -f ".env.example" ]; then
    fail ".env.example not found — repository may be incomplete"
fi

if [ -f ".env" ]; then
    warn ".env already exists"
    ask "Overwrite with fresh config? [y/N] "
    read -r answer
    if [[ ! "$answer" =~ ^[Yy]$ ]]; then
        success "Keeping existing .env"
        SKIP_ENV=true
    fi
fi

if [ "$SKIP_ENV" = false ]; then
    cp .env.example .env
    info "Copied .env.example → .env"

    # ── Required settings ──
    echo ""
    echo -e "  ${DIM}─── Required settings ───${RESET}"
    echo ""

    # Discord Token (masked input)
    while true; do
        ask "Discord bot token: "
        read -rs discord_token  # -s: silent (no echo)
        echo ""  # newline after hidden input
        if [ -n "$discord_token" ]; then
            set_env "DISCORD_TOKEN" "$discord_token"
            # Show masked preview
            masked="${discord_token:0:8}...${discord_token: -4}"
            success "Token set (${masked})"
            break
        else
            warn "Discord token is required. Get one at https://discord.com/developers/applications"
        fi
    done

    # Agent Type
    echo ""
    echo -e "    ${DIM}Supported: claude / gemini / codex / aider / custom${RESET}"
    ask "Agent type [claude]: "
    read -r agent_type
    agent_type="${agent_type:-claude}"
    # Validate agent type
    case "$agent_type" in
        claude|gemini|codex|aider|custom)
            set_env "AGENT_TYPE" "$agent_type"
            success "Agent type: ${agent_type}"
            ;;
        *)
            warn "Unknown agent type '${agent_type}', defaulting to 'claude'"
            agent_type="claude"
            set_env "AGENT_TYPE" "claude"
            ;;
    esac

    # Agent Binary (auto-detect)
    default_binary=""
    case "$agent_type" in
        claude) default_binary=$(command -v claude 2>/dev/null || echo "claude") ;;
        gemini) default_binary=$(command -v gemini 2>/dev/null || echo "gemini") ;;
        codex)  default_binary=$(command -v codex  2>/dev/null || echo "codex") ;;
        aider)  default_binary=$(command -v aider  2>/dev/null || echo "aider") ;;
        custom) default_binary="" ;;
    esac
    ask "Agent binary path [${default_binary:-<enter path>}]: "
    read -r agent_binary
    agent_binary="${agent_binary:-$default_binary}"
    set_env "AGENT_BINARY" "$agent_binary"
    if command -v "$agent_binary" &>/dev/null; then
        # Try to get version
        agent_ver=$("$agent_binary" --version 2>/dev/null | head -1 || echo "")
        if [ -n "$agent_ver" ]; then
            success "Agent binary: ${agent_binary} (${agent_ver})"
        else
            success "Agent binary: ${agent_binary}"
        fi
    else
        warn "Binary '${agent_binary}' not found in PATH — verify path in .env"
    fi

    # Working Directory
    ask "Agent working directory [$(pwd)]: "
    read -r working_dir
    working_dir="${working_dir:-$(pwd)}"
    # Validate directory exists
    if [ -d "$working_dir" ]; then
        set_env "AGENT_WORKING_DIR" "$working_dir"
        success "Working directory: ${working_dir}"
    else
        warn "Directory '${working_dir}' does not exist — creating it"
        mkdir -p "$working_dir"
        set_env "AGENT_WORKING_DIR" "$working_dir"
        success "Working directory created: ${working_dir}"
    fi

    # ── Optional settings ──
    echo ""
    echo -e "  ${DIM}─── Optional settings (press Enter to skip) ───${RESET}"
    echo ""

    # Allowed Channels
    ask "Allowed channel IDs (JSON array, e.g. [123,456]): "
    read -r channels
    if [ -n "$channels" ]; then
        # Basic JSON array validation
        if [[ "$channels" =~ ^\[.*\]$ ]]; then
            set_env "ALLOWED_CHANNEL_IDS" "$channels"
            success "Channel filter set"
        else
            warn "Invalid format — expected JSON array like [123,456]. Skipped."
        fi
    else
        info "No channel filter (all channels allowed)"
    fi

    # Allowed Users
    ask "Allowed user IDs (JSON array, e.g. [123,456]): "
    read -r users
    if [ -n "$users" ]; then
        if [[ "$users" =~ ^\[.*\]$ ]]; then
            set_env "ALLOWED_USER_IDS" "$users"
            success "User filter set"
        else
            warn "Invalid format — expected JSON array like [123,456]. Skipped."
        fi
    else
        info "No user filter (all users allowed)"
    fi

    # Permission Mode
    echo ""
    echo -e "    ${DIM}auto_approve — Skip all permission prompts (default)${RESET}"
    echo -e "    ${DIM}relay       — Relay prompts to Discord as buttons${RESET}"
    echo -e "    ${DIM}deny        — Auto-deny all permission prompts${RESET}"
    ask "Permission mode [auto_approve]: "
    read -r perm_mode
    perm_mode="${perm_mode:-auto_approve}"
    case "$perm_mode" in
        auto_approve|relay|deny)
            set_env "AGENT_PERMISSION_MODE" "$perm_mode"
            success "Permission mode: ${perm_mode}"
            ;;
        *)
            warn "Unknown mode '${perm_mode}', defaulting to 'auto_approve'"
            set_env "AGENT_PERMISSION_MODE" "auto_approve"
            ;;
    esac

    echo ""
    success ".env configured"
fi

# ──────────────────────────────────────────────────────────────
#  Step 5: Final verification
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  Step 5/5  ${DIM}Final verification${RESET}"

# Make scripts executable
for script in run.sh stop.sh kill.sh status.sh install.sh; do
    if [ -f "$script" ]; then
        chmod +x "$script"
    fi
done
success "Shell scripts are executable"

# Verify .env completeness
ERRORS=0
WARNINGS=0

# Check Discord token
TOKEN=$(grep "^DISCORD_TOKEN=" .env 2>/dev/null | cut -d= -f2-)
if [ -z "$TOKEN" ] || [ "$TOKEN" = "your_bot_token_here" ]; then
    warn "Discord token not set — edit .env before starting"
    ERRORS=$((ERRORS + 1))
else
    success "Discord token configured"
fi

# Check agent binary
AGENT_BIN=$(grep "^AGENT_BINARY=" .env 2>/dev/null | cut -d= -f2-)
if [ -n "$AGENT_BIN" ] && command -v "$AGENT_BIN" &>/dev/null; then
    success "Agent CLI found: $(command -v "$AGENT_BIN")"
elif [ -n "$AGENT_BIN" ] && [ -x "$AGENT_BIN" ]; then
    success "Agent CLI found: ${AGENT_BIN}"
else
    warn "Agent CLI not found: ${AGENT_BIN:-<not set>}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check working directory
WORK_DIR=$(grep "^AGENT_WORKING_DIR=" .env 2>/dev/null | cut -d= -f2-)
if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
    success "Working directory exists: ${WORK_DIR}"
else
    warn "Working directory not found: ${WORK_DIR:-<not set>}"
    WARNINGS=$((WARNINGS + 1))
fi

# Quick import test
info "Running import check..."
if python -c "from src.config import settings" 2>/dev/null; then
    success "Python imports OK"
else
    warn "Import check failed — some modules may have issues"
    WARNINGS=$((WARNINGS + 1))
fi

# ── Summary ───────────────────────────────────────────────────
echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}${BOLD}  ▲ Installation complete with ${ERRORS} error(s)${RESET}"
    echo -e "    ${DIM}Fix the issues above, then run ./run.sh${RESET}"
elif [ "$WARNINGS" -gt 0 ]; then
    echo -e "${GREEN}${BOLD}  ✔ Installation complete${RESET} ${DIM}(${WARNINGS} warning(s))${RESET}"
else
    echo -e "${GREEN}${BOLD}  ✔ Installation complete!${RESET}"
fi

echo ""
echo -e "  ${DIM}┌──────────────────────────────────────────────┐${RESET}"
echo -e "  ${DIM}│${RESET}  ${BOLD}Quick Reference${RESET}                             ${DIM}│${RESET}"
echo -e "  ${DIM}│${RESET}                                              ${DIM}│${RESET}"
echo -e "  ${DIM}│${RESET}  ${CYAN}./run.sh${RESET}      Start bot (background)        ${DIM}│${RESET}"
echo -e "  ${DIM}│${RESET}  ${CYAN}./status.sh${RESET}   Check status / uptime          ${DIM}│${RESET}"
echo -e "  ${DIM}│${RESET}  ${CYAN}./stop.sh${RESET}     Graceful shutdown (SIGTERM)    ${DIM}│${RESET}"
echo -e "  ${DIM}│${RESET}  ${CYAN}./kill.sh${RESET}     Force kill (SIGKILL)           ${DIM}│${RESET}"
echo -e "  ${DIM}│${RESET}                                              ${DIM}│${RESET}"
echo -e "  ${DIM}│${RESET}  ${DIM}Logs:${RESET}  tail -f bot.log                      ${DIM}│${RESET}"
echo -e "  ${DIM}│${RESET}  ${DIM}Config:${RESET} nano .env                            ${DIM}│${RESET}"
echo -e "  ${DIM}└──────────────────────────────────────────────┘${RESET}"
echo ""
