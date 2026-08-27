#!/usr/bin/env bash
set -euo pipefail

#
# check_network.sh
# ---------------------------------------------------
#
# Verifies network connectivity during system startup.
#
# Workflow:
#   1. Check the current network connectivity status.
#   2. If connectivity is available, exit successfully.
#   4. If connectivity is unavailable, launch the provisioning server
#      to allow the device to be configured by the client.
#
#
# (network configuration requires root privileges).
#
# ---------------------------------------------------

# ---------------------------
# Constants & Utilities
# ---------------------------

readonly NMCLI_BIN="/usr/bin/nmcli"
readonly PYTHON_BIN="/usr/bin/python3"

SERVER_FILE="__INSTALL_DIR__/server.py"

echo "Checking network connectivity..."

log() {
	echo "[check_network] $*"
}

die() {
	echo "[check_network] ERROR: $*" >&2
	exit 1
}

# Verify that the script is running with the required privileges.
require_root() {
	if [[ "${EUID}" -ne 0 ]]; then
		die "this script must run as root (it configures networking)."
	fi
}

# Verify that a required executable exists and is executable.
require_bin() {
	local bin_path="$1"
	[[ -x "${bin_path}" ]] || die "required binary not found or not executable: ${bin_path}"
}

# ---------------------------
# Pre-flight validation
# ---------------------------

log "Network bootstrap process started"

require_root
require_bin "${NMCLI_BIN}"
require_bin "${PYTHON_BIN}"

[[ -f "${SERVER_FILE}" ]] || die "server.py not found: ${SERVER_FILE}"

# ---------------------------
# Network connectivity check
# ---------------------------

log "Checking network connectivity..."

# Possible values:
#   full     - Internet connectivity is available.
#   limited  - Connected to a network but Internet access is restricted.
#   portal   - Captive portal detected.
#   none     - No network connection.
#   unknown  - Connectivity state could not be determined.
#
CONNECTIVITY="$("${NMCLI_BIN}" networking connectivity check || echo "unknown")"

log "Connectivity status: ${CONNECTIVITY}"
# Possible values: full | limited | portal | none | unknown

if [[ "${CONNECTIVITY}" == "full" ]]; then
	log "Network connectivity confirmed. No provisioning required."
	exit 0
fi

# ---------------------------
# Launch provisioning server
# ---------------------------

log "No confirmed connectivity, starting provisioning server..."

exec "${PYTHON_BIN}" "${SERVER_FILE}"
