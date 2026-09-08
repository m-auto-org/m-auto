#!/bin/bash

# ==============================================================================
# Keep-Pinging: Wi-Fi Radio Keep-Alive & Latency Stabilizer
# Keeps local Wi-Fi PHY modulation rate at maximum & prevents idle power-save sleep
# ==============================================================================

PID_FILE="/tmp/keep_pinging.pid"
LOG_FILE="/tmp/keep_pinging.log"

# Default configuration
DEFAULT_TARGET="8.8.8.8"
DEFAULT_INTERVAL=1.5
DEFAULT_SIZE=32

TARGET="$DEFAULT_TARGET"
INTERVAL="$DEFAULT_INTERVAL"
SIZE="$DEFAULT_SIZE"
PING_GATEWAY=false
PREVENT_SLEEP=true
QUIET_MODE=false
DAEMON_MODE=false

# ANSI colors
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
BLUE=$'\033[0;34m'
MAGENTA=$'\033[0;35m'
CYAN=$'\033[0;36m'
WHITE=$'\033[1;37m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
RESET=$'\033[0m'

# Get default gateway IP
get_gateway_ip() {
    route -n get default 2>/dev/null | grep 'gateway:' | awk '{print $2}' || echo "10.0.0.1"
}

# Print usage information
usage() {
    cat << EOF
Usage: $(basename "$0") [COMMAND] [OPTIONS]

Commands:
  (no command)       Run in interactive dashboard mode
  start              Start keep-pinging in the background (daemon)
  stop               Stop background keep-pinging daemon
  status             Check status of background daemon
  logs               Follow background daemon log output

Options:
  -t, --target <ip>      Destination IP or hostname (default: $DEFAULT_TARGET)
  -i, --interval <sec>   Interval between pings in seconds (default: $DEFAULT_INTERVAL)
  -s, --size <bytes>     ICMP payload size in bytes (default: $DEFAULT_SIZE)
  -g, --gateway          Also ping local default gateway to keep AP link hot
  -q, --quiet            Quiet mode, log minimal output without dashboard
  -n, --no-sleep-lock    Do not engage macOS caffeinate to keep network awake
  -h, --help             Show this help message

Examples:
  ./keep_pinging.sh                     # Interactive mode (pings $DEFAULT_TARGET every 1.5s)
  ./keep_pinging.sh -i 1.0 -g           # Ping every 1.0s including gateway
  ./keep_pinging.sh start               # Run silently in background
  ./keep_pinging.sh stop                # Stop background pinging
EOF
    exit 0
}

# Check if daemon is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Command: stop
cmd_stop() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE")
        echo -e "${YELLOW}Stopping keep-pinging daemon (PID: $pid)...${RESET}"
        kill "$pid" 2>/dev/null
        # Wait up to 3 seconds for graceful shutdown
        for _ in {1..30}; do
            if ! ps -p "$pid" >/dev/null 2>&1; then
                break
            fi
            sleep 0.1
        done
        # Force kill if still running
        if ps -p "$pid" >/dev/null 2>&1; then
            kill -9 "$pid" 2>/dev/null
        fi
        rm -f "$PID_FILE"
        echo -e "${GREEN}Keep-pinging stopped successfully.${RESET}"
    else
        echo -e "${DIM}Keep-pinging is not currently running.${RESET}"
        rm -f "$PID_FILE" 2>/dev/null
    fi
    exit 0
}

# Command: status
cmd_status() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE")
        echo -e "${GREEN}${BOLD}● ACTIVE${RESET} - Keep-pinging is running (PID: ${CYAN}$pid${RESET})"
        if [ -f "$LOG_FILE" ]; then
            echo -e "${DIM}Recent activity from $LOG_FILE:${RESET}"
            echo -e "${DIM}----------------------------------------${RESET}"
            tail -n 8 "$LOG_FILE"
            echo -e "${DIM}----------------------------------------${RESET}"
        fi
    else
        echo -e "${RED}${BOLD}○ INACTIVE${RESET} - Keep-pinging is not running."
        if [ -f "$LOG_FILE" ]; then
            echo -e "${DIM}Last log file exists at $LOG_FILE${RESET}"
        fi
    fi
    exit 0
}

# Command: logs
cmd_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        touch "$LOG_FILE"
    fi
    echo -e "${CYAN}Following $LOG_FILE (Press Ctrl+C to exit)...${RESET}"
    tail -f "$LOG_FILE"
    exit 0
}

