#!/usr/bin/env python3
"""
WoL-Caster - Wake-on-LAN Network Broadcaster with Magical GUI & CLI
A powerful, intelligent cross-platform utility that automatically detects all your network interfaces
and casts Wake-on-LAN magic packets with a beautiful, mystical interface.
"""

__version__ = "1.0.0"
__author__ = "Cardigans of the Galaxy"
__description__ = "Wake-on-LAN Network Broadcaster with Perfect GUI & CLI Interrupt"

# Standard library imports
import ipaddress
import json
import os
import pickle
import platform
import re
import select
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Third-party imports
import netifaces

# Smart GUI detection
GUI_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

def is_gui_mode():
    """Determine if we should run in GUI mode."""
    # Force CLI mode if --cli argument is passed
    if '--cli' in sys.argv or '-c' in sys.argv:
        return False

    # Force GUI mode if --gui argument is passed
    if '--gui' in sys.argv or '-g' in sys.argv:
        return GUI_AVAILABLE

    # Check if we're being run from a terminal or as an app
    if not GUI_AVAILABLE:
        return False

    # On macOS, check if we're running as an app bundle
    if platform.system() == 'Darwin':
        if os.path.basename(sys.argv[0]).endswith('.app'):
            return True
        # Check if we're in an app bundle structure
        if '/Applications/' in sys.executable or '.app/Contents/' in sys.executable:
            return True

    # On Windows, check if we're running as an executable without console
    if platform.system() == 'Windows':
        try:
            # If we can't write to stdout, we're likely running without console (windowed mode)
            sys.stdout.write('')
            sys.stdout.flush()
        except Exception:
            return True

        # Check if we were launched by double-clicking
        if hasattr(sys, 'frozen') and not os.environ.get('PROMPT'):
            return True

    # Check if stdout is connected to a terminal
    if not sys.stdout.isatty():
        return True

    # Check for GUI environment variables
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        # If we have a display but no terminal session indicators, prefer GUI
        if not any(var in os.environ for var in ['TERM', 'SSH_CLIENT', 'SSH_TTY']):
            return True

    # Default to CLI mode for terminal usage
    return False

def get_terminal_size():
    """Get terminal dimensions with fallback."""
    try:
        return shutil.get_terminal_size()
    except Exception:
        try:
            return os.get_terminal_size()
        except Exception:
            # Fallback dimensions
            return os.terminal_size((80, 24))

def try_resize_terminal():
    """Attempt to resize terminal to 100x50."""
    try:
        # Only attempt on macOS and Linux terminals that support it
        if platform.system() in ['Darwin', 'Linux']:
            # Try to resize using ANSI escape sequences
            sys.stdout.write('\033[8;50;100t')
            sys.stdout.flush()
            time.sleep(0.1)  # Give terminal time to resize
            
            # Check if resize was successful
            new_size = get_terminal_size()
            if new_size.columns >= 80 and new_size.lines >= 30:
                print("✅ Terminal resized successfully!")
                print("🔄 Restarting CLI with proper terminal size...")
                time.sleep(1)
                
                # Restart the CLI in the same terminal
                os.execv(sys.executable, ['python3', 'wol_caster.py', '--cli'])
            else:
                print("⚠️  Terminal resize may not have worked completely")
                print("💡 Current size:", f"{new_size.columns}x{new_size.lines}")
    except Exception:
        pass

def should_launch_new_terminal():
    """Check if current terminal is too small for optimal CLI experience."""
    try:
        terminal_size = get_terminal_size()
        # If terminal is too narrow or short, suggest launching new window
        return terminal_size.columns < 80 or terminal_size.lines < 30
    except Exception:
        return False

def launch_proper_terminal():
    """Launch CLI in a new, properly-sized terminal window."""
    try:
        if platform.system() == 'Darwin':  # macOS
            # Get current working directory
            cwd = os.getcwd()
            # Check for both .venv and venv folders
            venv_path = None
            for venv_name in ['.venv', 'venv']:
                test_path = os.path.join(cwd, venv_name, 'bin', 'activate')
                if os.path.exists(test_path):
                    venv_path = test_path
                    break

            if not venv_path:
                venv_path = os.path.join(cwd, '.venv', 'bin', 'activate')  # Default fallback

            # Create AppleScript to launch new Terminal window
            # First activate Terminal, then create new window
            cmd = f"cd '{cwd}' && source '{venv_path}' && python3 wol_caster.py --cli"

            script_parts = [
                'tell application "Terminal"',
                '    activate',
                f'    do script "{cmd}" in front window',
                '    set custom title of front window to "WoL-Caster CLI"',
                '    set bounds of front window to {100, 100, 900, 600}',
                'end tell'
            ]

            # Execute AppleScript
            subprocess.run(['osascript', '-e', '\n'.join(script_parts)], check=True)

            print("🪄 Launching WoL-Caster CLI in new terminal window...")
            print("📱 Current terminal is too small for optimal experience")
            print("✨ New window will have proper sizing for progress bars")
            print("👋 Closing this terminal...")

            # Give user time to read the message
            time.sleep(3)

            # Exit current process
            sys.exit(0)

        else:
            # For other platforms, just show a warning
            print("⚠️  Terminal size may be too small for optimal CLI experience")
            print("💡 Consider resizing your terminal to at least 80x30 characters")
            print("📏 Current size:", get_terminal_size())

    except Exception as e:
        print(f"❌ Could not launch new terminal: {e}")
        print("💡 Please manually resize your terminal or open a new one")

def wrap_text(text, width, indent=0):
    """Wrap text to specified width with optional indent."""
    if len(text) <= width:
        return [text]

    words = text.split()
    lines = []
    current_line = ' ' * indent

    for word in words:
        if len(current_line) + len(word) + 1 <= width:
            if current_line.strip():
                current_line += ' ' + word
            else:
                current_line = ' ' * indent + word
        else:
            if current_line.strip():
                lines.append(current_line)
            current_line = ' ' * indent + word

    if current_line.strip():
        lines.append(current_line)

    return lines

def create_adaptive_separator(char='=', min_width=20):
    """Create a separator that adapts to terminal width."""
    try:
        width = get_terminal_size().columns
        return char * max(min_width, width)
    except Exception:
        return char * min_width

def format_table_row(columns, widths, terminal_width):
    """Format a table row with auto-wrapping support."""
    # Check if the row fits in terminal width
    total_width = sum(widths) + len(widths) - 1  # Account for separators

    if total_width <= terminal_width:
        # Normal formatting
        formatted_columns = []
        for i, (col, width) in enumerate(zip(columns, widths)):
            if len(col) > width:
                col = col[:width-3] + '...'
            formatted_columns.append(col.ljust(width))
        return [' '.join(formatted_columns)]
    else:
        # Multi-line formatting for narrow terminals
        lines = []
        for i, (col, width) in enumerate(zip(columns, widths)):
            label = f"  {chr(65+i)}: "  # A:, B:, C:, etc.
            content_width = terminal_width - len(label)
            if content_width < 10:
                content_width = terminal_width - 4
                label = f"{chr(65+i)}: "

            wrapped_lines = wrap_text(col, content_width)
            if wrapped_lines:
                lines.append(label + wrapped_lines[0])
                for wrap_line in wrapped_lines[1:]:
                    lines.append(' ' * len(label) + wrap_line)

        return lines

def print_adaptive_table(headers, rows, min_col_width=8):
    """Print a table that adapts to terminal width."""
    terminal_size = get_terminal_size()
    terminal_width = terminal_size.columns

    if not rows:
        return

    # Calculate optimal column widths
    num_cols = len(headers)

    # Calculate minimum required widths
    col_widths = []
    for i in range(num_cols):
        max_width = len(headers[i])
        for row in rows:
            if i < len(row):
                max_width = max(max_width, len(str(row[i])))
        col_widths.append(max(min_col_width, max_width))

    # Check if table fits in terminal
    total_width = sum(col_widths) + num_cols - 1

    if total_width > terminal_width:
        # Adjust column widths proportionally
        available_width = terminal_width - (num_cols - 1)  # Account for separators
        scale_factor = available_width / sum(col_widths)

        if scale_factor < 0.3:  # Too narrow for table format
            print(f"\n{headers[0]} Details:")
            print("-" * min(terminal_width, 40))
            for i, row in enumerate(rows, 1):
                print(f"\n{i}. Entry:")
                for j, (header, value) in enumerate(zip(headers, row)):
                    wrapped_lines = wrap_text(f"{header}: {value}", terminal_width - 3, 3)
                    for line in wrapped_lines:
                        print(line)
            print()
            return

        # Scale down column widths
        col_widths = [max(min_col_width, int(w * scale_factor)) for w in col_widths]

        # Redistribute any remaining space
        remaining = available_width - sum(col_widths)
        for i in range(remaining):
            col_widths[i % num_cols] += 1

    # Print headers
    separator_line = create_adaptive_separator('-', total_width)
    print()

    header_lines = format_table_row(headers, col_widths, terminal_width)
    for line in header_lines:
        print(line)

    print(separator_line[:terminal_width])

    # Print rows
    for row in rows:
        row_strs = [str(cell) for cell in row]
        row_lines = format_table_row(row_strs, col_widths, terminal_width)
        for line in row_lines:
            print(line)

    print()

def get_network_interfaces():
    """Get all network interfaces and their IP addresses with subnet masks."""
    interfaces = []

    for interface_name in netifaces.interfaces():
        try:
            # Skip loopback interfaces
            if interface_name.startswith('lo') or 'Loopback' in interface_name:
                continue

            addrs = netifaces.ifaddresses(interface_name)

            # Check for IPv4 addresses
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    ip = addr_info.get('addr')
                    netmask = addr_info.get('netmask')

                    if ip and netmask and ip != '127.0.0.1':
                        try:
                            # Create network object to get subnet info
                            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                            interfaces.append({
                                'interface': interface_name,
                                'ip': ip,
                                'network': str(network.network_address),
                                'netmask': netmask,
                                'subnet': str(network),
                                'broadcast': str(network.broadcast_address)
                            })
                        except Exception:
                            continue
        except Exception:
            continue

    # Now check for additional networks that might be accessible via this interface
    # by looking at the routing table and ARP cache
    additional_interfaces = []
    for interface in interfaces:
        try:
            # Check ARP table for additional networks
            if platform.system() == 'Darwin':  # macOS
                try:
                    result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        arp_lines = result.stdout.split('\n')
                        discovered_networks = set()

                        for line in arp_lines:
                            if interface['interface'] in line:
                                # Extract IP from ARP line
                                parts = line.split()
                                for part in parts:
                                    if '.' in part and part.count('.') == 3:
                                        try:
                                            ip_obj = ipaddress.IPv4Address(part)
                                            # Check if this IP is in a different network than the interface
                                            if ip_obj not in ipaddress.IPv4Network(interface['subnet'], strict=False):
                                                # This IP is in a different network - create a new interface entry
                                                # Try to determine the network by looking at the IP structure
                                                network_parts = part.split('.')
                                                if len(network_parts) == 4:
                                                    # Assume /24 network for discovered IPs
                                                    discovered_network = (f"{network_parts[0]}.{network_parts[1]}."
                                                                         f"{network_parts[2]}.0/24")
                                                    if discovered_network not in discovered_networks:
                                                        discovered_networks.add(discovered_network)
                                                        additional_interfaces.append({
                                                            'interface': interface['interface'],
                                                            'ip': interface['ip'],  # Use interface IP as gateway
                                                            'network': (f"{network_parts[0]}.{network_parts[1]}."
                                                                         f"{network_parts[2]}.0"),
                                                            'netmask': '255.255.255.0',
                                                            'subnet': discovered_network,
                                                            'broadcast': (f"{network_parts[0]}.{network_parts[1]}."
                                                                          f"{network_parts[2]}.255"),
                                                            'discovered': True  # Mark as discovered, not primary
                                                        })
                                        except Exception:
                                            continue
                except Exception as e:
                    # Debug output only in CLI debug mode
                    if ('cli_persistent_data' in globals() and 
                        cli_persistent_data.get('debug_mode', False)):
                        print(f"🔍 DEBUG: ARP check failed: {e}")
        except Exception:
            continue

    # Combine primary and discovered interfaces
    all_interfaces = interfaces + additional_interfaces

    # Debug output only in CLI debug mode
    if ('cli_persistent_data' in globals() and
            cli_persistent_data.get('debug_mode', False)):
        print(f"🔍 DEBUG: Found {len(interfaces)} primary interfaces and {len(additional_interfaces)} discovered networks")

    return all_interfaces

def ping_host(ip):
    """Ping a host to check if it's alive."""
    try:
        system = platform.system().lower()
        if system == "windows":
            cmd = ["ping", "-n", "1", "-w", "1000", ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", ip]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return result.returncode == 0
    except Exception:
        return False

def check_device_status(ip):
    """Check if a device is online, offline, or in standby."""
    try:
        # First try ping
        is_pingable = ping_host(ip)

        if is_pingable:
            return "online"

        # If not pingable, check for common standby ports
        standby_ports = [80, 443, 22, 23, 3389, 5900]  # HTTP, HTTPS, SSH, Telnet, RDP, VNC

        for port in standby_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return "standby"
            except Exception:
                continue

        return "offline"
    except Exception:
        return "offline"

def get_host_machine_info():
    """Get the host machine's network information and system name."""
    try:
        # Get the hostname
        hostname = platform.node()

        # Get local IP addresses from all network interfaces
        local_ips = []
        try:
            # Get IPs from all network interfaces (same method as get_network_interfaces)
            for interface_name in netifaces.interfaces():
                try:
                    # Skip loopback interfaces
                    if interface_name.startswith('lo') or 'Loopback' in interface_name:
                        continue

                    addrs = netifaces.ifaddresses(interface_name)

                    # Check for IPv4 addresses
                    if netifaces.AF_INET in addrs:
                        for addr_info in addrs[netifaces.AF_INET]:
                            ip = addr_info.get('addr')
                            if ip and ip != '127.0.0.1':
                                local_ips.append(ip)
                except Exception:
                    continue
        except Exception:
            pass

        # Also try to get IP from socket as fallback
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            if local_ip not in local_ips:
                local_ips.append(local_ip)
        except Exception:
            pass

        return {
            'hostname': hostname,
            'local_ips': local_ips
        }
    except Exception as e:
        print(f"Error getting host machine info: {e}")
        return {'hostname': 'Unknown', 'local_ips': []}

def get_mac_address(ip):
    """Get MAC address for an IP using improved ARP method with automatic padding."""
    try:
        system = platform.system().lower()
        if system == "windows":
            cmd = ["arp", "-a", ip]
        else:
            # On macOS/Linux, try arp -n <ip> first, then fall back to arp -a
            cmd = ["arp", "-n", ip]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout
            # Look for MAC address in the output
            # Handle both formats: 0:3e:e1:b7:57:54 and 00-3e-e1-b7-57-54
            mac_pattern = r'([0-9a-fA-F]{1,2}[:-]){5}[0-9a-fA-F]{1,2}'
            match = re.search(mac_pattern, output, re.IGNORECASE)
            if match:
                mac = match.group(0).upper().replace('-', ':')
                # Apply MAC padding rule: pad with leading zeros to reach 12 characters
                mac = pad_mac_address(mac)
                return mac
    except Exception:
        pass

    # Fallback: try arp -a and search for the IP
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            output = result.stdout
            if ip in output:
                for line in output.split('\n'):
                    if ip in line:
                        mac_pattern = r'([0-9a-fA-F]{1,2}[:-]){5}[0-9a-fA-F]{1,2}'
                        mac_match = re.search(mac_pattern, line)
                        if mac_match:
                            mac = mac_match.group(0).upper().replace('-', ':')
                            # Apply MAC padding rule: pad with leading zeros to reach 12 characters
                            mac = pad_mac_address(mac)
                            return mac
    except Exception:
        pass

    return None

def pad_mac_address(mac_address):
    """
    Apply the MAC padding rule: pad with leading zeros to reach 12 characters.
    Rule: "To all MAC Addresses with less than 12 characters, we will fill all your earliest character slots with zeroes until you are 12 in total"
    """
    if not mac_address:
        return mac_address

    # Remove separators and count characters
    clean_mac = mac_address.replace(':', '').replace('-', '')
    current_length = len(clean_mac)

    if current_length == 12:
        # Already correct length, just format with colons
        return ':'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])
    elif current_length < 12:
        # Pad with leading zeros
        needed_zeros = 12 - current_length
        padded_mac = '0' * needed_zeros + clean_mac

        # Format with colons
        formatted_mac = ':'.join([padded_mac[i:i+2] for i in range(0, 12, 2)])

        print(f"🔧 MAC padding applied:")
        print(f"   {mac_address} → {formatted_mac} (added {needed_zeros} leading zeros)")
        return formatted_mac
    else:
        # More than 12 characters - may god have mercy on their souls
        print(f"⚠️  MAC address {mac_address} has {current_length} characters - truncating to 12")
        truncated_mac = clean_mac[:12]
        formatted_mac = ':'.join([truncated_mac[i:i+2] for i in range(0, 12, 2)])
        return formatted_mac

def get_mac_vendor(mac_address, silent=False):
    """
    Get vendor information from MAC address using OUI database.
    This is our breakthrough method for vendor identification!

    Args:
        mac_address: MAC address in format XX:XX:XX:XX:XX:XX
        silent: If True, suppress vendor detection messages

    Returns:
        str: Vendor name if found, None otherwise
    """
    try:
        if not mac_address or len(mac_address.split(':')) < 3:
            return None

        # Extract first 6 characters (OUI) and convert to database format
        mac_prefix = ":".join(mac_address.split(":")[:3]).upper()
        # Convert to database format (remove colons): 0:3E:E1 -> 03E1
        db_prefix = mac_prefix.replace(":", "").upper()

        # Try to find vendor in OUI database
        oui_file = os.path.join(os.path.dirname(__file__), 'assets', 'oui_database.txt')

        if os.path.exists(oui_file):
            try:
                with open(oui_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line and db_prefix in line:
                            # Extract vendor name from the line
                            # Format: MAC_PREFIX\tVENDOR_NAME
                            parts = line.split('\t')
                            if len(parts) >= 2:
                                vendor = parts[1].strip()
                                if vendor:
                                    if not silent:
                                        print(f"🏭 Found vendor via OUI database: {vendor}")
                                    return vendor
            except Exception as e:
                print(f"⚠️  OUI database read error: {e}")

        # Fallback to hardcoded common vendors
        common_vendors = {
            "00:50:56": "VMware",
            "00:0C:29": "VMware",
            "00:1A:11": "Google",
            "00:16:3E": "Xen",
            "52:54:00": "QEMU",
            "08:00:27": "VirtualBox",
            "0E:C6:63": "ASIX ELECTRONICS CORP."  # From our testing!
        }

        if mac_prefix in common_vendors:
            return common_vendors[mac_prefix]

        return None

    except Exception as e:
        print(f"❌ MAC vendor lookup failed: {e}")
    return None

def get_device_identifier(ip):
    """Get comprehensive device identifier information using multiple discovery methods."""
    try:
        # Method 1: Try to get hostname via standard DNS resolution
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            if hostname and hostname != ip and len(hostname) > 2:
                return hostname
        except Exception:
            pass

        # Method 2: Try to get Windows NetBIOS name via smbutil (macOS only)
        try:
            if platform.system() == 'Darwin':  # Only on macOS
                netbios_name = get_netbios_name_smbutil(ip)
                if netbios_name:
                    return netbios_name
        except Exception:
            pass

        # Method 3: Try to get Apple device name via mDNS/Bonjour (macOS only)
        try:
            if platform.system() == 'Darwin':  # Only on macOS
                apple_device_name = get_apple_device_name(ip)
                if apple_device_name:
                    return apple_device_name
        except Exception:
            pass

        # Method 4: Try to get additional device information via service detection
        try:
            # Check for common service names
            service_ports = {
                22: "SSH",
                23: "Telnet",
                80: "HTTP",
                443: "HTTPS",
                3389: "RDP",
                5900: "VNC",
                8080: "HTTP-Alt",
                8443: "HTTPS-Alt"
            }

            for port, service in service_ports.items():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    if result == 0:
                        return f"{service}-{ip.split('.')[-1]}"
                except Exception:
                    continue
        except Exception:
            pass

        # Method 5: Try to get MAC address vendor info using OUI database
        try:
            mac = get_mac_address(ip)
            if mac:
                # Use our breakthrough OUI database lookup method!
                vendor = get_mac_vendor(mac, silent=True)
                if vendor:
                    return f"{vendor}-{ip.split('.')[-1]}"
        except Exception:
            pass

        # If nothing else works, return the last octet
        return f".{ip.split('.')[-1]}"

    except Exception:
        # Fallback to last octet
        return f".{ip.split('.')[-1]}"

def scan_network_for_devices_live(interface_info, live_callback=None, known_devices=None, progress_callback=None):
    """Scan a network for active devices with live updates."""
    try:
        network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)
        host_ips = [str(ip) for ip in network.hosts()]

        # Chunked scanning for large networks
        chunk_size = 255  # Process networks in 255-address chunks
        total_ips = len(host_ips)

        devices = []
        scanned = 0

        # Initialize with known devices if provided
        if known_devices:
            devices.extend(known_devices)

        def scan_ip(ip):
            nonlocal scanned
            # Call progress callback to show current IP being scanned
            if progress_callback:
                try:
                    progress_callback(f"Scrying {interface_info['interface']} - {ip}")
                except Exception:
                    pass

            status = check_device_status(ip)
            hostname = None
            mac_address = None

            if status in ["online", "standby"]:
                hostname = get_device_identifier(ip)
                mac_address = get_mac_address(ip)

            # Check if this device was previously known
            known_device = None
            if known_devices:
                for known in known_devices:
                    if known['ip'] == ip:
                        known_device = known
                        break

            # Determine status and hostname
            if status in ["online", "standby"]:
                # Use discovered hostname or last known hostname
                display_hostname = hostname or (known_device['hostname'] if known_device else f".{ip.split('.')[-1]}")
            else:
                # If no known devices (history was cleared), don't show offline devices
                if not known_devices:
                    status = "hidden"
                    display_hostname = None
                elif known_device:
                    # Previously discovered device that's now offline
                    display_hostname = known_device['hostname']
                else:
                    # Never discovered device - hide it
                    status = "hidden"
                    display_hostname = None

            device = {
                'ip': ip,
                'hostname': display_hostname,
                'mac': mac_address or (known_device['mac'] if known_device else None),
                'status': status,
                'pingable': status == "online",
                'last_seen': time.time() if status in ["online", "standby"] else (known_device.get('last_seen', 0) if known_device else 0)
            }

            scanned += 1

            return device

        # Process in chunks to allow other networks to be scanned
        for chunk_start in range(0, total_ips, chunk_size):
            chunk_end = min(chunk_start + chunk_size, total_ips)
            chunk_ips = host_ips[chunk_start:chunk_end]

            # Use ThreadPoolExecutor for concurrent scanning within chunk
            with ThreadPoolExecutor(max_workers=20) as executor:
                device_futures = [executor.submit(scan_ip, ip) for ip in chunk_ips]

                # Process devices as they complete and call live callback immediately
                for future in device_futures:
                    try:
                        device = future.result(timeout=3)
                        if device['status'] != "hidden":  # Only include non-hidden devices
                            # Check for duplicates and update existing entries
                            existing_device = None
                            for existing in devices:
                                if existing['ip'] == device['ip']:
                                    existing_device = existing
                                    break

                            if existing_device:
                                # Update existing device with new status
                                existing_device.update(device)
                            else:
                                # Add new device
                                devices.append(device)

                            # Call live callback immediately for this individual device
                            if live_callback:
                                try:
                                    live_callback(device, interface_info['interface'])
                                except Exception as e:
                                    print(f"Error in live callback for {device['ip']}: {e}")
                    except Exception:
                        scanned += 1
                        continue

            # Small delay between chunks to allow other networks to process
            if chunk_end < total_ips:
                time.sleep(0.1)

        return devices

    except Exception:
        return []

