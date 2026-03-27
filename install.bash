#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.build-venv"

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# ── Aggressively remove every trace of a previous rclonecli install ──

# 1. pip3 system-level uninstall (repeat until gone)
while sudo pip3 show rclonecli &> /dev/null 2>&1; do
    echo "Removing system-level rclonecli via pip3..."
    sudo pip3 uninstall -y rclonecli --break-system-packages
done

# 2. pip3 user-level uninstall (repeat until gone)
while pip3 show rclonecli &> /dev/null 2>&1; do
    echo "Removing user-level rclonecli via pip3..."
    pip3 uninstall -y rclonecli --break-system-packages 2>/dev/null || true
done

# 3. pipx uninstall
if command -v pipx &> /dev/null && pipx list 2>/dev/null | grep -q rclonecli; then
    echo "Removing rclonecli via pipx..."
    pipx uninstall rclonecli 2>/dev/null || true
fi

# 4. uv uninstall
if command -v uv &> /dev/null; then
    uv pip uninstall rclonecli 2>/dev/null || true
fi

# 5. Nuke any leftover .dist-info / .egg-info dirs from all site-packages
echo "Cleaning leftover metadata from site-packages..."
for sp in $(python3 -c "import site,sys; print(' '.join(site.getsitepackages() + [site.getusersitepackages()]))" 2>/dev/null); do
    sudo rm -rf "$sp"/rclonecli-*.dist-info "$sp"/rclonecli-*.egg-info "$sp"/rclonecli.egg-link 2>/dev/null || true
    sudo rm -rf "$sp"/rcli "$sp"/rcli-*.dist-info 2>/dev/null || true
done

# 6. Remove stale console-script entries from common bin dirs
for bin_dir in /usr/local/bin /usr/bin "$HOME/.local/bin"; do
    if [ -f "$bin_dir/rcli" ]; then
        echo "Removing stale rcli script from $bin_dir..."
        sudo rm -f "$bin_dir/rcli" 2>/dev/null || rm -f "$bin_dir/rcli" 2>/dev/null || true
    fi
done

# ── Build fresh ──

# Clean old build artifacts so only the fresh wheel gets installed
rm -rf "$SCRIPT_DIR/dist/" "$SCRIPT_DIR/build/" "$SCRIPT_DIR"/*.egg-info
rm -rf "$VENV_DIR"

# Create a new venv and install build dependencies
echo "Creating build environment..."
uv venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
uv pip install build

# Stamp the copyright year at build time
echo "BUILD_YEAR = $(date +%Y)" > "$SCRIPT_DIR/rcli/_buildinfo.py"

# Build the package
echo "Building package..."
python3 -m build .

# Deactivate and clean up the build venv
deactivate
rm -rf "$VENV_DIR"

# ── Install ──

echo "Installing package..."
sudo pip3 install --force-reinstall --no-deps --break-system-packages dist/*.whl
sudo pip3 install --break-system-packages dist/*.whl

echo "Done!"
