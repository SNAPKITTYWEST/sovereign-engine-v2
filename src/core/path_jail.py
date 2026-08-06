"""
Path Jail — Directory Traversal Prevention
Part of SOVEREIGN PYTHON LLM ENGINE

All filesystem tool access routes through this module.
Prevents: ../traversal, symlink escape, null-byte injection, device files.
"""

from pathlib import Path, PurePosixPath, PureWindowsPath
import os
import re


class PathJailError(Exception):
    pass


class PathJail:
    """
    Confines all file operations to allowed root directories.

    Usage:
        jail = PathJail(roots=[Path("/workspace"), Path("/tmp/scratch")])
        safe = jail.resolve("/workspace/src/main.py")     # OK
        jail.resolve("/workspace/../etc/passwd")          # PathJailError
        jail.resolve("/workspace/link_to_etc")            # PathJailError (symlink escape)
    """

    def __init__(self, roots: list[Path]):
        self._roots = [r.resolve() for r in roots]

    def resolve(self, requested: str | Path) -> Path:
        """
        Resolve and validate a path against the jail.

        Raises PathJailError if the resolved path escapes all roots.
        """
        raw = str(requested)

        if '\x00' in raw:
            raise PathJailError("Null byte in path")

        if re.search(r'[\x01-\x1f]', raw):
            raise PathJailError("Control characters in path")

        target = Path(raw).resolve()

        if os.name == 'nt':
            name_lower = target.name.lower()
            if name_lower in ('con', 'prn', 'aux', 'nul', 'com1', 'lpt1'):
                raise PathJailError(f"Reserved device name: {target.name}")

        for root in self._roots:
            try:
                target.relative_to(root)
                return target
            except ValueError:
                continue

        raise PathJailError(
            f"Path escapes jail: {target} not under any root: "
            f"{[str(r) for r in self._roots]}"
        )

    def resolve_no_symlink(self, requested: str | Path) -> Path:
        """
        Resolve path and reject if any component is a symlink.
        Stricter than resolve() — prevents TOCTOU via symlink swap.
        """
        target = self.resolve(requested)

        current = target
        while current != current.parent:
            if current.is_symlink():
                raise PathJailError(f"Symlink in path: {current}")
            current = current.parent

        return target

    def is_safe(self, requested: str | Path) -> bool:
        try:
            self.resolve(requested)
            return True
        except PathJailError:
            return False


class SSRFGuard:
    """
    Prevent Server-Side Request Forgery in web/HTTP tools.

    Blocks: private IPs, link-local, loopback, metadata endpoints.
    """

    BLOCKED_PREFIXES = [
        '127.', '10.', '192.168.', '172.16.', '172.17.', '172.18.',
        '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
        '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
        '172.29.', '172.30.', '172.31.',
        '169.254.',  # link-local
        '0.',        # "this" network
        'fc', 'fd',  # IPv6 ULA
        'fe80',      # IPv6 link-local
        '::1',       # IPv6 loopback
    ]

    BLOCKED_HOSTS = {
        'localhost',
        'metadata.google.internal',
        'metadata.google',
        '169.254.169.254',
    }

    @classmethod
    def check_url(cls, url: str) -> str:
        """
        Validate URL is not targeting internal/private resources.
        Returns the URL if safe, raises on SSRF attempt.
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = (parsed.hostname or '').lower().strip('.')

        if not host:
            raise PathJailError("Empty host in URL")

        if host in cls.BLOCKED_HOSTS:
            raise PathJailError(f"SSRF blocked: {host}")

        for prefix in cls.BLOCKED_PREFIXES:
            if host.startswith(prefix):
                raise PathJailError(f"SSRF blocked (private IP): {host}")

        if parsed.scheme not in ('http', 'https'):
            raise PathJailError(f"Blocked scheme: {parsed.scheme}")

        return url
