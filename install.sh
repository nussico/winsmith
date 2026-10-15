#!/bin/sh
# Winsmith installer for Linux:  curl -fsSL https://raw.githubusercontent.com/nussico/winsmith/main/install.sh | sh
set -e
SRC="https://github.com/nussico/winsmith/archive/refs/heads/main.zip"

if command -v uv >/dev/null 2>&1; then
    uv tool install --force "$SRC"
elif command -v pipx >/dev/null 2>&1; then
    pipx install --force "$SRC"
    pipx ensurepath >/dev/null
else
    echo "Needs pipx or uv. Install one, then run this again:"
    echo "  Debian/Ubuntu: sudo apt install pipx     Fedora: sudo dnf install pipx     Arch: sudo pacman -S python-pipx"
    exit 1
fi

echo
echo "Done. Start it with:  winsmith   (open a new terminal if the command is not found)"
for tool in 7z xorriso; do
    command -v "$tool" >/dev/null 2>&1 || echo "Writing the ISO also needs $tool, e.g.: sudo apt install 7zip xorriso"
done
