# 🪄 WoL-Caster v1.0.0

**Wake-on-LAN Network Broadcaster**

Automatically detect all your network interfaces and cast Wake-on-LAN magic packets!

## ✨ Features

### 🎭 **Dual Interface Modes**
- **GUI Mode**: Beautiful dark-themed interface with real-time device discovery
- **CLI Mode**: Command-line interface with parallel scanning and progress bars
- **Smart Auto-Detection**: Automatically chooses the best mode for your environment

### 🔮 **Advanced Network Discovery**
- **Parallel Scanning**: Multi-threaded device discovery for lightning-fast results
- **Live Updates**: Real-time device status updates during scanning
- **Persistent Storage**: Remembers discovered devices and network states
- **Multi-Interface Support**: Discovers devices across all network adapters

### 🎯 **Intelligent Target Selection**
- **Network-Wide Casting**: Target entire subnets for comprehensive coverage
- **Individual Device Targeting**: Select specific devices for precision
- **Redundant Target Handling**: Honors both network and device selections (see details below)
- **Session-Based Selection**: Maintains selections during current CLI session

### 🪄 **Efficient Magic Packet Delivery**
- **Parallel Broadcasting**: Sends packets concurrently for maximum speed
- **Progress Tracking**: Real-time progress bars for both GUI and CLI
- **Interrupt Support**: Stop operations at any time with graceful cleanup
- **Error Handling**: Robust error handling with user-friendly feedback

### 💾 **Persistent Data Management**
- **Export/Import JSON**: Save and restore your discovered devices and selections
- **Smart Data Merging**: Intelligent import that combines new and existing data
- **Format Validation**: Ensures imported JSON files are compatible
- **Duplicate Handling**: Automatically manages duplicate devices during import

## 🏰 **Magical Theme**

WoL-Caster embraces a mystical, magical aesthetic:
- **✨ Start/End Cast** (instead of Broadcast)
- **🔮 Start/End Scry** (instead of Scan)
- **🎯 Arm/Disarm** devices with Bullseye emoji
- **🔥 Clear History** with fire emoji
- **🪄 Wand emoji** in the title

## 🔧 **Installation & Usage**

### **Prerequisites**
```bash
pip3 install -r requirements.txt
```

### **Basic Usage**
```bash
# Smart mode detection (recommended)
python3 wol_caster.py

# Force GUI mode
python3 wol_caster.py --gui

# Force CLI mode
python3 wol_caster.py --cli

# Show version
python3 wol_caster.py --version

# Show help
python3 wol_caster.py --help
```

### **Command-Line Tool Installation**
```bash
# Install as system command
pip3 install -e .

# Available commands
wol              # Main command
wol-cast         # Alternative command
wol-caster       # Alternative command
wolcast          # Alternative command
wolcaster        # Alternative command
```

## 🎯 **Target Selection & Redundancy Handling**

### **Understanding Target Calculation**

WoL-Caster provides complete transparency in target selection:

```
Current selections:
   Networks: 1
   Devices: 5
   Total Targets: ~259 addresses
```

### **Redundant Target Behavior**

**Important**: WoL-Caster honors ALL selected targets without automatic deduplication:

1. **Network Selection**: Sends magic packets to ALL IPs in the subnet
2. **Individual Device Selection**: Sends magic packets to specific devices
3. **Combined Selection**: If a device is both in a selected network AND individually selected, it receives **TWO magic packets**

### **Why This Design?**

- **Network Coverage**: Ensures no devices are missed in the subnet
- **Targeted Delivery**: Provides specific, reliable delivery to chosen devices
- **Redundancy Benefits**: Multiple packets can improve wake-up reliability
- **User Control**: Gives users complete control over their targeting strategy

### **Example Scenario**
```
Network: 192.168.1.0/24 (254 addresses)
Individual Device: 192.168.1.100

Target Total: ~255 addresses
Actual Packets Sent: 255 packets
- 254 packets to network (including 192.168.1.100)
- 1 packet to individual device 192.168.1.100

Result: Device 192.168.1.100 receives 2 magic packets
```

## 🖥️ **GUI Features**

### **Real-Time Device Discovery**
- **Live Updates**: See devices appear as they're discovered
- **Status Indicators**: Visual status for online, offline, and standby devices
- **Network Trees**: Hierarchical view of networks and their devices
- **Selection Management**: Click to select/deselect networks and devices

### **Smart Interface**
- **Hidden Scrollbars**: Clean interface with full scroll functionality
- **Keyboard Navigation**: Arrow keys, Page Up/Down, Home/End for scrolling
- **Mouse Wheel Support**: Smooth scrolling with mouse wheel
- **Persistent States**: Remembers tree expansion and device selections

### **Progress Tracking**
- **Real-Time Progress**: Live progress bars during casting operations
- **Status Updates**: Current operation status and completion percentage
- **Operation Control**: Start, stop, and monitor casting operations

### **Data Management**
- **Export JSON**: Save your discovered devices and selections to a file
- **Import JSON**: Load previously saved data with intelligent merging
- **Clear History**: Reset all persistent data and start fresh

## 💻 **CLI Features**

### **Enhanced User Experience**
- **Auto-Terminal Resize**: Automatically resizes small terminals for optimal experience
- **Smart Terminal Launch**: Opens new terminal windows only when necessary
- **Single-Character Input**: Use numbers 1-9 for menu navigation
- **Smooth Progress Bars**: Python-style progress bars that update in-place
- **Parallel Processing**: Multi-threaded scanning for maximum speed

