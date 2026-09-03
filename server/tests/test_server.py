import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import server  # noqa: E402


# ---------------------------------------------------------------------------
# parse_message
# ---------------------------------------------------------------------------


def test_parse_message_valid():
    assert server.parse_message(b"tok123|MyWiFi|hunter2") == (
        "tok123",
        "MyWiFi",
        "hunter2",
    )


def test_parse_message_rejects_wrong_field_count():
    assert server.parse_message(b"only|two") is None
    assert server.parse_message(b"no-separators-at-all") is None


def test_parse_message_password_may_contain_separator_char():
    # maxsplit=2 means anything after the second "|" belongs to password.
    assert server.parse_message(b"tok|ssid|pass|with|pipes") == (
        "tok",
        "ssid",
        "pass|with|pipes",
    )


def test_parse_message_rejects_empty_token_or_ssid_or_password():
    assert server.parse_message(b"|ssid|pass") is None
    assert server.parse_message(b"|ssid| ") is None
    assert server.parse_message(b"||pass") is None
    assert server.parse_message(b"| |pass") is None
    assert server.parse_message(b"tok|ssid|") is None
    assert server.parse_message(b"tok|ssid| ") is None
    assert server.parse_message(b"tok||pass") is None
    assert server.parse_message(b"tok|| ") is None
    assert server.parse_message(b"tok||") is None


def test_parse_message_rejects_oversized_fields():
    long_ssid = "a" * (server.MAX_FIELD_LENGTH + 1)
    assert server.parse_message(f"tok|{long_ssid}|pw".encode()) is None

    long_password = "b" * (server.MAX_FIELD_LENGTH + 1)
    assert server.parse_message(f"tok|ssid|{long_password}".encode()) is None


def test_parse_message_rejects_invalid_utf8():
    assert server.parse_message(b"\xff\xfe\x00") is None


# ---------------------------------------------------------------------------
# load_expected_token
# ---------------------------------------------------------------------------


def test_load_expected_token_reads_file(tmp_path, monkeypatch):
    token_file = tmp_path / "provision.token"
    token_file.write_text("  secret-token  \n", encoding="utf-8")
    monkeypatch.setattr(server, "TOKEN_FILE", token_file)

    assert server.load_expected_token() == "secret-token"


def test_load_expected_token_missing_file_warns(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(server, "TOKEN_FILE", tmp_path / "does-not-exist.token")

    with caplog.at_level("WARNING"):
        assert server.load_expected_token() is None

    assert "No provisioning token configured" in caplog.text


# ---------------------------------------------------------------------------
# rescan_wifi
# ---------------------------------------------------------------------------


def test_rescan_wifi_success():
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch.object(server.subprocess, "run", return_value=completed) as mock_run:
        assert server.rescan_wifi() is True

    args, kwargs = mock_run.call_args
    assert args[0] == [server.NMCLI_BIN, "device", "wifi", "rescan"]
    assert kwargs["timeout"] == server.NMCLI_RESCAN_TIMEOUT_SECONDS


def test_rescan_wifi_nonzero_exit_returns_false(caplog):
    completed = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="not authorized"
    )
    with caplog.at_level("WARNING"):
        with patch.object(server.subprocess, "run", return_value=completed):
            assert server.rescan_wifi() is False

    assert "nmcli rescan failed" in caplog.text


def test_rescan_wifi_timeout_returns_false(caplog):
    with caplog.at_level("WARNING"):
        with patch.object(
            server.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="nmcli", timeout=15),
        ):
            assert server.rescan_wifi() is False

    assert "nmcli rescan could not run" in caplog.text


def test_rescan_wifi_missing_binary_returns_false():
    with patch.object(server.subprocess, "run", side_effect=FileNotFoundError()):
        assert server.rescan_wifi() is False


# ---------------------------------------------------------------------------
# list_wifi_networks
# ---------------------------------------------------------------------------