def scan_network_for_devices(interface_info, progress_callback=None, known_devices=None):
    """Scan a network for active devices with enhanced discovery and chunked scanning."""
    try:
        network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)
        host_ips = [str(ip) for ip in network.hosts()]

        # Chunked scanning for large networks
        chunk_size = 255  # Process networks in 255-address chunks
        total_ips = len(host_ips)

        devices = []
        scanned = 0

        # Initialize with known devices if provided
        if known_devices:
            devices.extend(known_devices)

        def scan_ip(ip):
            nonlocal scanned
            # Call progress callback to show current IP being scanned
            if progress_callback:
                try:
                    progress_callback(f"Scrying {interface_info['interface']} - {ip}")
                except Exception:
                    pass

            status = check_device_status(ip)
            hostname = None
            mac_address = None

            if status in ["online", "standby"]:
                hostname = get_device_identifier(ip)
                mac_address = get_mac_address(ip)

            # Check if this device was previously known
            known_device = None
            if known_devices:
                for known in known_devices:
                    if known['ip'] == ip:
                        known_device = known
                        break

            # Determine status and hostname
            if status in ["online", "standby"]:
                # Use discovered hostname or last known hostname
                display_hostname = hostname or (known_device['hostname'] if known_device else f".{ip.split('.')[-1]}")
            else:
                # If no known devices (history was cleared), don't show offline devices
                if not known_devices:
                    status = "hidden"
                    display_hostname = None
                elif known_device:
                    # Previously discovered device that's now offline
                    display_hostname = known_device['hostname']
                else:
                    # Never discovered device - hide it
                    status = "hidden"
                    display_hostname = None

            device = {
                'ip': ip,
                'hostname': display_hostname,
                'mac': mac_address or (known_device['mac'] if known_device else None),
                'status': status,
                'pingable': status == "online",
                'last_seen': time.time() if status in ["online", "standby"] else (known_device.get('last_seen', 0) if known_device else 0)
            }

            scanned += 1
            if progress_callback:
                try:
                    progress_callback(scanned, total_ips, interface_info['interface'])
                except Exception:
                    pass

            return device

        # Process in chunks to allow other networks to be scanned
        for chunk_start in range(0, total_ips, chunk_size):
            chunk_end = min(chunk_start + chunk_size, total_ips)
            chunk_ips = host_ips[chunk_start:chunk_end]

            # Use ThreadPoolExecutor for concurrent scanning within chunk
            with ThreadPoolExecutor(max_workers=20) as executor:
                device_futures = [executor.submit(scan_ip, ip) for ip in chunk_ips]

                for future in device_futures:
                    try:
                        device = future.result(timeout=3)
                        if device['status'] != "hidden":  # Only include non-hidden devices
                            # Check for duplicates and update existing entries
                            existing_device = None
                            for existing in devices:
                                if existing['ip'] == device['ip']:
                                    existing_device = existing
                                    break

                            if existing_device:
                                # Update existing device with new status
                                existing_device.update(device)
                            else:
                                # Add new device
                                devices.append(device)
                    except Exception:
                        scanned += 1
                        if progress_callback:
                            try:
                                progress_callback(scanned, total_ips, interface_info['interface'])
                            except Exception:
                                pass
                        continue

            # Small delay between chunks to allow other networks to process
            if chunk_end < total_ips:
                time.sleep(0.1)

        return devices
    except Exception:
        return []

def format_network_range(subnet_str):
    """Format a subnet into a user-friendly range display."""
    try:
        network = ipaddress.IPv4Network(subnet_str, strict=False)
        network_parts = str(network.network_address).split('.')

        # For /24 networks (most common), show as xxx.xxx.xxx.*
        if network.prefixlen == 24:
            return f"{'.'.join(network_parts[:3])}.*"
        elif network.prefixlen == 16:
            return f"{'.'.join(network_parts[:2])}.*.*"
        elif network.prefixlen == 8:
            return f"{network_parts[0]}.*.*.*"
        else:
            first_ip = str(network.network_address)
            last_ip = str(network.broadcast_address)
            return f"{first_ip} → {last_ip}"
    except Exception:
        return subnet_str

def create_magic_packet(mac_address=None):
    """Create a Wake-on-LAN magic packet."""
    try:
        if mac_address:
            # Clean and validate MAC address
            mac_clean = mac_address.replace(':', '').replace('-', '').upper()
            # Ensure it's exactly 12 hex characters
            if len(mac_clean) == 12 and all(c in '0123456789ABCDEF' for c in mac_clean):
                mac_bytes = bytes.fromhex(mac_clean)
            else:
                print(f"⚠️  Invalid MAC address format: {mac_address}")
                return None
        else:
            # Use broadcast MAC address (FF:FF:FF:FF:FF:FF)
            mac_bytes = bytes.fromhex('FF' * 6)

        magic_packet = b'\xFF' * 6 + mac_bytes * 16
        return magic_packet
    except Exception as e:
        print(f"❌ Error creating magic packet: {e}")
        return None

