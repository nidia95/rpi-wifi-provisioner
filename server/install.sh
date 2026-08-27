#!/usr/bin/env bash
set -euo pipefail

#
# install.sh
# ----------------------------------------------------
#
# Installs and configures the wifi-portal system.
#
# Notes:
#   - Must be run as root (sudo)
#   - Intended for Raspberry Pi / Linux systems using NetworkManager
#   - AP profile is persistent and auto-managed by NetworkManager
#
# ----------------------------------------------------

# ---------------------------
# Configuration Constants
# ---------------------------

PROJECT_NAME="wifi-portal"
INSTALL_DIR="/opt/${PROJECT_NAME}"
SERVICE_NAME="${PROJECT_NAME}.service"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Must match uninstall.sh configuration
HOTSPOT_NAME="wifi-portal-ap"

# ------------------------------------------------------------------
# Pre-flight validation
# ------------------------------------------------------------------

if [[ "${EUID}" -ne 0 ]]; then
	echo "Please run this installer with sudo: sudo ./install.sh" >&2
	exit 1
fi

# ------------------------------------------------------------------
# Install system dependencies
# ------------------------------------------------------------------

echo "==> Installing dependencies"

apt-get update
apt-get install -y network-manager openssl

# ------------------------------------------------------------------
# Hotspot password
# ------------------------------------------------------------------
#
# A weak, guessable default (e.g. "raspberry") is a real risk once this
# device is on a public network. Generate a strong random password by
# default, but let the operator override it.
#

DEFAULT_HOTSPOT_PASSWORD="$(openssl rand -base64 12 2>/dev/null || head -c 12 /dev/urandom | base64)"

read -rsp "Hotspot password [press Enter to use a generated one]: " HOTSPOT_PASSWORD_INPUT
echo
HOTSPOT_PASSWORD="${HOTSPOT_PASSWORD_INPUT:-${DEFAULT_HOTSPOT_PASSWORD}}"

if [[ "${#HOTSPOT_PASSWORD}" -lt 8 ]]; then
	echo "Hotspot password must be at least 8 characters." >&2
	exit 1
fi

# ------------------------------------------------------------------
# Install application files
# ------------------------------------------------------------------

echo "==> Installing ${PROJECT_NAME} to ${INSTALL_DIR}"

mkdir -p "${INSTALL_DIR}"
cp -r "${SOURCE_DIR}/src/." "${INSTALL_DIR}/"

# Inject install path into runtime scripts
sed -i "s|__INSTALL_DIR__|${INSTALL_DIR}|g" "${INSTALL_DIR}/check_network.sh"

chmod +x "${INSTALL_DIR}"/*.sh

# ------------------------------------------------------------------
# Provisioning token
# ------------------------------------------------------------------
#
# Without a shared secret, any device that can reach the hotspot can
# send arbitrary Wi-Fi credentials to this Pi. Generate a random token
# that client.py must also be given (--token / $WIFI_PORTAL_TOKEN).
#

PROVISION_TOKEN="$(openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | xxd -p)"
echo -n "${PROVISION_TOKEN}" >"${INSTALL_DIR}/provision.token"
chmod 600 "${INSTALL_DIR}/provision.token"

echo "Provisioning token generated and saved to ${INSTALL_DIR}/provision.token"
echo "Keep this token secret! It is required to provision the device from a client."

# ------------------------------------------------------------------
# Configure Access Point (one-time setup)
# ------------------------------------------------------------------

echo "==> Configuring Access Point"

sed -i "s|__HOTSPOT_NAME__|${HOTSPOT_NAME}|g" "${INSTALL_DIR}/ap_mode_config.sh"
sed -i "s|__HOTSPOT_PASSWORD__|${HOTSPOT_PASSWORD}|g" "${INSTALL_DIR}/ap_mode_config.sh"
chmod 700 "${INSTALL_DIR}/ap_mode_config.sh"

"${INSTALL_DIR}/ap_mode_config.sh"

# ------------------------------------------------------------------
# Install systemd service
# ------------------------------------------------------------------

echo "==> Installing systemd unit"

cp "${SOURCE_DIR}/systemd/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
sed -i "s|__INSTALL_DIR__|${INSTALL_DIR}|g" "/etc/systemd/system/${SERVICE_NAME}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

# ------------------------------------------------------------------
# Completion summary
# ------------------------------------------------------------------

echo
echo "Service setup complete."
echo
echo "IMPORTANT — save these values, you'll need them on the client:"
echo "---------------------------"
echo "Hotspot password:     ${HOTSPOT_PASSWORD}"
echo "Provisioning token:   ${PROVISION_TOKEN}"
echo "---------------------------"
echo
echo "On the client machine, run:"
echo "  python3 client.py --token ${PROVISION_TOKEN}"
echo
echo "Useful commands:"
echo "---------------------------"
echo "View logs:"
echo "  journalctl -u ${SERVICE_NAME} -f"
echo
echo "Restart service:"
echo "  sudo systemctl restart ${SERVICE_NAME}"
echo
echo "Stop service:"
echo "  sudo systemctl stop ${SERVICE_NAME}"
echo
echo "Disable auto-start:"
echo "  sudo systemctl disable ${SERVICE_NAME}"
echo "---------------------------"
echo

# ------------------------------------------------------------------
# Optional: Activate Access Point now
# ------------------------------------------------------------------
#
# The AP profile is created but not explicitly activated here.
# NetworkManager will automatically activate it on boot if no known
# network is available.
#
# Activating it now may interrupt the current Wi-Fi connection,
# since the wireless interface switches into AP mode immediately.
#

read -rp "Activate the access point now? This may disconnect your current Wi-Fi session. [y/N] " do_connection_up
if [[ "${do_connection_up}" =~ ^[Yy]$ ]]; then
	echo "Activating access point..."
	nmcli connection up "${HOTSPOT_NAME}"
	systemctl restart "${SERVICE_NAME}"
else
	echo "Skipping activation. It will activate automatically on next boot if needed."
fi

exit 0
