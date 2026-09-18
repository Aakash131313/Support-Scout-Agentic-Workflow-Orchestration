"""Public HTTP(S) URL policy with injectable DNS resolution.

This is the server-side request forgery defence. It resolves the hostname and rejects
any destination that lands on a private, loopback, link-local, multicast or reserved
address, which blocks localhost tricks and DNS rebinding. The scraper calls it twice:
once before the request and once on the final URL after redirects.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from ..exceptions import UnsafeURLError

_ALLOWED_SCHEMES = frozenset({"http", "https"})


class URLPolicy:
    """Validates that a URL points at a public internet destination."""

    def __init__(self, resolver=None) -> None:
        self.resolver = resolver or socket.getaddrinfo

    def validate(self, url: str) -> str:
        """Return the URL when safe; raise `UnsafeURLError` otherwise."""
        parsed = urlparse(url)

        if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.hostname:
            raise UnsafeURLError("Only public HTTP(S) URLs are allowed")

        if parsed.username or parsed.password:
            raise UnsafeURLError("Embedded credentials are forbidden")

        host = parsed.hostname.casefold()
        if host == "localhost" or host.endswith(".localhost"):
            raise UnsafeURLError("Local destinations are forbidden")

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            resolved = self.resolver(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeURLError("Hostname resolution failed") from exc

        addresses = {entry[4][0] for entry in resolved}
        if not addresses:
            raise UnsafeURLError("Hostname did not resolve")

        for raw_address in addresses:
            address = ipaddress.ip_address(raw_address)
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise UnsafeURLError("Non-public destination is forbidden")

        return url

    def allow(self, url: str) -> bool:
        """Boolean form of `validate` for callers that prefer not to catch."""
        try:
            self.validate(url)
        except UnsafeURLError:
            return False
        return True
