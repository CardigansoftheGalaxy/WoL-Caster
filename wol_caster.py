#!/usr/bin/env python3
"""
WoL-Caster: Wake-on-LAN Network Broadcaster
A simple utility to send magic packets to all devices on all local network subnets.
"""

import socket
import struct
import netifaces
import ipaddress
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import sys
import platform
import os

# Smart GUI detection
GUI_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import messagebox
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
    # This is the smart detection logic
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
        except:
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
                        except:
                            continue
        except:
            continue
    
    return interfaces

def format_network_range(subnet_str):
    """Format a subnet into a user-friendly range display."""
    try:
        network = ipaddress.IPv4Network(subnet_str, strict=False)
        network_parts = str(network.network_address).split('.')
        
        # For /24 networks (most common), show as xxx.xxx.xxx.*
        if network.prefixlen == 24:
            return f"{'.'.join(network_parts[:3])}.*"
        
        # For /16 networks, show as xxx.xxx.*.*
        elif network.prefixlen == 16:
            return f"{'.'.join(network_parts[:2])}.*.*"
        
        # For /8 networks, show as xxx.*.*.*
        elif network.prefixlen == 8:
            return f"{network_parts[0]}.*.*.*"
        
        # For other subnet sizes, show the range more explicitly
        else:
            first_ip = str(network.network_address)
            last_ip = str(network.broadcast_address)
            # If they're similar, show a compact range
            first_parts = first_ip.split('.')
            last_parts = last_ip.split('.')
            
            # Find the first differing octet
            for i in range(4):
                if first_parts[i] != last_parts[i]:
                    if i == 3:  # Only last octet differs
                        return f"{'.'.join(first_parts[:3])}.{first_parts[3]}-{last_parts[3]}"
                    elif i == 2:  # Last two octets differ
                        return f"{'.'.join(first_parts[:2])}.{first_parts[2]}-{last_parts[2]}.*"
                    else:
                        return f"{first_ip} → {last_ip}"
            
            return f"{first_ip}"
    except:
        return subnet_str

def get_network_summary(interfaces):
    """Get a summary of networks that will be targeted."""
    summary = []
    total_addresses = 0
    
    for iface in interfaces:
        try:
            network = ipaddress.IPv4Network(iface['subnet'], strict=False)
            address_count = len(list(network.hosts())) + 2  # +2 for network and broadcast
            range_display = format_network_range(iface['subnet'])
            
            summary.append({
                'interface': iface['interface'],
                'range': range_display,
                'count': address_count,
                'host_ip': iface['ip']
            })
            total_addresses += address_count
        except:
            continue
    
    return summary, total_addresses

def create_magic_packet():
    """Create a Wake-on-LAN magic packet with broadcast MAC address."""
    # Use broadcast MAC address (FF:FF:FF:FF:FF:FF) since we don't know target MACs
    mac_bytes = bytes.fromhex('FF' * 6)
    magic_packet = b'\xFF' * 6 + mac_bytes * 16
    return magic_packet

