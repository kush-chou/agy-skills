#!/usr/bin/env bash
# agy-skills turnkey installer
# https://agy-skills.sh / https://agy-skills.com
set -euo pipefail

# Colors and formatting
BOLD="$(tput bold 2>/dev/null || echo '')"
RESET="$(tput sgr0 2>/dev/null || echo '')"
CYAN="$(tput setaf 6 2>/dev/null || echo '')"
GREEN="$(tput setaf 2 2>/dev/null || echo '')"
YELLOW="$(tput setaf 3 2>/dev/null || echo '')"
RED="$(tput setaf 1 2>/dev/null || echo '')"
DIM="$(tput dim 2>/dev/null || echo '')"

echo ""
echo "${CYAN}${BOLD}    ⚡ agy-skills — Antigravity Context & Skills Manager${RESET}"
echo "${DIM}    Keyboard-first package manager for Google Antigravity & AI Coding Agents${RESET}"
echo ""

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "==> Detecting host environment..."
echo "    OS:   ${OS} (${ARCH})"

PYTHON_BIN=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
            PYTHON_BIN="$(command -v "$cmd")"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "${RED}Error: Python 3.9 or newer is required to run agy-skills.${RESET}"
    echo "Please install Python via brew (macOS) or apt/dnf (Linux), then re-run this script."
    exit 1
fi

echo "    Python: ${PYTHON_BIN} (${VER})"

INSTALL_DIR="${HOME}/.local/share/agy-skills"
BIN_DIR="${HOME}/.local/bin"
mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"

echo "==> Installing agy-skills to ${INSTALL_DIR}..."

REPO_URL="https://github.com/kush-chou/agy-skills.git"

if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "    Updating existing installation..."
    git -C "${INSTALL_DIR}" fetch --quiet origin main 2>/dev/null || true
    git -C "${INSTALL_DIR}" reset --hard origin/main --quiet 2>/dev/null || true
else
    echo "    Cloning repository..."
    rm -rf "${INSTALL_DIR}"
    if command -v git >/dev/null 2>&1; then
        git clone --quiet --depth=1 "${REPO_URL}" "${INSTALL_DIR}" 2>/dev/null || {
            echo "${YELLOW}Git clone failed, downloading archive...${RESET}"
            curl -fsSL "https://github.com/kush-chou/agy-skills/archive/refs/heads/main.tar.gz" | tar -xz -C "${HOME}/.local/share"
            mv "${HOME}/.local/share/agy-skills-main" "${INSTALL_DIR}"
        }
    else
        echo "${YELLOW}Git not found, downloading archive...${RESET}"
        curl -fsSL "https://github.com/kush-chou/agy-skills/archive/refs/heads/main.tar.gz" | tar -xz -C "${HOME}/.local/share"
        mv "${HOME}/.local/share/agy-skills-main" "${INSTALL_DIR}"
    fi
fi

cat << 'EOF' > "${BIN_DIR}/agy-skills"
#!/bin/sh
set -e
DIR="${HOME}/.local/share/agy-skills"
export PYTHONPATH="${DIR}:${PYTHONPATH:-}"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" -m agy_skills.main "$@"
EOF

chmod +x "${BIN_DIR}/agy-skills"
ln -sf "${BIN_DIR}/agy-skills" "${BIN_DIR}/agy-skill" 2>/dev/null || true

PATH_OK=false
case ":$PATH:" in
    *":${BIN_DIR}:"*) PATH_OK=true ;;
esac

echo ""
echo "${GREEN}${BOLD}✔ Successfully installed agy-skills!${RESET}"
echo ""

if [ "$PATH_OK" = false ]; then
    echo "${YELLOW}${BOLD}⚠️  Action Required: Add ~/.local/bin to your PATH${RESET}"
    echo "Add the following line to your shell configuration file (~/.zshrc or ~/.bashrc):"
    echo ""
    echo "    ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    echo ""
    echo "Then reload your shell: ${DIM}source ~/.zshrc${RESET} (or ${DIM}source ~/.bashrc${RESET})"
    echo ""
fi

echo "${BOLD}Quick Start:${RESET}"
echo "  • Launch interactive TUI:      ${CYAN}agy-skills${RESET}"
echo "  • List all skills & context:   ${CYAN}agy-skills list${RESET}"
echo "  • Search skill marketplace:    ${CYAN}agy-skills search <query>${RESET}"
echo "  • Lint Antigravity compliance: ${CYAN}agy-skills lint${RESET}"
echo "  • Inspect MCP servers:         ${CYAN}agy-skills mcp${RESET}"
echo ""
echo "Documentation & Marketplace: ${CYAN}https://agy-skills.sh${RESET}"
echo ""
