#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Auto-detect and use venv if not already running in it
def ensure_venv():
    script_dir = Path(__file__).parent.absolute()
    venv_python = script_dir / "venv" / "bin" / "python3"
    
    # Check if we're already running in the venv
    if str(sys.executable).endswith("venv/bin/python3"):
        return  # Already running in venv, continue normally
    
    # Check if venv exists
    if not venv_python.exists():
        print(f"ERROR: Virtual environment not found!")
        print(f"Expected location: {venv_python}")
        print("Please ensure the 'venv' directory exists in the same folder as this script.")
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
from typing import List, Set
import pyshark

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
        # Create file with proper permissions if it doesn't exist
        if not os.path.exists(log_file):
            # Get the real user ID (not root when using sudo)
            real_user = os.environ.get('SUDO_USER', os.environ.get('USER', 'francislargo'))
            with open(log_file, 'w') as f:
                pass  # Create empty file
            # Try to change ownership to the real user
            try:
                import pwd
                import grp
                user_info = pwd.getpwnam(real_user)
                os.chown(log_file, user_info.pw_uid, user_info.pw_gid)
            except:
                pass  # If we can't change ownership, continue anyway
        
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

def toggle_wifi(interface: str, state: str) -> bool:
    """
    Turn WiFi interface on or off.
    """
    try:
        action = "on" if state == "on" else "off"
        print(f"\nTurning WiFi {action}...")
        subprocess.run(['networksetup', '-setairportpower', interface, action], check=True)
        print(f"WiFi turned {action} successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error turning WiFi {state}: {e}")
        return False

def test_mac_address(interface: str, mac_address: str, log_file: str) -> bool:
    """
    Test a MAC address using macchanger.
    """
    try:
        # First toggle WiFi off then on
        print("\nPreparing interface by toggling WiFi...")
        if not toggle_wifi(interface, "off"):
            print("Failed to turn off WiFi. Aborting MAC address change.")
            return False
        
        if not toggle_wifi(interface, "on"):
            print("Failed to turn on WiFi. Aborting MAC address change.")
            return False

        print(f"\nCurrent MAC address for {interface}:")
        subprocess.run(['ifconfig', interface], check=True)
        
        print(f"\nChanging MAC address to {mac_address}...")
        result = subprocess.run(
            ['sudo', 'macchanger', '-m', mac_address, interface],
            capture_output=True,
            text=True
        )
        
        print(f"\nMAC changer output: {result.stdout}")
        if result.stderr:
            print(f"MAC changer errors: {result.stderr}")
        
        print(f"\nNew MAC address for {interface}:")
        subprocess.run(['ifconfig', interface], check=True)
        
        if result.returncode == 0:
            print(f"Successfully changed MAC address to {mac_address}")
            save_tested_mac(log_file, mac_address)
            return True
        else:
            print(f"Failed to change MAC address to {mac_address}")
            print(f"Error: {result.stderr}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(f"Command output: {e.output if hasattr(e, 'output') else 'No output'}")
        return False
    except Exception as e:
        print(f"Unexpected error during MAC address change: {e}")
        return False

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 mac_changer.py <pcapng_file> <interface>")
        print("Example: python3 mac_changer.py capture.pcapng en0")
        sys.exit(1)
    
    pcapng_file = sys.argv[1]
    interface = sys.argv[2]
    log_file = "tested_macs.log"
    
    if not os.path.exists(pcapng_file):
        print(f"Error: File {pcapng_file} does not exist")
        sys.exit(1)
    
    print(f"Reading MAC addresses from {pcapng_file}...")
    all_mac_addresses = get_mac_addresses(pcapng_file)
    tested_macs = load_tested_macs(log_file)
    
    # Filter out already tested MAC addresses
    mac_addresses = all_mac_addresses - tested_macs
    
    if not mac_addresses:
        print("No new MAC addresses to test")
        sys.exit(0)
    
    print(f"Found {len(mac_addresses)} new MAC addresses to test")
    print(f"Skipping {len(tested_macs)} already tested MAC addresses")
    print("Testing each MAC address...")
    
    for mac in mac_addresses:
        print(f"\nTesting MAC address: {mac}")
        test_mac_address(interface, mac, log_file)
        
        # Ask user if they want to continue testing
        response = input("Continue testing next MAC address? (y/n): ")
        if response.lower() != 'y':
            break

if __name__ == "__main__":
    main() 