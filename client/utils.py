"""Shared helper functions for the WiFiPortal-RPi client.

This module is intentionally free of side effects on import (no prints,
no network/process calls at import time) so it can be safely imported
and unit tested.
"""

from __future__ import annotations

import re
import logging
import platform
import ipaddress
import subprocess


try:
    import manuf

except ImportError:  # pragma: no cover - defensive, requirements.txt covers this
    manuf = None

log = logging.getLogger(__name__)

# Loaded lazily and cached so we don't re-parse the OUI database on every call.
_mac_parser: manuf.MacParser | None = None


def is_manuf_available() -> bool:
    """Return whether MAC vendor lookups are available."""
    return manuf is not None


def get_network_ip_range() -> str | None:
    """Determine the CIDR range of the current network's default interface.

    Returns:
        A CIDR string such as "192.168.1.0/24", or None if it could not
        be determined.
    """
    os_name = platform.system().lower()

    if os_name == "linux":
        return _get_network_ip_range_linux()
    if os_name == "windows":
        return _get_network_ip_range_windows()

    log.error("Unsupported operating system: %s", os_name)
    return None


def _to_network_range(ip_with_prefix: str) -> str | None:
    """Given a host address like '192.168.1.116/24', return the network's
    address range in CIDR form, e.g. '192.168.1.0/24' -- suitable for
    passing to nmap or any other range-based scan.
    """
    try:
        interface = ipaddress.ip_interface(ip_with_prefix)

    except ValueError as error:
        log.error("Invalid IP/prefix '%s': %s", ip_with_prefix, error)
        return None

    return str(interface.network)


def _get_network_ip_range_linux() -> str | None:
    try:
        route_output = subprocess.check_output(
            ["ip", "route", "show"], text=True, timeout=5
        )

    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as error:
        log.error("Failed to read routing table: %s", error)
        return None

    for line in route_output.splitlines():
        if "default via " not in line:
            continue

        interface_name = line.split("dev ")[-1].split(" ")[0]

        try:
            addr_output = subprocess.check_output(
                ["ip", "addr", "show", interface_name], text=True, timeout=5
            )

        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as error:
            log.error("Failed to read interface %s: %s", interface_name, error)
            return None

        for addr_line in addr_output.splitlines():
            if "inet " not in addr_line:
                continue

            ip_with_prefix = addr_line.split()[1]  # "192.168.1.42/24"
            ip_address, _, prefix = ip_with_prefix.partition("/")

            if not ip_address or not prefix:
                return None

            return _to_network_range(ip_with_prefix)

    log.warning("No default route found; are you connected to a network?")
    return None


def _netmask_to_prefix(mask: str) -> int:
    return sum(bin(int(octet)).count("1") for octet in mask.split("."))


def _get_network_ip_range_windows() -> str | None:
    try:
        raw = subprocess.check_output(
            ["ipconfig"], stderr=subprocess.STDOUT, text=True, timeout=5
        )

    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as error:
        log.error("Failed to run ipconfig: %s", error)
        return None

    # Walk line-by-line and collect only the lines that belong to the
    # Wi-Fi adapter's block. Detail lines are always indented; a new
    # adapter header is always flush-left. Blank lines can appear
    # anywhere inside the block (including right after the header), so
    # they can't be used as the boundary -- indentation can.
    wifi_lines: list[str] = []
    in_wifi_section = False

    for line in raw.splitlines():
        if line.startswith("Wireless LAN adapter Wi-Fi"):
            in_wifi_section = True
            continue

        if not in_wifi_section:
            continue

        if line.strip() == "":
            # Blank line inside (or bordering) the section -- keep going,
            # don't treat this as the end of the block.
            continue

        if not line[0].isspace():
            # Flush-left line reached -> this is the next adapter's
            # header, so the Wi-Fi block is over.
            break

        wifi_lines.append(line)

    if not wifi_lines:
        log.error("Could not find a Wi-Fi adapter section in ipconfig output.")
        return None

    wifi_section = "\n".join(wifi_lines)

    ip_match = re.search(r"IPv4 Address[.\s]+: ([0-9.]+)", wifi_section)
    subnet_match = re.search(r"Subnet Mask[.\s]+: ([0-9.]+)", wifi_section)

    if not ip_match or not subnet_match:
        log.error("Could not find IPv4 address/subnet mask in Wi-Fi adapter section.")
        return None

    ip_address = ip_match.group(1)
    subnet_mask = subnet_match.group(1)

    try:
        prefix = _netmask_to_prefix(subnet_mask)

    except ValueError as error:
        log.error("Could not parse subnet mask '%s': %s", subnet_mask, error)
        return None

    ip_with_prefix = f"{ip_address}/{prefix}"

    return _to_network_range(ip_with_prefix)


def is_rasp(mac_address: str) -> bool:
    """Check whether a MAC address belongs to a Raspberry Pi Foundation NIC.

    Args:
        mac_address: MAC address in standard notation, e.g. "B8:27:EB:12:34:56".

    Returns:
        True if the OUI vendor lookup identifies a Raspberry Pi device.
    """
    global _mac_parser

    if manuf is None:
        log.error(
            "The 'manuf' package is not installed; run: pip install -r requirements.txt"
        )
        return False

    try:
        if _mac_parser is None:
            _mac_parser = manuf.MacParser()

        vendor = _mac_parser.get_manuf(mac_address)
        return vendor is not None and "raspberr" in vendor.lower()

    except Exception:
        log.exception("Failed to look up vendor for MAC %s", mac_address)
        return False


def resolve_scan_range(ip_range: str) -> str | None:
    """Return a canonical CIDR range, or ``None`` when no range is available."""
    if not ip_range:
        log.error("No IP range provided and could not auto-detect one.")

    try:
        return str(ipaddress.ip_network(ip_range, strict=False))
    except ValueError:
        log.error("Invalid IP range: %s", ip_range)


if __name__ == "__main__":
    print("This module is a library and is not meant to be run directly.")
