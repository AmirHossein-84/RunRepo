#!/usr/bin/env bash
set -e

# RunRepo Automated Installer for Linux, WSL 2, and macOS
echo "========================================"
echo "    RunRepo Automated Installation     "
echo "========================================"

# 1. Check for curl
if ! command -v curl &> /dev/null; then
    echo "[!] Error: 'curl' is required but not installed."
    echo "    Install curl using your package manager (e.g. sudo apt install curl) and retry."
    exit 1
fi

# 2. Check and install uv if missing
if ! command -v uv &> /dev/null; then
    echo "[*] 'uv' is not installed. Installing uv (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Export PATH for current session
    if [ -d "$HOME/.local/bin" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    fi
    if [ -d "$HOME/.cargo/bin" ]; then
        export PATH="$HOME/.cargo/bin:$PATH"
    fi
fi

if ! command -v uv &> /dev/null; then
    echo "[!] Warning: 'uv' was installed to ~/.local/bin or ~/.cargo/bin."
    echo "    Please run: source \$HOME/.local/bin/env  or restart your terminal."
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

# 3. Locate RunRepo repository directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] Installing RunRepo globally via uv tool..."
uv tool install -e . --force

echo ""
echo "========================================"
echo " [✓] RunRepo successfully installed!   "
echo "========================================"
echo ""
echo "Try running:"
echo "  runrepo doctor"
echo "  runrepo setup https://github.com/owner/project"
echo ""
