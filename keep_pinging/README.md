# Keep-Pinging (Wi-Fi Radio Keep-Alive)

A lightweight background network keep-alive utility designed to prevent Wi-Fi power-saving sleep, maintain peak Wi-Fi PHY modulation rates, and stop connection stalls while streaming or browsing.

---

## Why This Works

When streaming video (e.g. TikTok, YouTube), media players download video in bursts (chunks) and then go completely idle for several seconds. During these idle gaps:
1. **Wi-Fi Power-Save Sleep:** Both your device and the router enter 802.11 Power Save / WMM sleep mode to save micro-watts of power.
2. **Link Rate Drop:** The router down-negotiates the PHY modulation scheme (MCS index) to save airtime.
3. **Connection Stall:** When the app requests the next chunk, buggy DTIM/beacon wake-up handshakes can cause the connection to hesitate or hang.

By sending a tiny (32-byte) ICMP probe every 1–2 seconds, **the Wi-Fi radio never enters idle sleep**, the router keeps its beamforming and link rate pegged at maximum, and upstream NAT routing tables stay warm.

---

## Bandwidth & Resource Footprint

| Metric | Measurement |
| :--- | :--- |
| **Payload Size** | 32 bytes (60 bytes total over the wire with IP/ICMP headers) |
| **Airtime Rate** | ~40–60 bytes / second (~0.0004 Mbps) |
| **Data Usage** | ~3.6 KB / minute (~5 MB over a full 24-hour day) |
| **CPU / Battery** | Uses macOS native ICMP socket; < 0.1% CPU |

---

## Usage

### 1. Interactive HUD Mode (Live Dashboard)
Run in the foreground to monitor latency, packet loss, uptime, and bandwidth in real time:
```bash
./keep_pinging/keep_pinging.sh
```

To probe both your **Local Wi-Fi Gateway** (`10.0.0.1`) and **External WAN** (`8.8.8.8`) alternately:
```bash
./keep_pinging/keep_pinging.sh -g
```

### 2. Background Daemon Mode (Fire-and-Forget)
Start in the background so it runs silently while you work or browse:
```bash
./keep_pinging/keep_pinging.sh start
```

Check status and recent latency:
```bash
./keep_pinging/keep_pinging.sh status
```

Stream live logs:
```bash
./keep_pinging/keep_pinging.sh logs
```

Stop the daemon:
```bash
./keep_pinging/keep_pinging.sh stop
```

---

## Custom Options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `-t, --target <IP>` | Target IP or domain to ping | `8.8.8.8` |
| `-i, --interval <sec>` | Seconds between pings | `1.5` |
| `-s, --size <bytes>` | ICMP payload size in bytes | `32` |
| `-g, --gateway` | Probes both local gateway and external target | Off |
| `-q, --quiet` | Run without interactive dashboard | Off |
| `-n, --no-sleep-lock` | Disable macOS `caffeinate` lock | Off |

---

## Using on Mobile Phones (TikTok Setup)

If you are watching TikTok on your phone:

### Option A: Route Phone Through Mac SOCKS Proxy (Recommended)
Since you already have `quiet_socks_proxy.sh` running on this Mac:
1. Connect your phone's Wi-Fi proxy setting to your Mac's IP (Port `8084`).
2. Run `./keep_pinging/keep_pinging.sh start` on this Mac.
3. Because the Mac's Wi-Fi link remains active at full modulation, all routed phone traffic avoids gateway sleep stalls.

### Option B: On Android (Termux)
Install **Termux** from F-Droid or Play Store and run:
```bash
ping -i 1.5 -s 32 8.8.8.8
```
*(Termux will keep running in your notification shade with virtually zero battery consumption).*

### Option C: On iOS (iPhone)
1. Install a free background ping app like **HE.NET Network Tools** or **Ping** by Network Analyzer.
2. Set target to `8.8.8.8`, interval to `1.5s`, and start continuous ping in the background.
