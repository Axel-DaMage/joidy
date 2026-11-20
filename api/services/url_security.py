"""Outbound-URL validation to blunt server-side request forgery (SSRF) (#1316).

Any URL the API itself is about to connect to — Web Push subscription
endpoints today — must pass through :func:`validate_public_https_url` before
it is stored or used. The URL must be ``https://`` and its host must resolve
exclusively to public addresses: every resolved IP is checked against
non-public ranges (RFC1918, loopback, link-local/cloud-metadata, CGNAT,
unique-local, multicast, reserved) so an authenticated caller cannot point
the server at internal services such as ``169.254.169.254`` or
``ai-service:8002``.

Validation is dependency-free (``ipaddress`` + ``socket.getaddrinfo``) and
must be repeated at send time: DNS results can change between subscribe and
send (DNS rebinding), so a stored endpoint is never trusted blindly.
"""

import ipaddress
import socket
from urllib.parse import urlparse

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class URLValidationError(ValueError):
    """Raised when an outbound URL fails SSRF validation."""


# Address ranges that must never receive a server-side request. The explicit
# list documents the audit requirement (#1316); ``_is_blocked`` additionally
# rejects anything ``ip.is_global`` flags as non-public, which covers
# documentation/benchmarking ranges independently of this table.
_BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        # IPv4
        "0.0.0.0/8",  # "this network"
        "10.0.0.0/8",  # RFC1918
        "100.64.0.0/10",  # CGNAT (RFC6598)
        "127.0.0.0/8",  # loopback
        "169.254.0.0/16",  # link-local / cloud metadata
        "172.16.0.0/12",  # RFC1918
        "192.0.0.0/24",  # IETF protocol assignments
        "192.168.0.0/16",  # RFC1918
        "198.18.0.0/15",  # benchmarking (RFC2544)
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved for future use
        # IPv6
        "::/128",  # unspecified
        "::1/128",  # loopback
        "fc00::/7",  # unique local
        "fe80::/10",  # link-local
        "ff00::/8",  # multicast
        "2001::/32",  # Teredo (embeds an IPv4; never a legit push host)
        "2002::/16",  # 6to4 (embeds an IPv4; never a legit push host)
    )
)

# Characters that make URL parsers disagree about the authority component.
# urllib3/requests may treat them differently than urlparse, which would let
# the checked host diverge from the connected host.
_UNSAFE_URL_CHARS = frozenset("\\ \t\r\n\x00")


def _normalize_ip(ip: IPAddress) -> IPAddress:
    """Collapse IPv4-mapped IPv6 addresses (``::ffff:169.254.169.254``) to IPv4."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _is_blocked(ip: IPAddress) -> bool:
    """True if ``ip`` is not a public, globally routable address."""
    ip = _normalize_ip(ip)
    if not ip.is_global:
        return True
    return any(ip in net for net in _BLOCKED_NETWORKS)


def _resolve_ips(host: str, port: int) -> set[IPAddress]:
    """Resolve ``host`` via ``socket.getaddrinfo``; all answers must be safe.

    Wrapped so tests can stub DNS deterministically and so resolution errors
    surface as :class:`URLValidationError` instead of leaking ``gaierror``.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as exc:
        raise URLValidationError(f"host {host!r} could not be resolved") from exc
    ips = {_normalize_ip(ipaddress.ip_address(sockaddr[0])) for *_rest, sockaddr in infos}
    if not ips:
        raise URLValidationError(f"host {host!r} resolved to no addresses")
    return ips


def validate_public_https_url(url: str) -> str:
    """Validate that ``url`` is a safe target for a server-side request.

    Requires a syntactically valid ``https://`` URL whose host resolves only
    to public IPs. Returns ``url`` unchanged on success so call sites can
    store the verbatim endpoint; raises :class:`URLValidationError` on any
    failure, including DNS resolution errors (fail closed).
    """
    if not url or any(ch in url for ch in _UNSAFE_URL_CHARS):
        raise URLValidationError("URL is empty or contains invalid characters")
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise URLValidationError("URL is malformed") from exc
    if parsed.scheme.lower() != "https":
        raise URLValidationError("URL must use the https:// scheme")
    try:
        host = parsed.hostname
        port = parsed.port or 443
    except ValueError as exc:
        raise URLValidationError("URL has an invalid host or port") from exc
    if not host:
        raise URLValidationError("URL must include a host")
    if parsed.username or parsed.password:
        # Push endpoints never carry credentials; userinfo is only useful to
        # obscure the real host from URL parsers.
        raise URLValidationError("URL must not contain credentials")
    try:
        ips = {_normalize_ip(ipaddress.ip_address(host))}
    except ValueError:
        ips = _resolve_ips(host, port)
    for ip in ips:
        if _is_blocked(ip):
            raise URLValidationError(f"host {host!r} resolves to a non-public address ({ip})")
    return url
