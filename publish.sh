#!/bin/bash
# Manual publish script for MCP-A2A-Gateway
# Use this for emergency publishes or when automated release fails

set -e

echo "📦 Building package..."
uv build

echo ""
echo "🔍 Package contents:"
ls -la dist/

echo ""
echo "🧪 Testing package installation locally..."
latest_wheel=$(ls dist/*.whl | head -1)
if [ -f "$latest_wheel" ]; then
    echo "Testing: $latest_wheel"
    uvx --from "$latest_wheel" mcp-a2a-gateway --help > /dev/null && echo "✅ Package test successful"
else
    echo "❌ No wheel file found"
    exit 1
fi

echo ""
echo "📋 Publishing options:"
echo ""
echo "1. 🧪 Test on TestPyPI first (recommended):"
echo "   export UV_PUBLISH_USERNAME='__token__'"
echo "   export UV_PUBLISH_PASSWORD='pypi-your-testpypi-token-here'"
echo "   uv publish --publish-url https://test.pypi.org/legacy/"
echo ""
echo "2. 🚀 Publish to PyPI:"
echo "   export UV_PUBLISH_USERNAME='__token__'"
echo "   export UV_PUBLISH_PASSWORD='pypi-your-pypi-token-here'"
echo "   uv publish"
echo ""
echo "3. 📤 Using twine:"
echo "   pip install twine"
echo "   twine upload dist/*"
echo ""
echo "📝 After publishing:"
echo "   - Wait 5-10 minutes for PyPI to process"
echo "   - Test with: uvx mcp-a2a-gateway"
echo "   - Update documentation with new installation instructions"
echo ""
echo "🔗 Get your API tokens:"
echo "   - PyPI: https://pypi.org/manage/account/token/"
echo "   - TestPyPI: https://test.pypi.org/manage/account/token/"
echo ""
echo "💡 For automated releases, use: ./release.sh [patch|minor|major]"