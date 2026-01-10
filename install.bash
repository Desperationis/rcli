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

# Clean up any existing build venv
rm -rf "$VENV_DIR"

# Create a new venv and install build dependencies
echo "Creating build environment..."
uv venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
uv pip install build

# Build the package
echo "Building package..."
python3 -m build .

# Deactivate the venv
deactivate

# Clean up the build venv
rm -rf "$VENV_DIR"

# Install globally with pip
echo "Installing package..."
pip3 install --break-system-packages dist/*.whl --force-reinstall

echo "Done!"
