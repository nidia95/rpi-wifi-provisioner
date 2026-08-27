"""Custom exceptions for missing dependencies, so we can provide user-friendly error messages."""


class ScanDependencyError(RuntimeError):
    """Raised when a required external tool or package is unavailable."""


class ManufUnavailableError(ScanDependencyError):
    """Raised when Raspberry Pi vendor lookup support is unavailable."""

    @classmethod
    def not_installed(cls) -> "ManufUnavailableError":
        return cls(
            "The 'manuf' package is not installed; run: pip install -r requirements.txt"
        )


class NmapUnavailableError(ScanDependencyError):
    """Raised when nmap is not installed or not on PATH, or fails to run."""

    @classmethod
    def not_installed(cls) -> "NmapUnavailableError":
        return cls(
            "nmap is not installed or not on PATH. "
            "Install it using your OS package manager."
        )

    @classmethod
    def timed_out(cls, timeout_seconds: float) -> "NmapUnavailableError":
        return cls(f"nmap scan timed out after {timeout_seconds}s")

    @classmethod
    def command_failed(cls, stderr: str) -> "NmapUnavailableError":
        return cls(f"nmap scan failed: {stderr.strip()}")


class ArpUnavailableError(ScanDependencyError):
    """Raised when arp is not installed, not on PATH, or fails to run."""

    @classmethod
    def not_installed(cls) -> "ArpUnavailableError":
        return cls(
            "arp is not installed or not on PATH. "
            "Install it using your OS package manager."
        )

    @classmethod
    def timed_out(cls, timeout_seconds: float) -> "ArpUnavailableError":
        return cls(f"arp command timed out after {timeout_seconds}s")

    @classmethod
    def command_failed(cls, stderr: str) -> "ArpUnavailableError":
        return cls(f"arp command failed: {stderr.strip()}")