# Command: start (daemon)
cmd_start() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE")
        echo -e "${YELLOW}Keep-pinging is already running with PID: $pid${RESET}"
        exit 0
    fi

    echo -e "${CYAN}Starting keep-pinging in the background...${RESET}"
    echo -e "  Target:   ${BOLD}$TARGET${RESET}"
    echo -e "  Interval: ${BOLD}${INTERVAL}s${RESET}"
    echo -e "  Payload:  ${BOLD}${SIZE} bytes${RESET}"
    echo -e "  Log file: ${BOLD}$LOG_FILE${RESET}"

    # Re-invoke script in daemon mode and detach
    nohup "$0" --daemon -t "$TARGET" -i "$INTERVAL" -s "$SIZE" $([ "$PING_GATEWAY" = true ] && echo "-g") $([ "$PREVENT_SLEEP" = false ] && echo "-n") > "$LOG_FILE" 2>&1 &
    local new_pid=$!
    echo "$new_pid" > "$PID_FILE"

    sleep 1
    if ps -p "$new_pid" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Keep-pinging daemon started successfully (PID: $new_pid).${RESET}"
        echo -e "${DIM}To view live logs: $0 logs${RESET}"
        echo -e "${DIM}To stop daemon:   $0 stop${RESET}"
    else
        echo -e "${RED}✗ Failed to start keep-pinging daemon. Check $LOG_FILE for details.${RESET}"
        rm -f "$PID_FILE"
        exit 1
    fi
    exit 0
}

# Parse options
POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        start)
            COMMAND="start"
            shift
            ;;
        stop)
            COMMAND="stop"
            shift
            ;;
        status)
            COMMAND="status"
            shift
            ;;
        logs)
            COMMAND="logs"
            shift
            ;;
        -t|--target)
            TARGET="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -s|--size)
            SIZE="$2"
            shift 2
            ;;
        -g|--gateway)
            PING_GATEWAY=true
            shift
            ;;
        -q|--quiet)
            QUIET_MODE=true
            shift
            ;;
        --daemon)
            DAEMON_MODE=true
            QUIET_MODE=true
            shift
            ;;
        -n|--no-sleep-lock)
            PREVENT_SLEEP=false
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Route commands if matched
case "$COMMAND" in
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    logs)   cmd_logs ;;
esac

# Prevent Mac from sleeping network while pinging is active
CAFF_PID=""
if [ "$PREVENT_SLEEP" = true ] && command -v caffeinate >/dev/null 2>&1; then
    caffeinate -i -s &
    CAFF_PID=$!
fi