def send_magic_packet_to_ip(target_ip, magic_packet):
    """Send a magic packet to a specific IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.1)  # Short timeout to avoid hanging
            
            # Send to common WOL ports
            for port in [7, 9]:
                try:
                    sock.sendto(magic_packet, (target_ip, port))
                except:
                    pass  # Ignore individual send failures
    except:
        pass  # Ignore socket creation failures

def create_progress_bar(current, total, width=50, prefix="Progress"):
    """Create a visual progress bar for CLI."""
    filled_width = int(width * current // total)
    bar = "█" * filled_width + "▒" * (width - filled_width)
    percent = (current / total) * 100
    return f"{prefix}: |{bar}| {current}/{total} ({percent:.1f}%)"

def broadcast_to_subnet(interface_info, progress_callback=None, verbose=False):
    """Send magic packets to all IPs in a subnet."""
    magic_packet = create_magic_packet()
    network = ipaddress.IPv4Network(interface_info['subnet'], strict=False)
    
    # Get all host IPs in the network
    host_ips = [str(ip) for ip in network.hosts()]
    
    # Also include network and broadcast addresses for completeness
    all_ips = [str(network.network_address)] + host_ips + [str(network.broadcast_address)]
    
    if verbose:
        print(f"\n🌐 Interface: {interface_info['interface']}")
        print(f"📡 Target Range: {format_network_range(interface_info['subnet'])}")
        print(f"🎯 Addresses: {len(all_ips):,}")
        print(f"⚡ Starting broadcast...")
    else:
        print(f"Sending magic packets to {len(all_ips)} addresses in {interface_info['subnet']} via {interface_info['interface']}")
    
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
            except:
                pass
            completed += 1
            
            # Update progress
            if progress_callback:
                progress_callback(completed, len(all_ips), interface_info['interface'])
            
            # CLI progress bar (update every 10 packets or at 100% to avoid spam)
            if verbose and (completed % max(1, len(all_ips) // 100) == 0 or completed == len(all_ips)):
                progress_bar = create_progress_bar(completed, len(all_ips), 
                                                 prefix=f"📡 {interface_info['interface'][:12]}")
                print(f"\r{progress_bar}", end="", flush=True)
        
        if verbose:
            print()  # New line after progress bar
            print(f"✅ Completed {interface_info['interface']}: {completed:,} packets sent")
        
    return completed

def main_broadcast_selected(selected_network_summaries, progress_callback=None, network_display_callback=None, overall_progress_callback=None):
    """Main function to broadcast to selected network interfaces only."""
    if not selected_network_summaries:
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
    
    print(f"Broadcasting to {len(selected_network_summaries)} selected network(s):")
    print("Networks to target:")
    for summary in selected_network_summaries:
        print(f"  {summary['interface']}: {summary['range']} ({summary['count']} addresses) [Host: {summary['host_ip']}]")
    
    total_addresses = sum(net['count'] for net in selected_network_summaries)
    print(f"Total addresses to contact: {total_addresses}")
    
    print("\nStarting Wake-on-LAN broadcast...")
    print("=" * 60)
    
    # Process each selected interface
    for i, interface_info in enumerate(interfaces_to_broadcast, 1):
        try:
            if overall_progress_callback:
                overall_progress_callback(i, len(interfaces_to_broadcast))
            
            # Use verbose mode for CLI to show progress bars
            completed = broadcast_to_subnet(interface_info, progress_callback, verbose=True)
            
        except Exception as e:
            print(f"❌ Error processing {interface_info['interface']}: {e}")
    
    print("=" * 60)
    print(f"🎉 BROADCAST COMPLETE!")
    print(f"📊 Total: {total_addresses:,} addresses across {len(interfaces_to_broadcast)} network(s)")
    print(f"⏱️  All operations completed successfully")
    return True, selected_network_summaries

def get_user_network_selection(network_summary):
    """Get user selection of networks for CLI mode."""
    if not network_summary:
        return []
    
    print("\nAvailable Networks:")
    print("=" * 50)
    
    for i, summary in enumerate(network_summary, 1):
        print(f"{i}. {summary['interface']}: {summary['range']} ({summary['count']:,} addresses)")
        print(f"   Host: {summary['host_ip']}")
        print()
    
    while True:
        try:
            print("Select networks to broadcast to:")
            print("  • Enter numbers separated by commas (e.g., 1,3,4)")
            print("  • Enter 'all' to select all networks")
            print("  • Enter 'quit' to cancel")
            
            user_input = input("\nYour selection: ").strip().lower()
            
            if user_input == 'quit':
                return []
            
            if user_input == 'all':
                return network_summary
            
            # Parse comma-separated numbers
            selected_indices = []
            for num_str in user_input.split(','):
                num = int(num_str.strip())
                if 1 <= num <= len(network_summary):
                    selected_indices.append(num - 1)  # Convert to 0-based index
                else:
                    raise ValueError(f"Invalid selection: {num}")
            
            if not selected_indices:
                print("No valid networks selected. Please try again.\n")
                continue
            
            selected_networks = [network_summary[i] for i in selected_indices]
            
            # Confirm selection
            print(f"\nSelected {len(selected_networks)} network(s):")
            for net in selected_networks:
                print(f"  ✓ {net['interface']}: {net['range']}")
            
            total = sum(net['count'] for net in selected_networks)
            print(f"\nTotal addresses to contact: {total:,}")
            
            confirm = input("\nProceed with broadcast? (y/n): ").strip().lower()
            if confirm in ['y', 'yes']:
                return selected_networks
            else:
                print("Selection cancelled.\n")
                continue
                
        except (ValueError, KeyboardInterrupt):
            print("Invalid input. Please try again.\n")
            continue

class WOLCasterGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WoL-Caster - Wake-on-LAN Network Broadcaster")
        self.root.geometry("520x450")
        self.root.resizable(True, True)
        
        # Center the window
        self.root.geometry("+%d+%d" % ((self.root.winfo_screenwidth()/2 - 260), 
                                       (self.root.winfo_screenheight()/2 - 225)))
        
        self.selected_networks = []
        self.create_widgets()
        
    def create_widgets(self):
        # Title
        title_label = tk.Label(self.root, text="WoL-Caster", 
                              font=("Arial", 16, "bold"), fg="#2E7D32")
        title_label.pack(pady=5)
        
        subtitle_label = tk.Label(self.root, text="Wake-on-LAN Network Broadcaster", 
                                 font=("Arial", 11))
        subtitle_label.pack(pady=2)
        
        # Description
        desc_label = tk.Label(self.root, 
                             text="Select networks to send magic packets to all devices",
                             font=("Arial", 9), fg="gray")
        desc_label.pack(pady=5)
        
        # Networks frame
        networks_frame = tk.Frame(self.root, relief=tk.SUNKEN, bd=1)
        networks_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        networks_title = tk.Label(networks_frame, text="Available Networks:", 
                                 font=("Arial", 11, "bold"))
        networks_title.pack(pady=5)
        
        # Scrollable listbox for network selection
        listbox_frame = tk.Frame(networks_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.networks_listbox = tk.Listbox(listbox_frame, height=8, font=("Courier", 9),
                                          selectmode=tk.MULTIPLE, bg="#f8f9fa")
        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.networks_listbox.yview)
        self.networks_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.networks_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Selection buttons
        button_frame = tk.Frame(networks_frame)
        button_frame.pack(pady=5)
        
        select_all_btn = tk.Button(button_frame, text="Select All", 
                                  command=self.select_all_networks, font=("Arial", 9))
        select_all_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = tk.Button(button_frame, text="Clear Selection", 
                             command=self.clear_selection, font=("Arial", 9))
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Load networks on startup
        self.load_networks()
        
        # Progress frames (initially hidden)
        self.progress_frame = tk.Frame(self.root)
        
        self.overall_progress = tk.Label(self.progress_frame, text="", font=("Arial", 9), fg="blue")
        self.overall_progress.pack()
        
        self.interface_progress = tk.Label(self.progress_frame, text="", font=("Arial", 8))
        self.interface_progress.pack()
        
        self.progress_label = tk.Label(self.progress_frame, text="", font=("Arial", 8), fg="gray")
        self.progress_label.pack()
        
        # Start button
        self.start_button = tk.Button(self.root, text="🚀 Start Broadcast", 
                                     command=self.start_broadcast,
                                     font=("Arial", 12, "bold"),
                                     bg="#4CAF50", fg="white",
                                     padx=20, pady=8)
        self.start_button.pack(pady=15)
        
        # Status label
        self.status_label = tk.Label(self.root, text="Ready - Select networks and click Start Broadcast", 
                                    font=("Arial", 9), fg="gray")
        self.status_label.pack(pady=5)
        
    def load_networks(self):
        """Load and display detected networks."""
        try:
            interfaces = get_network_interfaces()
            if interfaces:
                network_summary, total_addresses = get_network_summary(interfaces)
                self.display_networks(network_summary, total_addresses)
            else:
                self.networks_listbox.insert(tk.END, "No active network interfaces detected.")
        except Exception as e:
            self.networks_listbox.insert(tk.END, f"Error detecting networks: {e}")
    
    def display_networks(self, network_summary, total_addresses):
        """Display the network summary in the listbox."""
        self.networks_listbox.delete(0, tk.END)
        self.network_data = network_summary
        
        if not network_summary:
            self.networks_listbox.insert(tk.END, "No networks detected.")
            return
        
        # Display each network
        for summary in network_summary:
            interface_name = summary['interface']
            range_display = summary['range']
            count = summary['count']
            host_ip = summary['host_ip']
            
            # Create a nice display line
            line = f"📡 {interface_name} | {range_display} | {count:,} addresses | {host_ip}"
            self.networks_listbox.insert(tk.END, line)
        
        # Select all networks by default
        self.select_all_networks()
        
    def select_all_networks(self):
        """Select all networks in the listbox."""
        self.networks_listbox.select_set(0, tk.END)
        self.update_selection_status()
        
    def clear_selection(self):
        """Clear all selections."""
        self.networks_listbox.select_clear(0, tk.END)
        self.update_selection_status()
        
    def update_selection_status(self):
        """Update the status based on current selection."""
        selected_indices = self.networks_listbox.curselection()
        if hasattr(self, 'network_data') and selected_indices:
            selected_count = len(selected_indices)
            total_addresses = sum(self.network_data[i]['count'] for i in selected_indices)
            self.status_label.config(text=f"Selected: {selected_count} network(s), {total_addresses:,} addresses")
        else:
            self.status_label.config(text="No networks selected")
    
    def get_selected_networks(self):
        """Get currently selected networks."""
        selected_indices = self.networks_listbox.curselection()
        if not hasattr(self, 'network_data') or not selected_indices:
            return []
        
        return [self.network_data[i] for i in selected_indices]
        
    def progress_callback(self, completed, total, interface):
        """Update progress display in GUI."""
        # Update interface-specific progress
        percent = (completed / total) * 100
        progress_text = f"📡 {interface}: {completed:,}/{total:,} ({percent:.1f}%)"
        self.interface_progress.config(text=progress_text)
        
        # Create visual progress bar for current interface
        bar_width = 40
        filled = int(bar_width * completed // total)
        progress_bar = "█" * filled + "▒" * (bar_width - filled)
        bar_text = f"|{progress_bar}|"
        self.progress_label.config(text=bar_text)
        
        self.root.update_idletasks()
        
    def update_overall_progress(self, current_network, total_networks):
        """Update overall progress across all networks."""
        overall_text = f"Overall: Network {current_network}/{total_networks}"
        self.overall_progress.config(text=overall_text)
        
    def start_broadcast(self):
        """Start the broadcasting process."""
        # Bind selection update to listbox
        self.networks_listbox.bind('<<ListboxSelect>>', lambda e: self.update_selection_status())
        
        # Get selected networks
        selected_networks = self.get_selected_networks()
        
        if not selected_networks:
            messagebox.showwarning("No Networks Selected", 
                                 "Please select at least one network to broadcast to.")
            return
        
        self.start_button.config(state="disabled", text="🔄 Broadcasting...")
        self.status_label.config(text="Broadcasting magic packets...", fg="orange")
        
        # Show progress frame
        self.progress_frame.pack(pady=10)
        self.progress_label.config(text="")
        self.interface_progress.config(text="")
        self.overall_progress.config(text=f"Overall: Network 0/{len(selected_networks)}")
        
        def broadcast_worker():
            try:
                success, network_summary = main_broadcast_selected(selected_networks, 
                                                                 self.progress_callback, 
                                                                 None,
                                                                 self.update_overall_progress)
                
                # Update GUI from main thread
                self.root.after(0, lambda: self.broadcast_complete(success, network_summary))
                
            except Exception as e:
                self.root.after(0, lambda: self.broadcast_error(str(e)))
        
        # Run broadcast in separate thread to avoid blocking GUI
        threading.Thread(target=broadcast_worker, daemon=True).start()
    
    def broadcast_complete(self, success, network_summary=None):
        """Handle broadcast completion."""
        if success and network_summary:
            total_addresses = sum(net['count'] for net in network_summary)
            network_count = len(network_summary)
            
            self.status_label.config(text="✅ Broadcast completed successfully!", fg="green")
            self.overall_progress.config(text=f"✅ Completed: {network_count} network(s)")
            self.interface_progress.config(text="🎯 All networks processed!")
            self.progress_label.config(text="")
            
            # Create detailed success message
            ranges = [net['range'] for net in network_summary]
            ranges_text = ", ".join(ranges)
            
            messagebox.showinfo("🎯 WoL-Caster Success", 
                              f"Magic packets sent successfully!\n\n"
                              f"Networks targeted: {ranges_text}\n"
                              f"Total addresses contacted: {total_addresses:,}\n"
                              f"Networks: {network_count}\n\n"
                              f"Devices with Wake-on-LAN enabled should now be waking up.")
        else:
            self.status_label.config(text="⚠️ No network interfaces found", fg="red")
            messagebox.showwarning("No Networks", 
                                 "No active network interfaces were found.")
        
        self.start_button.config(state="normal", text="🚀 Start Broadcast")
        # Hide progress frame
        self.progress_frame.pack_forget()
    
    def broadcast_error(self, error_msg):
        """Handle broadcast errors."""
        self.status_label.config(text="❌ Error occurred during broadcast", fg="red")
        messagebox.showerror("Error", f"An error occurred:\n{error_msg}")
        
        self.start_button.config(state="normal", text="🚀 Start Broadcast")
        self.progress_frame.pack_forget()
    
    def run(self):
        """Start the GUI application."""
        self.root.mainloop()

def run_cli():
    """Run CLI mode."""
    print("WoL-Caster - Wake-on-LAN Network Broadcaster")
    print("CLI Mode")
    print("=" * 50)
    
    # Get all available networks
    interfaces = get_network_interfaces()
    if not interfaces:
        print("❌ No network interfaces found!")
        return
    
    network_summary, total_addresses = get_network_summary(interfaces)
    
    # Let user select networks
    selected_networks = get_user_network_selection(network_summary)
    
    if not selected_networks:
        print("No networks selected. Exiting.")
        return
    
    # Broadcast to selected networks
    success, broadcast_summary = main_broadcast_selected(selected_networks)
    
    if success and broadcast_summary:
        print("\n" + "=" * 50)
        print("📊 BROADCAST SUMMARY:")
        print("=" * 50)
        
        for summary in broadcast_summary:
            print(f"✓ {summary['interface']}: {summary['range']} ({summary['count']:,} addresses)")
        
        total = sum(net['count'] for net in broadcast_summary)
        print(f"\n🎯 Total: {total:,} addresses across {len(broadcast_summary)} network(s)")
        print("📡 All devices with Wake-on-LAN enabled should now be waking up!")

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
    print("""
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
    """)

def show_version():
    """Show version information."""
    print("WoL-Caster v1.0.0")
    print("Wake-on-LAN Network Broadcaster")
    print("https://github.com/CardigansoftheGalaxy/wol-caster")

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

if __name__ == "__main__":
    main()
