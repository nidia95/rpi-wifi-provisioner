# WiFiPortal-RPi

![Python 3](https://img.shields.io/badge/python-3-blue.svg)
![OS](https://img.shields.io/badge/os-Raspberry_Pi_OS-crimson.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

A lightweight Wi-Fi provisioning server for Raspberry Pi devices.

## About

Configuring a Raspberry Pi's network credentials in headless environments — no display, no keyboard — is a frustrating and repetitive task.

**WiFiPortal-RPi** solves this with an automated provisioning flow. When the Pi boots with no active internet connection, it automatically switches into Access Point mode and launches a lightweight Python server. A client machine connects to that hotspot and transmits the target Wi-Fi credentials. The Pi then tears down the AP, saves the new configuration, and connects to the internet.

> **Before deploying:** read [`SECURITY.md`](SECURITY.md) to understand the security tradeoffs. The provisioning hotspot relies on a Wi-Fi password and a generated token, but credentials are transmitted unencrypted, so use it only on devices and networks you fully control.


## How It Works

1. **Check:** On boot, the system checks for an active internet connection.
2. **Portal Mode:** If offline, the Pi broadcasts its own Wi-Fi hotspot and hosts a provisioning server.
3. **Provision:** The client connects to the hotspot and sends the target Wi-Fi credentials (plus a shared provisioning token) to the Pi.
4. **Connect:** The Pi shuts down the hotspot, saves the new configuration, and connects to the local Wi-Fi network.

## Repository Structure

```text
├── client/
│   ├── client.py             # Sends target Wi-Fi credentials to the Pi.
│   ├── finder.py              # Discovers the Pi's IP address on the local network.
│   ├── utils.py                # Shared helpers (network/MAC lookups).
│   ├── requirements.txt        # Client-side Python dependencies.
│   ├── requirements-dev.txt    # + lint/test tooling.
│   ├── .env.example             # Optional environment variable template.
│   └── tests/                    # Unit tests.
├── server/
│   ├── install.sh              # Installs and configures everything on the Pi.
│   ├── uninstall.sh             # Removes the installation cleanly.
│   ├── systemd/
│   │   └── wifi-portal.service   # Systemd unit: runs check_network.sh on boot.
│   └── src/
│       ├── ap_mode_config.sh      # Creates the Access Point (one-time, run by installer).
│       ├── check_network.sh        # Checks connectivity; launches server.py if offline.
│       └── server.py                # Receives Wi-Fi credentials and connects the Pi to the internet.
├── SECURITY.md
└── CONTRIBUTING.md
```

## System Requirements

**Raspberry Pi (server)**
- Raspberry Pi OS (any recent release)
- Python 3
- NetworkManager (`nmcli`)

**Client machine**
- Python 3
- `nmap` for network discovery (`sudo apt install nmap` on Debian/Ubuntu)

## Setup

### Part 1 — Raspberry Pi

**1. Flash and connect**

Flash your SD card using the Raspberry Pi Imager. Before first boot, enable SSH either via Imager's settings or by placing an empty file named `ssh` in the boot partition. Connect the Pi to your local network initially via Ethernet or home Wi-Fi so the installer can fetch dependencies.

**2. Find the Pi's IP address**

From your local machine, use `finder.py` to locate the Pi on the network (or, if you want to use the hostname you set during Raspberry Pi OS setup, use `<hostname>.local` instead of the Pi’s IP address and skip this step).

```bash
cd client
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python3 finder.py # python -m finder [-h] [--range]
```

**3. Copy the server folder to the Pi**

Only the `server/` folder needs to be transferred—the client runs entirely on your local machine. **Make sure you are in the project root directory for this step**:


```bash
scp -r server/* <pi-user>@<PI_IP>:~/wifi-portal
```

**4. Run the installer**

SSH into the Pi, make the installer executable, and run it:

```bash
ssh <pi-user>@<PI_IP>

cd ~/wifi-portal

chmod +x install.sh
sudo ./install.sh
```

The installer will:
- Copy server files to `/opt/wifi-portal/`
- Install required system packages
- Prompt for a hotspot password (or generate a strong random one)
- Generate a random provisioning token and print it once — **save it**
- Create the AP connection profile via `ap_mode_config.sh`
- Register and enable the `wifi-portal` systemd service

**5. Connect to the access point**

After rebooting without a known network available, the Pi will broadcast a hotspot:

- **SSID:** `RaspberryPi-XXXXXX` (last 6 digits of the Wi-Fi MAC address)
- **Password:** whatever you set (or was generated) during install

---

### Part 2 — Client Machine

**6. Send credentials to the Pi**

Connect your machine to the Pi's hotspot, then run:

```bash
python3 client.py --token <the token printed by install.sh>
```

You'll be prompted for the target SSID and password interactively (they
are never stored in source or shell history this way). Credentials can
also be supplied via `--ssid`/`--password` flags or the `WIFI_PORTAL_*`
environment variables — see `.env.example`.

The Pi will receive the credentials, tear down the hotspot, and connect to the target network. From this point on, whenever the Pi loses its connection, it will rebroadcast the hotspot on the next boot and wait for new credentials.

## Useful Commands

```bash
# Live service logs
journalctl -u wifi-portal.service -f

# Service status
systemctl status wifi-portal.service

# Restart the service
sudo systemctl restart wifi-portal.service

# Stop the service
sudo systemctl stop wifi-portal.service

# Disable auto-start on boot
sudo systemctl disable wifi-portal.service
```

## Uninstalling

SSH into the Pi and run:

```bash
cd ~/wifi-portal
sudo ./uninstall.sh
```

This stops and disables the service, removes the systemd unit, and optionally deletes the installed files (including the provisioning token) from `/opt/wifi-portal/`.

## Troubleshooting

**Line endings (Windows editors)**
If you edited scripts on Windows, hidden carriage return characters can cause execution failures. Fix with:

```bash
sudo apt install -y dos2unix
dos2unix ./*.sh
```

**AP not appearing after reboot**
Confirm NetworkManager is running and the profile was created:

```bash
systemctl status NetworkManager
nmcli connection show
```

**Permission errors**
All server-side scripts require root. Always use `sudo ./install.sh`.

## Roadmap & Known Limitations

This project is currently a working proof-of-concept. The following improvements are planned:
- **UDP Retry Logic:** the client sends credentials in a single UDP burst. If the packet drops, the Pi remains in AP mode. Client-side retry with a server-side ack is the top priority.
- **Transport encryption:** the credential exchange is currently authenticated (via token) but not encrypted; see `SECURITY.md`.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Authors

- **Nadia Davari**
  - GitHub: [nidia95](https://github.com/nidia95)
  - LinkedIn: [Nadia Davari](https://www.linkedin.com/in/nadia-davari)
  - Website: [nadiadavari.ir](https://nadiadavari.ir)
  - Email: nadiadavari.dev@gmail.com

## License

Distributed under the MIT License. See `LICENSE` for more information.