# Cleanup on exit
cleanup() {
    if [ -n "$CAFF_PID" ] && ps -p "$CAFF_PID" >/dev/null 2>&1; then
        kill "$CAFF_PID" 2>/dev/null
    fi
    if [ "$DAEMON_MODE" = true ]; then
        rm -f "$PID_FILE" 2>/dev/null
    fi
    if [ "$QUIET_MODE" = false ]; then
        echo -e "\n\n${YELLOW}Keep-pinging stopped.${RESET}"
        if [ "$TOTAL_SENT" -gt 0 ]; then
            local loss_pct=0
            if [ "$TOTAL_SENT" -gt 0 ]; then
                loss_pct=$(( (TOTAL_LOST * 100) / TOTAL_SENT ))
            fi
            echo -e "${BOLD}Summary:${RESET} Sent: $TOTAL_SENT | Received: $TOTAL_RECV | Lost: $TOTAL_LOST (${loss_pct}%) | Bandwidth: ~${TOTAL_BYTES} bytes"
        fi
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Statistics counters
TOTAL_SENT=0
TOTAL_RECV=0
TOTAL_LOST=0
TOTAL_BYTES=0
LAST_LATENCY="--"
MIN_LATENCY=999999
MAX_LATENCY=0
SUM_LATENCY=0
GATEWAY_IP=$(get_gateway_ip)

# Main worker loop
run_worker() {
    local start_time
    start_time=$(date +%s)
    local toggle=0

    if [ "$DAEMON_MODE" = true ]; then
        echo "$$" > "$PID_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Keep-pinging started (PID: $$) - Target: $TARGET, Interval: ${INTERVAL}s, Size: ${SIZE}b"
    fi

    while true; do
        local current_dest="$TARGET"
        if [ "$PING_GATEWAY" = true ]; then
            if [ $((toggle % 2)) -eq 1 ]; then
                current_dest="$GATEWAY_IP"
            fi
            toggle=$((toggle + 1))
        fi

        # Send single probe (macOS ping format)
        local ping_out
        ping_out=$(ping -c 1 -W 1000 -s "$SIZE" "$current_dest" 2>/dev/null)
        local ping_rc=$?

        TOTAL_SENT=$((TOTAL_SENT + 1))
        TOTAL_BYTES=$((TOTAL_BYTES + SIZE + 28)) # ICMP + IP header overhead approx 28 bytes

        local latency=""
        if [ $ping_rc -eq 0 ]; then
            # Extract latency: "time=18.423 ms"
            latency=$(echo "$ping_out" | grep -o 'time=[0-9.]*' | cut -d'=' -f2)
            if [ -n "$latency" ]; then
                LAST_LATENCY="${latency} ms"
                TOTAL_RECV=$((TOTAL_RECV + 1))
                
                # Integer arithmetic for min/max
                local lat_int
                lat_int=$(echo "$latency" | cut -d'.' -f1)
                if [ -n "$lat_int" ]; then
                    if [ "$lat_int" -lt "$MIN_LATENCY" ]; then MIN_LATENCY="$lat_int"; fi
                    if [ "$lat_int" -gt "$MAX_LATENCY" ]; then MAX_LATENCY="$lat_int"; fi
                    SUM_LATENCY=$((SUM_LATENCY + lat_int))
                fi
            else
                LAST_LATENCY="<1 ms"
                TOTAL_RECV=$((TOTAL_RECV + 1))
            fi
        else
            TOTAL_LOST=$((TOTAL_LOST + 1))
            LAST_LATENCY="TIMEOUT"
        fi

        # Rendering
        if [ "$QUIET_MODE" = true ]; then
            local ts
            ts=$(date '+%Y-%m-%d %H:%M:%S')
            if [ $ping_rc -eq 0 ]; then
                echo "[$ts] Probe to $current_dest: OK ($LAST_LATENCY)"
            else
                echo "[$ts] Probe to $current_dest: TIMEOUT"
            fi
        else
            # Interactive visual dashboard
            local now
            now=$(date +%s)
            local uptime=$((now - start_time))
            local uptime_formatted
            uptime_formatted=$(printf "%02d:%02d:%02d" $((uptime/3600)) $(( (uptime%3600)/60 )) $((uptime%60)))

            local avg_lat="--"
            if [ "$TOTAL_RECV" -gt 0 ]; then
                avg_lat="$((SUM_LATENCY / TOTAL_RECV)) ms"
            fi

            local loss_pct=0
            if [ "$TOTAL_SENT" -gt 0 ]; then
                loss_pct=$(( (TOTAL_LOST * 100) / TOTAL_SENT ))
            fi

            # Format total data sent nicely
            local data_str
            if [ "$TOTAL_BYTES" -gt 1048576 ]; then
                data_str="$(awk "BEGIN {printf \"%.2f MB\", $TOTAL_BYTES/1048576}")"
            elif [ "$TOTAL_BYTES" -gt 1024 ]; then
                data_str="$(awk "BEGIN {printf \"%.2f KB\", $TOTAL_BYTES/1024}")"
            else
                data_str="${TOTAL_BYTES} B"
            fi

            # Heartbeat pulse icon
            local pulse_icon="●"
            local status_color="$GREEN"
            if [ $ping_rc -ne 0 ]; then
                pulse_icon="▲"
                status_color="$RED"
            fi

            clear
            cat << EOF
${CYAN}${BOLD}======================================================${RESET}
${CYAN}${BOLD}           KEEP-PINGING: WI-FI KEEP-ALIVE             ${RESET}
${CYAN}${BOLD}======================================================${RESET}
 ${status_color}${BOLD}[$pulse_icon] STATUS:${RESET} Radio active & prevent-sleep engaged
 ${BOLD}Target WAN:${RESET}   $TARGET
 ${BOLD}Gateway LAN:${RESET}  $GATEWAY_IP $([ "$PING_GATEWAY" = true ] && echo "${GREEN}(Dual-probed)${RESET}" || echo "${DIM}(Idle)${RESET}")
 ${BOLD}Probe Interval:${RESET} ${INTERVAL}s  |  ${BOLD}Payload Size:${RESET} ${SIZE} bytes
------------------------------------------------------
 ${BOLD}Uptime:${RESET}       $uptime_formatted
 ${BOLD}Packets:${RESET}      Sent: ${CYAN}$TOTAL_SENT${RESET}  |  Recv: ${GREEN}$TOTAL_RECV${RESET}  |  Lost: ${RED}$TOTAL_LOST ($loss_pct%)${RESET}
 ${BOLD}Bandwidth:${RESET}    $data_str ${DIM}(Near-zero airtime footprint)${RESET}
------------------------------------------------------
 ${BOLD}Last Latency:${RESET} $status_color$LAST_LATENCY${RESET}
 ${BOLD}Avg / Max:${RESET}    $avg_lat / ${MAX_LATENCY} ms
======================================================
${DIM}Press [Ctrl+C] to stop | Keeps PHY modulation & NAT hot${RESET}
EOF
        fi

        sleep "$INTERVAL"
    done
}

run_worker