def test_list_wifi_networks_parses_ssids():
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="HomeNet\nCafeWiFi\n\n", stderr=""
    )
    with patch.object(server.subprocess, "run", return_value=completed) as mock_run:
        assert server.list_wifi_networks() == ["HomeNet", "CafeWiFi"]

    args, kwargs = mock_run.call_args
    assert args[0] == [server.NMCLI_BIN, "-t", "-f", "SSID", "device", "wifi", "list"]
    assert kwargs["timeout"] == server.NMCLI_LIST_TIMEOUT_SECONDS


def test_list_wifi_networks_failure_returns_empty_list(caplog):
    completed = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="boom"
    )
    with caplog.at_level("WARNING"):
        with patch.object(server.subprocess, "run", return_value=completed):
            assert server.list_wifi_networks() == []

    assert "nmcli list failed" in caplog.text


def test_list_wifi_networks_timeout_returns_empty_list():
    with patch.object(
        server.subprocess,
        "run",
        side_effect=subprocess.TimeoutExpired(cmd="nmcli", timeout=10),
    ):
        assert server.list_wifi_networks() == []


# ---------------------------------------------------------------------------
# connect_to_network -- verifies the rescan -> list -> connect ordering
# ---------------------------------------------------------------------------


def test_connect_to_network_rescans_and_lists_before_connecting():
    call_order = []

    def fake_rescan_wifi():
        call_order.append("rescan")
        return True

    def fake_list_wifi_networks():
        call_order.append("list")
        return ["TargetNet"]

    connect_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="Connected", stderr=""
    )

    def fake_run(*args, **kwargs):
        call_order.append("connect")
        return connect_result

    with patch.object(
        server, "rescan_wifi", side_effect=fake_rescan_wifi
    ), patch.object(
        server, "list_wifi_networks", side_effect=fake_list_wifi_networks
    ), patch.object(
        server.subprocess, "run", side_effect=fake_run
    ) as mock_run:
        result = server.connect_to_network("TargetNet", "hunter2")

    assert call_order == ["rescan", "list", "connect"]
    assert result.returncode == 0

    args, _ = mock_run.call_args
    assert args[0] == [
        server.NMCLI_BIN,
        "device",
        "wifi",
        "connect",
        "TargetNet",
        "password",
        "hunter2",
    ]


def test_connect_to_network_warns_when_ssid_not_visible(caplog):
    connect_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )

    with caplog.at_level("WARNING"):
        with patch.object(server, "rescan_wifi", return_value=True), patch.object(
            server, "list_wifi_networks", return_value=["SomeOtherNet"]
        ), patch.object(server.subprocess, "run", return_value=connect_result):
            server.connect_to_network("TargetNet", "hunter2")

    assert "was not seen in the latest scan" in caplog.text


def test_connect_to_network_still_attempts_connect_if_rescan_fails():
    connect_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )

    with patch.object(server, "rescan_wifi", return_value=False), patch.object(
        server, "list_wifi_networks", return_value=[]
    ), patch.object(server.subprocess, "run", return_value=connect_result) as mock_run:
        result = server.connect_to_network("TargetNet", "hunter2")

    mock_run.assert_called_once()
    assert result.returncode == 0


def test_connect_to_network_never_logs_the_password(caplog):
    connect_result = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="general error"
    )

    with caplog.at_level("DEBUG"):
        with patch.object(server, "rescan_wifi", return_value=False), patch.object(
            server, "list_wifi_networks", return_value=["TargetNet"]
        ), patch.object(server.subprocess, "run", return_value=connect_result):
            server.connect_to_network("TargetNet", "super-secret-password")

    assert "super-secret-password" not in caplog.text


# ---------------------------------------------------------------------------
# _reply
# ---------------------------------------------------------------------------


def test_reply_sends_encoded_message():
    sock = MagicMock()
    server._reply(sock, ("1.2.3.4", 5555), "hello")
    sock.sendto.assert_called_once_with(b"hello", ("1.2.3.4", 5555))


def test_reply_swallows_socket_errors():
    sock = MagicMock()
    sock.sendto.side_effect = OSError("network unreachable")
    # Should not raise.
    server._reply(sock, ("1.2.3.4", 5555), "hello")
