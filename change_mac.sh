#!/bin/bash

# Usage: sudo ./change_mac.sh <new-mac-address>
# Example: sudo ./change_mac.sh 00:11:22:33:44:55

if [ -z "$1" ]; then
    echo "Usage: $0 <new-mac-address>"
    exit 1
fi

NEW_MAC=$1
WIFI_DEVICE=$(networksetup -listallhardwareports | \
    awk '/Wi-Fi|AirPort/{getline; print $2}')

if [ -z "$WIFI_DEVICE" ]; then
    echo "No Wi-Fi interface found."
    exit 1
fi

echo "[*] Disabling Wi-Fi..."
networksetup -setairportpower "$WIFI_DEVICE" off
sleep 1

echo "[*] Re-enabling Wi-Fi..."
networksetup -setairportpower "$WIFI_DEVICE" on

echo "[*] Changing MAC to $NEW_MAC ..."
macchanger -m "$NEW_MAC" "$WIFI_DEVICE"

echo "[*] Done. Current MAC:"
ifconfig "$WIFI_DEVICE" | grep ether
