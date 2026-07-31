#!/bin/bash

# Quiet SOCKS5 Proxy for macOS (with Ad Blocking)
# Routes all traffic from other devices through Mac with minimal logging & ad blocking

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "This script requires root privileges. Please run with sudo."
    exit 1
fi

SOCKS_PORT=8084
# Log file for proxy output
PROXY_LOG="/tmp/socks_proxy_block.log"
# View mode (clients or websites)
VIEW_MODE="clients"

# Resolve directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLOCKLIST_FILE="$SCRIPT_DIR/blocklist.txt"
SESSION_LOG_DIR="$SCRIPT_DIR/session_logs"

# Ensure directories exist
mkdir -p "$SESSION_LOG_DIR"
SESSION_LOG_FILE="$SESSION_LOG_DIR/session_$(date +%Y%m%d_%H%M%S).log"

# Ensure blocklist exists
if [ ! -f "$BLOCKLIST_FILE" ]; then
    echo "Creating empty blocklist at $BLOCKLIST_FILE"
    touch "$BLOCKLIST_FILE"
fi

# Function to disable sleep
disable_sleep() {
    echo "Disabling system sleep..."
    pmset -a sleep 0
    pmset -b disablesleep 1
}

# Function to enable sleep
enable_sleep() {
    echo "Re-enabling system sleep..."
    pmset -a sleep 1
    pmset -b disablesleep 0
}

# Get Mac's IP address
MAC_IP=$(ifconfig en0 | grep "inet " | awk '{print $2}')
if [ -z "$MAC_IP" ]; then
    # Try alternative interfaces if en0 doesn't have an IP
    MAC_IP=$(ifconfig en1 | grep "inet " | awk '{print $2}')
    if [ -z "$MAC_IP" ]; then
        echo "Error: Could not determine your Mac's IP address. Exiting."
        exit 1
    fi
fi

echo "====================================="
# Highlight that this is the Ad Blocking version
echo "   AD-BLOCKING SOCKS5 PROXY SETUP    "
echo "====================================="
echo "Mac's IP: $MAC_IP"
echo "SOCKS Port: $SOCKS_PORT"
echo "Blocklist: $BLOCKLIST_FILE"
echo "Session Log: $SESSION_LOG_FILE"
echo "====================================="

# Install required Python packages if not already installed
echo "Checking for required Python packages..."
if ! python3 -c "import socks" 2>/dev/null; then
    echo "Installing required Python packages..."
    pip3 install pysocks
fi

# Create a quiet socks proxy script with ad-blocking
cat > /tmp/quiet_socks_proxy_block.py << 'EOF'
#!/usr/bin/env python3
import sys
import os
import socket
import threading
import select
import time
import logging
from socketserver import ThreadingMixIn
import json
from collections import defaultdict, deque
from datetime import datetime

