import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import finder
from exceptions import ArpUnavailableError, ManufUnavailableError, NmapUnavailableError

RASP_MAC = "B8:27:EB:12:34:56"
OTHER_MAC = "AC:DE:48:00:11:22"


def _is_rasp_for(mac_addresses):
    """Build a fake is_rasp() that only returns True for given MACs."""

    def fake_is_rasp(mac):
        return mac.upper() in mac_addresses

    return fake_is_rasp


# ---------------------------------------------------------------------------
# _parse_nmap_output
# ---------------------------------------------------------------------------


def test_parse_nmap_output_extracts_matching_devices():
    output = (
        "Nmap scan report for 192.168.1.10\n"
        f"MAC Address: {RASP_MAC} (Raspberry Pi Foundation)\n"
        "Nmap scan report for 192.168.1.11\n"
        f"MAC Address: {OTHER_MAC} (Apple)\n"
    )
    with patch.object(finder, "is_rasp", side_effect=_is_rasp_for({RASP_MAC})):
        result = finder._parse_nmap_output(output)

    assert result == {RASP_MAC: "192.168.1.10"}


def test_parse_nmap_output_no_matches_returns_empty_dict():
    output = "Nmap scan report for 192.168.1.10\nHost is up.\n"
    with patch.object(finder, "is_rasp", return_value=False):
        assert finder._parse_nmap_output(output) == {}


# ---------------------------------------------------------------------------
# _find_via_arp / _read_arp_table / _parse_arp_output
# ---------------------------------------------------------------------------


def test_parse_arp_output_filters_by_live_ips_and_vendor():
    live_ips = {"192.168.1.10", "192.168.1.11"}
    arp_output = (
        f"192.168.1.10 ether {RASP_MAC} C eth0\n"
        f"192.168.1.11 ether {OTHER_MAC} C eth0\n"
        f"192.168.1.99 ether {RASP_MAC} C eth0\n"  # not in live_ips
    )
    with patch.object(finder, "is_rasp", side_effect=_is_rasp_for({RASP_MAC})):
        result = finder._parse_arp_output(live_ips, arp_output)

    assert result == {RASP_MAC: "192.168.1.10"}


def test_find_via_arp_returns_empty_when_no_live_ips():
    assert finder._find_via_arp("no ip addresses here") == {}


def test_find_via_arp_raises_when_arp_missing():
    nmap_output = "Nmap scan report for 192.168.1.10\n"
    with patch.object(finder.shutil, "which", return_value=None):
        try:
            finder._find_via_arp(nmap_output)
            assert False, "expected ArpUnavailableError"
        except ArpUnavailableError:
            pass


def test_read_arp_table_timeout_raises():
    with patch.object(
        finder.subprocess,
        "run",
        side_effect=subprocess.TimeoutExpired(cmd="arp", timeout=30),
    ):
        try:
            finder._read_arp_table({"192.168.1.10"})
            assert False, "expected ArpUnavailableError"
        except ArpUnavailableError:
            pass


# ---------------------------------------------------------------------------
# find_raspberry_pi_ips
# ---------------------------------------------------------------------------


def test_find_raspberry_pi_ips_raises_when_manuf_unavailable():
    with patch.object(finder, "is_manuf_available", return_value=False):
        try:
            finder.find_raspberry_pi_ips("192.168.1.0/24")
            assert False, "expected ManufUnavailableError"
        except ManufUnavailableError:
            pass


def test_find_raspberry_pi_ips_raises_when_nmap_missing(monkeypatch):
    monkeypatch.setattr(finder, "is_manuf_available", lambda: True)
    monkeypatch.setattr(finder.time, "sleep", lambda *_: None)
    with patch.object(finder.shutil, "which", return_value=None):
        try:
            finder.find_raspberry_pi_ips("192.168.1.0/24")
            assert False, "expected NmapUnavailableError"
        except NmapUnavailableError:
            pass


def test_find_raspberry_pi_ips_raises_on_nmap_timeout(monkeypatch):
    monkeypatch.setattr(finder, "is_manuf_available", lambda: True)
    monkeypatch.setattr(finder.time, "sleep", lambda *_: None)
    with patch.object(finder.shutil, "which", return_value="/usr/bin/nmap"):
        with patch.object(
            finder.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="nmap", timeout=60),
        ):
            try:
                finder.find_raspberry_pi_ips("192.168.1.0/24")
                assert False, "expected NmapUnavailableError"
            except NmapUnavailableError:
                pass
