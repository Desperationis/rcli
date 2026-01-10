#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Extract version from rcli/__init__.py
VERSION=$(grep -oP '__version__\s*=\s*"\K[^"]+' rcli/__init__.py)

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}       rclonecli PyPI Uploader${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "Package: ${GREEN}rclonecli${NC}"
echo -e "Version: ${GREEN}${VERSION}${NC}"
echo ""

# Check for required tools
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: $1 is not installed.${NC}"
        echo -e "Install with: ${YELLOW}pip install $2${NC}"
        exit 1
    fi
}

check_tool "python3" "python3"
check_tool "twine" "twine"

# Confirm before proceeding
echo -e "${YELLOW}This script will:${NC}"
echo "  1. Clean old build artifacts"
echo "  2. Build the package"
echo "  3. Upload to PyPI"
echo ""
read -p "Continue? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Clean old builds
echo ""
echo -e "${CYAN}Cleaning old build artifacts...${NC}"
rm -rf dist/ build/ *.egg-info rcli.egg-info/
echo -e "${GREEN}Done.${NC}"

# Build the package
echo ""
echo -e "${CYAN}Building package...${NC}"
python3 -m build .
echo -e "${GREEN}Build complete.${NC}"

# Show built files
echo ""
echo -e "${CYAN}Built files:${NC}"
ls -la dist/

# Choose repository
echo ""
echo -e "${YELLOW}Where would you like to upload?${NC}"
echo "  1) TestPyPI (for testing)"
echo "  2) PyPI (production)"
echo ""
read -p "Enter choice (1 or 2): " repo_choice

case $repo_choice in
    1)
        REPO_URL="https://test.pypi.org/legacy/"
        REPO_NAME="TestPyPI"
        VIEW_URL="https://test.pypi.org/project/rclonecli/${VERSION}/"
        ;;
    2)
        REPO_URL="https://upload.pypi.org/legacy/"
        REPO_NAME="PyPI"
        VIEW_URL="https://pypi.org/project/rclonecli/${VERSION}/"
        ;;
    *)
        echo -e "${RED}Invalid choice. Aborted.${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${YELLOW}Uploading to ${REPO_NAME}...${NC}"
echo -e "${YELLOW}You may be prompted for your API token.${NC}"
echo ""

if [[ "$repo_choice" == "1" ]]; then
    twine upload --repository-url "$REPO_URL" dist/*
else
    twine upload dist/*
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Upload complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "View your package at:"
echo -e "${CYAN}${VIEW_URL}${NC}"
echo ""
echo -e "Install with:"
if [[ "$repo_choice" == "1" ]]; then
    echo -e "${CYAN}pip install -i https://test.pypi.org/simple/ rclonecli==${VERSION}${NC}"
else
    echo -e "${CYAN}pip install rclonecli==${VERSION}${NC}"
fi
