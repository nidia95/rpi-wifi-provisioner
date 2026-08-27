#!/usr/bin/env bash
set -euo pipefail

#
# uninstall.sh
# ----------------------------------------------------
#
# Removes wifi-portal installation from the system.
#
# What it does:
#   1. Stops and disables systemd service
#   2. Removes systemd unit file
#   3. Optionally removes installed application files (including the
#      provisioning token)
#   4. Optionally removes NetworkManager hotspot profile
#
# Safety:
#   - Destructive operations require confirmation
#   - Must be run as root
#


# ---------------------------
# Configuration Constants & Utilities
# ---------------------------

PROJECT_NAME="wifi-portal"
INSTALL_DIR="/opt/${PROJECT_NAME}"
SERVICE_NAME="${PROJECT_NAME}.service"

# Must match install.sh configuration
HOTSPOT_NAME="wifi-portal-ap"

confirm() {
  read -rp "$1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

# ---------------------------
# Pre-flight validation
# ---------------------------

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run this with sudo: sudo ./uninstall.sh" >&2
  exit 1
fi

# ------------------------------------------------------------------
# Stop and remove service
# ------------------------------------------------------------------

systemctl disable --now "${SERVICE_NAME}" 2> /dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}"
systemctl daemon-reload

# ------------------------------------------------------------------
# Remove installation files (optional)
# ------------------------------------------------------------------

if confirm "Remove installed files at ${INSTALL_DIR} (including the provisioning token)?"; then
  rm -rf "${INSTALL_DIR}"
fi

# ------------------------------------------------------------------
# Remove NetworkManager hotspot profile (optional)
# ------------------------------------------------------------------

if confirm "Remove hotspot profile ${HOTSPOT_NAME}? This may disconnect your current connection."; then
  nmcli connection delete "$HOTSPOT_NAME" 2> /dev/null || true
fi

echo "==> Uninstallation complete."
