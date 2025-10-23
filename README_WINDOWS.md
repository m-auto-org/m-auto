# Windows MAC Address Changer

This directory contains Windows-compatible versions of the MAC address changing tools.

## Files

- `arp_mac_changer_windows.py` - Main Python script for Windows
- `change_mac_windows.ps1` - PowerShell script for direct MAC changing
- `run_mac_changer_windows.bat` - Batch file for easy execution
- `README_WINDOWS.md` - This file

## Requirements

### Software Requirements
- **Python 3.7+** - Download from [python.org](https://python.org)
- **Administrator privileges** - Required for network interface modifications
- **PowerShell 5.0+** - Usually pre-installed on Windows 10/11

### Python Dependencies
- `pyshark` - Automatically installed by the script
- `typing` - Usually included with Python 3.5+

## Installation & Setup

### Method 1: Automatic Setup (Recommended)
```batch
# Clone the repository
git clone https://github.com/m-auto-org/m-auto.git
cd m-auto

# Run the script - it will automatically create venv and install dependencies
python arp_mac_changer_windows.py capture.pcapng "Wi-Fi"
```

### Method 2: Manual Setup
```batch
# Clone and setup virtual environment
git clone https://github.com/m-auto-org/m-auto.git
cd m-auto
python -m venv venv
venv\Scripts\activate
pip install pyshark

# Run the script
python arp_mac_changer_windows.py capture.pcapng "Wi-Fi"
```

## Usage

### Using the Batch File (Easiest)
```batch
run_mac_changer_windows.bat capture.pcapng "Wi-Fi"
```

### Using Python Directly
```batch
python arp_mac_changer_windows.py capture.pcapng "Wi-Fi"
```

### Using PowerShell Script (Direct MAC Change)
```powershell
# Run PowerShell as Administrator
.\change_mac_windows.ps1 -InterfaceName "Wi-Fi" -NewMacAddress "AA:BB:CC:DD:EE:FF"

# Show available interfaces
.\change_mac_windows.ps1 -ShowInterfaces
```

## Finding Your Network Interface Name

### Method 1: Command Line
```batch
# List all network adapters
netsh interface show interface

# Or use PowerShell
powershell "Get-NetAdapter | Select Name, Status"
```

### Method 2: Network Settings
1. Open **Settings** → **Network & Internet**
2. Click on your connection type (Wi-Fi or Ethernet)
3. The interface name is usually "Wi-Fi" or "Ethernet"

### Method 3: Device Manager
1. Open **Device Manager** (`devmgmt.msc`)
2. Expand **Network adapters**
3. Your interface names are listed there

## Windows-Specific Limitations

### MAC Address Changing Challenges
Windows has more restrictions on MAC address changing compared to macOS/Linux:

1. **Driver Support**: Not all network adapters support MAC address spoofing
2. **Registry Method**: Requires administrator privileges and adapter restart
3. **Hardware Limitations**: Some adapters ignore software MAC changes

### Supported Methods

#### 1. Registry Method (Automatic)
- Used by the Python script
- Requires administrator privileges
- Works with most adapters that support MAC spoofing

#### 2. Device Manager Method (Manual)
1. Open **Device Manager**
2. Right-click network adapter → **Properties**
3. **Advanced** tab → **Network Address** or **Locally Administered Address**
4. Enter new MAC address (without colons)
5. Restart adapter

#### 3. PowerShell Method (Semi-Automatic)
- Use the included `change_mac_windows.ps1` script
- Handles adapter disable/enable automatically
- Provides better error handling

## Troubleshooting

### Common Issues

#### "Access Denied" Errors
- **Solution**: Run Command Prompt or PowerShell as Administrator
- Right-click → "Run as administrator"

#### "Interface Not Found"
- **Solution**: Check exact interface name using:
  ```batch
  netsh interface show interface
  ```

#### MAC Address Not Changing
- **Cause**: Network adapter doesn't support MAC spoofing
- **Solutions**:
  1. Try different network adapter
  2. Update network drivers
  3. Use USB Wi-Fi adapter that supports spoofing
  4. Use third-party tools

#### Virtual Environment Issues
- **Solution**: The script automatically creates and manages the virtual environment
- If issues persist, manually delete `venv` folder and re-run

### Third-Party Alternatives

If the built-in methods don't work, consider these tools:

1. **Technitium MAC Address Changer** (Free)
   - Download: [technitium.com](https://technitium.com/tmac/)
   - GUI-based, easy to use

2. **SMAC MAC Address Changer**
   - Commercial tool with good hardware support

3. **NoVirusThanks MAC Address Changer**
   - Free alternative with simple interface

## Security Notes

### Administrator Privileges
- Required for modifying network interface settings
- Scripts will prompt for elevation when needed

### Antivirus Software
- Some antivirus programs may flag MAC changing tools
- Add exceptions if necessary (false positives are common)

### Network Policies
- Corporate networks may detect/block MAC address changes
- Use responsibly and in compliance with local policies

## Example Output

```
Windows MAC Address Changer
Note: This script demonstrates the concept but has limitations on Windows.
For full functionality, consider using dedicated Windows tools.

Reading MAC addresses from capture.pcapng...
Found 15 new MAC addresses to test
Skipping 5 already tested MAC addresses

========================================
WINDOWS MAC ADDRESS CHANGING INSTRUCTIONS
========================================

Method 1: Device Manager
1. Open Device Manager (devmgmt.msc)
2. Expand 'Network adapters'
3. Right-click your network adapter -> Properties
4. Go to 'Advanced' tab
5. Look for 'Network Address' or 'Locally Administered Address'
6. Select 'Value' and enter the new MAC address (without colons)
7. Click OK and restart the adapter

Testing each MAC address...

Testing MAC address: aa:bb:cc:dd:ee:ff
Current MAC address for Wi-Fi:
Current MAC: AA-BB-CC-DD-EE-FF

Attempting to change MAC address to aa:bb:cc:dd:ee:ff...
Registry-based MAC changing requires more complex implementation.
Consider using third-party tools like Technitium MAC Address Changer.

Continue testing next MAC address? (y/n):
```

## Support

For Windows-specific issues:
1. Check Windows version compatibility
2. Verify administrator privileges
3. Test with different network adapters
4. Consider third-party tools for stubborn hardware

For general issues, refer to the main project documentation.
