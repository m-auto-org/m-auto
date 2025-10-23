# Windows MAC Address Changer PowerShell Script
# Run as Administrator for full functionality

param(
    [Parameter(Mandatory=$true)]
    [string]$InterfaceName,
    
    [Parameter(Mandatory=$true)]
    [string]$NewMacAddress,
    
    [switch]$ShowInterfaces
)

function Show-NetworkInterfaces {
    Write-Host "Available Network Interfaces:" -ForegroundColor Green
    Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, MacAddress | Format-Table -AutoSize
}

function Test-AdminPrivileges {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Validate-MacAddress {
    param([string]$Mac)
    
    # Remove common separators and validate format
    $cleanMac = $Mac -replace '[:-]', ''
    
    if ($cleanMac.Length -ne 12) {
        return $false
    }
    
    if ($cleanMac -notmatch '^[0-9A-Fa-f]{12}$') {
        return $false
    }
    
    return $true
}

function Change-MacAddress {
    param(
        [string]$Interface,
        [string]$Mac
    )
    
    try {
        Write-Host "Attempting to change MAC address for interface: $Interface" -ForegroundColor Yellow
        Write-Host "New MAC address: $Mac" -ForegroundColor Yellow
        
        # Get current MAC address
        $adapter = Get-NetAdapter -Name $Interface -ErrorAction Stop
        $currentMac = $adapter.MacAddress
        Write-Host "Current MAC address: $currentMac" -ForegroundColor Cyan
        
        # Disable the adapter
        Write-Host "Disabling network adapter..." -ForegroundColor Yellow
        Disable-NetAdapter -Name $Interface -Confirm:$false
        Start-Sleep -Seconds 3
        
        # Format MAC address for registry (no separators)
        $registryMac = $Mac -replace '[:-]', ''
        
        # Try to set MAC address using registry method
        $adapterGuid = $adapter.InterfaceGuid
        $registryPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
        
        # Find the correct registry subkey for this adapter
        $subKeys = Get-ChildItem $registryPath | Where-Object { $_.Name -match '\d{4}$' }
        
        foreach ($subKey in $subKeys) {
            $netCfgInstanceId = Get-ItemProperty -Path $subKey.PSPath -Name "NetCfgInstanceId" -ErrorAction SilentlyContinue
            if ($netCfgInstanceId -and $netCfgInstanceId.NetCfgInstanceId -eq $adapterGuid) {
                Write-Host "Found adapter registry key: $($subKey.PSPath)" -ForegroundColor Green
                
                # Set the NetworkAddress value
                Set-ItemProperty -Path $subKey.PSPath -Name "NetworkAddress" -Value $registryMac
                Write-Host "Registry updated with new MAC address" -ForegroundColor Green
                break
            }
        }
        
        # Re-enable the adapter
        Write-Host "Re-enabling network adapter..." -ForegroundColor Yellow
        Enable-NetAdapter -Name $Interface
        Start-Sleep -Seconds 5
        
        # Verify the change
        $newAdapter = Get-NetAdapter -Name $Interface
        $newMacAddress = $newAdapter.MacAddress
        
        Write-Host "Verification:" -ForegroundColor Green
        Write-Host "  Old MAC: $currentMac" -ForegroundColor Cyan
        Write-Host "  New MAC: $newMacAddress" -ForegroundColor Cyan
        
        if ($newMacAddress -eq $Mac -or $newMacAddress -eq ($Mac -replace ':', '-')) {
            Write-Host "✅ MAC address changed successfully!" -ForegroundColor Green
            return $true
        } else {
            Write-Host "⚠️  MAC address may not have changed. Some adapters don't support MAC spoofing." -ForegroundColor Yellow
            return $false
        }
        
    } catch {
        Write-Host "❌ Error changing MAC address: $($_.Exception.Message)" -ForegroundColor Red
        
        # Try to re-enable adapter if something went wrong
        try {
            Enable-NetAdapter -Name $Interface -ErrorAction SilentlyContinue
        } catch {
            Write-Host "⚠️  Warning: Could not re-enable adapter. You may need to do this manually." -ForegroundColor Yellow
        }
        
        return $false
    }
}

# Main script execution
if ($ShowInterfaces) {
    Show-NetworkInterfaces
    exit 0
}

# Check if running as administrator
if (-not (Test-AdminPrivileges)) {
    Write-Host "❌ This script requires administrator privileges!" -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit 1
}

# Validate MAC address format
if (-not (Validate-MacAddress -Mac $NewMacAddress)) {
    Write-Host "❌ Invalid MAC address format: $NewMacAddress" -ForegroundColor Red
    Write-Host "Please use format: XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX" -ForegroundColor Yellow
    exit 1
}

# Check if interface exists
try {
    $adapter = Get-NetAdapter -Name $InterfaceName -ErrorAction Stop
    Write-Host "Found network interface: $($adapter.InterfaceDescription)" -ForegroundColor Green
} catch {
    Write-Host "❌ Network interface '$InterfaceName' not found!" -ForegroundColor Red
    Write-Host "Available interfaces:" -ForegroundColor Yellow
    Show-NetworkInterfaces
    exit 1
}

# Perform MAC address change
$success = Change-MacAddress -Interface $InterfaceName -Mac $NewMacAddress

if ($success) {
    Write-Host "`n✅ MAC address change completed!" -ForegroundColor Green
} else {
    Write-Host "`n❌ MAC address change failed!" -ForegroundColor Red
    Write-Host "Some network adapters don't support MAC address spoofing." -ForegroundColor Yellow
    Write-Host "Try using Device Manager method or third-party tools." -ForegroundColor Yellow
}

Write-Host "`nPress any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
