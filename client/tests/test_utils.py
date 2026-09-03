import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils import is_rasp


def test_is_rasp_rejects_malformed_mac():
    assert is_rasp("not-a-mac") is False


def test_is_rasp_rejects_non_rasp_vendor():
    # Apple OUI — should not be identified as a Raspberry Pi.
    assert is_rasp("AC:DE:48:00:11:22") is False
