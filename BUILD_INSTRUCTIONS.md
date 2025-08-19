# Building WoL-Caster macOS App Bundle

## Overview
This guide explains how to build a proper macOS application bundle that will show "WoL-Caster" in the dock and menu bar instead of "Python".

## Prerequisites
- Python 3.6+
- PyInstaller
- macOS (for building macOS apps)

## Quick Build

### 1. Install PyInstaller
```bash
pip3 install pyinstaller
```

### 2. Build the App Bundle
```bash
# Simple build command
pyinstaller --onefile --windowed --name "WoL-Caster" --icon "assets/Wol-Caster.icns" wol_caster.py

# Or use the spec file for more control
pyinstaller wol_caster.spec
```

### 3. Run the App
```bash
# Test the built app
open dist/WoL-Caster.app

# Or move to Applications
cp -r dist/WoL-Caster.app /Applications/
```

## What This Achieves

### ✅ **Dock Label**: Shows "WoL-Caster" instead of "Python"
### ✅ **Menu Bar**: Custom WoL-Caster menu with professional options
### ✅ **Export Devices**: Save device lists as TXT, CSV, or JSON
### ✅ **Professional Interface**: Native macOS app experience

## Menu Features

### **WoL-Caster Menu**
- About WoL-Caster
- Preferences
- Quit WoL-Caster (Cmd+Q)

### **File Menu**
- Export Device List... (Cmd+E)
- Import Device List...
- Clear History

### **View Menu**
- Toggle Fullscreen (Cmd+F)
- Zoom In/Out (Cmd+=, Cmd+-)
- Actual Size (Cmd+0)

### **Tools Menu**
- Network Diagnostics
- Device Statistics
- Wake All Devices
- Wake Selected Devices

### **Window Menu**
- Minimize (Cmd+M)
- Zoom
- Bring All to Front

### **Help Menu**
- WoL-Caster Help
- Network Troubleshooting
- About WoL-Caster

## Export Device List Feature

The Export Device List functionality allows you to save all discovered devices to:

- **TXT files**: Human-readable formatted text
- **CSV files**: Spreadsheet-compatible format
- **JSON files**: Structured data format

### Export Includes:
- Interface name
- IP address
- Hostname
- MAC address
- Device status
- Vendor information
- Last seen timestamp

## Troubleshooting

### Build Issues
- Ensure PyInstaller is installed: `pip3 install pyinstaller`
- Check that all assets exist in the `assets/` folder
- Verify Python path and dependencies

### Runtime Issues
- Check network permissions for the app
- Ensure firewall allows network discovery
- Verify the app has access to network interfaces

## Advanced Customization

### Custom Icon
Replace `assets/Wol-Caster.icns` with your own icon file.

### Bundle Identifier
Modify the bundle identifier in `wol_caster.spec`:
```python
bundle_identifier='com.yourcompany.wol-caster'
```

### App Category
Change the app category in `wol_caster.spec`:
```python
'LSApplicationCategoryType': 'public.app-category.utilities'
```

## Distribution

### Local Use
- Copy the `.app` file to your Applications folder
- Launch from Spotlight or Applications folder

### Distribution
- Zip the `.app` file for sharing
- Consider code signing for distribution
- Test on target macOS versions

## Support

For issues or questions:
- Check the main README.md
- Review the PyInstaller documentation
- Ensure all dependencies are properly installed