### **Menu System**
```
📋 MAIN MENU
============================================================
1. 🔮 Scry Networks for Devices
2. 👁️  View Discovered Devices
3. 🎯  Arm/Disarm Targets
4. 📋 View Selected Targets
5. 🪄 Start Wake-on-LAN Cast
6. 🔥 Clear All Selections
7. 📄 Print Persistent Data (JSON)
8. 🔧 Debug Mode ON/OFF
9. 🚪 Exit
============================================================
```

### **Device Discovery**
- **Parallel Scanning**: 50 concurrent threads for maximum speed
- **Progress Tracking**: Real-time progress bars with smooth animation
- **Complete Device Lists**: Shows ALL discovered devices (no truncation)
- **Selection Indicators**: Clear visual feedback for selected targets

### **Terminal Intelligence**
- **Size Detection**: Automatically detects if terminal is too small
- **Resize Attempt**: First tries to resize the current terminal
- **Smart Fallback**: Only launches new terminal if resize fails
- **Seamless Experience**: Maintains CLI state during terminal operations

## 🪄 **Performance Features**

### **Parallel Processing**
- **Network Scanning**: 50 concurrent threads for device discovery
- **Packet Broadcasting**: Parallel magic packet delivery
- **Progress Updates**: Real-time completion tracking

### **Optimized Timeouts**
- **Fast Ping**: 500ms timeout for online device detection
- **Quick Port Check**: 200ms timeout for standby device detection
- **Efficient ARP**: 1-second timeout for MAC address resolution

### **Memory Management**
- **Persistent Storage**: JSON-based device and state persistence
- **Efficient Data Structures**: Optimized for large network scanning
- **Graceful Cleanup**: Proper resource management and cleanup

## 🔒 **Security & Reliability**

### **Network Safety**
- **Broadcast-Only**: Sends only Wake-on-LAN magic packets
- **No Data Collection**: Only discovers device presence, no sensitive data
- **Local Network**: Operates only on local network interfaces

### **Error Handling**
- **Graceful Degradation**: Falls back to CLI if GUI fails
- **Exception Recovery**: Continues operation after individual failures
- **User Feedback**: Clear error messages and status updates

### **Data Persistence**
- **Local Storage**: All data stored locally in user's home directory
- **No Cloud Services**: Complete privacy and offline operation
- **Configurable**: Easy to clear history and reset state

## 🛠️ **Technical Details**

### **Supported Platforms**
- **macOS**: Native support with custom menu bar and AppleScript terminal launching
- **Linux**: Full compatibility with standard terminal operations
- **Windows**: Basic compatibility (see note below)

**Note on Windows**: While WoL-Caster is designed to work on Windows, some features may have limitations:
- Network interface detection may differ from Unix-based systems
- Terminal handling and auto-resize features are optimized for Unix/macOS
- NetBIOS discovery tools may not be available on all Windows installations

### **Network Protocols**
- **Wake-on-LAN**: Standard magic packet format
- **ARP Resolution**: MAC address discovery
- **ICMP Ping**: Device status detection
- **TCP Port Scanning**: Standby device detection

### **Dependencies**
```
netifaces      # Network interface detection
ipaddress     # IP address manipulation
concurrent.futures  # Parallel processing
tkinter       # GUI framework
pyobjc-framework-Cocoa  # macOS menu integration (macOS only)
```

**Note**: All dependencies are automatically installed via `pip3 install -r requirements.txt`. Built-in Python modules (tkinter, concurrent.futures) are gracefully skipped by pip.

## 🍎 **macOS Menu Customization**

### **Custom Menu Bar**
WoL-Caster features a custom macOS menu bar that provides a native app experience:

- **Clean Design**: Only essential menus (WoL-Caster, File, Edit, Help)
- **Native About**: Professional About dialog with copyright information
- **File Operations**: Import/Export JSON functionality
- **Edit Functions**: Clear history and manage persistent data
- **Quit Option**: Standard macOS quit functionality with keyboard shortcut (⌘Q)

### **Technical Implementation**
The menu customization is implemented using:
- **Tkinter Integration**: Native-looking menus built with Tkinter
- **PyInstaller Configuration**: `force_menu_bar=False` for custom control
- **Info.plist Customization**: Enhanced metadata for native About dialog

### **Building the App**
To build the macOS app bundle:

```bash
# Build the app
./build_app.sh

# Run the app
open dist/WoL-Caster.app

# Move to Applications (optional)
cp -r dist/WoL-Caster.app /Applications/
```

**Note**: The `/Applications/` directory supports persistent data writes without authorization on macOS, making it safe for app installation.

## 📝 **Version History**

### **v1.0.0 (Current)**
- **Complete GUI/CLI dual-mode implementation**
- **Parallel network scanning with live updates**
- **Intelligent target selection and redundancy handling**
- **Magical theme with emojis and mystical terminology**
- **Auto-terminal resizing and smart terminal launching**
- **Persistent data storage with Export/Import JSON**
- **Professional-grade error handling and user experience**
- **Custom macOS menu bar with native About dialog**
- **CLI auto-resize and intelligent terminal management**

## 🤝 **Contributing**

WoL-Caster is developed with a focus on:
- **User Experience**: Intuitive interfaces and clear feedback
- **Performance**: Efficient algorithms and parallel processing
- **Reliability**: Robust error handling and graceful degradation
- **Aesthetics**: Beautiful, themed interfaces that delight users

## 📄 **License**

**MIT License** - Developed by **Cardigans of the Galaxy** with ❤️ for the Wake-on-LAN community.

---

**🪄✨ Happy Casting!!**