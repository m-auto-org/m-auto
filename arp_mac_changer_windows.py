#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Auto-detect and use venv if not already running in it
def ensure_venv():
    script_dir = Path(__file__).parent.absolute()
    # Windows uses Scripts/python.exe instead of bin/python3
    venv_python = script_dir / "venv" / "Scripts" / "python.exe"
    
    # Check if we're already running in the venv
    if str(sys.executable).endswith(("venv\\Scripts\\python.exe", "venv/Scripts/python.exe")):
        return  # Already running in venv, continue normally
    
    # Check if venv exists, create it if it doesn't
    if not venv_python.exists():
        print(f"Virtual environment not found at {venv_python}")
        print("Creating virtual environment automatically...")
        
        try:
            # Create virtual environment
            import subprocess
            result = subprocess.run([sys.executable, '-m', 'venv', str(script_dir / 'venv')], 
                                  capture_output=True, text=True, check=True)
            print("✅ Virtual environment created successfully!")
            
            # Install required packages
            print("Installing required packages (pyshark)...")
            pip_path = script_dir / 'venv' / 'Scripts' / 'pip.exe'
            result = subprocess.run([str(pip_path), 'install', 'pyshark'], 
                                  capture_output=True, text=True, check=True)
            print("✅ Required packages installed successfully!")
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create virtual environment!")
            print(f"Command: {' '.join(e.cmd)}")
            print(f"Error output: {e.stderr}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Unexpected error creating virtual environment: {e}")
            sys.exit(1)
    
    # Try to switch to venv Python
    try:
        print(f"Switching to virtual environment Python: {venv_python}")
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)
    except Exception as e:
        print(f"ERROR: Failed to switch to virtual environment!")
        print(f"Error: {e}")
        print("Please check that the virtual environment is properly set up.")
        sys.exit(1)

# Call this at the start
ensure_venv()

# Import all other modules after ensuring we're in the correct environment
import subprocess
from typing import List, Set, Dict
import pyshark
import re
import time

def load_tested_macs(log_file: str) -> Set[str]:
    """
    Load already tested MAC addresses from log file.
    """
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_tested_mac(log_file: str, mac: str):
    """
    Save a tested MAC address to the log file.
    """
    try:
        with open(log_file, 'a') as f:
            f.write(f"{mac}\n")
    except PermissionError:
        print(f"Warning: Could not write to {log_file} due to permission issues.")
        print("This MAC address will not be logged as tested.")
    except Exception as e:
        print(f"Warning: Could not write to {log_file}: {e}")
        print("This MAC address will not be logged as tested.")

def get_mac_addresses(pcapng_file: str) -> Set[str]:
    """
    Extract unique MAC addresses from a pcapng file.
    """
    try:
        capture = pyshark.FileCapture(pcapng_file, display_filter='eth.src')
        mac_addresses = set()
        
        for packet in capture:
            if hasattr(packet, 'eth') and hasattr(packet.eth, 'src'):
                mac_addresses.add(packet.eth.src)
        
        return mac_addresses
    except Exception as e:
        print(f"Error reading pcapng file: {e}")
        sys.exit(1)

def get_network_interfaces() -> Dict[str, str]:
    """
    Get available network interfaces on Windows.
    Returns dict with interface names as keys and descriptions as values.
    """
    try:
        result = subprocess.run(['netsh', 'interface', 'show', 'interface'], 
                              capture_output=True, text=True, check=True)
        
        interfaces = {}
        lines = result.stdout.split('\n')
        
        for line in lines:
            if 'Connected' in line and ('Wi-Fi' in line or 'Ethernet' in line or 'Wireless' in line):
                parts = line.split()
                if len(parts) >= 4:
                    # Extract interface name (usually the last part)
                    interface_name = ' '.join(parts[3:])
                    interfaces[interface_name] = interface_name
        
        return interfaces
    except subprocess.CalledProcessError as e:
        print(f"Error getting network interfaces: {e}")
        return {}

