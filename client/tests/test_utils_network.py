import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import utils

# ---------------------------------------------------------------------------
# resolve_scan_range
# ---------------------------------------------------------------------------


def test_resolve_scan_range_normalizes_host_bits():
    assert utils.resolve_scan_range("192.168.1.42/24") == "192.168.1.0/24"


def test_resolve_scan_range_returns_none_for_invalid_input():
    assert utils.resolve_scan_range("not-a-network") is None


def test_resolve_scan_range_returns_none_for_empty_input():
    assert utils.resolve_scan_range("") is None


# ---------------------------------------------------------------------------
# _to_network_range
# ---------------------------------------------------------------------------


def test_to_network_range_valid():
    assert utils._to_network_range("10.0.0.5/24") == "10.0.0.0/24"


def test_to_network_range_invalid_returns_none():
    assert utils._to_network_range("not-an-ip") is None


# ---------------------------------------------------------------------------
# _netmask_to_prefix
# ---------------------------------------------------------------------------


def test_netmask_to_prefix_common_masks():
    assert utils._netmask_to_prefix("255.255.255.0") == 24
    assert utils._netmask_to_prefix("255.255.0.0") == 16
    assert utils._netmask_to_prefix("255.0.0.0") == 8


# ---------------------------------------------------------------------------
# get_network_ip_range dispatch
# ---------------------------------------------------------------------------


def test_get_network_ip_range_dispatches_linux(monkeypatch):
    monkeypatch.setattr(utils.platform, "system", lambda: "Linux")
    with patch.object(
        utils, "_get_network_ip_range_linux", return_value="192.168.1.0/24"
    ) as mock_fn:
        assert utils.get_network_ip_range() == "192.168.1.0/24"
    mock_fn.assert_called_once()


def test_get_network_ip_range_dispatches_windows(monkeypatch):
    monkeypatch.setattr(utils.platform, "system", lambda: "Windows")
    with patch.object(
        utils, "_get_network_ip_range_windows", return_value="10.0.0.0/24"
    ) as mock_fn:
        assert utils.get_network_ip_range() == "10.0.0.0/24"
    mock_fn.assert_called_once()


def test_get_network_ip_range_unsupported_os_returns_none(monkeypatch):
    monkeypatch.setattr(utils.platform, "system", lambda: "Darwin")
    assert utils.get_network_ip_range() is None


# ---------------------------------------------------------------------------
# _get_network_ip_range_linux
# ---------------------------------------------------------------------------


def test_get_network_ip_range_linux_success():
    route_output = "default via 192.168.1.1 dev wlan0 proto dhcp metric 600\n"
    addr_output = (
        "3: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n"
        "    inet 192.168.1.42/24 brd 192.168.1.255 scope global wlan0\n"
    )

    def fake_check_output(cmd, **kwargs):
        if cmd[:2] == ["ip", "route"]:
            return route_output
        return addr_output

    with patch.object(utils.subprocess, "check_output", side_effect=fake_check_output):
        assert utils._get_network_ip_range_linux() == "192.168.1.0/24"


def test_get_network_ip_range_linux_no_default_route_returns_none():
    with patch.object(
        utils.subprocess, "check_output", return_value="no default here\n"
    ):
        assert utils._get_network_ip_range_linux() is None


def test_get_network_ip_range_linux_route_command_failure_returns_none():
    with patch.object(
        utils.subprocess, "check_output", side_effect=FileNotFoundError("ip not found")
    ):
        assert utils._get_network_ip_range_linux() is None


# ---------------------------------------------------------------------------
# _get_network_ip_range_windows
# ---------------------------------------------------------------------------


def test_get_network_ip_range_windows_success():
    output = (
        "Wireless LAN adapter Wi-Fi:\n"
        "\n"
        "   Connection-specific DNS Suffix  . :\n"
        "   IPv4 Address. . . . . . . . . . . : 192.168.0.42\n"
        "   Subnet Mask . . . . . . . . . . . : 255.255.255.0\n"
        "\n"
        "Ethernet adapter Ethernet:\n"
        "   IPv4 Address. . . . . . . . . . . : 10.0.0.5\n"
    )
    with patch.object(utils.subprocess, "check_output", return_value=output):
        assert utils._get_network_ip_range_windows() == "192.168.0.0/24"


def test_get_network_ip_range_windows_no_wifi_section_returns_none():
    output = (
        "Ethernet adapter Ethernet:\n   IPv4 Address. . . . . . . . . . . : 10.0.0.5\n"
    )
    with patch.object(utils.subprocess, "check_output", return_value=output):
        assert utils._get_network_ip_range_windows() is None


def test_get_network_ip_range_windows_command_failure_returns_none():
    with patch.object(
        utils.subprocess,
        "check_output",
        side_effect=FileNotFoundError("ipconfig missing"),
    ):
        assert utils._get_network_ip_range_windows() is None


# ---------------------------------------------------------------------------
# is_manuf_available
# ---------------------------------------------------------------------------


def test_is_manuf_available_reflects_import_state(monkeypatch):
    monkeypatch.setattr(utils, "manuf", object())
    assert utils.is_manuf_available() is True

    monkeypatch.setattr(utils, "manuf", None)
    assert utils.is_manuf_available() is False
