"""Send target Wi-Fi credentials to a Raspberry Pi running WiFiPortal-RPi.

Credentials are never hardcoded in source. Provide them via CLI flags,
environment variables, or (recommended) the interactive password prompt:

    python3 client.py --ssid "MyHomeWiFi"

Environment variables (useful for scripting/CI, not recommended for
day-to-day interactive use since they can leak into shell history/logs):
    WIFI_PORTAL_SSID
    WIFI_PORTAL_PASSWORD
    WIFI_PORTAL_TOKEN     required — the token printed by install.sh
                            when it provisioned this Pi
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import platform
import re
import socket
import subprocess

log = logging.getLogger(__name__)

BUFFER_SIZE = 1024
SERVER_PORT = 2222
RECEIVE_TIMEOUT_SECONDS = 15

# Must match MAX_FIELD_LENGTH in server/src/server.py. Kept in sync manually
# since the two sides don't share a module; if you change one, change both.
MAX_FIELD_LENGTH = 128

_GATEWAY_DETECTION_ERRORS = (
    subprocess.CalledProcessError,
    FileNotFoundError,
    OSError,
    IndexError,
)


def get_gateway_ip() -> str | None:
    """Best-effort detection of the current default gateway.

    When connected to the Pi's provisioning hotspot, the Pi is almost
    always the gateway, so this is used as the default target IP.
    """
    system = platform.system()

    try:
        if system == "Windows":
            return _get_gateway_windows()
        if system == "Darwin":
            return _get_gateway_macos()
        return _get_gateway_linux()

    except _GATEWAY_DETECTION_ERRORS as error:
        log.debug("Gateway detection failed: %s", error)
        return None


def _get_gateway_linux() -> str | None:
    """Parse `ip route show default` for the current default gateway."""
    output = subprocess.check_output(
        ["ip", "route", "show", "default"], text=True, timeout=5
    )
    match = re.search(r"default via (\d{1,3}(?:\.\d{1,3}){3})", output)
    return match.group(1) if match else None


def _get_gateway_macos() -> str | None:
    """Parse `route -n get default` for the current default gateway."""
    output = subprocess.check_output(
        ["route", "-n", "get", "default"], text=True, timeout=5
    )
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("gateway:"):
            return line.split(":", 1)[1].strip() or None
    return None


def _get_gateway_windows() -> str | None:
    """Parse `ipconfig` for the Wi-Fi adapter's Default Gateway."""
    output = subprocess.check_output(["ipconfig"], text=True, timeout=5)
    for block in output.split("Wireless LAN adapter Wi-Fi:")[1:]:
        for line in block.splitlines():
            if "Default Gateway" in line and ":" in line:
                ip = line.split(":", 1)[1].strip()
                if ip:
                    return ip
    return None


def send_credentials(
    ssid: str,
    password: str,
    host: str,
    token: str,
    port: int = SERVER_PORT,
    timeout: float = RECEIVE_TIMEOUT_SECONDS,
) -> None:
    """Send Wi-Fi credentials to the Raspberry Pi provisioning server.

    Args:
        ssid: Target network SSID.
        password: Target network password.
        host: IP address of the Raspberry Pi (its hotspot gateway IP).
        token: Shared provisioning token.
        port: UDP port the server listens on.
        timeout: Seconds to wait for a response before assuming the Pi
            has started reconnecting (which drops this connection).
    """
    payload = f"{token}|{ssid}|{password}"

    log.info("Sending credentials to %s:%s ...", host, port)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(payload.encode("utf-8"), (host, port))

        try:
            data, _ = sock.recvfrom(BUFFER_SIZE)
            log.info("Response from Pi: %s", data.decode("utf-8"))

        except TimeoutError:
            log.info(
                "No response within %ss (this usually means the Pi accepted "
                "the credentials and is now reconnecting).\n"
                "  1. Reconnect this machine to your normal Wi-Fi network.\n"
                "  2. Give the Pi a minute to come back online.\n"
                "  3. Run finder.py to locate its new IP address.\n"
                "If the Pi's hotspot is still visible after a few minutes, "
                "the credentials were likely wrong — reboot the Pi and retry.",
                timeout,
            )


def _validate_field(name: str, value: str) -> None:
    """Fail fast, client-side, on inputs the server would silently drop.

    The server (server/src/server.py) rejects any SSID/password longer
    than MAX_FIELD_LENGTH with no reply, which otherwise just looks like
    a dropped packet to the client until the timeout fires.
    """
    if len(value) > MAX_FIELD_LENGTH:
        raise SystemExit(
            f"{name} is too long ({len(value)} chars, max {MAX_FIELD_LENGTH})."
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ssid",
        default=os.environ.get("WIFI_PORTAL_SSID"),
        help="Target Wi-Fi SSID (default: $WIFI_PORTAL_SSID, or prompt)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("WIFI_PORTAL_PASSWORD"),
        help="Target Wi-Fi password (default: $WIFI_PORTAL_PASSWORD, or "
        "prompt — prefer the prompt to avoid leaking secrets in shell "
        "history/process lists)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Raspberry Pi IP address (default: auto-detect default gateway)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("WIFI_PORTAL_TOKEN"),
        help="Provisioning token, if the server has authentication enabled",
    )
    parser.add_argument("--port", type=int, default=SERVER_PORT)
    parser.add_argument("--timeout", type=float, default=RECEIVE_TIMEOUT_SECONDS)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    ssid = args.ssid or input("Target Wi-Fi SSID: ").strip()
    if not ssid:
        raise SystemExit("SSID cannot be empty.")

    password = args.password or getpass.getpass("Target Wi-Fi password: ")
    if not password:
        raise SystemExit("Password cannot be empty.")

    _validate_field("SSID", ssid)
    _validate_field("Password", password)

    host = args.host or get_gateway_ip()
    if not host:
        raise SystemExit(
            "Could not auto-detect the Raspberry Pi's IP address. "
            "Connect to its hotspot and try again, or pass --host explicitly."
        )

    send_credentials(
        ssid=ssid,
        password=password,
        host=host,
        token=args.token,
        port=args.port,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
    except Exception as error:
        log.error("%s", error)
        raise SystemExit(1) from error