def toggle_wifi(interface: str, state: str) -> bool:
    """
    Turn WiFi interface on or off using Windows netsh.
    """
    try:
        action = "enable" if state == "on" else "disable"
        print(f"\nTurning WiFi {state}...")
        
        result = subprocess.run(['netsh', 'interface', 'set', 'interface', 
                               interface, action], 
                              capture_output=True, text=True, check=True)
        
        print(f"WiFi turned {state} successfully")
        time.sleep(2)  # Give Windows time to process the change
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error turning WiFi {state}: {e}")
        print(f"Command output: {e.stdout}")
        print(f"Command error: {e.stderr}")
        return False

def get_current_mac(interface: str) -> str:
    """
    Get current MAC address of the interface.
    """
    try:
        result = subprocess.run(['getmac', '/fo', 'csv', '/v'], 
                              capture_output=True, text=True, check=True)
        
        lines = result.stdout.split('\n')
        for line in lines:
            if interface in line and 'Physical Address' in line:
                # Parse CSV-like output to extract MAC address
                parts = line.split(',')
                for part in parts:
                    part = part.strip('"')
                    if re.match(r'^[0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}$', part):
                        return part
        
        # Alternative method using ipconfig
        result = subprocess.run(['ipconfig', '/all'], 
                              capture_output=True, text=True, check=True)
        
        lines = result.stdout.split('\n')
        found_interface = False
        
        for line in lines:
            if interface in line:
                found_interface = True
            elif found_interface and 'Physical Address' in line:
                mac_match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}', line)
                if mac_match:
                    return mac_match.group(0)
        
        return "Unknown"
    except Exception as e:
        print(f"Error getting current MAC address: {e}")
        return "Unknown"

