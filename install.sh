#!/usr/bin/env bash
# agy-skills one-line installer
set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "${INSTALL_DIR}"

REPO_DIR="${HOME}/.gemini/antigravity/scratch/agy-skills"

if [ ! -d "${REPO_DIR}" ]; then
  echo "Cloning agy-skills..."
  git clone https://github.com/kush-chou/agy-skills "${REPO_DIR}"
fi

echo "Linking agy-skills into ${INSTALL_DIR}..."
cat << 'EOF' > "${INSTALL_DIR}/agy-skills"
#!/usr/bin/env bash
python3 -m agy_skills.cli "$@"
EOF

chmod +x "${INSTALL_DIR}/agy-skills"
ln -sf "${INSTALL_DIR}/agy-skills" "${INSTALL_DIR}/agy-skill"

echo "✅ agy-skills installed successfully to ${INSTALL_DIR}/agy-skills"
echo "Run 'agy-skills list' to get started."
