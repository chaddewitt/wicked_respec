#!/usr/bin/env bash
# Build a standalone Linux (x86_64) onedir binary of Wicked Respec with PyInstaller.
# Run inside a Linux environment (native, or Windows WSL). Requires sudo for apt deps.
#
#   bash scripts/build_linux.sh
#
# Output: dist/Wicked Respec/  and  Wicked-Respec-linux-x86_64.tar.gz
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
echo "REPO=$REPO"

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

# 1. System deps: Tcl/Tk (for tkinter) + venv.
$SUDO apt-get update -qq
$SUDO apt-get install -y python3-tk python3-venv >/dev/null

# 2. Stage a clean build tree in $HOME (faster + avoids NTFS perms under /mnt/c).
BUILD="$HOME/wr_build"
rm -rf "$BUILD"
mkdir -p "$BUILD/assets"
cp -r "$REPO/src" "$BUILD/src"
# The Zstd dictionary is gitignored; fetch it on a fresh clone.
if [ ! -f "$REPO/assets/cerimal_zstd.dict" ]; then
  echo "Zstd dictionary missing - downloading..."
  python3 "$REPO/scripts/fetch_dict.py"
fi
cp "$REPO/assets/cerimal_zstd.dict" "$BUILD/assets/cerimal_zstd.dict"
cd "$BUILD"

# 3. Venv + build deps.
python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet pyinstaller zstandard

# 4. Build onedir. NOTE: Linux uses ':' as the --add-data separator (Windows uses ';').
./.venv/bin/pyinstaller --onedir --noconfirm \
  --name "wicked-respec" \
  --add-data "assets/cerimal_zstd.dict:." \
  --paths . src/main.py

# 5. Verify the artifact, then package as tar.gz back in the repo dir.
test -f "dist/wicked-respec/wicked-respec"
test -f "dist/wicked-respec/_internal/cerimal_zstd.dict"
OUT="$REPO/Wicked-Respec-linux-x86_64.tar.gz"
rm -f "$OUT"
tar -czf "$OUT" -C dist "wicked-respec"
echo "ARTIFACT: $OUT"
ls -l "$OUT"
file "dist/wicked-respec/wicked-respec" 2>/dev/null || true
echo "LINUX BUILD OK"
