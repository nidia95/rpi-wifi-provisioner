"""Discover Raspberry Pi devices on the local network by MAC OUI.

Usage:
    python -m finder [--range 192.168.1.0/24]
"""

from __future__ import annotations

import argparse
import logging
import platform
import re
import shutil
import subprocess
import time

from exceptions import (
    ArpUnavailableError,
    ManufUnavailableError,
    NmapUnavailableError,
    ScanDependencyError,
)
from utils import (
    get_network_ip_range,
    is_manuf_available,
    is_rasp,
    resolve_scan_range,
)

log = logging.getLogger(__name__)

NMAP_TIMEOUT_SECONDS = 60
ARP_TIMEOUT_SECONDS = 30
DEFAULT_SCAN_DELAY_SECONDS = 2

_NMAP_IP_PATTERN = re.compile(r"Nmap scan report.*?(\d{1,3}(?:\.\d{1,3}){3})")
_IP_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_MAC_PATTERN = re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")


def find_raspberry_pi_ips(resolved_range: str | None = None) -> dict[str, str]:
    """Scan the local network for Raspberry Pi devices.

    Args:
        resolved_range: CIDR range to scan, e.g. "192.168.1.0/24". Auto-detected
            from the current network if not provided.

    Returns:
        A mapping of MAC address -> IP address for every Raspberry Pi found.
        Empty if none were found or the scan could not run.

    Raises:
        ManufUnavailableError: if the vendor-lookup package isn't installed.
        NmapUnavailableError: if nmap isn't installed or not on PATH.
        ArpUnavailableError: on Linux, if arp isn't installed or not on PATH.
    """
    if not is_manuf_available():
        raise ManufUnavailableError.not_installed()

    log.info("Scanning range: %s (this may take a while...)", resolved_range)
    time.sleep(DEFAULT_SCAN_DELAY_SECONDS)

    if not shutil.which("nmap"):
        raise NmapUnavailableError.not_installed()

    try:
        result = subprocess.run(
            ["nmap", "-sn", resolved_range],
            capture_output=True,
            text=True,
            timeout=NMAP_TIMEOUT_SECONDS,
            check=True,
        )
        nmap_output: str = result.stdout

        os_name = platform.system()
        if os_name == "Linux":
            return _find_via_arp(nmap_output)

        # Windows and macOS: nmap reports MACs directly
        log.info("Using nmap for scanning on %s", os_name)
        return _parse_nmap_output(nmap_output)

    except subprocess.TimeoutExpired as error:
        log.error("nmap scan timed out after %ss", NMAP_TIMEOUT_SECONDS)
        raise NmapUnavailableError.timed_out(NMAP_TIMEOUT_SECONDS) from error

    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", "") or str(error)
        log.error("nmap scan failed: %s", stderr.strip())
        raise NmapUnavailableError.command_failed(stderr) from error


def _parse_nmap_output(output: str) -> dict[str, str]:
    """Parse nmap output to extract Raspberry Pi MACs and their corresponding IPs."""
    rasp_ips: dict[str, str] = {}
    current_ip: str | None = None

    for line in output.splitlines():
        ip_match = _NMAP_IP_PATTERN.search(line)
        if ip_match:
            current_ip = ip_match.group(1)
            continue

        mac_match = _MAC_PATTERN.search(line)
        if mac_match and current_ip:
            mac = mac_match.group().upper().replace("-", ":")
            if is_rasp(mac):
                rasp_ips[mac] = current_ip

            ip_match = None
            mac_match = None

    return rasp_ips


def _find_via_arp(nmap_output: str) -> dict[str, str]:
    """Use nmap's live-host IPs to filter the Linux ARP cache down to
    entries this scan actually confirmed, avoiding stale cache entries
    for IPs no longer in use by the device that once held them.

    Raises:
        ArpUnavailableError: if arp isn't installed or not on PATH."""
    live_ips = set(_NMAP_IP_PATTERN.findall(nmap_output))
    if not live_ips:
        return {}

    if not shutil.which("arp"):
        raise ArpUnavailableError.not_installed()

    return _read_arp_table(live_ips)


def _read_arp_table(live_ips: set[str]) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["arp", "-n"],
            capture_output=True,
            text=True,
            timeout=ARP_TIMEOUT_SECONDS,
            check=True,
        )
        return _parse_arp_output(live_ips, result.stdout)
    except subprocess.TimeoutExpired as error:
        log.error("arp command timed out after %ss", ARP_TIMEOUT_SECONDS)
        raise ArpUnavailableError.timed_out(ARP_TIMEOUT_SECONDS) from error
    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", "") or str(error)
        log.error("arp command failed: %s", stderr.strip())
        raise ArpUnavailableError.command_failed(stderr) from error


def _parse_arp_output(live_ips: set[str], output: str) -> dict[str, str]:
    rasp_ips: dict[str, str] = {}

    for line in output.splitlines():
        ip_match = _IP_PATTERN.search(line)
        mac_match = _MAC_PATTERN.search(line)

        if not ip_match or not mac_match:
            continue

        ip = ip_match.group()
        mac = mac_match.group().upper().replace("-", ":")

        if ip in live_ips and is_rasp(mac):
            rasp_ips[mac] = ip

    return rasp_ips


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the finder CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--range",
        dest="ip_range",
        default=None,
        help="CIDR range to scan (default: auto-detect from current network)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    return parser.parse_args()


def main() -> None:
    """Run the finder CLI and report discovered Raspberry Pis."""
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    log.info("Finding Raspberry Pis...")

    candidate_range = args.ip_range or get_network_ip_range()
    if not candidate_range:
        log.error(
            "Could not determine an IP range to scan. "
            "Make sure you're connected to a network, or pass --range explicitly."
        )
        return

    resolved_range = resolve_scan_range(candidate_range)

    if resolved_range is None:
        return

    try:
        found = find_raspberry_pi_ips(resolved_range=resolved_range)
        if not found:
            log.info(
                "No Raspberry Pi found on the network. "
                "Check that it's powered on and its hotspot is active."
            )
            return

        log.info("Found %d Raspberry Pi(s):", len(found))
        for mac, ip in found.items():
            log.info(" - %s  (MAC: %s)", ip, mac)
    except ScanDependencyError as error:
        log.error("%s", error)
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
    except Exception as error:
        log.error("%s", error)
        raise SystemExit(1) from error
