#!/bin/bash

# Build WoL-Caster macOS App Bundle
echo "🔮 Building WoL-Caster macOS App Bundle..."

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "❌ PyInstaller not found. Installing..."
    pip3 install pyinstaller
fi

# Menu configuration test skipped (logic now built into wol_caster.py)
echo "🧪 Menu configuration test skipped (logic now built into wol_caster.py)"

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/ __pycache__/

# Build the app bundle
echo "🏗️  Building with PyInstaller..."
pyinstaller WoL-Caster.spec

# Check if build was successful
if [ -d "dist/WoL-Caster.app" ]; then
    echo "✅ Build successful!"
    echo "🎯 App bundle created at: dist/WoL-Caster.app"
    echo "🚀 You can now drag this to your Applications folder or run it directly!"
    echo ""
    echo "To run the app:"
    echo "  open dist/WoL-Caster.app"
    echo ""
    echo "To move to Applications:"
    echo "  cp -r dist/WoL-Caster.app /Applications/"
    
    # Cleanup build artifacts
    echo ""
    echo "🧹 Cleaning up build artifacts..."
    rm -rf build/ __pycache__/
    
else
    echo "❌ Build failed!"
    exit 1
fi




