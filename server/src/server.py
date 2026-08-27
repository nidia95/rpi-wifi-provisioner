"""Wi-Fi provisioning server.

Listens on a UDP port for "token|ssid|password" messages and, once a
valid message arrives, uses NetworkManager (nmcli) to join the target
network. Intended to run on the Raspberry Pi via check_network.sh /
the wifi-portal systemd service.

Security note: if a provisioning token file is present next to this
script (provision.token, created by install.sh), clients must supply a
matching token. Without it, ANY device that can reach this hotspot can
redirect the Pi's network connection. See SECURITY.md.
"""

from __future__ import annotations

import sys
import time
import socket
import logging
import subprocess

from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("wifi-portal-server")

BUFFER_SIZE = 1024
LISTEN_PORT = 2222
NMCLI_BIN = "/usr/bin/nmcli"

NMCLI_TIMEOUT_SECONDS = 30
MAX_FIELD_LENGTH = 128

TOKEN_FILE = Path(__file__).resolve().parent / "provision.token"


def load_expected_token() -> str | None:
    """Load the provisioning token from the local file, if present."""
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()

    log.warning(
        "No provisioning token configured (%s not found) — the server will "
        "accept credentials from ANY client that can reach this hotspot. "
        "Run install.sh to generate one.",
        TOKEN_FILE,
    )
    return None


def parse_message(raw: bytes) -> tuple[str, str, str] | None:
    """Parse a "token|ssid|password" UDP payload.

    Returns (token, ssid, password) or None if the payload is malformed.
    """
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None

    parts = text.split("|", maxsplit=2)
    if len(parts) != 3:
        return None

    token, ssid, password = parts

    if not ssid or not password:
        return None

    if len(ssid) > MAX_FIELD_LENGTH or len(password) > MAX_FIELD_LENGTH:
        return None

    return token, ssid, password


def connect_to_network(ssid: str, password: str) -> subprocess.CompletedProcess:
    """Use nmcli to connect to the given Wi-Fi network."""
    return subprocess.run(
        [NMCLI_BIN, "device", "wifi", "connect", ssid, "password", password],
        capture_output=True,
        text=True,
        check=False,
        timeout=NMCLI_TIMEOUT_SECONDS,
    )


def run() -> None:
    """Run the provisioning server, listening for UDP messages and connecting to Wi-Fi."""
    expected_token: str | None = load_expected_token()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as pi_socket:
        pi_socket.bind(("0.0.0.0", LISTEN_PORT))
        log.info("UDP provisioning server listening on port %s", LISTEN_PORT)

        while True:
            try:
                raw, address = pi_socket.recvfrom(BUFFER_SIZE)

            except OSError as error:
                log.error("Socket error while receiving: %s", error)
                continue

            parsed: tuple[str, str, str] | None = parse_message(raw)

            if parsed is None:
                log.warning("Ignoring malformed packet from %s", address[0])
                continue

            token, ssid, password = parsed

            log.info("Client %s requested connection to SSID '%s'", address[0], ssid)

            if expected_token is not None and token != expected_token:
                log.warning("Rejected packet from %s: invalid token", address[0])
                continue

            try:
                result = connect_to_network(ssid, password)

            except subprocess.TimeoutExpired:
                log.error("nmcli timed out connecting to '%s'", ssid)
                _reply(pi_socket, address, "Connection attempt timed out. Try again.")
                continue

            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Unexpected error while connecting to '%s'", ssid)
                _reply(pi_socket, address, "Unexpected server error. Try again.")
                continue

            if result.returncode == 0:
                log.info("Connected successfully: %s", result.stdout.strip())
                # NOTE The reply is not seen by the client if the Pi immediately drops
                #   the hotspot connection
                _reply(pi_socket, address, "Connected successfully.")
                time.sleep(4)
                log.info("Connected successfully... Shutting down provisioning server.")
                return

            log.error("nmcli failed: %s", result.stderr.strip())
            _reply(
                pi_socket,
                address,
                "Failed to connect. Check the SSID and password and try "
                "again. If this persists, reboot the Raspberry Pi.",
            )


def _reply(sock: socket.socket, address: tuple[str, int], message: str) -> None:
    try:
        sock.sendto(message.encode("utf-8"), address)

    except OSError as error:
        log.debug("Could not send reply to %s: %s", address[0], error)


if __name__ == "__main__":
    try:
        run()

    except KeyboardInterrupt:
        sys.exit(0)