# Set up minimal logging
logging.basicConfig(
    level=logging.ERROR,  # Only show errors
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('proxy')

# Global flag for minimal logging
MINIMAL_LOGGING = True

# Global dictionaries to track connections and websites
active_clients = defaultdict(int)
visited_websites = defaultdict(int)
recent_websites = deque(maxlen=10)  # Keep only last 10 websites
connections_lock = threading.Lock()

class SocksProxy:
    SOCKS_VERSION = 5  # SOCKS5

    def __init__(self, host='0.0.0.0', port=8084, blocklist_path=None, session_log_path=None):
        self.host = host
        self.port = port
        self.blocklist_path = blocklist_path
        self.session_log_path = session_log_path
        self.blocklist = []
        self._last_load = 0
        self.get_blocklist()  # Initial load
        
    def log_to_session(self, client_ip, target_addr, status="ALLOWED"):
        if not self.session_log_path:
            return
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.session_log_path, 'a') as f:
                f.write(f"[{timestamp}] {client_ip} -> {target_addr} [{status}]\n")
        except Exception as e:
            logger.error(f"Error writing to session log: {e}")
        
    def load_blocklist(self):
        if not self.blocklist_path or not os.path.exists(self.blocklist_path):
            return []
        blocklist = []
        try:
            with open(self.blocklist_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        blocklist.append(line.lower())
        except Exception as e:
            logger.error(f"Error loading blocklist: {e}")
        return blocklist

    def get_blocklist(self):
        now = time.time()
        # Cache blocklist for 5 seconds to prevent excessive disk reads
        if now - self._last_load > 5:
            self.blocklist = self.load_blocklist()
            self._last_load = now
        return self.blocklist

    def is_blocked(self, target_addr):
        target = target_addr.lower()
        for pattern in self.get_blocklist():
            if pattern.startswith('*.'):
                suffix = pattern[2:]
                if target == suffix or target.endswith('.' + suffix):
                    return True
            elif pattern == target:
                return True
            elif target.endswith('.' + pattern) or target == pattern:
                return True
        return False
        
    def update_stats(self, client_ip, target_addr):
        with connections_lock:
            if target_addr:
                # Add to recent websites with timestamp
                recent_websites.appendleft({
                    'site': target_addr,
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'client': client_ip
                })
                # Only count active counts and visited stats for allowed sites
                if not target_addr.startswith("[BLOCKED]"):
                    active_clients[client_ip] += 1
                    visited_websites[target_addr] += 1
            
            # Save stats to file
            stats = {
                'active_clients': dict(active_clients),
                'visited_websites': dict(visited_websites),
                'recent_websites': list(recent_websites)
            }
            with open('/tmp/proxy_stats_block.json', 'w') as f:
                json.dump(stats, f)
    
    def remove_client(self, client_ip):
        with connections_lock:
            if client_ip in active_clients:
                active_clients[client_ip] -= 1
                if active_clients[client_ip] <= 0:
                    del active_clients[client_ip]
            # Save stats to file
            stats = {
                'active_clients': dict(active_clients),
                'visited_websites': dict(visited_websites),
                'recent_websites': list(recent_websites)
            }
            with open('/tmp/proxy_stats_block.json', 'w') as f:
                json.dump(stats, f)
        
    def handle_client(self, client_socket, client_address):
        try:
            client_ip = client_address[0]
            self.update_stats(client_ip, None)
            
            # Greeting header
            header = client_socket.recv(2)
            if len(header) < 2 or header[0] != self.SOCKS_VERSION:
                if not MINIMAL_LOGGING:
                    logger.warning(f"Invalid SOCKS version from {client_address}")
                client_socket.close()
                return
            
            # Get available auth methods
            num_methods = header[1]
            methods = client_socket.recv(num_methods)
            
            # Accept only 'no authentication'
            client_socket.sendall(b'\x05\x00')  # SOCKS5, no auth required
            
            # Request
            version, cmd, _, address_type = client_socket.recv(4)
            if version != self.SOCKS_VERSION or cmd != 1:  # Only support CONNECT
                client_socket.close()
                return
            
            # Parse destination address
            if address_type == 1:  # IPv4
                target_addr = socket.inet_ntoa(client_socket.recv(4))
            elif address_type == 3:  # Domain name
                domain_length = client_socket.recv(1)[0]
                target_addr = client_socket.recv(domain_length).decode()
            else:
                client_socket.close()
                return
            
            # Parse port
            target_port = int.from_bytes(client_socket.recv(2), 'big')
            
            # Ad blocking logic
            if self.is_blocked(target_addr):
                self.update_stats(client_ip, f"[BLOCKED] {target_addr}")
                self.log_to_session(client_ip, target_addr, "BLOCKED")
                # SOCKS5 Connection Refused reply
                reply = b'\x05\x05\x00\x01'
                reply += socket.inet_aton('0.0.0.0') + (0).to_bytes(2, 'big')
                client_socket.sendall(reply)
                client_socket.close()
                self.remove_client(client_ip)
                return
            
            self.update_stats(client_ip, target_addr)
            self.log_to_session(client_ip, target_addr, "ALLOWED")
            
            if not MINIMAL_LOGGING:
                logger.info(f"Connection request from {client_address} to {target_addr}:{target_port}")
            
            # Connect to target
            try:
                remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote_socket.connect((target_addr, target_port))
                bind_addr = remote_socket.getsockname()
                if not MINIMAL_LOGGING:
                    logger.debug(f"Connected to {target_addr}:{target_port}")
            except Exception as e:
                if not MINIMAL_LOGGING:
                    logger.error(f"Failed to connect to {target_addr}:{target_port}: {e}")
                # Return connection refused error
                reply = b'\x05\x05\x00\x01'  # SOCKS5, connection refused, reserved, IPv4
                reply += socket.inet_aton('0.0.0.0') + (0).to_bytes(2, 'big')
                client_socket.sendall(reply)
                client_socket.close()
                self.remove_client(client_ip)
                return
            
            # Send success response
            bind_addr_bytes = socket.inet_aton(bind_addr[0])
            bind_port_bytes = bind_addr[1].to_bytes(2, 'big')
            reply = b'\x05\x00\x00\x01' + bind_addr_bytes + bind_port_bytes
            client_socket.sendall(reply)
            
            # Establish data exchange
            if client_socket.fileno() != -1 and remote_socket.fileno() != -1:
                self.exchange_loop(client_socket, remote_socket)
            
        except Exception as e:
            if not MINIMAL_LOGGING:
                logger.error(f"Error handling client: {e}")
        finally:
            if client_socket:
                client_socket.close()
            self.remove_client(client_ip)
    
    def exchange_loop(self, client, remote):
        while True:
            # Wait until client or remote is available for read
            r, w, e = select.select([client, remote], [], [], 60)
            
            if client in r:
                data = client.recv(4096)
                if not data:
                    break
                remote.sendall(data)
            
            if remote in r:
                data = remote.recv(4096)
                if not data:
                    break
                client.sendall(data)
    
    def start(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind((self.host, self.port))
                server_socket.listen(100)
                logger.info(f"SOCKS5 proxy listening on {self.host}:{self.port}")
                
                while True:
                    client_socket, client_address = server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Error starting SOCKS5 proxy: {e}")

if __name__ == '__main__':
    blocklist_path = sys.argv[1] if len(sys.argv) > 1 else None
    session_log_path = sys.argv[2] if len(sys.argv) > 2 else None
    proxy = SocksProxy(blocklist_path=blocklist_path, session_log_path=session_log_path)
    proxy.start()
EOF

# Make the Python script executable
chmod +x /tmp/quiet_socks_proxy_block.py

# Function to check if proxy is running
check_proxy() {
    nc -z localhost $SOCKS_PORT 2>/dev/null
    return $?
}

# Function to display interface
display_interface() {
    clear
    echo "====================================="
    echo "    QUIET SOCKS5 PROXY (AD BLOCK)    "
    echo "====================================="
    echo "Mac's IP: $MAC_IP"
    echo "SOCKS Port: $SOCKS_PORT"
    echo "Last refresh: $(date +"%H:%M:%S")"
    echo "====================================="
    echo ""
    
    if [ -f "/tmp/proxy_stats_block.json" ]; then
        if [ "$VIEW_MODE" = "clients" ]; then
            echo "--- ACTIVE CLIENTS ---"
            echo ""
            python3 -c '
import json
try:
    with open("/tmp/proxy_stats_block.json") as f:
        stats = json.load(f)
        clients = stats.get("active_clients", {})
        if clients:
            for ip, count in clients.items():
                print(f"- {ip} ({count} connections)")
        else:
            print("No active clients")
except:
    print("No active clients")
'
        elif [ "$VIEW_MODE" = "websites" ]; then
            echo "--- RECENT WEBSITES (BLOCKS LOGGED) ---"
            echo ""
            python3 -c '
import json
try:
    with open("/tmp/proxy_stats_block.json") as f:
        stats = json.load(f)
        recent = stats.get("recent_websites", [])
        if recent:
            for site in recent:
                time = site["time"]
                url = site["site"]
                client = site["client"]
                print("- [%s] %s (from %s)" % (time, url, client))
        else:
            print("No websites visited")
except:
    print("No websites visited")
'
        fi
    else
        echo "No statistics available yet"
    fi
    
    echo ""
    echo "====================================="
    echo "[1] Active Clients | [2] Recent Sites | [q] Quit"
    echo "====================================="
}

# Kill any existing proxy processes
pkill -f "quiet_socks_proxy_block.py" >/dev/null 2>&1
pkill -f "quiet_socks_proxy.py" >/dev/null 2>&1

# Start the proxy
echo "Starting SOCKS5 proxy..."
python3 /tmp/quiet_socks_proxy_block.py "$BLOCKLIST_FILE" "$SESSION_LOG_FILE" > $PROXY_LOG 2>&1 &
PROXY_PID=$!

# Wait for proxy to start
sleep 2
if ! check_proxy; then
    echo "Failed to start SOCKS5 proxy. Check $PROXY_LOG for details."
    exit 1
fi

# Disable sleep mode
disable_sleep

echo "SOCKS5 proxy is running successfully!"
echo "Configure your devices with these settings:"
echo "  - Host: $MAC_IP"
echo "  - Port: $SOCKS_PORT"
echo "  - Type: SOCKS5"
echo ""
echo "Press Enter to continue to the interface..."
read

# Main loop
while true; do
    # Check if proxy is still running
    if ! ps -p $PROXY_PID > /dev/null; then
        echo "Error: Proxy process died. Restarting..."
        python3 /tmp/quiet_socks_proxy_block.py "$BLOCKLIST_FILE" "$SESSION_LOG_FILE" > "$PROXY_LOG" 2>&1 &
        PROXY_PID=$!
        sleep 2
        
        if ! ps -p $PROXY_PID > /dev/null; then
            echo "Error: Failed to restart proxy. Exiting."
            exit 1
        fi
    fi
    
    display_interface
    
    echo -n "Enter option: "
    read -n 1 key
    
    case "$key" in
        1)
            VIEW_MODE="clients"
            ;;
        2)
            VIEW_MODE="websites"
            ;;
        q|Q)
            echo ""
            echo "Cleaning up..."
            kill $PROXY_PID 2>/dev/null
            rm -f $PROXY_LOG /tmp/proxy_stats_block.json /tmp/quiet_socks_proxy_block.py 2>/dev/null
            # Re-enable sleep mode
            enable_sleep
            echo "Proxy stopped."
            exit 0
            ;;
    esac
done
