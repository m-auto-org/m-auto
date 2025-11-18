#!/usr/bin/env python3

import os
import sys
import platform
from pathlib import Path

# Auto-detect and use venv if not already running in it
def ensure_venv():
    script_dir = Path(__file__).parent.absolute()
    
    # Detect operating system and set appropriate paths
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        venv_python = script_dir / "venv" / "Scripts" / "python.exe"
        venv_pip = script_dir / "venv" / "Scripts" / "pip.exe"
        venv_identifier = "venv\\Scripts\\python.exe"
    else:
        venv_python = script_dir / "venv" / "bin" / "python3"
        venv_pip = script_dir / "venv" / "bin" / "pip"
        venv_identifier = "venv/bin/python3"
    
    # Check if we're already running in the venv
    if venv_identifier in str(sys.executable):
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
            print("[OK] Virtual environment created successfully!")
            
            # Install required packages
            print("Installing required packages (pyshark)...")
            install_args = [str(venv_pip), 'install', 'pyshark']
            if not is_windows:
                install_args.insert(2, '--no-user')  # --no-user flag only for Unix-like systems
            
            result = subprocess.run(install_args, 
                                  capture_output=True, text=True, check=True)
            print("[OK] Required packages installed successfully!")
            
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
        if is_windows:
            # On Windows, use subprocess to restart with venv Python
            import subprocess
            result = subprocess.run([str(venv_python)] + sys.argv, check=True)
            sys.exit(result.returncode)
        else:
            # On Unix-like systems, use execv for seamless replacement
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)
    except Exception as e:
        print(f"ERROR: Failed to switch to virtual environment!")
        print(f"Error: {e}")
        print("Please check that the virtual environment is properly set up.")
        sys.exit(1)

# Call this at the start
ensure_venv()

# Import all other modules after ensuring we're in the correct environment
from typing import Set
import pyshark

def find_tshark_windows():
    """
    Automatically find TShark executable on Windows across all drives.
    """
    import string
    from pathlib import Path
    
    # Common installation paths for Wireshark/TShark
    common_paths = [
        "Program Files\\Wireshark\\tshark.exe",
        "Program Files (x86)\\Wireshark\\tshark.exe",
        "Wireshark\\tshark.exe",  # For installations in root of drive (e.g., D:\Wireshark)
        "wireshark\\tshark.exe",  # Lowercase variant (e.g., D:\wireshark)
    ]
    
    # Get all available drives (C:, D:, E:, etc.)
    available_drives = [f"{d}:\\" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
    
    print("Searching for TShark across all drives...")
    
    # Search each drive for TShark
    for drive in available_drives:
        for path in common_paths:
            tshark_path = Path(drive) / path
            if tshark_path.exists():
                print(f"[OK] Found TShark at: {tshark_path}")
                return str(tshark_path)
    
    return None

# Global variable to store TShark path
tshark_path = None

def configure_pyshark_windows():
    """
    Configure pyshark to use TShark on Windows by finding it automatically.
    """
    global tshark_path
    tshark_path = find_tshark_windows()
    
    if tshark_path:
        # Set the TShark path for pyshark config as well (for compatibility)
        try:
            import pyshark.config
            pyshark.config.tshark_path = tshark_path
        except:
            pass  # If config doesn't work, we'll pass it directly to FileCapture
        print(f"Configured pyshark to use TShark at: {tshark_path}")
    else:
        print("[WARNING] TShark not found on any drive!")
        print("Please install Wireshark from: https://www.wireshark.org/download.html")
        print("Make sure to include TShark during installation.")
        sys.exit(1)

# Configure TShark path on Windows
if platform.system() == "Windows":
    configure_pyshark_windows()

def get_mac_addresses(pcapng_file: str) -> Set[str]:
    """
    Extract unique MAC addresses from a pcapng file.
    """
    try:
        # Use tshark_path if configured, otherwise let pyshark find it
        if tshark_path:
            capture = pyshark.FileCapture(pcapng_file, display_filter='eth.src', tshark_path=tshark_path)
        else:
            capture = pyshark.FileCapture(pcapng_file, display_filter='eth.src')
        mac_addresses = set()
        
        for packet in capture:
            if hasattr(packet, 'eth') and hasattr(packet.eth, 'src'):
                mac_addresses.add(packet.eth.src)
        
        return mac_addresses
    except Exception as e:
        print(f"Error reading pcapng file: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 arp_mac_lister.py <pcapng_file>")
        print("Example: python3 arp_mac_lister.py capture.pcapng")
        sys.exit(1)
    
    pcapng_file = sys.argv[1]
    
    if not os.path.exists(pcapng_file):
        print(f"Error: File {pcapng_file} does not exist")
        sys.exit(1)
    
    print(f"Reading MAC addresses from {pcapng_file}...")
    mac_addresses = get_mac_addresses(pcapng_file)
    
    if not mac_addresses:
        print("No MAC addresses found in the capture file")
        sys.exit(0)
    
    print(f"\nFound {len(mac_addresses)} unique MAC addresses:\n")
    print("=" * 50)
    for mac in sorted(mac_addresses):
        print(mac)
    print("=" * 50)
    print(f"\nTotal: {len(mac_addresses)} MAC addresses")

if __name__ == "__main__":
    main() 