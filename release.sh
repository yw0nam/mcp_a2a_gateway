#!/bin/bash
# Release script for MCP-A2A-Gateway
# Usage: ./release.sh [patch|minor|major]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default to patch if no argument provided
VERSION_TYPE=${1:-patch}

echo -e "${BLUE}🚀 Starting release process for MCP-A2A-Gateway${NC}"

# Check if we're on main branch
current_branch=$(git branch --show-current)
if [ "$current_branch" != "main" ]; then
    echo -e "${RED}❌ Error: Must be on main branch to create a release${NC}"
    echo -e "${YELLOW}Current branch: $current_branch${NC}"
    exit 1
fi

# Check if working directory is clean
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${RED}❌ Error: Working directory is not clean${NC}"
    echo -e "${YELLOW}Please commit or stash your changes first${NC}"
    git status --short
    exit 1
fi

# Get current version from pyproject.toml
current_version=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo -e "${BLUE}📋 Current version: $current_version${NC}"

# Calculate new version based on semantic versioning
IFS='.' read -r major minor patch <<< "$current_version"

case $VERSION_TYPE in
    major)
        new_version="$((major + 1)).0.0"
        ;;
    minor)
        new_version="$major.$((minor + 1)).0"
        ;;
    patch)
        new_version="$major.$minor.$((patch + 1))"
        ;;
    *)
        echo -e "${RED}❌ Error: Invalid version type. Use 'major', 'minor', or 'patch'${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}📈 New version: $new_version${NC}"

# Confirm the release
read -p "$(echo -e ${YELLOW}Continue with release $new_version? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Release cancelled${NC}"
    exit 1
fi

# Update version in pyproject.toml
echo -e "${BLUE}📝 Updating version in pyproject.toml${NC}"
sed -i.bak "s/version = \"$current_version\"/version = \"$new_version\"/" pyproject.toml
rm pyproject.toml.bak

# Build and test the package
echo -e "${BLUE}🔨 Building package${NC}"
uv build

echo -e "${BLUE}🧪 Testing package installation${NC}"
# Test that the package can be imported without starting the server
uvx --from dist/mcp_a2a_gateway-${new_version}-py3-none-any.whl python -c "
import mcp_a2a_gateway
from mcp_a2a_gateway.main import main
print('✅ Package imports successfully')
"

# Commit the version change
echo -e "${BLUE}📤 Committing version bump${NC}"
git add pyproject.toml
git commit -m "chore: bump version to $new_version"

# Create and push tag
echo -e "${BLUE}🏷️  Creating and pushing tag${NC}"
git tag "v$new_version"
git push origin main
git push origin "v$new_version"

echo -e "${GREEN}✅ Release $new_version completed!${NC}"
echo -e "${BLUE}📋 Next steps:${NC}"
echo -e "   1. GitHub Actions will automatically publish to PyPI"
echo -e "   2. Check the Actions tab: https://github.com/yw0nam/MCP-A2A-Gateway/actions"
echo -e "   3. Create a GitHub release: https://github.com/yw0nam/MCP-A2A-Gateway/releases/new?tag=v$new_version"
echo -e "   4. Test the published package: ${GREEN}uvx mcp-a2a-gateway==$new_version${NC}"
