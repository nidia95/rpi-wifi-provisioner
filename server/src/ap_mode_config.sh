#!/usr/bin/env bash
set -euo pipefail

#
# ap_mode_config.sh
# ----------------------------------------------------
#
# Configures a persistent Wi-Fi Access Point using NetworkManager.
#
# Overview:
#   This script creates a permanent AP connection profile that is
#   managed by NetworkManager. It is intended as a one-time setup
#   step during installation (run by install.sh as root).
#
#   Once created, the profile is automatically managed by NetworkManager
#   and will:
#     - Persist across reboots
#     - Auto-start when no known Wi-Fi networks are available
#     - Not require this script to run again unless reconfiguration is needed
#
# Requirements:
#   - Must run as root
#   - Requires NetworkManager (nmcli)
#
# ----------------------------------------------------


# ---------------------------
# Constants & Utilities
# ---------------------------

readonly NMCLI_BIN="/usr/bin/nmcli"

HOTSPOT_NAME="__HOTSPOT_NAME__"
HOTSPOT_PASSWORD="__HOTSPOT_PASSWORD__"

log() { echo "[ap_mode_config] $*"; }

die() {
  echo "[ap_mode_config] ERROR: $*" >&2
  exit 1
}

# Verify that the script is running with the required privileges.
require_root() {
  [[ "${EUID}" -eq 0 ]] || die "this script must run as root."
}

# Verify that a required executable exists and is executable.
require_bin() {
  [[ -x "$1" ]] || die "required binary not found or not executable: $1"
}

# ---------------------------
# Pre-flight validation
# ---------------------------

log "Setting up Raspberry Pi Wi-Fi access point"

require_root
require_bin "${NMCLI_BIN}"


# ---------------------------
# Initializing Wi-Fi access point configuration
# ---------------------------

WIFI_IFACE=$("${NMCLI_BIN}" -t -f DEVICE,TYPE device status | awk -F: '$2=="wifi"{print $1; exit}')

[[ -n "${WIFI_IFACE}" ]] || die "no Wi-Fi interface detected on this device."

log "Detected Wi-Fi interface: ${WIFI_IFACE}"

MAC="$(cat "/sys/class/net/${WIFI_IFACE}/address")"
MAC_NO_COLONS="${MAC//:/}"
UNIQUE_ID="${MAC_NO_COLONS: -6}"
SSID="RaspberryPi-${UNIQUE_ID}"

log "Generated SSID: ${SSID}"

log "Creating persistent AP profile: ${HOTSPOT_NAME}"

if "${NMCLI_BIN}" -t -f NAME connection show | grep -qx "${HOTSPOT_NAME}"; then
  log "Access point '${HOTSPOT_NAME}' already configured (SSID would be '${SSID}'), nothing to do."
  exit 0
fi

# ---------------------------
# Creating persistent AP profile
# ---------------------------

"${NMCLI_BIN}" con add \
  con-name "${HOTSPOT_NAME}" \
  type wifi \
  ifname "${WIFI_IFACE}" \
  ssid "${SSID}" \
  autoconnect yes

# ---------------------------
# Configuring AP security
# ---------------------------

log "Configuring AP security settings (WPA2-PSK)"

"${NMCLI_BIN}" connection modify "${HOTSPOT_NAME}" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  ipv4.method shared \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "${HOTSPOT_PASSWORD}"

log "Access point ready: SSID=${SSID}"
