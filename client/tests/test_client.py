import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import client

# ---------------------------------------------------------------------------
# _validate_field
# ---------------------------------------------------------------------------


def test_validate_field_accepts_short_value():
    # Should not raise.
    client._validate_field("SSID", "a" * client.MAX_FIELD_LENGTH)


def test_validate_field_rejects_oversized_value():
    try:
        client._validate_field("SSID", "a" * (client.MAX_FIELD_LENGTH + 1))
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "SSID" in str(exc)


# ---------------------------------------------------------------------------
# get_gateway_ip dispatch
# ---------------------------------------------------------------------------


def test_get_gateway_ip_dispatches_to_linux(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Linux")
    with patch.object(client, "_get_gateway_linux", return_value="10.0.0.1") as mock_fn:
        assert client.get_gateway_ip() == "10.0.0.1"
    mock_fn.assert_called_once()


def test_get_gateway_ip_dispatches_to_macos(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Darwin")
    with patch.object(client, "_get_gateway_macos", return_value="10.0.0.2") as mock_fn:
        assert client.get_gateway_ip() == "10.0.0.2"
    mock_fn.assert_called_once()


def test_get_gateway_ip_dispatches_to_windows(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Windows")
    with patch.object(
        client, "_get_gateway_windows", return_value="10.0.0.3"
    ) as mock_fn:
        assert client.get_gateway_ip() == "10.0.0.3"
    mock_fn.assert_called_once()


def test_get_gateway_ip_swallows_errors(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Linux")
    with patch.object(
        client, "_get_gateway_linux", side_effect=subprocess.CalledProcessError(1, "ip")
    ):
        assert client.get_gateway_ip() is None


# ---------------------------------------------------------------------------
# _get_gateway_linux / _get_gateway_macos / _get_gateway_windows
# ---------------------------------------------------------------------------


def test_get_gateway_linux_parses_output():
    output = "default via 192.168.1.1 dev wlan0 proto dhcp metric 600\n"
    with patch.object(client.subprocess, "check_output", return_value=output):
        assert client._get_gateway_linux() == "192.168.1.1"


def test_get_gateway_linux_returns_none_when_no_match():
    with patch.object(
        client.subprocess, "check_output", return_value="no default route\n"
    ):
        assert client._get_gateway_linux() is None


def test_get_gateway_macos_parses_output():
    output = "   route to: default\ndestination: default\ngateway: 192.168.1.254\n"
    with patch.object(client.subprocess, "check_output", return_value=output):
        assert client._get_gateway_macos() == "192.168.1.254"


def test_get_gateway_macos_returns_none_without_gateway_line():
    with patch.object(
        client.subprocess, "check_output", return_value="destination: default\n"
    ):
        assert client._get_gateway_macos() is None


def test_get_gateway_windows_parses_output():
    output = (
        "Wireless LAN adapter Wi-Fi:\n"
        "\n"
        "   Default Gateway . . . . . . . . . : 192.168.0.1\n"
    )
    with patch.object(client.subprocess, "check_output", return_value=output):
        assert client._get_gateway_windows() == "192.168.0.1"


def test_get_gateway_windows_returns_none_without_wifi_section():
    output = "Ethernet adapter Ethernet:\n\n   Default Gateway . . . . . . . . . : 10.0.0.1\n"
    with patch.object(client.subprocess, "check_output", return_value=output):
        assert client._get_gateway_windows() is None


# ---------------------------------------------------------------------------
# send_credentials
# ---------------------------------------------------------------------------


def test_send_credentials_sends_payload_and_logs_response():
    fake_sock = MagicMock()
    fake_sock.recvfrom.return_value = (b"Connected successfully.", ("10.0.0.1", 2222))
    fake_sock.__enter__.return_value = fake_sock
    fake_sock.__exit__.return_value = False

    with patch.object(client.socket, "socket", return_value=fake_sock):
        client.send_credentials(
            ssid="MyWiFi", password="hunter2", host="10.0.0.1", token="tok"
        )

    fake_sock.sendto.assert_called_once_with(
        b"tok|MyWiFi|hunter2", ("10.0.0.1", client.SERVER_PORT)
    )


def test_send_credentials_handles_timeout_gracefully():
    fake_sock = MagicMock()
    fake_sock.recvfrom.side_effect = TimeoutError()
    fake_sock.__enter__.return_value = fake_sock
    fake_sock.__exit__.return_value = False

    with patch.object(client.socket, "socket", return_value=fake_sock):
        # Should not raise.
        client.send_credentials(
            token="tok", ssid="MyWiFi", password="hunter2", host="10.0.0.1"
        )

    fake_sock.sendto.assert_called_once()