def change_mac_address_registry(interface: str, new_mac: str) -> bool:
    """
    Change MAC address using Windows registry method.
    This requires administrator privileges.
    """
    try:
        # Format MAC address for registry (remove colons/dashes)
        registry_mac = new_mac.replace(':', '').replace('-', '').upper()
        
        print(f"Attempting to change MAC address via registry...")
        print(f"Note: This requires administrator privileges and may need a reboot.")
        
        # Get interface registry key
        result = subprocess.run(['reg', 'query', 
                               'HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e972-e325-11ce-bfc1-08002be10318}',
                               '/s', '/f', interface], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Could not find interface in registry")
            return False
        
        # This is a simplified approach - in practice, you'd need to:
        # 1. Find the exact registry key for the interface
        # 2. Set the NetworkAddress value
        # 3. Restart the interface
        
        print("Registry-based MAC changing requires more complex implementation.")
        print("Consider using third-party tools like Technitium MAC Address Changer.")
        return False
        
    except Exception as e:
        print(f"Error changing MAC address via registry: {e}")
        return False

def change_mac_address_netsh(interface: str, new_mac: str) -> bool:
    """
    Attempt to change MAC address using netsh (limited support).
    """
    try:
        print(f"Attempting to change MAC address using netsh...")
        
        # Disable interface first
        if not toggle_wifi(interface, "off"):
            return False
        
        # Note: netsh doesn't directly support MAC address changing
        # This is a placeholder for the concept
        print("Note: Windows netsh doesn't directly support MAC address changing.")
        print("You may need to use:")
        print("1. Device Manager -> Network Adapter -> Properties -> Advanced -> Network Address")
        print("2. Third-party tools like Technitium MAC Address Changer")
        print("3. Registry editing (requires admin privileges)")
        
        # Re-enable interface
        toggle_wifi(interface, "on")
        
        return False
        
    except Exception as e:
        print(f"Error changing MAC address: {e}")
        return False

def test_mac_address(interface: str, mac_address: str, log_file: str) -> bool:
    """
    Test a MAC address change on Windows.
    """
    try:
        print(f"\nCurrent MAC address for {interface}:")
        current_mac = get_current_mac(interface)
        print(f"Current MAC: {current_mac}")
        
        print(f"\nAttempting to change MAC address to {mac_address}...")
        
        # Try registry method first
        success = change_mac_address_registry(interface, mac_address)
        
        if not success:
            # Try netsh method (limited)
            success = change_mac_address_netsh(interface, mac_address)
        
        if success:
            print(f"Successfully changed MAC address to {mac_address}")
            save_tested_mac(log_file, mac_address)
            return True
        else:
            print(f"Failed to change MAC address to {mac_address}")
            print("\nWindows MAC address changing options:")
            print("1. Use Device Manager -> Network Adapter -> Properties -> Advanced -> Network Address")
            print("2. Use third-party tools like Technitium MAC Address Changer")
            print("3. Use PowerShell with administrator privileges")
            return False
            
    except Exception as e:
        print(f"Unexpected error during MAC address change: {e}")
        return False

def show_windows_mac_change_instructions():
    """
    Show instructions for manually changing MAC address on Windows.
    """
    print("\n" + "="*60)
    print("WINDOWS MAC ADDRESS CHANGING INSTRUCTIONS")
    print("="*60)
    print("\nMethod 1: Device Manager")
    print("1. Open Device Manager (devmgmt.msc)")
    print("2. Expand 'Network adapters'")
    print("3. Right-click your network adapter -> Properties")
    print("4. Go to 'Advanced' tab")
    print("5. Look for 'Network Address' or 'Locally Administered Address'")
    print("6. Select 'Value' and enter the new MAC address (without colons)")
    print("7. Click OK and restart the adapter")
    
    print("\nMethod 2: PowerShell (Run as Administrator)")
    print("1. Get-NetAdapter | Select Name, InterfaceDescription, MacAddress")
    print("2. Set-NetAdapter -Name 'Wi-Fi' -MacAddress 'XX-XX-XX-XX-XX-XX'")
    print("3. Restart-NetAdapter -Name 'Wi-Fi'")
    
    print("\nMethod 3: Third-party Tools")
    print("- Technitium MAC Address Changer (Free)")
    print("- SMAC MAC Address Changer")
    print("- NoVirusThanks MAC Address Changer")
    print("\n" + "="*60)

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 arp_mac_changer_windows.py <pcapng_file> <interface>")
        print("Example: python3 arp_mac_changer_windows.py capture.pcapng \"Wi-Fi\"")
        print("\nAvailable interfaces:")
        interfaces = get_network_interfaces()
        for name in interfaces:
            print(f"  - \"{name}\"")
        sys.exit(1)
    
    pcapng_file = sys.argv[1]
    interface = sys.argv[2]
    log_file = "tested_macs_windows.log"
    
    if not os.path.exists(pcapng_file):
        print(f"Error: File {pcapng_file} does not exist")
        sys.exit(1)
    
    print("Windows MAC Address Changer")
    print("Note: This script demonstrates the concept but has limitations on Windows.")
    print("For full functionality, consider using dedicated Windows tools.")
    
    print(f"\nReading MAC addresses from {pcapng_file}...")
    all_mac_addresses = get_mac_addresses(pcapng_file)
    tested_macs = load_tested_macs(log_file)
    
    # Filter out already tested MAC addresses
    mac_addresses = all_mac_addresses - tested_macs
    
    if not mac_addresses:
        print("No new MAC addresses to test")
        sys.exit(0)
    
    print(f"Found {len(mac_addresses)} new MAC addresses to test")
    print(f"Skipping {len(tested_macs)} already tested MAC addresses")
    
    # Show instructions for manual MAC changing
    show_windows_mac_change_instructions()
    
    print("\nTesting each MAC address...")
    
    for mac in mac_addresses:
        print(f"\nTesting MAC address: {mac}")
        test_mac_address(interface, mac, log_file)
        
        # Ask user if they want to continue testing
        response = input("Continue testing next MAC address? (y/n): ")
        if response.lower() != 'y':
            break

if __name__ == "__main__":
    main()
