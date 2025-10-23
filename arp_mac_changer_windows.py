#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Auto-detect and use venv if not already running in it
def ensure_venv():
    script_dir = Path(__file__).parent.absolute()
    venv_python = script_dir / "venv" / "Scripts" / "python.exe"
    
    if str(sys.executable).endswith(("venv\\Scripts\\python.exe", "venv/Scripts/python.exe")):
        return  # Already running in venv
    
    if not venv_python.exists():
        print("Creating virtual environment...")
        import subprocess
        subprocess.run([sys.executable, '-m', 'venv', str(script_dir / 'venv')], check=True)
        pip_path = script_dir / 'venv' / 'Scripts' / 'pip.exe'
        subprocess.run([str(pip_path), 'install', 'pyshark'], check=True)
        print("✅ Setup complete!")
    
    print(f"Switching to venv...")
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)

ensure_venv()

import subprocess
import pyshark
from typing import Set

def get_mac_addresses(pcapng_file: str) -> Set[str]:
    """Extract MAC addresses from pcapng file."""
    capture = pyshark.FileCapture(pcapng_file, display_filter='eth.src')
    mac_addresses = set()
    for packet in capture:
        if hasattr(packet, 'eth') and hasattr(packet.eth, 'src'):
            mac_addresses.add(packet.eth.src)
    return mac_addresses

def change_mac_powershell(interface: str, new_mac: str) -> bool:
    """Change MAC address using PowerShell method."""
    try:
        # Format MAC for registry (no separators)
        registry_mac = new_mac.replace(':', '').replace('-', '')
        
        # PowerShell script to change MAC
        ps_script = f'''
        $adapter = Get-NetAdapter -Name "{interface}"
        $guid = $adapter.InterfaceGuid
        $regPath = "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}"
        
        Get-ChildItem $regPath | Where-Object {{
            $_.Name -match '\\d{{4}}$'
        }} | ForEach-Object {{
            $netCfg = Get-ItemProperty -Path $_.PSPath -Name "NetCfgInstanceId" -ErrorAction SilentlyContinue
            if ($netCfg -and $netCfg.NetCfgInstanceId -eq $guid) {{
                Set-ItemProperty -Path $_.PSPath -Name "NetworkAddress" -Value "{registry_mac}"
                Write-Host "Registry updated"
            }}
        }}
        
        Disable-NetAdapter -Name "{interface}" -Confirm:$false
        Start-Sleep 3
        Enable-NetAdapter -Name "{interface}" -Confirm:$false
        Start-Sleep 3
        
        $newAdapter = Get-NetAdapter -Name "{interface}"
        Write-Host "New MAC: $($newAdapter.MacAddress)"
        '''
        
        print(f"Changing MAC to {new_mac} using PowerShell...")
        result = subprocess.run(['powershell', '-Command', ps_script], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ MAC address changed successfully!")
            return True
        else:
            print(f"❌ Failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    if len(sys.argv) != 3:
        print("Usage: python windows_mac_changer.py <pcapng_file> <interface>")
        print('Example: python windows_mac_changer.py capture.pcapng "Wi-Fi"')
        
        # Show available interfaces
        try:
            result = subprocess.run(['powershell', '-Command', 
                                   'Get-NetAdapter | Select Name, Status | Format-Table -AutoSize'], 
                                  capture_output=True, text=True)
            print("\nAvailable interfaces:")
            print(result.stdout)
        except:
            pass
        sys.exit(1)
    
    pcapng_file = sys.argv[1]
    interface = sys.argv[2]
    
    if not os.path.exists(pcapng_file):
        print(f"Error: File {pcapng_file} does not exist")
        sys.exit(1)
    
    print("🔍 Reading MAC addresses from pcapng file...")
    mac_addresses = get_mac_addresses(pcapng_file)
    
    if not mac_addresses:
        print("No MAC addresses found")
        sys.exit(0)
    
    print(f"Found {len(mac_addresses)} MAC addresses")
    print("\n⚠️  IMPORTANT: Run this script as Administrator for MAC changing to work!")
    print("Right-click Command Prompt → 'Run as administrator'\n")
    
    for i, mac in enumerate(mac_addresses, 1):
        print(f"\n[{i}/{len(mac_addresses)}] Testing MAC: {mac}")
        
        success = change_mac_powershell(interface, mac)
        
        if success:
            print(f"✅ Successfully changed to {mac}")
        else:
            print(f"❌ Failed to change to {mac}")
            print("💡 Try:")
            print("  1. Run as Administrator")
            print("  2. Check if your network adapter supports MAC spoofing")
            print("  3. Use Device Manager method manually")
        
        if i < len(mac_addresses):
            response = input("\nContinue to next MAC? (y/n): ")
            if response.lower() != 'y':
                break
    
    print("\n🏁 Done!")

if __name__ == "__main__":
    main()