def send_magic_packet_to_ip(target_ip, magic_packet):
    """Send a magic packet to a specific IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.1)

            # Send to common WOL ports
            for port in [7, 9]:
                try:
                    sock.sendto(magic_packet, (target_ip, port))
                except Exception:
                    pass
    except Exception:
        pass

def send_magic_packet_to_device(device):
    """Send a magic packet to a specific device."""
    magic_packet = create_magic_packet(device.get('mac'))
    if magic_packet:
        send_magic_packet_to_ip(device['ip'], magic_packet)
    else:
        print(f"⚠️  Could not create magic packet for device {device.get('ip', 'Unknown')}")

class WOLCasterGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WoL-Caster - Wake-on-LAN Network Broadcaster")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        # Set application icon
        try:
            # Try to set icon from assets folder (use PNG for cross-platform compatibility)
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "Wol-Caster.png")
            if os.path.exists(icon_path):
                icon_image = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon_image)
                print(f"✅ Application icon loaded from: {icon_path}")
            else:
                print(f"⚠️  Icon file not found at: {icon_path}")
        except Exception as e:
            print(f"❌ Icon loading error: {e}")
            # Continue without icon if there's an error

        # Dark theme colors
        self.dark_bg = "#2b2b2b"
        self.dark_fg = "#ffffff"
        self.dark_select_bg = "#404040"
        self.dark_entry_bg = "#3c3c3c"
        self.dark_button_bg = "#404040"
        self.accent_green = "#4CAF50"

        # Status colors
        self.status_colors = {
            'online': '#4CAF50',    # Green
            'offline': '#F44336',   # Red
            'standby': '#FF9800'    # Orange
        }

        # Configure root window with dark theme
        self.root.configure(bg=self.dark_bg)

        # Center the window
        self.center_window()

        self.network_data = {}
        self.device_data = {}
        self.known_devices = {}  # Persistent device storage
        self.tree_expanded_states = {}  # Track tree expansion states
        self.debug_mode = False  # Debug mode setting
        self.scanning_active = False
        self.scan_thread = None
        self.broadcasting_active = False  # Track broadcast state

        # Load persistent data
        self.load_persistent_data()

        self.create_widgets()
        
        # Configure macOS menu if on macOS
        if sys.platform == 'darwin':
            self.configure_macos_menu()
            
        self.start_continuous_scan()

    def center_window(self):
        """Center the window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def get_data_file_path(self, filename):
        """Get the path for persistent data files."""
        data_dir = os.path.join(os.path.expanduser("~"), ".wol_caster")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, filename)

    def load_persistent_data(self):
        """Load persistent device data and tree states."""
        try:
            # Load known devices
            devices_file = self.get_data_file_path("known_devices.json")
            if os.path.exists(devices_file):
                with open(devices_file, 'r') as f:
                    self.known_devices = json.load(f)

            # Load tree expansion states
            states_file = self.get_data_file_path("tree_states.json")
            if os.path.exists(states_file):
                with open(states_file, 'r') as f:
                    self.tree_expanded_states = json.load(f)

            # Load debug mode setting
            debug_file = self.get_data_file_path("debug_settings.json")
            if os.path.exists(debug_file):
                with open(debug_file, 'r') as f:
                    debug_settings = json.load(f)
                    self.debug_mode = debug_settings.get('debug_mode', False)
            else:
                # Default to disabled
                self.debug_mode = False
        except Exception as e:
            print(f"Error loading persistent data: {e}")
            self.known_devices = {}
            self.tree_expanded_states = {}
            self.debug_mode = False

    def save_persistent_data(self):
        """Save persistent device data and tree states."""
        try:
            # Save known devices
            devices_file = self.get_data_file_path("known_devices.json")
            with open(devices_file, 'w') as f:
                json.dump(self.known_devices, f, indent=2)

            # Save tree expansion states
            states_file = self.get_data_file_path("tree_states.json")

            with open(states_file, 'w') as f:
                json.dump(self.tree_expanded_states, f, indent=2)
        except Exception as e:
            print(f"Error saving persistent data: {e}")

    def update_known_devices(self, interface_name, devices):
        """Update known devices for an interface."""
        self.known_devices[interface_name] = []
        for device in devices:
            if device['status'] != 'hidden':
                # Store device info for persistence - including vendor information
                known_device = {
                    'ip': device['ip'],
                    'hostname': device['hostname'],
                    'mac': device['mac'],
                    'last_seen': device.get('last_seen', time.time()),
                    'status': device['status']
                }

                # Add vendor information if available (preserves discovery data for offline devices)
                if device['mac']:
                    vendor = get_mac_vendor(device['mac'], silent=True)
                    if vendor and vendor != "Unknown":
                        known_device['vendor'] = vendor
                self.known_devices[interface_name].append(known_device)

        # Save to disk
        self.save_persistent_data()

    def create_widgets(self):
        # Title with wand emoji and superscript text on same line
        title_frame = tk.Frame(self.root, bg=self.dark_bg)
        title_frame.pack(pady=8)

        # Wand emoji (large size)
        wand_label = tk.Label(title_frame, text="🪄",
                             font=("SF Pro Display", 40, "bold"),
                             fg="#FFD700", bg=self.dark_bg)
        wand_label.pack(side=tk.LEFT, padx=(0, 5))

        # Title text (smaller superscript size)
        text_label = tk.Label(title_frame, text="WoL-Caster",
                             font=("SF Pro Display", 16, "bold"),  # Smaller for superscript effect
                             fg="#FFD700", bg=self.dark_bg)
        text_label.pack(side=tk.LEFT, pady=(0, 0))  # No top padding - position at very top



        # Updated description
        desc_label = tk.Label(self.root,
                             text="Arm devices for casting magic packets:",
                             font=("SF Pro Text", 11),
                             fg="#cccccc", bg=self.dark_bg)
        desc_label.pack(pady=8)

        # Main frame
        self.main_frame = tk.Frame(self.root, relief=tk.SUNKEN, bd=1,
                                  bg=self.dark_entry_bg)
        self.main_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        # Title for the tree view
        self.main_title = tk.Label(self.main_frame, text="Networks & Devices:",
                                 font=("Arial", 11, "bold"),
                                 fg=self.dark_fg, bg=self.dark_entry_bg)
        self.main_title.pack(pady=5)

        # Create treeview with scrollbar
        self.create_treeview()

        # Start button
        self.create_buttons()

        # Status label
        self.status_label = tk.Label(self.root,
                                    text="Scrying networks and devices...",
                                    font=("SF Pro Text", 10),
                                    fg="#cccccc", bg=self.dark_bg)
        self.status_label.pack(pady=(0, 10))

        # Progress bar (hidden by default)
        self.progress_frame = tk.Frame(self.root, bg=self.dark_bg)
        self.progress_frame.pack(pady=(0, 10), fill=tk.X, padx=20)

        self.progress_label = tk.Label(self.progress_frame,
                                     text="",
                                     font=("SF Pro Text", 9),
                                     fg="#cccccc", bg=self.dark_bg)
        self.progress_label.pack()

        self.progress_bar = ttk.Progressbar(self.progress_frame,
                                          mode='determinate',
                                          length=400)

        # Configure progress bar style to match title color
        style = ttk.Style()
        style.configure('Gold.Horizontal.TProgressbar',
                       troughcolor=self.dark_entry_bg,
                       background='#FFD700',  # Yellow-gold to match title
                       bordercolor=self.dark_entry_bg,
                       lightcolor='#FFD700',
                       darkcolor='#FFD700')
        self.progress_bar.configure(style='Gold.Horizontal.TProgressbar')

        self.progress_bar.pack(pady=(5, 0))

        # Hide progress bar initially
        self.progress_frame.pack_forget()

        # Control buttons
        self.create_control_buttons()

    def create_treeview(self):
        """Create the treeview widget."""
        tree_frame = tk.Frame(self.main_frame, bg=self.dark_entry_bg)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Configure ttk style for dark theme
        style = ttk.Style()
        style.theme_use('clam')

        # Configure treeview style
        style.configure('Dark.Treeview',
                       background=self.dark_entry_bg,
                       foreground=self.dark_fg,
                       fieldbackground=self.dark_entry_bg,
                       borderwidth=0)
        style.configure('Dark.Treeview.Heading',
                       background=self.dark_button_bg,
                       foreground=self.dark_fg,
                       borderwidth=1)
        # Remove hover effects for column headers
        style.map('Dark.Treeview.Heading',
                 background=[('active', self.dark_button_bg),
                           ('pressed', self.dark_button_bg)])
        style.map('Dark.Treeview',
                 background=[('selected', self.dark_select_bg)])

        # Create treeview
        columns = ('Status', 'IP', 'MAC', 'Info')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings',
                                style='Dark.Treeview')

        # Add subtle border to indicate scrollable area
        tree_frame.configure(relief=tk.SUNKEN, bd=1)

        # Configure columns with toggle sorting
        self.tree.heading('#0', text='Name', anchor='w', command=lambda: self.toggle_sort('#0'))
        self.tree.heading('Status', text='Status', anchor='center', command=lambda: self.toggle_sort('Status'))
        self.tree.heading('IP', text='IP Address', anchor='center', command=lambda: self.toggle_sort('IP'))
        self.tree.heading('MAC', text='MAC Address', anchor='center', command=lambda: self.toggle_sort('MAC'))
        self.tree.heading('Info', text='📄 Export Data', anchor='center', command=self.export_json_to_terminal)

        # Configure column widths and alignment
        self.tree.column('#0', width=250, minwidth=200)
        self.tree.column('Status', width=80, minwidth=60, anchor='center')
        self.tree.column('IP', width=120, minwidth=100, anchor='center')
        self.tree.column('MAC', width=150, minwidth=120, anchor='center')
        self.tree.column('Info', width=120, minwidth=100, anchor='center')

        # Hidden scrollbar for treeview (maintains scroll functionality)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Pack treeview to fill the frame
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Hide scrollbar but keep it functional
        scrollbar.pack_forget()

        # Bind single-click to toggle selection and expansion
        self.tree.bind('<Button-1>', self.on_tree_click)
        self.tree.bind('<<TreeviewOpen>>', self.on_tree_expand)
        self.tree.bind('<<TreeviewClose>>', self.on_tree_collapse)

        # Add mouse wheel scrolling support (since scrollbar is hidden)
        self.tree.bind('<MouseWheel>', self.on_mousewheel)
        self.tree.bind('<Button-4>', self.on_mousewheel)  # Linux scroll up
        self.tree.bind('<Button-5>', self.on_mousewheel)  # Linux scroll down

        # Add keyboard scrolling support
        self.tree.bind('<Up>', self.on_key_scroll)
        self.tree.bind('<Down>', self.on_key_scroll)
        self.tree.bind('<Prior>', self.on_key_scroll)  # Page Up
        self.tree.bind('<Next>', self.on_key_scroll)   # Page Down
        self.tree.bind('<Home>', self.on_key_scroll)
        self.tree.bind('<End>', self.on_key_scroll)

        # Track sort state
        self.sort_column = 'IP'  # Default sort by IP
        self.sort_reverse = False

    def create_buttons(self):
        """Create the start/stop cast button and scry toggle button."""
        # Create button frame for horizontal layout with consistent spacing
        button_frame = tk.Frame(self.root, bg=self.dark_bg)
        button_frame.pack(pady=(15, 5))

        try:
            style = ttk.Style()
            style.configure('Dark.TButton',
                          background='#2a2a2a',
                          foreground='white',
                          borderwidth=1,
                          focuscolor='none',
                          relief='raised',
                          width=15)
            style.map('Dark.TButton',
                     background=[('active', '#404040'),
                               ('pressed', '#1a1a1a')])

            style.configure('Stop.TButton',
                          background='#d32f2f',
                          foreground='white',
                          borderwidth=1,
                          focuscolor='none',
                          relief='raised')
            style.map('Stop.TButton',
                     background=[('active', '#b71c1c'),
                               ('pressed', '#8e0000')])

            style.configure('Scan.TButton',
                          background='#9C27B0',
                          foreground='white',
                          borderwidth=1,
                          focuscolor='none',
                          relief='raised',
                          width=15)
            style.map('Scan.TButton',
                     background=[('active', '#7B1FA2'),
                               ('pressed', '#4A148C')])

            self.start_button = ttk.Button(button_frame,
                                         text="✨ Start Cast",
                                         command=self.toggle_broadcast,
                                         style='Dark.TButton')

            self.scan_button = ttk.Button(button_frame,
                                        text="🔮 End Scry",
                                        command=self.toggle_scan,
                                        style='Scan.TButton')
        except Exception:
            self.start_button = tk.Button(button_frame,
                                         text="✨ Start Cast",
                                         command=self.toggle_broadcast,
                                         font=("SF Pro Text", 12, "bold"),
                                         bg="lightgray", fg="black",
                                         relief=tk.RAISED, bd=3,
                                         padx=20, pady=8,
                                         width=15)

            self.scan_button = tk.Button(button_frame,
                                        text="🔮 End Scry",
                                        command=self.toggle_scan,
                                        font=("SF Pro Text", 12, "bold"),
                                        bg="#9C27B0", fg="white",
                                        relief=tk.RAISED, bd=3,
                                        padx=20, pady=8,
                                        width=15)

        # Pack buttons horizontally with consistent spacing and width
        self.start_button.pack(side=tk.LEFT, padx=(0, 10), ipadx=10)
        self.scan_button.pack(side=tk.LEFT, padx=(0, 0), ipadx=10)

    def create_control_buttons(self):
        """Create control buttons."""
        control_frame = tk.Frame(self.root, bg=self.dark_bg)
        control_frame.pack(pady=(5, 15))

        # Track arm state
        self.all_armed = False

        try:
            self.arm_toggle_button = ttk.Button(control_frame,
                                              text="🎯 Arm All",
                                              command=self.toggle_arm_all,
                                              style='Dark.TButton')
            self.clear_data_button = ttk.Button(control_frame,
                                              text="🔥 Clear History",
                                              command=self.clear_persistent_data,
                                              style='Dark.TButton')

        except Exception:
            self.arm_toggle_button = tk.Button(control_frame,
                                             text="🎯 Arm All",
                                             command=self.toggle_arm_all,
                                             bg="lightgray", fg="black",
                                             relief=tk.RAISED, bd=2,
                                             width=15)
            self.clear_data_button = tk.Button(control_frame,
                                             text="🔥 Clear History",
                                             command=self.clear_persistent_data,
                                             bg="lightgray", fg="black",
                                             relief=tk.RAISED, bd=2,
                                             width=15)

        # Pack buttons horizontally with consistent spacing and width
        self.arm_toggle_button.pack(side=tk.LEFT, padx=(0, 10), ipadx=10)
        self.clear_data_button.pack(side=tk.LEFT, padx=(0, 0), ipadx=10)

    def start_continuous_scan(self):
        """Start continuous scanning of networks and devices."""
        if not self.scanning_active:
            self.scanning_active = True
            self.scan_thread = threading.Thread(target=self.scan_worker, daemon=True)
            self.scan_thread.start()

            # Update scan button to show scanning is active
            try:
                self.scan_button.config(text='🔮 End Scry', style='Scan.TButton')
            except Exception:
                self.scan_button.config(text='🔮 End Scry', style='Scan.TButton')

    def scan_worker(self):
        """Worker thread for continuous network and device scanning with live updates."""
        while self.scanning_active:
            try:
                # Get network interfaces
                interfaces = get_network_interfaces()

                # First, add all networks to the tree and expand them immediately
                for interface in interfaces:
                    interface_name = interface['interface']
                    if interface_name not in self.network_data:
                        # New network discovered - add it immediately
                        self.network_data[interface_name] = interface
                        self.device_data[interface_name] = []
                        self.tree_expanded_states[interface_name] = True

                        # Update GUI immediately to show the new network
                        self.root.after(0, self.update_tree_view)

                # Now scan each network with live updates
                for interface in interfaces:
                    if not self.scanning_active:
                        break

                    interface_name = interface['interface']

                    # Get known devices for this interface
                    known_devices = self.known_devices.get(interface_name, [])

                    # Scan devices on this network with live updates
                    devices = scan_network_for_devices_live(interface, self.live_device_callback, known_devices,
                                                         self.update_scan_progress)

                    # Update data structures
                    self.network_data[interface_name] = interface
                    self.device_data[interface_name] = devices

                    # Update known devices
                    self.update_known_devices(interface_name, devices)

                # Wait before next scan (faster refresh for first scan)
                if not hasattr(self, '_first_scan_complete'):
                    time.sleep(5)  # Faster refresh for first scan
                    self._first_scan_complete = True
                else:
                    # Check for stop signal more frequently to allow immediate stopping
                    for _ in range(30):  # Check every second instead of sleeping for 30 seconds
                        if not self.scanning_active:
                            break
                        time.sleep(1)

                # Show completion message if scanning is still active
                if self.scanning_active:
                    self.root.after(0, lambda: self.status_label.config(text="Scry cycle complete - waiting for next scan..."))

            except Exception as e:
                print(f"Scan error: {e}")
                time.sleep(10)

        # Show completion message when scanning stops
        if not self.scanning_active:
            self.discovery_in_progress = False  # Clear flag when thread stops
            print(f"🔮 Scry thread actually stopped (scanning_active = {self.scanning_active})")
            self.root.after(0, lambda: self.status_label.config(text="Ended Scry"))

    def live_device_callback(self, device, interface_name):
        """Callback for live device updates - handles individual devices."""
        try:
            # Add or update device in real-time
            if interface_name not in self.device_data:
                self.device_data[interface_name] = []

            # Check if device already exists
            existing_device = None
            for existing in self.device_data[interface_name]:
                # Safety check: ensure existing is a dictionary
                if not isinstance(existing, dict):
                    continue
                if existing.get('ip') == device.get('ip'):
                    existing_device = existing
                    break

            if existing_device:
                # Update existing device
                existing_device.update(device)
            else:
                # Add new device
                self.device_data[interface_name].append(device)

            # Update GUI immediately with this individual device
            self.root.after(0, self.update_tree_view)

        except Exception as e:
            print(f"Live device callback error: {e}")

    def scan_progress_callback(self, completed, total, interface):
        """Update scan progress."""
        try:
            self.root.after(0, lambda: self.status_label.config(
                text=f"Scrying {interface}: {completed}/{total} devices"))
        except Exception:
            pass

    def update_scan_progress(self, message):
        """Update scan progress with real-time IP address information."""
        try:
            self.root.after(0, lambda: self.status_label.config(text=message))
        except Exception:
            pass

    def update_tree_view(self):
        """Update the tree view with deep hierarchy: Adapter → Network → Devices."""
        try:
            # Save current selections and expansion states
            selected_items = set()
            expanded_adapters = set()
            expanded_networks = set()

            for item in self.tree.get_children():
                item_text = self.tree.item(item, 'text')
                if 'selected' in self.tree.item(item, 'tags'):
                    selected_items.add(item_text)
                if self.tree.item(item, 'open'):
                    expanded_adapters.add(item_text.split(' (')[0])  # Adapter name

                # Check children (networks) for expansion state
                for network_item in self.tree.get_children(item):
                    network_text = self.tree.item(network_item, 'text')
                    if 'selected' in self.tree.item(network_item, 'tags'):
                        selected_items.add(network_text)
                    if self.tree.item(network_item, 'open'):
                        expanded_networks.add(network_text.split(' (')[0])  # Network name

                    # Check devices for selections
                    for device_item in self.tree.get_children(network_item):
                        if 'selected' in self.tree.item(device_item, 'tags'):
                            selected_items.add(self.tree.item(device_item, 'values')[1])  # IP address

            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Group devices by adapter and network
            adapter_network_devices = {}

            if self.debug_mode:
                print(f"🔍 DEBUG: network_data keys: {list(self.network_data.keys())}")
                print(f"🔍 DEBUG: device_data keys: {list(self.device_data.keys())}")
                print(f"🔍 DEBUG: known_devices keys: {list(self.known_devices.keys())}")

            # Process currently active interfaces
            for interface_name, interface_info in self.network_data.items():
                # Use the full interface name as the adapter identifier
                # This ensures en0 and en1 are treated as separate adapters
                adapter_name = interface_name

                if self.debug_mode:
                    print(f"🔍 DEBUG: Processing interface {interface_name} with subnet {interface_info['subnet']}")

                if adapter_name not in adapter_network_devices:
                    adapter_network_devices[adapter_name] = {}

                # Get devices for this interface
                devices = self.device_data.get(interface_name, [])
                if self.debug_mode:
                    print(f"🔍 DEBUG: Found {len(devices)} devices for {interface_name}")

                # Group devices by their actual network ranges, not just the interface subnet
                # This handles cases where one interface can access multiple networks
                network_groups = {}

                # Get known devices from persistent data for smart merging
                known_devices = self.known_devices.get(interface_name, [])

                for device in devices:
                    # Safety check: ensure device is a dictionary
                    if not isinstance(device, dict):
                        continue
                    device_ip = device.get('ip')
                    if not device_ip:
                        continue
                    # Determine which network this device belongs to based on IP
                    if device_ip.startswith('192.168.0.'):
                        network_key = '192.168.0.0/24'
                    elif device_ip.startswith('134.124.230.'):
                        network_key = '134.124.230.0/24'  # Separate network
                    elif device_ip.startswith('134.124.231.'):
                        network_key = '134.124.231.0/24'  # Separate network
                    else:
                        # For any other IP ranges, use the interface subnet as fallback
                        network_key = interface_info['subnet']

                    if network_key not in network_groups:
                        network_groups[network_key] = []

                    # Smart merge: combine current scan results with persistent data
                    # Find if we have stored information for this device
                    stored_device = None
                    for known in known_devices:
                        if isinstance(known, dict) and known.get('ip') == device_ip:
                            stored_device = known
                            break

                    # Merge current status with stored device intelligence
                    merged_device = device.copy()
                    if stored_device and isinstance(stored_device, dict):
                        # Preserve hard-earned information from persistent data
                        if not merged_device.get('hostname') and stored_device.get('hostname'):
                            merged_device['hostname'] = stored_device['hostname']
                        if not merged_device.get('mac') and stored_device.get('mac'):
                            merged_device['mac'] = stored_device['mac']
                        if not merged_device.get('vendor') and stored_device.get('vendor'):
                            merged_device['vendor'] = stored_device['vendor']
                        # Keep the last_seen from current scan (more recent)
                        if stored_device.get('last_seen'):
                            merged_device['stored_last_seen'] = stored_device['last_seen']

                    # CRITICAL: Validate network context for status
                    # Only mark as online if device is actually reachable from current network context
                    if network_key != interface_info['subnet']:
                        # This is a discovered network (not the primary interface network)
                        # Validate if device is actually reachable
                        if not merged_device.get('pingable', False):
                            # Device not pingable from current context - mark as offline
                            merged_device['status'] = 'offline'
                            merged_device['network_context'] = 'discovered_offline'
                        else:
                            merged_device['network_context'] = 'discovered_online'
                    else:
                        # Primary network - status is accurate
                        merged_device['network_context'] = 'primary'

                    network_groups[network_key].append(merged_device)

                # Now add any offline devices from persistent data that weren't found in current scan
                # This ensures we show offline devices with their stored intelligence
                for known in known_devices:
                    # Safety check: ensure known is a dictionary
                    if not isinstance(known, dict):
                        continue

                    known_ip = known.get('ip')
                    if not known_ip:
                        continue

                    # Determine network for this known device
                    if known_ip.startswith('192.168.0.'):
                        network_key = '192.168.0.0/24'
                    elif known_ip.startswith('134.124.230.'):
                        network_key = '134.124.230.0/24'  # Separate from 134.124.231.*
                    elif known_ip.startswith('134.124.231.'):
                        network_key = '134.124.231.0/24'  # Separate network
                    else:
                        network_key = interface_info['subnet']

                    # Check if this device is already in the current scan results
                    already_found = any(d['ip'] == known_ip for d in network_groups.get(network_key, []))

                    if not already_found:
                        # This device is offline - add it with stored intelligence
                        offline_device = known.copy()
                        offline_device['status'] = 'offline'  # Mark as offline
                        offline_device['current_scan'] = False  # Flag that this wasn't found in current scan

                        if network_key not in network_groups:
                            network_groups[network_key] = []
                        network_groups[network_key].append(offline_device)

                # Now add each network group to the adapter
                for network_key, network_devices in network_groups.items():
                    if network_key not in adapter_network_devices[adapter_name]:
                        adapter_network_devices[adapter_name][network_key] = []
                    adapter_network_devices[adapter_name][network_key].extend(network_devices)

            # Process historical interfaces from persistent data that aren't currently active
            for interface_name, known_devices in self.known_devices.items():
                if interface_name not in self.network_data:
                    # This is a historical interface not currently active
                    adapter_name = interface_name

                    if self.debug_mode:
                        print(f"🔍 DEBUG: Processing historical interface {interface_name} with {len(known_devices)} known devices")

                    if adapter_name not in adapter_network_devices:
                        adapter_network_devices[adapter_name] = {}

                    # Group historical devices by network
                    for device in known_devices:
                        if not isinstance(device, dict):
                            continue

                        device_ip = device.get('ip')
                        if not device_ip:
                            continue

                        # Determine network for this historical device
                        if device_ip.startswith('192.168.0.'):
                            network_key = '192.168.0.0/24'
                        elif device_ip.startswith('134.124.230.'):
                            network_key = '134.124.230.0/24'
                        elif device_ip.startswith('134.124.231.'):
                            network_key = '134.124.231.0/24'
                        else:
                            # Use a generic network key for unknown ranges
                            network_parts = device_ip.split('.')
                            if len(network_parts) >= 3:
                                network_key = f"{'.'.join(network_parts[:3])}.0/24"
                            else:
                                continue

                        if network_key not in adapter_network_devices[adapter_name]:
                            adapter_network_devices[adapter_name][network_key] = []

                        # Mark as offline and historical
                        historical_device = device.copy()
                        historical_device['status'] = 'offline'
                        historical_device['current_scan'] = False
                        historical_device['historical'] = True

                        adapter_network_devices[adapter_name][network_key].append(historical_device)

            if self.debug_mode:
                print(f"🔍 DEBUG: Final adapter_network_devices structure: {adapter_network_devices}")

            # Build the deep tree structure
            for adapter_name, networks in adapter_network_devices.items():
                # Get interface type (WiFi vs Ethernet)
                interface_type = self.get_interface_type(adapter_name)
                if self.debug_mode:
                    print(f"🔍 DEBUG: Interface {adapter_name} detected as {interface_type}")

                # Check if this is a historical interface and add appropriate label
                is_historical = adapter_name not in self.network_data
                if is_historical:
                    adapter_text = f"{adapter_name} ({interface_type} - Historical)"
                else:
                    adapter_text = f"{adapter_name} ({interface_type})"
                adapter_tags = ['adapter']
                if adapter_text in selected_items:
                    adapter_tags.append('selected')

                adapter_item = self.tree.insert('', 'end', text=adapter_text,
                                              values=('', '', '', ''),
                                              tags=adapter_tags)

                # Add networks as children of adapter
                for network_subnet, devices in networks.items():
                    # Format network display with asterisk notation
                    try:
                        network_obj = ipaddress.IPv4Network(network_subnet, strict=False)
                        # Use standard network notation (.0 for network address)
                        if network_subnet == '192.168.0.0/24':
                            range_display = "192.168.0.0"
                        elif network_subnet == '134.124.230.0/24':
                            range_display = "134.124.230.0"
                        else:
                            # Fallback to original format for other networks
                            range_display = f"{network_obj.network_address} - {network_obj.broadcast_address}"
                    except Exception:
                        range_display = network_subnet

                device_count = len(devices)
                online_count = sum(1 for d in devices if d['status'] == 'online')

                # Determine network status color
                if online_count > 0:
                    network_color = '#4CAF50'  # Green if any devices online
                elif device_count > 0:
                    network_color = '#F44336'  # Red if devices but all offline
                else:
                    network_color = '#FFFFFF'  # White if no devices

                # Check if this is a discovered network (not primary interface network)
                is_discovered = False
                for interface_info in self.network_data.values():
                    if interface_info.get('subnet') == network_subnet and interface_info.get('discovered'):
                        is_discovered = True
                        break

                network_text = f"Network: {range_display}"
                if is_discovered:
                    network_text += " (Discovered)"

                network_tags = ['network']
                if network_text in selected_items:
                    network_tags.append('selected')

                network_item = self.tree.insert(adapter_item, 'end', text=network_text,
                                          values=('', '', '', f"{online_count}/{device_count} devices"),
                                          tags=network_tags)

                # Sort devices by IP address (alphanumeric)
                sorted_devices = sorted(devices, key=lambda x: [int(part) for part in x['ip'].split('.')])

                # Add devices as children of network
                for device in sorted_devices:
                    # Determine status symbol and color
                    if device['status'] == 'online':
                        status_symbol = "●"
                        status_color = '#4CAF50'  # Green
                    elif device['status'] == 'offline':
                        status_symbol = "○"
                        status_color = '#F44336'  # Red
                    elif device['status'] == 'standby':
                        status_symbol = "◐"
                        status_color = '#FF9800'  # Orange
                    else:
                        status_symbol = "○"
                        status_color = '#F44336'  # Red

                    # Check if this is the host machine
                    host_info = get_host_machine_info()
                    if device['ip'] in host_info['local_ips']:
                        device_text = f"🖥️  {host_info['hostname']}.local"
                        # Host machine gets special white color and no status-based coloring
                        device_tags = ['device_host']
                    else:
                        # Smart display: show stored hostname if available, otherwise fallback
                        if device.get('hostname') and device['hostname'] not in ['.1', '.24', '.69', '.12', '.113', '.220', '.243']:
                            device_text = device['hostname']
                        elif device.get('vendor') and device['vendor'] != "Unknown":
                            device_text = f"{device['vendor']}-{device['ip'].split('.')[-1]}"
                        else:
                            device_text = f"Device-{device['ip'].split('.')[-1]}"

                    # No status text in device name - keep it clean
                    device_tags = [f"device_{device['status']}"]

                    if device['ip'] in selected_items:
                        device_tags.append('selected')

                    mac_display = device['mac'] or 'Unknown'

                    # Get vendor information for the Info column - prioritize vendor over status
                    vendor_info = ""
                    if device['mac']:
                        # For online devices, do fresh vendor lookup (handles network changes, adapter swaps, etc.)
                        # For offline devices, use stored vendor info if available
                        if device['status'] in ['online', 'standby']:
                            # Fresh lookup for active devices
                            vendor = get_mac_vendor(device['mac'], silent=True)
                            if vendor and vendor != "Unknown":
                                vendor_info = vendor
                            else:
                                vendor_info = device['status'].title()
                        else:
                            # Use stored vendor info for offline devices
                            if 'vendor' in device and device['vendor']:
                                vendor_info = device['vendor']
                            else:
                                vendor_info = device['status'].title()
                        # Only show debug during actual discovery, not tree refreshes
                        if hasattr(self, 'discovery_in_progress') and self.discovery_in_progress:
                            print(f"🔍 Device {device['ip']}: MAC={device['mac']}, Vendor={vendor_info}")
                    else:
                        # No MAC address - fallback to status
                        vendor_info = device['status'].title()
                        if hasattr(self, 'discovery_in_progress') and self.discovery_in_progress:
                            print(f"🔍 Device {device['ip']}: No MAC address found, using status: {vendor_info}")

                    # Only show debug during actual discovery, not tree refreshes
                    if hasattr(self, 'discovery_in_progress') and self.discovery_in_progress:
                        print(f"🌳 Inserting device {device['ip']} with vendor_info: '{vendor_info}'")

                    device_item = self.tree.insert(network_item, 'end', text=device_text,
                                                 values=(status_symbol, device['ip'], mac_display, vendor_info),
                                                 tags=device_tags)

                # Restore expansion state for networks (default to expanded)
                if network_text in expanded_networks or self.tree_expanded_states.get(network_text, True):
                    self.tree.item(network_item, open=True)
                    self.tree_expanded_states[network_text] = True
                else:
                    self.tree.item(network_item, open=False)
                    self.tree_expanded_states[network_text] = False

            # Restore expansion state for adapters (default to expanded for active, collapsed for historical)
            for adapter_name in adapter_network_devices.keys():
                # Check if this is a historical (inactive) adapter
                is_historical = adapter_name not in self.network_data
                default_expanded = not is_historical  # Active adapters default to expanded, historical to collapsed

                if adapter_name in expanded_adapters or self.tree_expanded_states.get(adapter_name, default_expanded):
                    # Find the adapter item and expand it
                    for item in self.tree.get_children():
                        if adapter_name in self.tree.item(item, 'text'):
                            self.tree.item(item, open=True)
                            self.tree_expanded_states[adapter_name] = True
                            break
                else:
                    self.tree_expanded_states[adapter_name] = False

            # Configure tags for colors
            self.tree.tag_configure('adapter', foreground='#FFD700')  # Gold for adapters
            self.tree.tag_configure('network', foreground='#FFFFFF')
            self.tree.tag_configure('device_host', foreground='#FFFFFF')  # Host machine always white
            self.tree.tag_configure('device_online', foreground='#4CAF50')
            self.tree.tag_configure('device_offline', foreground='#F44336')
            self.tree.tag_configure('device_standby', foreground='#FF9800')
            self.tree.tag_configure('selected', background=self.dark_select_bg)

            # Save tree states
            self.save_persistent_data()

            # Update status with smart merging info
            total_adapters = len(adapter_network_devices)
            total_networks = sum(len(networks) for networks in adapter_network_devices.values())

            # Count devices from the merged network groups (with safety checks)
            total_devices = 0
            total_online = 0
            total_offline = 0
            total_with_intelligence = 0

            for devices in adapter_network_devices.values():
                if isinstance(devices, dict):
                    for device_list in devices.values():
                        if isinstance(device_list, list):
                            total_devices += len(device_list)
                            for d in device_list:
                                if isinstance(d, dict):
                                    if d.get('status') == 'online':
                                        total_online += 1
                                    elif d.get('status') == 'offline':
                                        total_offline += 1
                                    if d.get('vendor') or d.get('hostname'):
                                        total_with_intelligence += 1

            status_text = f"Found {total_adapters} adapters, {total_networks} networks, {total_online}/{total_devices} devices online"
            if total_offline > 0:
                status_text += f" ({total_offline} offline with stored intelligence)"
            if total_with_intelligence > 0:
                status_text += f" - {total_with_intelligence} devices with enhanced info"
            if total_devices > 10:  # Only show scroll hint if there are many items
                status_text += " (Use mouse wheel or arrow keys to scroll)"

            self.status_label.config(text=status_text)
        except Exception as e:
            print(f"Tree update error: {e}")

    def get_interface_type(self, interface_name):
        """Determine if an interface is WiFi or Ethernet by querying the system."""
        try:
            if platform.system() == 'Darwin':  # macOS
                # Use system_profiler to get actual interface type
                try:
                    if self.debug_mode:
                        print(f"🔍 DEBUG: Running system_profiler for interface {interface_name}")
                    result = subprocess.run(['system_profiler', 'SPNetworkDataType'],
                                          capture_output=True, text=True, timeout=10)

                    if self.debug_mode:
                        print(f"🔍 DEBUG: system_profiler return code: {result.returncode}")
                    if result.returncode == 0:
                        output = result.stdout
                        if self.debug_mode:
                            print(f"🔍 DEBUG: system_profiler output length: {len(output)} characters")

                        # Look for the specific interface in the output
                        interface_section = None
                        lines = output.split('\n')
                        if self.debug_mode:
                            print(f"🔍 DEBUG: Looking for interface {interface_name} in {len(lines)} lines")

                        for i, line in enumerate(lines):
                            if interface_name in line:
                                if self.debug_mode:
                                    print(f"🔍 DEBUG: Found {interface_name} at line {i}: '{line.strip()}'")
                                # Found the interface, look for type info in nearby lines
                                for j in range(max(0, i-10), min(len(lines), i+10)):
                                    if 'Type:' in lines[j]:
                                        type_line = lines[j].strip()
                                        if self.debug_mode:
                                            print(f"🔍 DEBUG: Found Type line at {j}: '{type_line}'")
                                        if 'Wi-Fi' in type_line or 'WiFi' in type_line or 'AirPort' in type_line:
                                            if self.debug_mode:
                                                print(f"🔍 DEBUG: Detected WiFi for {interface_name}")
                                            return "WiFi"
                                        elif 'Ethernet' in type_line:
                                            if self.debug_mode:
                                                print(f"🔍 DEBUG: Detected Ethernet for {interface_name}")
                                            return "Ethernet"
                                        elif 'Thunderbolt' in type_line:
                                            if self.debug_mode:
                                                print(f"🔍 DEBUG: Detected Thunderbolt for {interface_name}")
                                            return "Thunderbolt"
                                        break
                                break

                        # Fallback: check if interface name appears in WiFi or Ethernet sections
                        if self.debug_mode:
                            print(f"🔍 DEBUG: Trying fallback section detection for {interface_name}")

                        if ('Wi-Fi' in output or 'AirPort' in output) and interface_name in output:
                            # Simple heuristic: if it's in a WiFi section, it's WiFi
                            wifi_start = output.find('Wi-Fi') if 'Wi-Fi' in output else output.find('AirPort')
                            wifi_end = output.find('\n\n', wifi_start)
                            if wifi_end == -1:
                                wifi_end = len(output)
                            wifi_section = output[wifi_start:wifi_end]
                            if self.debug_mode:
                                print(f"🔍 DEBUG: WiFi section contains {interface_name}: {interface_name in wifi_section}")
                            if interface_name in wifi_section:
                                if self.debug_mode:
                                    print(f"🔍 DEBUG: Fallback detected WiFi for {interface_name}")
                                return "WiFi"

                        if 'Ethernet' in output and interface_name in output:
                            ethernet_start = output.find('Ethernet')
                            ethernet_end = output.find('\n\n', ethernet_start)
                            if ethernet_end == -1:
                                ethernet_end = len(output)
                            ethernet_section = output[ethernet_start:ethernet_end]
                            if self.debug_mode:
                                print(f"🔍 DEBUG: Ethernet section contains {interface_name}: {interface_name in ethernet_section}")
                            if interface_name in ethernet_section:  # Fixed the bug here
                                if self.debug_mode:
                                    print(f"🔍 DEBUG: Fallback detected Ethernet for {interface_name}")
                                return "Ethernet"

                        if self.debug_mode:
                            print(f"🔍 DEBUG: No type found in system_profiler output for {interface_name}")

                    else:
                        if self.debug_mode:
                            print(f"🔍 DEBUG: system_profiler failed with return code {result.returncode}")
                            if result.stderr:
                                print(f"🔍 DEBUG: system_profiler stderr: {result.stderr}")

                except Exception as e:
                    if self.debug_mode:
                        print(f"🔍 DEBUG: system_profiler failed with exception: {e}")

                # Fallback to naming conventions (less reliable)
                if self.debug_mode:
                    print(f"🔍 DEBUG: Using naming convention fallback for {interface_name}")
                if interface_name.startswith('en0'):
                    if self.debug_mode:
                        print(f"🔍 DEBUG: Naming convention: en0 → WiFi")
                    return "WiFi"  # en0 is typically WiFi on macOS
                elif interface_name.startswith('en1'):
                    if self.debug_mode:
                        print(f"🔍 DEBUG: Naming convention: en1 → Ethernet")
                    return "Ethernet"  # en1 is typically Ethernet on macOS
                elif interface_name.startswith('wlan'):
                    if self.debug_mode:
                        print(f"🔍 DEBUG: Naming convention: wlan → WiFi")
                    return "WiFi"
                elif interface_name.startswith('eth'):
                    if self.debug_mode:
                        print(f"🔍 DEBUG: Naming convention: eth → Ethernet")
                    return "Ethernet"
                elif interface_name.startswith('lo'):
                    if self.debug_mode:
                        print(f"🔍 DEBUG: Naming convention: lo → Loopback")
                    return "Loopback"
                else:
                    if self.debug_mode:
                        print(f"🔍 DEBUG: Naming convention: {interface_name} → Network")
                    return "Network"
            else:
                # Non-macOS systems
                if interface_name.startswith('wlan'):
                    return "WiFi"
                elif interface_name.startswith('eth'):
                    return "Ethernet"
                elif interface_name.startswith('lo'):
                    return "Loopback"
                else:
                    return "Network"
        except Exception as e:
            print(f"🔍 DEBUG: Interface type detection failed: {e}")
            return "Network"

    def toggle_sort(self, column):
        """Toggle sort order for a column between ascending and descending."""
        if self.sort_column == column:
            # Same column - toggle direction
            self.sort_reverse = not self.sort_reverse
        else:
            # Different column - start with ascending
            self.sort_column = column
            self.sort_reverse = False

        # Apply the sort
        self.sort_treeview(column, self.sort_reverse)

    def sort_treeview(self, column, reverse):
        """Sort treeview by column."""
        try:
            # Get all items and their data
            items = []
            for item in self.tree.get_children():
                item_data = self.tree.item(item)
                items.append((item, item_data))

                # Get children
                for child in self.tree.get_children(item):
                    child_data = self.tree.item(child)
                    items.append((child, child_data))

            # Sort items
            if column == '#0':
                # Sort by name
                items.sort(key=lambda x: x[1]['text'], reverse=reverse)
            elif column == 'Status':
                # Sort by status
                items.sort(key=lambda x: x[1]['values'][0] if x[1]['values'] else '', reverse=reverse)
            elif column == 'IP':
                # Sort by IP address (numeric)
                def ip_key(x):
                    if x[1]['values'] and len(x[1]['values']) > 1:
                        ip = x[1]['values'][1]
                        try:
                            return [int(part) for part in ip.split('.')]
                        except Exception:
                            return [0, 0, 0, 0]
                    return [0, 0, 0, 0]
                items.sort(key=ip_key, reverse=reverse)
            elif column == 'MAC':
                # Sort by MAC address
                items.sort(key=lambda x: x[1]['values'][2] if x[1]['values'] and len(x[1]['values']) > 2 else '', reverse=reverse)
            elif column == 'Info':
                # Sort by additional info (vendor information)
                items.sort(key=lambda x: x[1]['values'][4] if x[1]['values'] and len(x[1]['values']) > 4 else '', reverse=reverse)

            # Reorder items in treeview
            for item, item_data in items:
                self.tree.move(item, '', 'end')

        except Exception as e:
            print(f"Sort error: {e}")

    def on_tree_click(self, event):
        """Handle single-click on tree items."""
        try:
            item = self.tree.identify_row(event.y)
            if item:
                # Toggle the item's selection state
                current_tags = list(self.tree.item(item, 'tags'))
                if 'selected' in current_tags:
                    # Remove selection
                    current_tags.remove('selected')
                else:
                    # Add selection
                    current_tags.append('selected')

                self.tree.item(item, tags=current_tags)

                # Configure selected appearance
                self.tree.tag_configure('selected', background=self.dark_select_bg)

                # Force tree update to reflect changes immediately
                self.root.after(10, self.update_tree_view)
        except Exception as e:
            print(f"Click handler error: {e}")

    def on_tree_expand(self, event):
        """Handle tree expansion events."""
        try:
            item = self.tree.focus()
            if item:
                item_text = self.tree.item(item, 'text')
                interface_name = item_text.split(' (')[0]
                self.tree_expanded_states[interface_name] = True
                self.save_persistent_data()
        except Exception as e:
            print(f"Tree expand error: {e}")

    def on_tree_collapse(self, event):
        """Handle tree collapse events."""
        try:
            item = self.tree.focus()
            if item:
                item_text = self.tree.item(item, 'text')
                interface_name = item_text.split(' (')[0]
                self.tree_expanded_states[interface_name] = False
                self.save_persistent_data()
        except Exception as e:
            print(f"Tree collapse error: {e}")

    def on_mousewheel(self, event):
        """Handle mouse wheel scrolling for the treeview."""
        try:
            # Handle different mouse wheel events across platforms
            if event.num == 4:  # Linux scroll up
                self.tree.yview_scroll(-1, "units")
            elif event.num == 5:  # Linux scroll down
                self.tree.yview_scroll(1, "units")
            elif hasattr(event, 'delta'):  # Windows/MacOS
                if event.delta > 0:
                    self.tree.yview_scroll(-1, "units")
                else:
                    self.tree.yview_scroll(1, "units")
        except Exception as e:
            print(f"Mouse wheel scroll error: {e}")

    def on_key_scroll(self, event):
        """Handle keyboard scrolling for the treeview."""
        try:
            if event.keysym == 'Up':
                self.tree.yview_scroll(-1, "units")
            elif event.keysym == 'Down':
                self.tree.yview_scroll(1, "units")
            elif event.keysym == 'Prior':  # Page Up
                self.tree.yview_scroll(-10, "units")
            elif event.keysym == 'Next':   # Page Down
                self.tree.yview_scroll(10, "units")
            elif event.keysym == 'Home':
                self.tree.yview_scroll(-1000, "units")  # Go to top
            elif event.keysym == 'End':
                self.tree.yview_scroll(1000, "units")   # Go to bottom
        except Exception as e:
            print(f"Keyboard scroll error: {e}")

    def toggle_arm_all(self):
        """Toggle between arming and disarming all devices."""
        if self.all_armed:
            self.clear_all()
            self.all_armed = False
            self.arm_toggle_button.config(text="🎯 Arm All")
        else:
            self.select_all()
            self.all_armed = True
            self.arm_toggle_button.config(text="🎯 Disarm All")

    def select_all(self):
        """Select all items in the tree."""
        for item in self.tree.get_children():
            self.select_item_and_children(item)

    def clear_all(self):
        """Clear all selections in the tree."""
        for item in self.tree.get_children():
            self.clear_item_and_children(item)

    def select_item_and_children(self, item):
        """Recursively select an item and its children."""
        current_tags = list(self.tree.item(item, 'tags'))
        if 'selected' not in current_tags:
            current_tags.append('selected')
            self.tree.item(item, tags=current_tags)

        # Select children
        for child in self.tree.get_children(item):
            self.select_item_and_children(child)

    def clear_item_and_children(self, item):
        """Recursively clear selection from an item and its children."""
        current_tags = [tag for tag in self.tree.item(item, 'tags') if tag != 'selected']
        self.tree.item(item, tags=current_tags)

        # Clear children
        for child in self.tree.get_children(item):
            self.clear_item_and_children(child)

    def clear_persistent_data(self):
        """Clear all persistent device data and tree states."""
        try:
            if messagebox.askyesno("Clear History",
                                 "This will clear all saved device history and tree states.\n\n"
                                 "This action cannot be undone. Continue?"):
                # Clear persistent storage
                self.known_devices = {}
                self.tree_expanded_states = {}

                # Clear in-memory data structures that populate the tree
                self.network_data = {}
                self.device_data = {}

                # Clear the tree view immediately
                for item in self.tree.get_children():
                    self.tree.delete(item)

                # Update status to reflect empty state
                self.status_label.config(text="History cleared. Click 'Start Scry' to begin discovery...")

                # Stop scanning and update button state
                self.scanning_active = False
                try:
                    self.scan_button.config(text='🔮 Start Scry', style='Dark.TButton')
                except Exception:
                    self.scan_button.config(text='🔮 Start Scry', style='Dark.TButton')

                # Delete persistent files
                try:
                    devices_file = self.get_data_file_path("known_devices.json")
                    states_file = self.get_data_file_path("tree_states.json")

                    if os.path.exists(devices_file):
                        os.remove(devices_file)
                    if os.path.exists(states_file):
                        os.remove(states_file)
                except Exception as e:
                    print(f"Error deleting persistent files: {e}")

                # Force a fresh scan by clearing any cached data
                # This ensures no old offline devices appear temporarily
                if hasattr(self, '_first_scan_complete'):
                    delattr(self, '_first_scan_complete')

                # The scanning thread will repopulate the data structures and tree
                messagebox.showinfo("History Cleared",
                                  "All device history and tree states have been cleared.\n"
                                  "Click 'Start Scry' when you're ready to rediscover devices.")
        except Exception as e:
            print(f"Clear persistent data error: {e}")

    def export_json_to_terminal(self):
        """Export persistent data to a new terminal window with proper sizing."""
        # Simple debounce mechanism to prevent rapid repeated calls
        import time
        current_time = time.time()
        if hasattr(self, '_last_export_time') and (current_time - self._last_export_time) < 2.0:
            return  # Ignore rapid clicks within 2 seconds
        self._last_export_time = current_time

        try:
            # Prepare the JSON data
            export_data = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'wol_caster_version': __version__,
                'persistent_data': self.known_devices,
                'tree_states': self.tree_expanded_states,
                'current_scan_data': getattr(self, 'network_data', {}),
                'export_note': 'This data can be copied, analyzed, or saved to files'
            }

            # Format JSON for display
            json_output = json.dumps(export_data, indent=2, default=str)

            # Create the terminal command with proper sizing
            if platform.system() == 'Darwin':  # macOS
                # Use Terminal.app with proper sizing (CLI standard: 100x50)
                # Write JSON to temporary file to avoid escaping issues
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                    temp_file.write(json_output)
                    temp_file_path = temp_file.name

                # Use the correct working AppleScript syntax
                # Use open -a Terminal with a temporary .command script for reliable new window
                # Create a temporary .command script that will display the JSON
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.command', delete=False) as cmd_file:
                    cmd_file.write(f"""#!/bin/bash
echo "📄 WoL-Caster JSON Export Data"
echo "=================================================="
cat '{temp_file_path}'
echo "=================================================="
echo "💡 Data displayed in new Terminal window"
rm '{temp_file_path}'
""")
                    cmd_file_path = cmd_file.name
                
                # Make the script executable
                os.chmod(cmd_file_path, 0o755)
                
                # Open the .command script in a new Terminal window with custom title
                # First open Terminal, then set the title
                subprocess.run(["open", "-a", "Terminal", cmd_file_path], check=True)
                
                # Wait a moment for Terminal to open, then set custom title
                time.sleep(0.5)
                try:
                    subprocess.run(["osascript", "-e", 'tell application "Terminal" to set custom title of front window to "Export Data"'], check=False)
                except Exception:
                    pass  # Title setting is optional
                
                print("📄 JSON data exported to new Terminal window!")
                
                # Clean up the temporary .command file after a delay
                def cleanup_cmd():
                    time.sleep(5)  # Wait for Terminal to open
                    try:
                        os.unlink(cmd_file_path)
                    except Exception:
                        pass
                
                # Run cleanup in background
                import threading
                cleanup_thread = threading.Thread(target=cleanup_cmd)
                cleanup_thread.daemon = True
                cleanup_thread.start()
            else:
                # For other platforms, try to open a new terminal
                print("\n📄 JSON Export Data:")
                print("=" * 50)
                print(json_output)
                print("\n💡 Copy this data from the terminal output above.")

            print("📄 JSON data exported to new terminal window!")

        except Exception as e:
            print(f"Error exporting JSON: {e}")
            messagebox.showerror("Export Error", f"Failed to export JSON data:\n{e}")

    def get_selected_items(self):
        """Get all selected items from the tree."""
        selected_networks = []
        selected_devices = []

        def check_item(item):
            tags = self.tree.item(item, 'tags')
            item_text = self.tree.item(item, 'text')
            if self.debug_mode:
                print(f"🔍 DEBUG: Checking item '{item_text}' with tags: {tags}")

            if 'selected' in tags:
                if self.debug_mode:
                    print(f"🔍 DEBUG: Item '{item_text}' is selected")
                if 'adapter' in tags:
                    # Adapter selected - add all networks under this adapter
                    adapter_name = item_text.split(' (')[0]  # Extract en1 from "en1 (WiFi)"
                    if self.debug_mode:
                        print(f"🔍 DEBUG: Adapter '{item_text}' selected, adding all networks under '{adapter_name}'")
                    if adapter_name in self.network_data:
                        selected_networks.append(adapter_name)
                        if self.debug_mode:
                            print(f"🔍 DEBUG: Added adapter '{adapter_name}' to selected_networks")
                    else:
                        if self.debug_mode:
                            print(f"🔍 DEBUG: Adapter '{adapter_name}' not found in network_data keys: {list(self.network_data.keys())}")
                elif 'network' in tags:
                    # Network selected - need to find the parent adapter to get interface name
                    parent = self.tree.parent(item)
                    if parent:
                        parent_text = self.tree.item(parent, 'text')
                        interface_name = parent_text.split(' (')[0]  # Extract en1 from "en1 (WiFi)"
                        if self.debug_mode:
                            print(f"🔍 DEBUG: Network '{item_text}' belongs to adapter '{interface_name}'")
                        if interface_name in self.network_data:
                            selected_networks.append(interface_name)
                            if self.debug_mode:
                                print(f"🔍 DEBUG: Added network '{interface_name}' to selected_networks")
                        else:
                            if self.debug_mode:
                                print(f"🔍 DEBUG: Interface '{interface_name}' not found in network_data keys: {list(self.network_data.keys())}")
                    else:
                        if self.debug_mode:
                            print(f"🔍 DEBUG: Network '{item_text}' has no parent")
                elif any(tag.startswith('device_') for tag in tags):
                    # Device selected - need to find the grandparent adapter to get interface name
                    network_parent = self.tree.parent(item)
                    if network_parent:
                        adapter_parent = self.tree.parent(network_parent)
                        if adapter_parent:
                            adapter_text = self.tree.item(adapter_parent, 'text')
                            interface_name = adapter_text.split(' (')[0]  # Extract en1 from "en1 (WiFi)"
                        device_ip = self.tree.item(item, 'values')[1]
                        if self.debug_mode:
                            print(f"🔍 DEBUG: Device '{item_text}' (IP: {device_ip}) belongs to adapter '{interface_name}'")

                        # Find the device in our data
                        for device in self.device_data.get(interface_name, []):
                            if device['ip'] == device_ip:
                                selected_devices.append((interface_name, device))
                                if self.debug_mode:
                                    print(f"🔍 DEBUG: Added device '{device_ip}' to selected_devices")
                                break
                        else:
                            if self.debug_mode:
                                print(f"🔍 DEBUG: Device '{item_text}' has no grandparent adapter")
                    else:
                        if self.debug_mode:
                            print(f"🔍 DEBUG: Device '{item_text}' has no parent network")

            # Check children
            for child in self.tree.get_children(item):
                check_item(child)

        # Check all top-level items
        for item in self.tree.get_children():
            check_item(item)

        if self.debug_mode:
            print(f"🔍 DEBUG: Final selection - Networks: {selected_networks}, Devices: {len(selected_devices)}")
        return selected_networks, selected_devices

    def toggle_broadcast(self):
        """Toggle between start and stop cast."""
        if self.broadcasting_active:
            self.stop_broadcast()
        else:
            self.start_broadcast()

    def start_broadcast(self):
        """Start the casting process."""
        try:
            selected_networks, selected_devices = self.get_selected_items()

            if not selected_networks and not selected_devices:
                messagebox.showwarning("No Selection",
                                     "Please select at least one network or device to cast to.")
                return

            # Show confirmation dialog
            total_targets = 0
            if selected_networks:
                for net in selected_networks:
                    try:
                        network = ipaddress.IPv4Network(self.network_data[net]['subnet'], strict=False)
                        total_targets += len(list(network.hosts())) + 2
                    except Exception:
                        total_targets += 254  # Reasonable estimate

            total_targets += len(selected_devices)

            message = f"Send magic packets to:\n"
            if selected_networks:
                message += f"• {len(selected_networks)} entire network(s)\n"
            if selected_devices:
                message += f"• {len(selected_devices)} specific device(s)\n"
            message += f"\nTotal targets: ~{total_targets} addresses"

            if not messagebox.askyesno("Confirm Cast", message):
                return

            # Start casting
            self.broadcasting_active = True
            # Scry continues running - no need to stop it!
            print(f"🔮 Cast started while scry continues (scanning_active = {self.scanning_active})")

            # Update buttons to reflect actual state
            try:
                self.start_button.config(text='✨ Stop Cast', style='Stop.TButton')
                # Scry button shows current scry state
                if self.scanning_active:
                    self.scan_button.config(text='🔮 End Scry', style='Scan.TButton')
                else:
                    self.scan_button.config(text='🔮 Start Scry', style='Dark.TButton')
            except Exception:
                self.start_button.config(text='✨ Stop Cast', bg='red', fg='white')
                if self.scanning_active:
                    self.scan_button.config(text='🔮 End Scry', bg='#9C27B0', fg='white')
                else:
                    self.scan_button.config(text='🔮 Start Scry', bg='lightgray', fg='black')

            # Run cast in separate thread
            def broadcast_worker():
                try:
                    total_targets = 0
                    completed = 0

                    # Calculate total targets
                    for interface_name in selected_networks:
                        interface_info = self.network_data[interface_name]
                        network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)
                        total_targets += len(list(network.hosts())) + 2

                    total_targets += len(selected_devices)

                    # Show progress bar
                    self.root.after(0, lambda: self.show_progress_bar("Preparing cast...", 0, total_targets))

                    # Small delay to ensure progress bar is visible
                    time.sleep(0.1)

                    # Cast to selected networks
                    for interface_name in selected_networks:
                        if not self.broadcasting_active:  # Check if stopped
                            break

                        interface_info = self.network_data[interface_name]
                        network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)

                        # Create magic packet
                        magic_packet = create_magic_packet()

                        # Send to all IPs in network
                        host_ips = list(network.hosts())
                        for i, ip in enumerate(host_ips):
                            if not self.broadcasting_active:  # Check if stopped
                                break

                            send_magic_packet_to_ip(str(ip), magic_packet)
                            completed += 1

                            # Update progress on every completion for smooth animation
                            self.root.after(0, lambda c=completed, t=total_targets:
                                          self.update_progress(f"Casting to {interface_name}...", c, t))

                    # Cast to selected devices
                    for interface_name, device in selected_devices:
                        if not self.broadcasting_active:  # Check if stopped
                            break

                        send_magic_packet_to_device(device)
                        completed += 1
                        self.root.after(0, lambda c=completed, t=total_targets:
                                      self.update_progress("Sending to selected devices...", c, t))

                    # Ensure progress shows 100% completion
                    self.root.after(0, lambda: self.update_progress("Cast complete!", total_targets, total_targets))

                    # Show completion message
                    if self.broadcasting_active:
                        self.root.after(0, self.broadcast_complete)
                    else:
                        self.root.after(0, self.broadcast_stopped)

                except Exception as e:
                    self.root.after(0, lambda error_msg=str(e): self.broadcast_error(error_msg))

            threading.Thread(target=broadcast_worker, daemon=True).start()
        except Exception as e:
            print(f"Cast start error: {e}")

    def broadcast_error(self, error_msg):
        """Handle cast errors."""
        try:
            messagebox.showerror("Cast Error", f"An error occurred during casting:\n{error_msg}")

            self.broadcasting_active = False

            # Update buttons
            try:
                self.start_button.config(text='✨ Start Cast', style='Dark.TButton')
                # Scry button shows current scry state
                if self.scanning_active:
                    self.scan_button.config(text='🔮 End Scry', style='Scan.TButton')
                else:
                    self.scan_button.config(text='🔮 Start Scry', style='Dark.TButton')
            except Exception:
                self.start_button.config(text='✨ Start Cast', bg='lightgray', fg='black')
                if self.scanning_active:
                    self.scan_button.config(text='🔮 End Scry', bg='#9C27B0', fg='white')
                else:
                    self.scan_button.config(text='🔮 Start Scry', bg='lightgray', fg='black')

            self.hide_progress_bar()

            # Note: Scry continues running independently of cast errors
            # User has full control over scry lifecycle

            # Update scan button to reflect actual state
            self.update_scan_button_state()
        except Exception as e:
            print(f"Cast error handler error: {e}")

    def show_progress_bar(self, message, current, total):
        """Show the progress bar with initial values."""
        self.progress_label.config(text=message)
        self.progress_bar['value'] = 0
        self.progress_bar['maximum'] = total
        self.progress_frame.pack(pady=(0, 10), fill=tk.X, padx=20)
        # Force immediate GUI update
        self.root.update_idletasks()
        self.root.update()

    def update_progress(self, message, current, total):
        """Update the progress bar."""
        try:
            self.progress_label.config(text=message)
            self.progress_bar['value'] = current
            percentage = (current / total) * 100 if total > 0 else 0
            self.progress_label.config(text=f"{message} ({percentage:.1f}%)")
            # Force immediate GUI update for smooth animation
            self.root.update_idletasks()
        except Exception as e:
            print(f"Progress update error: {e}")

    def hide_progress_bar(self):
        """Hide the progress bar."""
        self.progress_frame.pack_forget()

    def stop_broadcast(self):
        """Stop the casting process."""
        self.broadcasting_active = False
        messagebox.showinfo("Cast Stopped", "Casting has been stopped.")
        self.broadcast_stopped()

    def broadcast_stopped(self):
        """Handle cast stop."""
        try:
            self.broadcasting_active = False

            # Update buttons
            try:
                self.start_button.config(text='✨ Start Cast', style='Dark.TButton')
                # Scry button shows current scry state
                if self.scanning_active:
                    self.scan_button.config(text='🔮 End Scry', style='Scan.TButton')
                else:
                    self.scan_button.config(text='🔮 Start Scry', style='Dark.TButton')
            except Exception:
                self.start_button.config(text='✨ Start Cast', bg='lightgray', fg='black')
                if self.scanning_active:
                    self.scan_button.config(text='🔮 End Scry', bg='#9C27B0', fg='white')
                else:
                    self.scan_button.config(text='🔮 Start Scry', bg='lightgray', fg='black')

            self.hide_progress_bar()

            print(f"🔮 Cast stopped - scry state preserved (scanning_active = {self.scanning_active})")
            # Note: Scry continues running independently of cast stop
            # User has full control over scry lifecycle

            # Update scan button to reflect actual state
            self.update_scan_button_state()
        except Exception as e:
            print(f"Cast stop error: {e}")

    def broadcast_complete(self):
        """Handle successful cast completion."""
        try:
            messagebox.showinfo("Cast Complete",
                               "Magic packets sent successfully!\n\n"
                               "Devices with Wake-on-LAN enabled should now be waking up.")

            self.broadcasting_active = False

            # Update buttons
            try:
                self.start_button.config(text='✨ Start Cast', style='Dark.TButton')
                # Scry button shows current scry state
                if self.scanning_active:
                    self.scan_button.config(text='🔮 End Scry', style='Scan.TButton')
                else:
                    self.scan_button.config(text='🔮 Start Scry', style='Dark.TButton')
            except Exception:
                self.start_button.config(text='✨ Start Cast', bg='lightgray', fg='black')
                if self.scanning_active:
                    self.scan_button.config(text='🔮 End Scry', bg='#9C27B0', fg='white')
                else:
                    self.scan_button.config(text='🔮 Start Scry', bg='lightgray', fg='black')

            self.hide_progress_bar()

            print(f"🔮 Cast complete - scry state preserved (scanning_active = {self.scanning_active})")
            # Note: Scry continues running independently of cast completion
            # User has full control over scry lifecycle

            # Update scan button to reflect actual state
            self.update_scan_button_state()
        except Exception as e:
            print(f"Cast complete error: {e}")

    def toggle_scan(self):
        """Toggle between start and stop scanning."""
        print(f"🔮 Toggle scan called - current scanning_active: {self.scanning_active}")
        if self.scanning_active:
            self.stop_scan()
        else:
            self.start_scan()

    def start_scan(self):
        """Start the scanning process."""
        if not self.scanning_active and not self.broadcasting_active:
            self.scanning_active = True
            print(f"🔮 Manual scry started (scanning_active = {self.scanning_active})")
            self.scan_thread = threading.Thread(target=self.scan_worker, daemon=True)
            self.scan_thread.start()

            # Update scan button to reflect active state
            self.update_scan_button_state()

            # Update status
            self.status_label.config(text="Scrying networks and devices...")

    def update_scan_button_state(self):
        """Update the scan button to reflect the current scanning state."""
        try:
            if self.scanning_active:
                # Scry is active - show "End Scry"
                self.scan_button.config(text='🔮 End Scry', style='Scan.TButton')
                print(f"🔮 Button updated to 'End Scry' (scanning_active = {self.scanning_active})")
            else:
                # Scry is stopped - show "Start Scry"
                self.scan_button.config(text='🔮 Start Scry', style='Dark.TButton')
                print(f"🔮 Button updated to 'Start Scry' (scanning_active = {self.scanning_active})")
        except Exception as e:
            print(f"🔮 Button update error: {e}")
            # Fallback styling
            if self.scanning_active:
                self.scan_button.config(text='🔮 End Scry', bg='#9C27B0', fg='white')
            else:
                self.scan_button.config(text='🔮 Start Scry', bg='lightgray', fg='black')

    def stop_scan(self):
        """Stop the scanning process."""
        self.scanning_active = False
        print(f"🔮 Scry manually stopped (scanning_active = {self.scanning_active})")

        # Clear any progress message immediately
        self.root.after(0, lambda: self.status_label.config(text="Scrying will end at next boundary..."))

        # Update scan button to reflect stopped state
        self.update_scan_button_state()

    def run(self):
        """Start the GUI application."""
        def on_closing():
            self.scanning_active = False
            self.save_persistent_data()
            self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", on_closing)
        self.root.mainloop()

    def configure_macos_menu(self):
        """Configure the macOS menu bar for WoL-Caster using Tkinter."""
        try:
            # Remove default menus and create custom ones
            self.root.option_add('*tearOff', False)
            
            # Create main menu bar
            menubar = tk.Menu(self.root)
            self.root.config(menu=menubar)
            
            # Create File menu
            file_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="Import JSON...", command=self.importJSON)
            file_menu.add_command(label="Export JSON...", command=self.exportJSON)
            
            # Create Edit menu
            edit_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Edit", menu=edit_menu)
            edit_menu.add_command(label="Clear History", command=self.clearHistory)
            
            # Create Help menu
            help_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Help", menu=help_menu)
            
            print("✅ Configured Tkinter-based menu bar")
            
        except Exception as e:
            print(f"❌ Tkinter menu configuration error: {e}")
            print("   The app will run with default menu behavior")

    def importJSON(self):
        """Handle Import JSON menu action."""
        try:
            from tkinter import filedialog, messagebox
            
            filename = filedialog.askopenfilename(
                title="Import Device Data",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not filename:
                return  # User cancelled
                
            # Load and validate the JSON file
            try:
                with open(filename, 'r') as f:
                    imported_data = json.load(f)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON format in file:\n\n{str(e)}\n\nPlease ensure the file contains valid JSON data."
                messagebox.showerror("Import Error", error_msg)
                return
            except Exception as e:
                error_msg = f"Error reading file:\n\n{str(e)}\n\nPlease check file permissions and try again."
                messagebox.showerror("Import Error", error_msg)
                return
            
            # Simple import - just add devices to known_devices
            if 'devices' in imported_data:
                for device_data in imported_data['devices']:
                    # Create a unique key for this device
                    device_key = f"{device_data.get('ip', '')}_{device_data.get('mac', '')}"
                    if device_key not in self.known_devices:
                        self.known_devices[device_key] = device_data
                        print(f"➕ Added new device: {device_data.get('ip', 'Unknown')}")
                    else:
                        print(f"🔄 Device already exists: {device_data.get('ip', 'Unknown')}")
                
                # Save the imported data
                self.save_persistent_data()
                
                # Show import summary
                messagebox.showinfo("Import Complete", 
                    f"Successfully imported data from {os.path.basename(filename)}\n\n"
                    f"• Devices added to persistent storage\n"
                    f"• The device tree will update on next scan")
                
                print(f"✅ Imported data from {filename}")
                
        except Exception as e:
            error_msg = f"Unexpected error during import:\n{str(e)}"
            print(f"❌ Import error: {e}")
            messagebox.showerror("Import Error", error_msg)

    def exportJSON(self):
        """Handle Export JSON menu action."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                title="Export Device Data",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filename:
                # Prepare export data with comprehensive device information
                devices_to_export = []
                
                # Process each interface and its devices
                for interface_name, device_list in self.known_devices.items():
                    if isinstance(device_list, list):
                        for device_data in device_list:
                            if isinstance(device_data, dict):
                                # Create a clean export version with all important fields
                                export_device = {
                                    'ip': device_data.get('ip', ''),
                                    'mac': device_data.get('mac', ''),
                                    'hostname': device_data.get('hostname', ''),
                                    'vendor': device_data.get('vendor', ''),
                                    'status': device_data.get('status', ''),
                                    'last_seen': device_data.get('last_seen', ''),
                                    'interface': device_data.get('interface', interface_name),
                                    'current_scan': device_data.get('current_scan', False),
                                    'historical': device_data.get('historical', False)
                                }
                                
                                # Remove empty fields to keep export clean (but keep False values)
                                export_device = {k: v for k, v in export_device.items() if v or v is False}
                                devices_to_export.append(export_device)
                
                # Include debug mode status in export
                export_data = {
                    'export_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'export_version': '1.0',
                    'total_devices': len(devices_to_export),
                    'debug_mode': self.debug_mode,  # Include debug status
                    'devices': devices_to_export,
                    'scan_history': {
                        'total_devices': len(devices_to_export),
                        'last_scan': time.time()
                    }
                }
                
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                print(f"✅ Exported {len(devices_to_export)} devices to {filename}")
                print(f"   Export format includes: {list(export_data.keys())}")
                print(f"   Debug mode: {'ON' if self.debug_mode else 'OFF'}")
                
        except Exception as e:
            print(f"❌ Export error: {e}")

    def clearHistory(self):
        """Handle Clear History menu action."""
        try:
            # Clear the device tree
            self.device_tree.delete(*self.device_tree.get_children())
            
            # Clear known devices
            self.known_devices.clear()
            
            # Clear tree expansion states
            self.tree_expanded_states.clear()
            
            # Save the cleared state
            self.save_persistent_data()
            
            print("✅ History cleared")
            
        except Exception as e:
            print(f"❌ Clear history error: {e}")



# CLI Functions for backward compatibility

def get_network_summary(interfaces):
    """Get a summary of networks that will be targeted."""
    summary = []
    total_addresses = 0

    for iface in interfaces:
        try:
            network = ipaddress.IPv4Network(iface['subnet'], strict=False)
            address_count = len(list(network.hosts())) + 2
            range_display = format_network_range(iface['subnet'])

            summary.append({
                'interface': iface['interface'],
                'range': range_display,
                'count': address_count,
                'host_ip': iface['ip']
            })
            total_addresses += address_count
        except Exception:
            continue

    return summary, total_addresses

def create_progress_bar(current, total, width=50, prefix="Progress"):
    """Create a visual progress bar for CLI."""
    # Adjust width based on terminal size
    terminal_width = get_terminal_size().columns
    available_width = terminal_width - len(prefix) - 20  # Account for prefix and percentages
    width = max(10, min(width, available_width))

    filled_width = int(width * current // total)
    bar = "█" * filled_width + "░" * (width - filled_width)
    percent = (current / total) * 100
    return f"{prefix}: |{bar}| {current}/{total} ({percent:.1f}%)"

def broadcast_to_subnet(interface_info, progress_callback=None, verbose=False, is_gui_mode=False):
    """Send magic packets to all IPs in a subnet."""
    magic_packet = create_magic_packet()
    network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)

    # Get all host IPs in the network
    host_ips = [str(ip) for ip in network.hosts()]

    # Also include network and broadcast addresses for completeness
    all_ips = [str(network.network_address)] + host_ips + [str(network.broadcast_address)]

    if verbose and not is_gui_mode:
        terminal_width = get_terminal_size().columns
        print(f"\nInterface: {interface_info['interface']}")
        print(f"Target Range: {format_network_range(interface_info['subnet'])}")
        print(f"Addresses: {len(all_ips):,}")
        print(f"Starting broadcast...")
    elif not is_gui_mode:
        message = f"Sending magic packets to {len(all_ips)} addresses in {interface_info['subnet']} via {interface_info['interface']}"
        terminal_width = get_terminal_size().columns
        wrapped_lines = wrap_text(message, terminal_width)
        for line in wrapped_lines:
            print(line)

    # Use ThreadPoolExecutor for concurrent sending
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        for ip in all_ips:
            future = executor.submit(send_magic_packet_to_ip, ip, magic_packet)
            futures.append(future)

        # Wait for all to complete with progress tracking
        completed = 0
        for i, future in enumerate(futures):
            try:
                future.result(timeout=1.0)
            except Exception:
                pass
            completed += 1

            # Update progress
            if progress_callback:
                progress_callback(completed, len(all_ips), interface_info['interface'])

            # CLI progress bar
            if verbose and not is_gui_mode and (completed % max(1, len(all_ips) // 100) == 0 or completed == len(all_ips)):
                progress_bar = create_progress_bar(completed, len(all_ips),
                                                 prefix=f"{interface_info['interface'][:12]}")
                # Use proper terminal control sequences for line clearing
                terminal_width = get_terminal_size().columns
                # Clear entire line and rewrite
                sys.stdout.write('\r' + ' ' * terminal_width + '\r')
                sys.stdout.write(progress_bar)
                sys.stdout.flush()

        if verbose and not is_gui_mode:
            print()  # New line after progress bar completion
            print(f"Completed {interface_info['interface']}: {completed:,} packets sent")

    return completed

def main_broadcast_selected(selected_network_summaries, progress_callback=None, network_display_callback=None, overall_progress_callback=None, is_gui_mode=False):
    """Main function to broadcast to selected network interfaces only."""
    if not selected_network_summaries:
        if not is_gui_mode:
            print("No networks selected for broadcast!")
        return False, []

    # Convert summary back to interface format for broadcasting
    interfaces_to_broadcast = []
    all_interfaces = get_network_interfaces()

    for summary in selected_network_summaries:
        for interface_info in all_interfaces:
            if interface_info['interface'] == summary['interface']:
                interfaces_to_broadcast.append(interface_info)
                break

    if network_display_callback:
        total_addresses = sum(net['count'] for net in selected_network_summaries)
        network_display_callback(selected_network_summaries, total_addresses)

    if not is_gui_mode:
        terminal_width = get_terminal_size().columns

        print(f"Casting to {len(selected_network_summaries)} selected network(s):")
        print("Networks to target:")

        # Use adaptive table for network display
        headers = ['Interface', 'Range', 'Addresses', 'Host IP']
        rows = []
        for summary in selected_network_summaries:
            rows.append([
                summary['interface'],
                summary['range'],
                f"{summary['count']:,}",
                summary['host_ip']
            ])

        print_adaptive_table(headers, rows)

        total_addresses = sum(net['count'] for net in selected_network_summaries)
        total_msg = f"Total addresses to contact: {total_addresses:,}"
        wrapped_total = wrap_text(total_msg, terminal_width)
        for line in wrapped_total:
            print(line)

        print("\nStarting Wake-on-LAN broadcast...")
        print(create_adaptive_separator('='))

    # Process each selected interface
    for i, interface_info in enumerate(interfaces_to_broadcast, 1):
        try:
            if overall_progress_callback:
                overall_progress_callback(i, len(interfaces_to_broadcast))

            completed = broadcast_to_subnet(interface_info, progress_callback, verbose=not is_gui_mode, is_gui_mode=is_gui_mode)

        except Exception as e:
            if not is_gui_mode:
                error_msg = f"Error processing {interface_info['interface']}: {e}"
                terminal_width = get_terminal_size().columns
                wrapped_error = wrap_text(error_msg, terminal_width)
                for line in wrapped_error:
                    print(line)

    if not is_gui_mode:
        terminal_width = get_terminal_size().columns
        print(create_adaptive_separator('='))
        print(f"BROADCAST COMPLETE!")

        summary_lines = [
            f"Total: {sum(net['count'] for net in selected_network_summaries):,} addresses across {len(interfaces_to_broadcast)} network(s)",
            f"All operations completed successfully"
        ]

        for line in summary_lines:
            wrapped_lines = wrap_text(line, terminal_width)
            for wrapped_line in wrapped_lines:
                print(wrapped_line)

    return True, selected_network_summaries

# Global storage for CLI persistent data - UNIFIED WITH GUI
cli_persistent_data = {
    'known_devices': {},  # interface_name -> list of known devices (including offline) - UNIFIED WITH GUI
    'selected_networks': set(),
    'selected_devices': set(),
    'debug_mode': False  # Debug mode toggle for CLI
}

def load_cli_persistent_data():
    """Load persistent device data for CLI mode - EXACT SAME LOGIC AS GUI.

    ⚠️  CRITICAL: CLI is READ-ONLY for persistent data.
    CLI NEVER writes to known_devices.json to prevent corruption.
    Only the GUI writes to persistent data.

    ✅ FIXED: CLI now uses known_devices instead of discovered_devices for unified data structure.
    """
    try:
        # Use EXACT SAME file path as GUI
        data_dir = os.path.expanduser("~/.wol_caster")
        devices_file = os.path.join(data_dir, "known_devices.json")
        if os.path.exists(devices_file):
            with open(devices_file, 'r') as f:
                cli_persistent_data['known_devices'] = json.load(f)
        else:
            cli_persistent_data['known_devices'] = {}

        # Load debug mode setting (same file as GUI)
        debug_file = os.path.join(data_dir, "debug_settings.json")
        if os.path.exists(debug_file):
            with open(debug_file, 'r') as f:
                debug_settings = json.load(f)
                cli_persistent_data['debug_mode'] = debug_settings.get('debug_mode', False)
        else:
            # Default to disabled
            cli_persistent_data['debug_mode'] = False
    except Exception as e:
        print(f"Error loading CLI persistent data: {e}")
        cli_persistent_data['known_devices'] = {}
        cli_persistent_data['debug_mode'] = False

def get_cli_selection():
    """Get user selection in CLI mode with single network viewing, progress bar, and persistent data."""
    # Get network interfaces
    interfaces = get_network_interfaces()
    if not interfaces:
        print("No network interfaces found!")
        return [], []

    # Show network adapter choice menu first
    print("Available Network Adapters:")
    print("=" * 50)
    for i, interface in enumerate(interfaces, 1):
        range_display = format_network_range(interface['subnet'])
        device_count = len(cli_persistent_data['known_devices'].get(interface['interface'], []))
        status_indicator = f" ({device_count} devices)" if device_count > 0 else ""
        print(f"  {i}. {interface['interface']} ({range_display}){status_indicator}")
    print("=" * 50)

    # Get user choice for which network to view
    while True:
        try:
            choice = input("\nSelect network adapter to view (1-{}): ".format(len(interfaces))).strip()
            if choice.lower() == 'quit':
                return [], []

            choice_num = int(choice)
            if 1 <= choice_num <= len(interfaces):
                selected_interface = interfaces[choice_num - 1]
                break
            else:
                print("Invalid selection. Please choose 1-{}.".format(len(interfaces)))
        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\n\nExiting...")
            return [], []

    # Check if we already have discovered devices for this interface
    interface_name = selected_interface['interface']
    if interface_name in cli_persistent_data['known_devices']:
        print(f"Using previously discovered devices for {interface_name}")
        devices = cli_persistent_data['known_devices'][interface_name]
    else:
        # Scan the selected network with progress bar
        print(f"\nScrying {interface_name}...")
        devices = scan_network_for_devices_with_progress(selected_interface)
        # Store discovered devices in known_devices for persistence
        cli_persistent_data['known_devices'][interface_name] = devices

    network_data = {interface_name: selected_interface}
    device_data = {interface_name: devices}

    # Use persistent selections
    selected_networks = cli_persistent_data['selected_networks'].copy()
    selected_devices = cli_persistent_data['selected_devices'].copy()

    while True:
        # Display current tree (single network only)
        display_cli_tree(network_data, device_data, selected_networks, selected_devices)

        print("\nSelection Options:")
        print("  n <network_name> - Toggle network selection")
        print("  d <ip_address>   - Toggle device selection")
        print("  all              - Select all devices on this network")
        print("  clear            - Clear all selections")
        print("  scan             - Re-scry this network")
        print("  switch           - Switch to different network")
        print("  start            - Start broadcast")
        print("  quit             - Exit")

        try:
            user_input = input("\nEnter command: ").strip().lower()

            if user_input == 'quit':
                return [], []

            elif user_input == 'switch':
                # Save current selections to persistent storage
                cli_persistent_data['selected_networks'] = selected_networks.copy()
                cli_persistent_data['selected_devices'] = selected_devices.copy()
                # Return to network selection
                return get_cli_selection()

            elif user_input == 'all':
                selected_networks.add(interface_name)
                for device in devices:
                    selected_devices.add(device['ip'])
                print("All devices on this network selected")

            elif user_input == 'clear':
                selected_networks.clear()
                selected_devices.clear()
                print("All selections cleared")

            elif user_input == 'scan':
                print(f"Re-scrying {interface_name}...")
                devices = scan_network_for_devices_with_progress(selected_interface)
                device_data[interface_name] = devices
                # Update persistent storage
                cli_persistent_data['known_devices'][interface_name] = devices
                print("Scry complete")

            elif user_input == 'start':
                if not selected_networks and not selected_devices:
                    print("No networks or devices selected!")
                    continue

                # Save final selections to persistent storage
                cli_persistent_data['selected_networks'] = selected_networks.copy()
                cli_persistent_data['selected_devices'] = selected_devices.copy()

                # Convert selections to the format expected by broadcast functions
                selected_network_summaries = []
                for net_name in selected_networks:
                    if net_name in network_data:
                        interface_info = network_data[net_name]
                        network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)
                        selected_network_summaries.append({
                            'interface': net_name,
                            'range': format_network_range(interface_info['subnet']),
                            'count': len(list(network.hosts())) + 2,
                            'host_ip': interface_info['ip']
                        })

                return selected_network_summaries, selected_devices

            elif user_input.startswith('n '):
                network_name = user_input[2:].strip()
                if network_name in network_data:
                    if network_name in selected_networks:
                        selected_networks.remove(network_name)
                        print(f"Network '{network_name}' deselected")
                    else:
                        selected_networks.add(network_name)
                        print(f"Network '{network_name}' selected")
                else:
                    print(f"Network '{network_name}' not found")

            elif user_input.startswith('d '):
                ip_address = user_input[2:].strip()
                if ip_address in selected_devices:
                    selected_devices.remove(ip_address)
                    print(f"Device '{ip_address}' deselected")
                else:
                    selected_devices.add(ip_address)
                    print(f"Device '{ip_address}' selected")

            else:
                print("Invalid command. Please try again.")

        except KeyboardInterrupt:
            print("\n\nExiting...")
            return [], []
        except Exception as e:
            print(f"Error: {e}")
            continue

def display_cli_tree(network_data, device_data, selected_networks=None, selected_devices=None):
    """Display a tree-like structure in CLI for network and device detection."""
    if selected_networks is None:
        selected_networks = set()
    if selected_devices is None:
        selected_devices = set()

    terminal_width = get_terminal_size().columns
    print("\n" + "=" * terminal_width)
    print("NETWORK & DEVICE DETECTION TREE")
    print("=" * terminal_width)

    if not network_data:
        print("No networks detected.")
        return

    for interface_name, interface_info in network_data.items():
        # Network header
        range_display = format_network_range(interface_info['subnet'])
        devices = device_data.get(interface_name, [])
        device_count = len(devices)
        online_count = sum(1 for d in devices if d['status'] == 'online')

        # Determine network status
        if online_count > 0:
            network_status = "●"  # Green circle for online devices
        elif device_count > 0:
            network_status = "●"  # Red circle for offline devices
        else:
            network_status = "○"  # White circle for no devices

        # Selection indicator
        selection_indicator = "✓" if interface_name in selected_networks else " "

        # Network line
        network_line = f"{network_status} {selection_indicator} {interface_name} ({range_display}) - {online_count}/{device_count} devices"
        print(network_line)

        # Device details
        if devices:
            for device in devices:
                # Device status symbols
                if device['status'] == 'online':
                    device_status = "●"
                    status_color = "●"
                elif device['status'] == 'offline':
                    device_status = "○"
                    status_color = "●"
                elif device['status'] == 'standby':
                    device_status = "◐"
                    status_color = "●"
                else:
                    device_status = "○"
                    status_color = "○"

                # Selection indicator for device
                device_selection = "✓" if device['ip'] in selected_devices else " "

                # Device line
                device_line = f"  {status_color} {device_selection} {device['hostname']} - {device['ip']}"
                if device['mac']:
                    device_line += f" ({device['mac']})"
                    # Add vendor information
                    vendor = get_mac_vendor(device['mac'], silent=True)
                    if vendor:
                        device_line += f" - {vendor}"
                # Don't add redundant status - it's already shown by the status symbol

                print(device_line)
        else:
            print("  ○ No devices detected")

        print()  # Empty line between networks

    print("=" * terminal_width)
    print("Legend: ● Online | ● Offline | ◐ Standby | ○ No devices")
    print("        ✓ Selected |   Not selected")
    print("=" * terminal_width)

def scan_network_for_devices_with_progress(interface_info):
    """Scan a network with CLI progress bar and interrupt support."""
    try:
        network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)
        host_ips = [str(ip) for ip in network.hosts()]

        # Chunked scanning for large networks
        chunk_size = 255
        total_ips = len(host_ips)

        devices = []
        scanned = 0
        interrupted = False

        print(f"Scrying {total_ips} addresses in chunks of {chunk_size}...")
        print("Press '.' to interrupt scry and show discovered devices")

        # Process in chunks
        for chunk_start in range(0, total_ips, chunk_size):
            if interrupted:
                break

            chunk_end = min(chunk_start + chunk_size, total_ips)
            chunk_ips = host_ips[chunk_start:chunk_end]

            # Show progress
            progress = (scanned / total_ips) * 100
            progress_bar = create_progress_bar(scanned, total_ips, prefix=f"{interface_info['interface']}")
            print(f"\r{progress_bar}", end='', flush=True)

            # Check for interrupt key
            if check_for_interrupt():
                interrupted = True
                print(f"\nScry interrupted by user. Showing {len(devices)} discovered devices.")
                break

            # Use ThreadPoolExecutor for concurrent scanning within chunk
            with ThreadPoolExecutor(max_workers=20) as executor:
                device_futures = []

                for ip in chunk_ips:
                    future = executor.submit(scan_single_ip, ip)
                    device_futures.append(future)

                for future in device_futures:
                    try:
                        device = future.result(timeout=3)
                        if device and device['status'] != "hidden":
                            devices.append(device)
                        scanned += 1
                    except Exception:
                        scanned += 1
                        continue

            # Small delay between chunks
            if chunk_end < total_ips:
                time.sleep(0.1)

        # Final progress bar
        if not interrupted:
            progress_bar = create_progress_bar(total_ips, total_ips, prefix=f"{interface_info['interface']}")
            print(f"\r{progress_bar}")
            print(f"Found {len(devices)} devices on {interface_info['interface']}")
        else:
            print(f"Scry interrupted. Found {len(devices)} devices on {interface_info['interface']}")

        return devices
    except Exception as e:
        print(f"Scan error: {e}")
        return []

def check_for_interrupt():
    """Check if user pressed the interrupt key ('.')."""
    try:
        # Check if there's input available (non-blocking)
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if key == '.':
                return True
        return False
    except Exception:
        return False

def scan_single_ip(ip):
    """Scan a single IP address."""
    try:
        status = check_device_status(ip)
        hostname = None
        mac_address = None

        if status in ["online", "standby"]:
            hostname = get_device_identifier(ip)
            mac_address = get_mac_address(ip)

        # Determine hostname
        if status in ["online", "standby"]:
            display_hostname = hostname or f".{ip.split('.')[-1]}"
        else:
            status = "hidden"
            display_hostname = None

        device = {
            'ip': ip,
            'hostname': display_hostname,
            'mac': mac_address,
            'status': status,
            'pingable': status == "online",
            'last_seen': time.time() if status in ["online", "standby"] else 0
        }

        return device
    except Exception:
        return None

def run_cli():
    """Run enhanced CLI mode with parallel scanning and single-character menu."""
    # Try to resize terminal first if it's too small
    if should_launch_new_terminal():
        print("📱 Terminal size may be too small for optimal experience")
        print("🔄 Attempting to resize terminal...")
        try_resize_terminal()
        
        # Check if resize was successful, if not, then launch new terminal
        if should_launch_new_terminal():
            print("⚠️  Terminal resize didn't work completely")
            print("🚀 Launching new terminal window instead...")
            launch_proper_terminal()
            return

    # Load persistent data for CLI
    load_cli_persistent_data()

    print("🪄 WoL-Caster - Wake-on-LAN Network Broadcaster")
    print("💻 Enhanced CLI Mode with Parallel Device Detection")
    print("=" * 60)

    while True:
        try:
            # Main menu
            show_cli_main_menu()
            choice = input("\nEnter choice (1-9): ").strip()

            if choice == '1':
                # Scan networks
                scan_networks_cli()
            elif choice == '2':
                # View discovered devices
                view_devices_cli()
            elif choice == '3':
                # Arm targets
                select_targets_cli()
            elif choice == '4':
                # View selected targets
                view_selected_targets_cli()
            elif choice == '5':
                # Start broadcast
                start_broadcast_cli()
            elif choice == '6':
                # Clear selections
                clear_selections_cli()
            elif choice == '7':
                # Print persistent data
                print_persistent_data_cli()
            elif choice == '8':
                # Toggle debug mode
                toggle_debug_mode_cli()
            elif choice == '9':
                # Exit
                print("\n👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-9.")

        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("🔄 Returning to main menu...")
            time.sleep(2)
            continue

def show_cli_main_menu():
    """Display the main CLI menu."""
    print("\n" + "=" * 60)
    print("📋 MAIN MENU")
    print("=" * 60)
    print("1. 🔮 Scry Networks for Devices")
    print("2. 👁️  View Discovered Devices")
    print("3. 🎯  Arm/Disarm Targets")
    print("4. 📋 View Selected Targets")
    print("5. 🪄 Start Wake-on-LAN Cast")
    print("6. 🔥 Clear All Selections")
    print("7. 📄 Print Persistent Data (JSON)")
    debug_status = "🔧 Debug Mode: ON" if cli_persistent_data.get('debug_mode', False) else "🔧 Debug Mode: OFF"
    print(f"8. {debug_status}")
    print("9. 🚪 Exit")
    print("=" * 60)

def toggle_debug_mode_cli():
    """Toggle debug mode on/off with user feedback."""
    cli_persistent_data['debug_mode'] = not cli_persistent_data['debug_mode']
    status = "🔧 DEBUG MODE ENABLED" if cli_persistent_data['debug_mode'] else "🔧 DEBUG MODE DISABLED"
    print(f"\n{status}")
    print("=" * len(status))
    if cli_persistent_data['debug_mode']:
        print("📝 Debug notifications will now be displayed during operations.")
        print("💡 Use this to see detailed progress and device discovery information.")
    else:
        print("🔇 Debug notifications are now disabled.")
        print("💡 Re-enable for detailed progress and device discovery information.")
    print("=" * len(status))

    # Save debug mode setting to persistent file
    try:
        data_dir = os.path.expanduser("~/.wol_caster")
        debug_file = os.path.join(data_dir, "debug_settings.json")
        with open(debug_file, 'w') as f:
            json.dump({'debug_mode': cli_persistent_data['debug_mode']}, f, indent=2)
        print("💾 Debug mode setting saved to persistent storage.")
    except Exception as e:
        print(f"⚠️  Warning: Could not save debug mode setting: {e}")

    input("\nPress Enter to continue...")

def scan_networks_cli():
    """Scry all networks for devices with parallel processing."""
    print("\n🔮 SCRYING NETWORKS")
    print("=" * 40)

    # Get network interfaces
    interfaces = get_network_interfaces()
    if not interfaces:
        print("❌ No network interfaces found!")
        return

    print(f"📡 Found {len(interfaces)} network interface(s)")

    # Scan each interface
    for i, interface in enumerate(interfaces, 1):
        print(f"\n{i}/{len(interfaces)}: Scrying {interface['interface']} ({interface['subnet']})")

        # Clear previous results for this interface
        if interface['interface'] in cli_persistent_data['known_devices']:
            if cli_persistent_data['debug_mode']:
                print(f"   🔧 DEBUG: Clearing previous results for {interface['interface']}")
            del cli_persistent_data['known_devices'][interface['interface']]

        # Scan with parallel processing
        devices = scan_network_parallel(interface)

        # Store results
        cli_persistent_data['known_devices'][interface['interface']] = devices

        if cli_persistent_data['debug_mode']:
            print(f"   🔧 DEBUG: Stored {len(devices)} devices for {interface['interface']}")

        print(f"✅ Found {len(devices)} devices on {interface['interface']}")

    total_devices = sum(len(devs) for devs in cli_persistent_data['known_devices'].values())
    print(f"\n🎉 Network scry complete! Total devices: {total_devices}")

    if cli_persistent_data['debug_mode']:
        print(f"   🔧 DEBUG: Device breakdown by interface:")
        for interface_name, device_list in cli_persistent_data['known_devices'].items():
            print(f"      • {interface_name}: {len(device_list)} devices")

def scan_network_parallel(interface_info):
    """Scan a network using parallel processing for speed."""
    try:
        network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)
        host_ips = [str(ip) for ip in network.hosts()]
        total_ips = len(host_ips)

        print(f"   📊 Scrying {total_ips} IP addresses...")

        if cli_persistent_data['debug_mode']:
            print(f"   🔧 DEBUG: Using ThreadPoolExecutor with max_workers=50")
            print(f"   🔧 DEBUG: Network range: {interface_info['subnet']}")

        # Use parallel processing
        devices = []
        with ThreadPoolExecutor(max_workers=50) as executor:
            # Submit all IP scans
            future_to_ip = {executor.submit(scan_single_ip_fast, ip): ip for ip in host_ips}

            if cli_persistent_data['debug_mode']:
                print(f"   🔧 DEBUG: Submitted {len(future_to_ip)} scan tasks")

            # Process results with progress bar
            completed = 0
            for future in as_completed(future_to_ip):
                try:
                    device = future.result(timeout=1)
                    if device and device['status'] != "hidden":
                        devices.append(device)
                        if cli_persistent_data['debug_mode']:
                            print(f"   🔧 DEBUG: Found device {device['ip']} - {device.get('hostname', 'No hostname')}")
                    completed += 1

                    # Update progress bar on every completion for smooth animation
                    progress = (completed / total_ips) * 100
                    progress_bar = create_progress_bar_cli(completed, total_ips, width=40)
                    # Use fixed-width formatting to prevent text jumping
                    status_text = f"   {progress_bar} {completed}/{total_ips} ({progress:.1f}%)"
                    # Clear line and update in place with proper line clearing
                    print(f"\r{' ' * 80}\r{status_text}", end='', flush=True)

                except Exception as e:
                    completed += 1
                    if cli_persistent_data['debug_mode']:
                        print(f"   🔧 DEBUG: Error scanning IP: {e}")
                    continue

        # Final progress bar
        progress_bar = create_progress_bar_cli(total_ips, total_ips, width=40)
        print(f"\r   {progress_bar} {total_ips}/{total_ips} (100.0%)")

        if cli_persistent_data['debug_mode']:
            print(f"   🔧 DEBUG: Scan complete. Found {len(devices)} devices")

        return devices

    except Exception as e:
        print(f"   ❌ Scan error: {e}")
        return []

def scan_single_ip_fast(ip):
    """Fast single IP scan with optimized timeouts."""
    try:
        # Quick ping check (500ms timeout)
        is_pingable = ping_host_fast(ip)

        if is_pingable:
            # Device is online, get basic info
            hostname = get_device_identifier_fast(ip)
            mac_address = get_mac_address_fast(ip)

            # Get vendor info if MAC is available (same logic as GUI)
            vendor_info = None
            if mac_address:
                try:
                    vendor_info = get_mac_vendor(mac_address, silent=True)
                except Exception:
                    pass

            return {
                'ip': ip,
                'hostname': hostname or f"Device-{ip.split('.')[-1]}",
                'mac': mac_address,
                'vendor': vendor_info,
                'status': 'online',
                'last_seen': time.time()
            }
        else:
            # Quick port check for standby devices (200ms timeout)
            if check_standby_ports_fast(ip):
                return {
                    'ip': ip,
                    'hostname': f"Standby-{ip.split('.')[-1]}",
                    'mac': None,
                    'vendor': None,
                    'status': 'standby',
                    'last_seen': time.time()
                }

        return None

    except Exception:
        return None

def ping_host_fast(ip):
    """Fast ping with 500ms timeout."""
    try:
        system = platform.system().lower()
        if system == "windows":
            cmd = ["ping", "-n", "1", "-w", "500", ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "500", ip]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
        return result.returncode == 0
    except Exception:
        return False

def check_standby_ports_fast(ip):
    """Fast port check for standby devices."""
    standby_ports = [80, 443, 22]  # Most common ports only

    for port in standby_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)  # 200ms timeout
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return True
        except Exception:
            continue

    return False

def get_device_identifier_fast(ip):
    """Fast device identifier lookup using comprehensive discovery methods."""
    try:
        # Method 1: Try to get hostname via standard DNS resolution
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            if hostname and hostname != ip and len(hostname) > 2:
                return hostname
        except Exception:
            pass

        # Method 2: Try to get Windows NetBIOS name via smbutil (macOS only)
        try:
            if platform.system() == 'Darwin':  # Only on macOS
                netbios_name = get_netbios_name_smbutil(ip)
                if netbios_name:
                    return netbios_name
        except Exception:
            pass

        # Method 3: Try to get Apple device name via mDNS/Bonjour (macOS only)
        try:
            if platform.system() == 'Darwin':  # Only on macOS
                apple_device_name = get_apple_device_name(ip)
                if apple_device_name:
                    return apple_device_name
        except Exception:
            pass

        # Method 4: Try to get additional device information via service detection
        try:
            # Check for common service names
            service_ports = {
                22: "SSH",
                23: "Telnet",
                80: "HTTP",
                443: "HTTPS",
                3389: "RDP",
                5900: "VNC",
                8080: "HTTP-Alt",
                8443: "HTTPS-Alt"
            }

            for port, service in service_ports.items():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.2)  # Faster timeout for CLI
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    if result == 0:
                        return f"{service}-{ip.split('.')[-1]}"
                except Exception:
                    continue
        except Exception:
            pass

        return None
    except Exception:
        return None

def get_mac_address_fast(ip):
    """Fast MAC address lookup with automatic padding."""
    try:
        system = platform.system().lower()
        if system == "windows":
            cmd = ["arp", "-a", ip]
        else:
            cmd = ["arp", "-n", ip]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
        if result.returncode == 0:
            output = result.stdout
            mac_pattern = r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}'
            match = re.search(mac_pattern, output)
            if match:
                mac = match.group(0).upper().replace('-', ':')
                # Apply MAC padding rule: pad with leading zeros to reach 12 characters
                mac = pad_mac_address(mac)
                return mac
    except Exception:
        pass
    return None

def create_progress_bar_cli(current, total, width=40):
    """Create a proper CLI progress bar."""
    if total == 0:
        return "|" + "░" * width + "|"

    filled = int(width * current // total)
    bar = "█" * filled + "░" * (width - filled)
    return f"|{bar}|"

def view_devices_cli():
    """View all discovered devices with selection status."""
    print("\n👁️  DISCOVERED DEVICES")
    print("=" * 50)

    # Load persistent data if not already loaded
    if not cli_persistent_data['known_devices']:
        load_cli_persistent_data()

    total_devices = 0
    all_interfaces = set(cli_persistent_data['known_devices'].keys())

    for interface in all_interfaces:
        # Get persistent data (including offline devices)
        known_devices = cli_persistent_data['known_devices'].get(interface, [])
        # For CLI, we use the same data source since we're unified now
        current_devices = known_devices

        # Merge devices: EXACT SAME LOGIC AS GUI
        merged_devices = []

        # First: Merge current scan results with stored device intelligence (EXACT SAME AS GUI)
        for device in current_devices:
            # Find stored device data for this IP
            stored_device = next((d for d in known_devices if d.get('ip') == device['ip']), None)

            # Merge current status with stored device intelligence
            merged_device = device.copy()
            if stored_device and isinstance(stored_device, dict):
                # 💎 HARD-EARNED DATA ALWAYS PREVAILS (EXACT SAME AS GUI)
                # Always preserve stored hostname, MAC, and vendor - they're hard-earned!
                if stored_device.get('hostname'):
                    merged_device['hostname'] = stored_device['hostname']
                if stored_device.get('mac'):
                    merged_device['mac'] = stored_device['mac']
                if stored_device.get('vendor'):
                    merged_device['vendor'] = stored_device['vendor']
                # Keep the last_seen from current scan (more recent)
                if stored_device.get('last_seen'):
                    merged_device['stored_last_seen'] = stored_device['last_seen']

            merged_devices.append(merged_device)

        # Second: Add offline devices from persistent data that weren't found in current scan
        # This ensures we show offline devices with their stored intelligence (EXACT SAME AS GUI)
        current_ips = {d['ip'] for d in merged_devices}
        for known_device in known_devices:
            # Safety check: ensure known_device is a dictionary (EXACT SAME AS GUI)
            if not isinstance(known_device, dict):
                continue

            known_ip = known_device.get('ip')
            if not known_ip:
                continue

            # Check if this device is already in the current scan results
            already_found = any(d['ip'] == known_ip for d in merged_devices)

            if not already_found:
                # This device is offline - add it with stored intelligence (EXACT SAME AS GUI)
                offline_device = known_device.copy()
                offline_device['status'] = 'offline'  # Mark as offline
                offline_device['current_scan'] = False  # Flag that this wasn't found in current scan
                merged_devices.append(offline_device)

        if merged_devices:
            # 🌳 3-LEVEL DEEP TREE STRUCTURE (EXACT SAME AS GUI)
            print(f"\n🌐 {interface}:")

            # Group devices by network (EXACT SAME LOGIC AS GUI)
            network_groups = {}
            for device in merged_devices:
                # Determine network for this device (EXACT SAME LOGIC AS GUI)
                if device['ip'].startswith('192.168.0.'):
                    network_key = '192.168.0.0/24'
                elif device['ip'].startswith('134.124.230.'):
                    network_key = '134.124.230.0/24'  # Separate from 134.124.231.*
                elif device['ip'].startswith('134.124.231.'):
                    network_key = '134.124.231.0/24'  # Separate network
                else:
                    network_key = 'unknown_network'

                if network_key not in network_groups:
                    network_groups[network_key] = []
                network_groups[network_key].append(device)

            # Display each network level
            for network_key, network_devices in network_groups.items():
                # Format network display (EXACT SAME AS GUI)
                if network_key == '192.168.0.0/24':
                    range_display = "192.168.0.0"
                elif network_key == '134.124.230.0/24':
                    range_display = "134.124.230.0"
                elif network_key == '134.124.231.0/24':
                    range_display = "134.124.231.0"
                else:
                    range_display = network_key

                device_count = len(network_devices)
                online_count = sum(1 for d in network_devices if d['status'] == 'online')

                # Determine network status color (EXACT SAME LOGIC AS GUI)
                if online_count > 0:
                    network_status = "🟢"  # Green if any devices online
                elif device_count > 0:
                    network_status = "🔴"  # Red if devices but all offline
                else:
                    network_status = "⚪"  # White if no devices

                print(f"  {network_status} Network: {range_display} ({online_count}/{device_count} devices)")

                # Group devices by status within this network
                online_devices = [d for d in network_devices if d['status'] == 'online']
                standby_devices = [d for d in network_devices if d['status'] == 'standby']
                offline_devices = [d for d in network_devices if d['status'] == 'offline']

                # Display devices with proper indentation
            if online_devices:
                for device in online_devices:
                    device_key = f"{interface}:{device['ip']}"
                    selection_indicator = " ✅ SELECTED" if device_key in cli_persistent_data['selected_devices'] else ""
                    device_display = get_priority_device_display(device)
                    print(f"    🟢 {device_display}{selection_indicator}")

            if standby_devices:
                for device in standby_devices:
                    device_key = f"{interface}:{device['ip']}"
                    selection_indicator = " ✅ SELECTED" if device_key in cli_persistent_data['selected_devices'] else ""
                    device_display = get_priority_device_display(device)
                    print(f"    🟡 {device_display}{selection_indicator}")

                if offline_devices:
                    for device in offline_devices:
                        device_key = f"{interface}:{device['ip']}"
                        selection_indicator = " ✅ SELECTED" if device_key in cli_persistent_data['selected_devices'] else ""
                        device_display = get_priority_device_display(device)
                        print(f"    🔴 {device_display}{selection_indicator}")

            total_devices += len(merged_devices)

    if total_devices == 0:
        print("❌ No devices discovered yet. Run option 1 to scry networks first.")
    else:
        print(f"\n📊 Total devices: {total_devices}")

        # Show selection summary
        total_selected = len(cli_persistent_data['selected_devices'])
        if total_selected > 0:
            print(f"🎯 Selected devices: {total_selected}")

def view_selected_targets_cli():
    """View currently selected broadcast targets."""
    print("\n📋 SELECTED BROADCAST TARGETS")
    print("=" * 50)

    # Check if we have any selections
    if not cli_persistent_data['selected_networks'] and not cli_persistent_data['selected_devices']:
        print("❌ No targets selected yet. Use option 3 to select networks or devices.")
        return

    # Show selected networks
    if cli_persistent_data['selected_networks']:
        print("\n🌐 SELECTED NETWORKS:")
        print("-" * 30)
        for network in cli_persistent_data['selected_networks']:
            # Get network info
            interfaces = get_network_interfaces()
            network_interface = next((i for i in interfaces if i['interface'] == network), None)
            if network_interface:
                try:
                    network_obj = ipaddress.IPv4Network(network_interface['subnet'], strict=False)
                    address_count = len(list(network_obj.hosts())) + 2
                    print(f"   📡 {network} ({network_interface['subnet']}) - {address_count:,} addresses")
                except Exception:
                    print(f"   📡 {network} ({network_interface['subnet']})")
            else:
                print(f"   📡 {network}")

    # Show selected devices
    if cli_persistent_data['selected_devices']:
        print("\n💻 SELECTED DEVICES:")
        print("-" * 30)

        # Group devices by interface
        devices_by_interface = {}
        for device_key in cli_persistent_data['selected_devices']:
            interface, ip = device_key.split(':', 1)
            if interface not in devices_by_interface:
                devices_by_interface[interface] = []
            devices_by_interface[interface].append(ip)

        for interface, ips in devices_by_interface.items():
            print(f"   📡 {interface}:")
            for ip in sorted(ips):
                # Try to get device info
                device_info = None
                if interface in cli_persistent_data['known_devices']:
                    device_info = next((d for d in cli_persistent_data['known_devices'][interface] if d['ip'] == ip), None)

                if device_info:
                    status_icon = "🟢" if device_info['status'] == 'online' else "🟡"
                    # Use priority-based display system
                    device_display = get_priority_device_display(device_info)
                    print(f"      {status_icon} {device_display}")
                else:
                    print(f"      ⚪ {ip} - Unknown device")

    # Show summary
    total_networks = len(cli_persistent_data['selected_networks'])
    total_devices = len(cli_persistent_data['selected_devices'])

    print(f"\n📊 SELECTION SUMMARY:")
    print("-" * 30)
    print(f"   Networks: {total_networks}")
    print(f"   Devices: {total_devices}")

    # Calculate total broadcast targets
    total_targets = 0
    for network in cli_persistent_data['selected_networks']:
        interfaces = get_network_interfaces()
        network_interface = next((i for i in interfaces if i['interface'] == network), None)
        if network_interface:
            try:
                network_obj = ipaddress.IPv4Network(network_interface['subnet'], strict=False)
                total_targets += len(list(network_obj.hosts())) + 2
            except Exception:
                total_targets += 254  # Estimate

    total_targets += total_devices
    print(f"   Total targets: ~{total_targets:,} addresses")

def select_targets_cli():
    """Select cast targets."""
    print("\n🎯  ARM/DISARM TARGETS")
    print("=" * 40)

    # Check if we have discovered devices
    if not cli_persistent_data['known_devices']:
        print("❌ No devices discovered yet. Run option 1 to scry networks first.")
        return

    while True:
        print("\nCurrent selections:")
        print(f"   Networks: {len(cli_persistent_data['selected_networks'])}")
        print(f"   Devices: {len(cli_persistent_data['selected_devices'])}")

        # Calculate and show total targets
        total_targets = 0
        for network in cli_persistent_data['selected_networks']:
            interfaces = get_network_interfaces()
            network_interface = next((i for i in interfaces if i['interface'] == network), None)
            if network_interface:
                try:
                    network_obj = ipaddress.IPv4Network(network_interface['subnet'], strict=False)
                    total_targets += len(list(network_obj.hosts())) + 2
                except Exception:
                    total_targets += 254  # Estimate
        total_targets += len(cli_persistent_data['selected_devices'])
        print(f"   Total Targets: ~{total_targets:,} addresses")

        print("\nSelection options:")
        print("1. Select all networks")
        print("2. Select specific network")
        print("3. Select specific device")
        print("4. Clear all selections")
        print("5. Back to main menu")

        choice = input("\nEnter choice (1-5): ").strip()

        if choice == '1':
            # Select all networks
            interfaces = get_network_interfaces()
            for interface in interfaces:
                cli_persistent_data['selected_networks'].add(interface['interface'])
            print("✅ All networks selected")

        elif choice == '2':
            # Select specific network
            select_specific_network()

        elif choice == '3':
            # Select specific device
            select_specific_device()

        elif choice == '4':
            # Clear selections
            cli_persistent_data['selected_networks'].clear()
            cli_persistent_data['selected_devices'].clear()
            print("🔥 All selections cleared")

        elif choice == '5':
            # Back to main menu
            break

        else:
            print("❌ Invalid choice. Please enter 1-5.")

def select_specific_network():
    """Select a specific network interface."""
    interfaces = get_network_interfaces()

    print("\nAvailable networks:")
    for i, interface in enumerate(interfaces, 1):
        device_count = len(cli_persistent_data['known_devices'].get(interface['interface'], []))
        print(f"{i}. {interface['interface']} ({interface['subnet']}) - {device_count} devices")

    try:
        choice = int(input("\nSelect network (1-{}): ".format(len(interfaces))))
        if 1 <= choice <= len(interfaces):
            selected_interface = interfaces[choice - 1]['interface']
            if selected_interface in cli_persistent_data['selected_networks']:
                cli_persistent_data['selected_networks'].remove(selected_interface)
                print(f"❌ Network '{selected_interface}' deselected")
            else:
                cli_persistent_data['selected_networks'].add(selected_interface)
                print(f"✅ Network '{selected_interface}' selected")
        else:
            print("❌ Invalid selection")
    except ValueError:
        print("❌ Please enter a valid number")

def select_specific_device():
    """Select a specific device by IP."""
    # Load persistent data if not already loaded
    if not cli_persistent_data['known_devices']:
        load_cli_persistent_data()

    # Show all devices (persistent data only since we're unified now)
    all_devices = []
    all_interfaces = set(cli_persistent_data['known_devices'].keys())

    for interface in all_interfaces:
        # Get persistent data (including offline devices)
        known_devices = cli_persistent_data['known_devices'].get(interface, [])
        # For CLI, we use the same data source since we're unified now
        current_devices = known_devices

        # Merge devices: current scan results override stored status, but preserve offline devices
        current_ips = {d['ip'] for d in current_devices}

        # First: Merge current scan results with stored device intelligence (EXACT SAME AS GUI)
        for device in current_devices:
            # Find stored device data for this IP
            stored_device = next((d for d in known_devices if d.get('ip') == device['ip']), None)

            # Merge current status with stored device intelligence
            merged_device = device.copy()
            if stored_device and isinstance(stored_device, dict):
                # 💎 HARD-EARNED DATA ALWAYS PREVAILS (EXACT SAME AS GUI)
                # Always preserve stored hostname, MAC, and vendor - they're hard-earned!
                if stored_device.get('hostname'):
                    merged_device['hostname'] = stored_device['hostname']
                if stored_device.get('mac'):
                    merged_device['mac'] = stored_device['mac']
                if stored_device.get('vendor'):
                    merged_device['vendor'] = stored_device['vendor']
                # Keep the last_seen from current scan (more recent)
                if stored_device.get('last_seen'):
                    merged_device['stored_last_seen'] = stored_device['last_seen']

            all_devices.append((merged_device, interface))

        # Second: Add offline devices from persistent data that weren't found in current scan
        # This ensures we show offline devices with their stored intelligence (EXACT SAME AS GUI)
        current_ips = {d[0]['ip'] for d in all_devices}
        for known_device in known_devices:
            # Safety check: ensure known_device is a dictionary (EXACT SAME AS GUI)
            if not isinstance(known_device, dict):
                continue

            known_ip = known_device.get('ip')
            if not known_ip:
                continue

            # Check if this device is already in the current scan results
            already_found = any(d[0]['ip'] == known_ip for d in all_devices)

            if not already_found:
                # This device is offline - add it with stored intelligence (EXACT SAME AS GUI)
                offline_device = known_device.copy()
                offline_device['status'] = 'offline'  # Mark as offline
                offline_device['current_scan'] = False  # Flag that this wasn't found in current scan
                all_devices.append((offline_device, interface))

    if not all_devices:
        print("❌ No devices available for selection")
        return

    print("\nAvailable devices:")
    for i, (device, interface) in enumerate(all_devices, 1):
        # Status icon based on device status
        if device['status'] == 'online':
            status_icon = "🟢"
        elif device['status'] == 'standby':
            status_icon = "🟡"
        elif device['status'] == 'offline':
            status_icon = "🔴"
        else:
            status_icon = "⚪"

        device_key = f"{interface}:{device['ip']}"
        selection_indicator = " ✅ SELECTED" if device_key in cli_persistent_data['selected_devices'] else ""
        # Use priority-based display system
        device_display = get_priority_device_display(device)
        print(f"{i}. {status_icon} {device_display} ({interface}){selection_indicator}")

    print("\n💡 Selection Methods:")
    print("   • Single device: '5'")
    print("   • Range selection: '1-64'")
    print("   • Multiple devices: '1,3,4,5,6,9,8'")

    if cli_persistent_data['debug_mode']:
        print("   🔧 DEBUG: Enhanced selection with range support enabled")

    try:
        choice_input = input(f"\nSelect device(s) (1-{len(all_devices)}): ").strip()

        # Handle range selection (e.g., "1-64")
        if '-' in choice_input:
            try:
                start, end = map(int, choice_input.split('-'))
                if cli_persistent_data['debug_mode']:
                    print(f"   🔧 DEBUG: Processing range selection: {start}-{end}")

                if 1 <= start <= end <= len(all_devices):
                    selected_count = 0
                    for i in range(start, end + 1):
                        selected_device, interface = all_devices[i - 1]
                        device_key = f"{interface}:{selected_device['ip']}"
                        if device_key not in cli_persistent_data['selected_devices']:
                            cli_persistent_data['selected_devices'].add(device_key)
                            selected_count += 1
                            if cli_persistent_data['debug_mode']:
                                print(f"   🔧 DEBUG: Added device {selected_device['ip']} from range")
                        else:
                            if cli_persistent_data['debug_mode']:
                                print(f"   🔧 DEBUG: Device {selected_device['ip']} already selected, skipping")
                    print(f"✅ Selected {selected_count} devices (range {start}-{end})")
                else:
                    print("❌ Invalid range. Please enter valid start-end numbers.")
                    if cli_persistent_data['debug_mode']:
                        print(f"   🔧 DEBUG: Range {start}-{end} is invalid for {len(all_devices)} devices")
            except ValueError:
                print("❌ Invalid range format. Use 'start-end' (e.g., '1-64')")
                if cli_persistent_data['debug_mode']:
                    print(f"   🔧 DEBUG: Failed to parse range '{choice_input}'")

        # Handle comma-separated selection (e.g., "1,3,4,5,6,9,8")
        elif ',' in choice_input:
            try:
                choices = [int(x.strip()) for x in choice_input.split(',')]
                valid_choices = [c for c in choices if 1 <= c <= len(all_devices)]
                if valid_choices:
                    selected_count = 0
                    for choice in valid_choices:
                        selected_device, interface = all_devices[choice - 1]
                        device_key = f"{interface}:{selected_device['ip']}"
                        if device_key not in cli_persistent_data['selected_devices']:
                            cli_persistent_data['selected_devices'].add(device_key)
                            selected_count += 1
                    print(f"✅ Selected {selected_count} devices from comma-separated list")
                else:
                    print("❌ No valid device numbers in comma-separated list")
            except ValueError:
                print("❌ Invalid comma-separated format. Use '1,3,4,5'")

        # Handle single device selection
        else:
            try:
                choice = int(choice_input)
                if 1 <= choice <= len(all_devices):
                    selected_device, interface = all_devices[choice - 1]
                    device_key = f"{interface}:{selected_device['ip']}"

                    if device_key in cli_persistent_data['selected_devices']:
                        cli_persistent_data['selected_devices'].remove(device_key)
                        print(f"❌ Device '{selected_device['ip']}' deselected")
                    else:
                        cli_persistent_data['selected_devices'].add(device_key)
                        print(f"✅ Device '{selected_device['ip']}' selected")
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Please enter a valid number")
    except ValueError:
        print("❌ Please enter a valid number, range (e.g., '1-64'), or comma-separated list (e.g., '1,3,4,5')")

def start_broadcast_cli():
    """Start the Wake-on-LAN cast."""
    print("\n🪄 STARTING WAKE-ON-LAN CAST")
    print("=" * 40)

    # Check if we have selections
    if not cli_persistent_data['selected_networks'] and not cli_persistent_data['selected_devices']:
        print("❌ No targets selected! Use option 3 to select networks or devices first.")
        return

    # Show what we're casting to
    print("\nCasting to:")
    if cli_persistent_data['selected_networks']:
        print("   Networks:")
        for network in cli_persistent_data['selected_networks']:
            print(f"     • {network}")

    if cli_persistent_data['selected_devices']:
        print("   Devices:")
        for device_key in cli_persistent_data['selected_devices']:
            interface, ip = device_key.split(':', 1)
            print(f"     • {ip} ({interface})")

    # Confirm
    confirm = input("\nProceed with casting? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Broadcast cancelled")
        return

    # Start broadcast
    print("\n🪄 Casting magic packets...")

    # Cast to networks
    for network_name in cli_persistent_data['selected_networks']:
        try:
            interfaces = get_network_interfaces()
            network_interface = next((i for i in interfaces if i['interface'] == network_name), None)
            if network_interface:
                broadcast_to_network_cli(network_interface)
        except Exception as e:
            print(f"❌ Error casting to {network_name}: {e}")

    # Cast to individual devices
    for device_key in cli_persistent_data['selected_devices']:
        try:
            interface, ip = device_key.split(':', 1)
            send_magic_packet_to_ip(ip, create_magic_packet())
            print(f"✅ Magic packet sent to {ip}")
        except Exception as e:
            print(f"❌ Error casting to {ip}: {e}")

    print("\n🎉 Cast complete! All devices with Wake-on-LAN enabled should now be waking up.")

def broadcast_to_network_cli(interface_info):
    """Cast to a specific network."""
    try:
        network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)
        host_ips = list(network.hosts())
        total_ips = len(host_ips)

        print(f"📡 Casting to {interface_info['interface']} ({total_ips} addresses)...")

        # Create magic packet
        magic_packet = create_magic_packet()

        # Send with progress bar
        completed = 0
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(send_magic_packet_to_ip, str(ip), magic_packet) for ip in host_ips]

            for future in as_completed(futures):
                try:
                    future.result(timeout=1)
                    completed += 1

                    # Update progress on every completion for smooth animation
                    progress = (completed / total_ips) * 100
                    progress_bar = create_progress_bar_cli(completed, total_ips, width=30)
                    # Use fixed-width formatting to prevent text jumping
                    status_text = f"   {progress_bar} {completed}/{total_ips} ({progress:.1f}%)"
                    # Clear line and update in place with proper line clearing
                    print(f"\r{' ' * 60}\r{status_text}", end='', flush=True)

                except Exception:
                    completed += 1
                    continue

        # Final progress bar
        progress_bar = create_progress_bar_cli(total_ips, total_ips, width=30)
        print(f"\r   {progress_bar} {total_ips}/{total_ips} (100.0%)")
        print(f"✅ Cast to {interface_info['interface']} complete")

    except Exception as e:
        print(f"❌ Error casting to {interface_info['interface']}: {e}")

def clear_selections_cli():
    """Clear all selections."""
    cli_persistent_data['selected_networks'].clear()
    cli_persistent_data['selected_devices'].clear()
    print("🔥 All selections cleared")

def print_persistent_data_cli():
    """Print the current persistent data in JSON format."""
    print("\n📄 PERSISTENT DATA (JSON)")
    print("=" * 50)

    # Load persistent data if not already loaded
    if not cli_persistent_data['known_devices']:
        load_cli_persistent_data()

    if not cli_persistent_data['known_devices']:
        print("❌ No persistent data found.")
        print("💡 Run option 1 to scry networks and generate persistent data.")
        return

    print("📁 Current CLI Data:")
    print(json.dumps(cli_persistent_data, indent=2, default=str))

    print("\n📁 Persistent Data from known_devices.json:")
    print(json.dumps(cli_persistent_data['known_devices'], indent=2, default=str))

    print("\n💡 This shows the exact data structure used by both CLI and GUI.")
    print("🔒 CLI is read-only - only the GUI writes to persistent data.")

def run_gui():
    """Run GUI mode."""
    try:
        app = WOLCasterGUI()
        app.run()
    except Exception as e:
        print(f"GUI error: {e}. Falling back to CLI mode...")
        run_cli()

def show_help():
    """Show help information."""
    terminal_width = get_terminal_size().columns

    help_text = """
WoL-Caster - Wake-on-LAN Network Broadcaster

Usage:
    wol_caster.py [OPTIONS]

Options:
    --gui, -g    Force GUI mode
    --cli, -c    Force CLI mode
    --help, -h   Show this help message
    --version    Show version information

Smart Mode Detection:
    - Automatically detects whether to run in GUI or CLI mode
    - GUI mode when launched as app or from desktop
    - CLI mode when launched from terminal

Examples:
    wol_caster.py              # Smart mode detection
    wol_caster.py --gui        # Force GUI mode
    wol_caster.py --cli        # Force CLI mode
    """

    # Wrap help text for narrow terminals
    lines = help_text.strip().split('\n')
    for line in lines:
        if line.strip():
            wrapped_lines = wrap_text(line, terminal_width)
            for wrapped_line in wrapped_lines:
                print(wrapped_line)
        else:
            print()

def show_version():
    """Show version information."""
    print("WoL-Caster v1.0.0")
    print("Wake-on-LAN Network Broadcaster with Perfect GUI & CLI Interrupt")
    print("Features: Fixed GUI colors, toggle sorting, CLI interrupt (.), persistent CLI data")

def main():
    """Main entry point with smart mode detection."""
    # Handle help and version flags
    if '--help' in sys.argv or '-h' in sys.argv:
        show_help()
        return

    if '--version' in sys.argv:
        show_version()
        return

    # Smart mode detection
    if is_gui_mode():
        if GUI_AVAILABLE:
            print("Starting WoL-Caster in GUI mode...")
            run_gui()
        else:
            print("GUI not available. Starting in CLI mode...")
            run_cli()
    else:
        run_cli()

def get_netbios_name_smbutil(ip):
    """
    Get NetBIOS computer name using macOS smbutil command.
    This is the method that actually works for Windows devices!

    Args:
        ip: Target IP address

    Returns:
        str: Computer name if found, None otherwise
    """
    try:
        # Use smbutil status to get NetBIOS name
        result = subprocess.run(['smbutil', 'status', ip],
                              capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            output = result.stdout

            # Parse the output for computer name
            for line in output.split('\n'):
                if line.startswith('Server:'):
                    computer_name = line.split(':', 1)[1].strip()
                    if computer_name and computer_name != ip:
                        print(f"🎉 Discovered: {computer_name}")
                        return computer_name

        return None

    except Exception as e:
        # Silently fail - this is expected for non-Windows devices
        return None

def get_apple_device_name(ip):
    """
    Get Apple device name using macOS mDNS/Bonjour discovery.

    Args:
        ip: Target IP address

    Returns:
        str: Device name if found, None otherwise
    """
    try:
        # Method 1: Try dns-sd for device-info service
        try:
            result = subprocess.run(['dns-sd', '-G', 'v4', ip, '_device-info._tcp', 'local.'],
                                  capture_output=True, text=True, timeout=5)

            if result.returncode == 0 and result.stdout:
                # Parse dns-sd output for device names
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'device-info' in line and '=' in line:
                        # Extract device name from dns-sd output
                        parts = line.split('=')
                        if len(parts) >= 2:
                            device_name = parts[1].strip()
                            if device_name and len(device_name) > 2:
                                print(f"🍎 Found Apple device name via dns-sd: {device_name}")
                                return device_name
        except Exception:
            pass

        # Method 2: Try reverse DNS lookup with common Apple suffixes
        try:
            apple_suffixes = ['.local', '.home', '.lan', '.home.arpa']
            for suffix in apple_suffixes:
                try:
                    # Try to resolve the IP with Apple suffixes
                    hostname = socket.gethostbyaddr(ip)[0]
                    if hostname and hostname != ip and len(hostname) > 2:
                        # Check if it looks like an Apple device name
                        if any(suffix in hostname for suffix in apple_suffixes):
                            print(f"🍎 Found Apple device name via DNS: {hostname}")
                            return hostname
                except Exception:
                    continue
        except Exception:
            pass

        # Method 3: Try to detect Apple devices by MAC address vendor
        try:
            mac = get_mac_address(ip)
            if mac:
                # Apple MAC address prefixes (first 6 characters)
                apple_prefixes = [
                    "00:05:02", "00:0A:27", "00:0A:95", "00:1B:63", "00:1C:B3",
                    "00:1D:4F", "00:1E:52", "00:1E:C2", "00:21:E9", "00:23:12",
                    "00:23:32", "00:23:76", "00:23:DF", "00:24:E8", "00:25:00",
                    "00:26:08", "00:26:B0", "00:26:BB", "00:30:65", "00:50:C2",
                    "00:88:65", "00:A0:40", "00:B3:62", "00:C6:10", "00:D0:41",
                    "00:E0:81", "00:F4:6D", "08:00:07", "08:66:98", "08:70:45",
                    "0C:30:21", "0C:4D:E9", "0C:74:C2", "10:40:F3", "10:9A:DD",
                    "10:DD:B1", "18:20:32", "18:34:51", "18:9E:FC", "1C:1A:C0",
                    "1C:AB:A7", "1C:E6:2B", "20:3A:EF", "20:7D:74", "20:A6:CD",
                    "20:C9:D0", "24:AB:81", "24:E4:3F", "28:37:37", "28:6A:B8",
                    "28:CF:DA", "28:FF:3C", "2C:44:FD", "2C:BE:08", "30:10:E4",
                    "34:15:9E", "34:51:C9", "34:C0:59", "38:48:4C", "3C:07:54",
                    "3C:AB:8E", "3C:E0:72", "40:B0:76", "40:D3:2A", "44:D8:84",
                    "48:DB:50", "4C:00:10", "4C:32:75", "4C:57:CA", "4C:8D:79",
                    "4C:B1:99", "50:32:37", "50:7A:55", "50:EA:D6", "54:26:96",
                    "54:4E:90", "54:72:4F", "58:1F:AA", "58:BD:A3", "58:E6:BA",
                    "5C:09:79", "5C:8F:E0", "60:33:4B", "60:69:44", "60:FB:42",
                    "64:B9:E8", "68:96:7B", "68:9C:5E", "68:AB:1E", "68:FF:7B",
                    "6C:3E:6D", "6C:40:08", "6C:72:20", "6C:8D:C1", "6C:94:F8",
                    "70:11:24", "70:56:81", "70:73:CB", "70:CD:60", "70:DE:E2",
                    "74:E1:B6", "78:31:C1", "78:4B:87", "78:6C:1C", "78:A1:06",
                    "78:CA:39", "7C:04:D0", "7C:6D:62", "7C:C3:A1", "7C:F0:5F",
                    "80:00:6E", "80:BE:05", "80:D5:89", "80:EA:96", "84:29:99",
                    "84:85:06", "84:B1:53", "88:53:95", "88:63:DF", "88:87:17",
                    "88:C2:55", "8C:7B:9D", "8C:FA:22", "90:84:0D", "90:B9:31",
                    "90:C1:6E", "94:94:26", "98:01:A7", "98:5A:EB", "98:CA:33",
                    "98:D6:BB", "98:FE:94", "9C:04:EB", "9C:35:EB", "9C:84:CD",
                    "9C:B6:D0", "A0:ED:CD", "A4:B1:97", "A4:C6:4F", "A8:20:66",
                    "A8:66:7F", "A8:BB:CF", "AC:29:3A", "AC:3A:7A", "AC:5D:10",
                    "AC:7F:3E", "AC:87:A3", "AC:DE:48", "B0:34:95", "B0:65:BD",
                    "B0:9F:BA", "B4:18:82", "B4:2E:99", "B8:09:8A", "B8:44:4F",
                    "B8:53:AC", "B8:78:2E", "B8:C7:5D", "B8:F6:B1", "BC:3B:AF",
                    "BC:52:B7", "BC:67:78", "BC:9F:35", "C0:63:94", "C0:84:7A",
                    "C0:CE:CD", "C4:2C:03", "C4:85:08", "C8:1E:E7", "C8:2A:14",
                    "C8:33:4B", "C8:69:CD", "C8:85:50", "C8:BC:C8", "CC:08:E0",
                    "CC:20:E8", "CC:29:F5", "CC:78:5F", "CC:C3:EA", "D0:23:DB",
                    "D0:50:99", "D0:66:7B", "D0:81:7A", "D0:A6:37", "D0:BB:80",
                    "D0:C5:F3", "D0:E4:82", "D4:61:9D", "D4:9A:20", "D4:F4:6F",
                    "D8:30:62", "D8:96:95", "D8:A0:11", "D8:BB:2C", "D8:CF:9C",
                    "DC:2B:2A", "DC:37:14", "DC:86:D8", "DC:A4:CA", "DC:E1:AD",
                    "E0:66:78", "E0:8E:3C", "E0:B9:BA", "E0:C7:67", "E0:F5:C6",
                    "E0:F8:47", "E4:25:E7", "E4:98:6F", "E4:CE:8F", "E8:04:0B",
                    "E8:06:88", "E8:80:25", "E8:8D:28", "E8:B2:AC", "E8:CC:18",
                    "EC:35:86", "EC:85:2F", "EC:FA:BC", "F0:24:75", "F0:71:C9",
                    "F0:76:1C", "F0:9F:C2", "F0:B4:79", "F0:C1:F1", "F0:D1:A9",
                    "F4:1B:A1", "F4:31:C3", "F4:37:B7", "F4:5C:89", "F4:F1:5A",
                    "F4:F5:D8", "F4:F5:E8", "F8:1E:DF", "F8:27:93", "F8:95:EA",
                    "F8:FF:C2", "FC:00:12", "FC:25:3F", "FC:42:03", "FC:64:BA",
                    "FC:A8:9A", "FC:C1:11", "FC:D8:48", "00:1B:63", "00:1C:B3",
                    "00:1D:4F", "00:1E:52", "00:1E:C2", "00:21:E9", "00:23:12",
                    "00:23:32", "00:23:76", "00:23:DF", "00:24:E8", "00:25:00",
                    "00:26:08", "00:26:B0", "00:26:BB", "00:30:65", "00:50:C2",
                    "00:88:65", "00:A0:40", "00:B3:62", "00:C6:10", "00:D0:41",
                    "00:E0:81", "00:F4:6D", "08:00:07", "08:66:98", "08:70:45",
                    "0C:30:21", "0C:4D:E9", "0C:74:C2", "10:40:F3", "10:9A:DD",
                    "10:DD:B1", "18:20:32", "18:34:51", "18:9E:FC", "1C:1A:C0",
                    "1C:AB:A7", "1C:E6:2B", "20:3A:EF", "20:7D:74", "20:A6:CD",
                    "20:C9:D0", "24:AB:81", "24:E4:3F", "28:37:37", "28:6A:B8",
                    "28:CF:DA", "28:FF:3C", "2C:44:FD", "2C:BE:08", "30:10:E4",
                    "34:15:9E", "34:51:C9", "34:C0:59", "38:48:4C", "3C:07:54",
                    "3C:AB:8E", "3C:E0:72", "40:B0:76", "40:D3:2A", "44:D8:84",
                    "48:DB:50", "4C:00:10", "4C:32:75", "4C:57:CA", "4C:8D:79",
                    "4C:B1:99", "50:32:37", "50:7A:55", "50:EA:D6", "54:26:96",
                    "54:4E:90", "54:72:4F", "58:1F:AA", "58:BD:A3", "58:E6:BA",
                    "5C:09:79", "5C:8F:E0", "60:33:4B", "60:69:44", "60:FB:42",
                    "64:B9:E8", "68:96:7B", "68:9C:5E", "68:AB:1E", "68:FF:7B",
                    "6C:3E:6D", "6C:40:08", "6C:72:20", "6C:8D:C1", "6C:94:F8",
                    "70:11:24", "70:56:81", "70:73:CB", "70:CD:60", "70:DE:E2",
                    "74:E1:B6", "78:31:C1", "78:4B:87", "78:6C:1C", "78:A1:06",
                    "78:CA:39", "7C:04:D0", "7C:6D:62", "7C:C3:A1", "7C:F0:5F",
                    "80:00:6E", "80:BE:05", "80:D5:89", "80:EA:96", "84:29:99",
                    "84:85:06", "84:B1:53", "88:53:95", "88:63:DF", "88:87:17",
                    "88:C2:55", "8C:7B:9D", "8C:FA:22", "90:84:0D", "90:B9:31",
                    "90:C1:6E", "94:94:26", "98:01:A7", "98:5A:EB", "98:CA:33",
                    "98:D6:BB", "98:FE:94", "9C:04:EB", "9C:35:EB", "9C:84:CD",
                    "9C:B6:D0", "A0:ED:CD", "A4:B1:97", "A4:C6:4F", "A8:20:66",
                    "A8:66:7F", "A8:BB:CF", "AC:29:3A", "AC:3A:7A", "AC:5D:10",
                    "AC:7F:3E", "AC:87:A3", "AC:DE:48", "B0:34:95", "B0:65:BD",
                    "B0:9F:BA", "B4:18:82", "B4:2E:99", "B8:09:8A", "B8:44:4F",
                    "B8:53:AC", "B8:78:2E", "B8:C7:5D", "B8:F6:B1", "BC:3B:AF",
                    "BC:52:B7", "BC:67:78", "BC:9F:35", "C0:63:94", "C0:84:7A",
                    "C0:CE:CD", "C4:2C:03", "C4:85:08", "C8:1E:E7", "C8:2A:14",
                    "C8:33:4B", "C8:69:CD", "C8:85:50", "C8:BC:C8", "CC:08:E0",
                    "CC:20:E8", "CC:29:F5", "CC:78:5F", "CC:C3:EA", "D0:23:DB",
                    "D0:50:99", "D0:66:7B", "D0:81:7A", "D0:A6:37", "D0:BB:80",
                    "D0:C5:F3", "D0:E4:82", "D4:61:9D", "D4:9A:20", "D4:F4:6F",
                    "D8:30:62", "D8:96:95", "D8:A0:11", "D8:BB:2C", "D8:CF:9C",
                    "DC:2B:2A", "DC:37:14", "DC:86:D8", "DC:A4:CA", "DC:E1:AD",
                    "E0:66:78", "E0:8E:3C", "E0:B9:BA", "E0:C7:67", "E0:F5:C6",
                    "E0:F8:47", "E4:25:E7", "E4:98:6F", "E4:CE:8F", "E8:04:0B",
                    "E8:06:88", "E8:80:25", "E8:8D:28", "E8:B2:AC", "E8:CC:18",
                    "EC:35:86", "EC:85:2F", "EC:FA:BC", "F0:24:75", "F0:71:C9",
                    "F0:76:1C", "F0:9F:C2", "F0:B4:79", "F0:C1:F1", "F0:D1:A9",
                    "F4:1B:A1", "F4:31:C3", "F4:37:B7", "F4:5C:89", "F4:F1:5A",
                    "F4:F5:D8", "F4:F5:E8", "F8:1E:DF", "F8:27:93", "F8:95:EA",
                    "F8:FF:C2", "FC:00:12", "FC:25:3F", "FC:42:03", "FC:64:BA",
                    "FC:A8:9A", "FC:C1:11", "FC:D8:48"
                ]

                mac_prefix = ":".join(mac.split(":")[:3])
                if mac_prefix in apple_prefixes:
                    # Found an Apple device by MAC address
                    print(f"🍎 Detected Apple device by MAC prefix: {mac_prefix}")
                    return f"Apple-{ip.split('.')[-1]}"
        except Exception:
            pass

        return None

    except Exception as e:
        # Silently fail - this is expected for non-Apple devices
        return None

def get_priority_device_display(device):
    """
    Get priority-based device display string following the hierarchy:
    1. IP Address (always shown)
    2. MAC Address (if found, in brackets)
    3. Computer Name → NIC Manufacturer → Fallback Name (same space, priority-based)
    """
    # 1. IP Address (always shown)
    display = device['ip']

    # 2. MAC Address (if found, in brackets)
    if device.get('mac'):
        display += f" [{device['mac']}]"

    # 3. Priority-based identifier (same space) - using same logic as GUI
    identifier = None

    # Priority 1: Computer Name (if it's not a generic fallback name)
    if device.get('hostname') and device['hostname'] != f"Device-{device['ip'].split('.')[-1]}" and device['hostname'] != f"Standby-{device['ip'].split('.')[-1]}":
        identifier = device['hostname']

    # Priority 2: NIC Manufacturer (if no computer name) - using same logic as GUI
    if not identifier and device.get('mac'):
        # For online/standby devices, do fresh vendor lookup (handles network changes, adapter swaps, etc.)
        # For offline devices, use stored vendor info if available
        if device['status'] in ['online', 'standby']:
            # Fresh lookup for active devices
            vendor = get_mac_vendor(device['mac'], silent=True)
            if vendor and vendor != "Unknown":
                identifier = vendor
            else:
                # Fallback to stored vendor info if fresh lookup failed
                if device.get('vendor'):
                    identifier = device['vendor']
                # Don't fall back to status - it's redundant
        else:
            # Use stored vendor info for offline devices
            if device.get('vendor'):
                identifier = device['vendor']
            # Don't fall back to status - it's redundant

    # Priority 3: Fallback Name (if no manufacturer)
    if not identifier:
        # Create intelligent fallback names based on common services
        if device.get('status') == 'standby':
            identifier = f"Standby-{device['ip'].split('.')[-1]}"
        else:
            # For online devices, create service-based fallback
            last_octet = device['ip'].split('.')[-1]
            if last_octet in ['1', '254']:  # Common gateway/broadcast
                identifier = f"Gateway-{last_octet}"
            elif last_octet in ['100', '101', '200', '201']:  # Common server ranges
                identifier = f"Server-{last_octet}"
            else:
                identifier = f"Device-{last_octet}"

    display += f" {identifier}"
    return display

if __name__ == "__main__":
    main()
