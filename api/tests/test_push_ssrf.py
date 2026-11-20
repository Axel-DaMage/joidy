"""SSRF validation for Web Push subscription endpoints (#1316).

``SubscriptionIn.endpoint`` is stored and later POSTed to by pywebpush.
These tests pin the SSRF guard: https-only, public IPs only, DNS stubbed
via ``services.url_security._resolve_ips`` for hermeticity.
"""

import ipaddress
import socket
from unittest.mock import patch

import pytest
from models.push_subscription import PushSubscription
from services.push_service import send_push_to_user
from services.url_security import URLValidationError, validate_public_https_url

_PUBLIC_IPS = {ipaddress.ip_address("93.184.216.34")}
_METADATA_IPS = {ipaddress.ip_address("169.254.169.254")}
_PRIVATE_IPS = {ipaddress.ip_address("10.0.0.1")}
_LOOPBACK_IPS = {ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")}

_VALID_KEYS = {"p256dh": "p256dh-key", "auth": "auth-key"}


def _resolve(ips):
    """A ``_resolve_ips`` replacement that returns the given IPs."""
    return lambda _host, _port: set(ips)


def _resolve_fail(_host, _port):
    raise URLValidationError("host could not be resolved")


# ---------------------------------------------------------------------------
# validate_public_https_url — unit-level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://push.example.com/send",  # plain http
        "ftp://push.example.com/send",
        "https:///path-only",
        "not-a-url",
        "",
        "https://user:pass@push.example.com/",  # credentials obscure the host
        "https://push.example.com\\@169.254.169.254/",  # parser-differential char
    ],
)
def test_validate_rejects_bad_url_shape(url):
    with pytest.raises(URLValidationError):
        validate_public_https_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://10.0.0.7/push",
        "https://172.16.5.4/push",
        "https://192.168.1.1/push",
        "https://127.0.0.1/push",
        "https://169.254.169.254/latest/meta-data",  # cloud metadata
        "https://0.0.0.0/push",
        "https://[::1]/push",
        "https://[fd00::1]/push",
        "https://[fe80::1]/push",
        "https://[::ffff:169.254.169.254]/push",  # IPv4-mapped metadata
    ],
)
def test_validate_rejects_literal_non_public_ips(url):
    with pytest.raises(URLValidationError):
        validate_public_https_url(url)


def test_validate_accepts_literal_public_ip():
    url = "https://93.184.216.34/push"
    assert validate_public_https_url(url) == url


def test_validate_rejects_hostname_resolving_private():
    with patch("services.url_security._resolve_ips", side_effect=_resolve(_METADATA_IPS)):
        with pytest.raises(URLValidationError):
            validate_public_https_url("https://attacker.example/send")


def test_validate_rejects_when_any_answer_is_private():
    ips = _PUBLIC_IPS | _METADATA_IPS
    with patch("services.url_security._resolve_ips", side_effect=_resolve(ips)):
        with pytest.raises(URLValidationError):
            validate_public_https_url("https://attacker.example/send")


def test_validate_accepts_hostname_resolving_public():
    url = "https://fcm.googleapis.com/fcm/send/abc"
    with patch("services.url_security._resolve_ips", side_effect=_resolve(_PUBLIC_IPS)):
        assert validate_public_https_url(url) == url


def test_validate_rejects_on_dns_failure():
    with patch("services.url_security.socket.getaddrinfo", side_effect=socket.gaierror("NXDOMAIN")):
        with pytest.raises(URLValidationError):
            validate_public_https_url("https://no-such-host.invalid/send")


# ---------------------------------------------------------------------------
# POST /push/subscribe — endpoint validation at the router
# ---------------------------------------------------------------------------


def test_subscribe_rejects_http_endpoint(client):
    resp = client.post(
        "/push/subscribe",
        json={"endpoint": "http://localhost:8001/health", "keys": _VALID_KEYS},
    )
    assert resp.status_code == 400


def test_subscribe_rejects_literal_metadata_ip(client):
    resp = client.post(
        "/push/subscribe",
        json={"endpoint": "https://169.254.169.254/latest/meta-data", "keys": _VALID_KEYS},
    )
    assert resp.status_code == 400


def test_subscribe_rejects_hostname_resolving_to_metadata(client):
    with patch("services.url_security._resolve_ips", side_effect=_resolve(_METADATA_IPS)):
        resp = client.post(
            "/push/subscribe",
            json={"endpoint": "https://attacker.example/send", "keys": _VALID_KEYS},
        )
    assert resp.status_code == 400


def test_subscribe_rejects_loopback_resolution(client):
    with patch("services.url_security._resolve_ips", side_effect=_resolve(_LOOPBACK_IPS)):
        resp = client.post(
            "/push/subscribe",
            json={"endpoint": "https://internal.example/send", "keys": _VALID_KEYS},
        )
    assert resp.status_code == 400


def test_subscribe_rejects_on_dns_failure(client):
    with patch("services.url_security._resolve_ips", side_effect=_resolve_fail):
        resp = client.post(
            "/push/subscribe",
            json={"endpoint": "https://no-such-host.invalid/send", "keys": _VALID_KEYS},
        )
    assert resp.status_code == 400


def test_subscribe_accepts_legit_https_endpoint(client, db_session):
    endpoint = "https://fcm.googleapis.com/fcm/send/abc"
    with patch("services.url_security._resolve_ips", side_effect=_resolve(_PUBLIC_IPS)):
        resp = client.post(
            "/push/subscribe",
            json={"endpoint": endpoint, "keys": _VALID_KEYS},
        )
    assert resp.status_code == 200
    # Membership check, not a global count: under the SQLite fallback,
    # session commits can escape the per-test savepoint isolation and leak
    # rows between tests (pre-existing quirk; CI Postgres isolates properly).
    assert db_session.query(PushSubscription).filter_by(endpoint=endpoint).count() == 1


def test_rejected_subscribe_keeps_existing_subscription(client, db_session):
    db_session.add(
        PushSubscription(
            user_id=1,
            endpoint="https://old.example.com/send",
            p256dh="old-p256dh",
            auth="old-auth",
        )
    )
    db_session.flush()

    with patch("services.url_security._resolve_ips", side_effect=_resolve(_PRIVATE_IPS)):
        resp = client.post(
            "/push/subscribe",
            json={"endpoint": "https://attacker.example/send", "keys": _VALID_KEYS},
        )
    assert resp.status_code == 400

    endpoints = {s.endpoint for s in db_session.query(PushSubscription).all()}
    assert "https://old.example.com/send" in endpoints
    assert "https://attacker.example/send" not in endpoints


# ---------------------------------------------------------------------------
# send_push_to_user — re-validation at send time (DNS rebinding)
# ---------------------------------------------------------------------------


# Distinct user so leftover subscriptions seeded by other tests (SQLite
# fallback commits can leak rows across tests) never reach webpush.
_USER = 4242


def _seed_subscription(db_session, endpoint="https://push.example.com/send"):
    # flush() keeps the row inside the test's savepoint transaction so it is
    # rolled back on teardown; commit() would leak it into the shared SQLite
    # DB (see note on the accept test above).
    sub = PushSubscription(user_id=_USER, endpoint=endpoint, p256dh="p", auth="a")
    db_session.add(sub)
    db_session.flush()
    return sub


def test_send_skips_endpoint_rebinding_to_private(db_session, monkeypatch):
    monkeypatch.setattr("config.settings.vapid_private_key", "test-vapid-key")
    monkeypatch.setattr("config.settings.vapid_claim_email", "test@example.com")
    _seed_subscription(db_session)

    with (
        patch("services.url_security._resolve_ips", side_effect=_resolve(_METADATA_IPS)),
        patch("services.push_service.webpush") as mock_webpush,
    ):
        send_push_to_user(db_session, user_id=_USER, title="Hi", body="There")

    mock_webpush.assert_not_called()


def test_send_skips_endpoint_on_dns_failure(db_session, monkeypatch):
    monkeypatch.setattr("config.settings.vapid_private_key", "test-vapid-key")
    monkeypatch.setattr("config.settings.vapid_claim_email", "test@example.com")
    _seed_subscription(db_session)

    with (
        patch("services.url_security._resolve_ips", side_effect=_resolve_fail),
        patch("services.push_service.webpush") as mock_webpush,
    ):
        # Must not raise — a poisoned subscription is skipped, not fatal.
        send_push_to_user(db_session, user_id=_USER, title="Hi", body="There")

    mock_webpush.assert_not_called()


def test_send_still_delivers_public_endpoint(db_session, monkeypatch):
    monkeypatch.setattr("config.settings.vapid_private_key", "test-vapid-key")
    monkeypatch.setattr("config.settings.vapid_claim_email", "test@example.com")
    _seed_subscription(db_session)

    with (
        patch("services.url_security._resolve_ips", side_effect=_resolve(_PUBLIC_IPS)),
        patch("services.push_service.webpush") as mock_webpush,
    ):
        send_push_to_user(db_session, user_id=_USER, title="Hi", body="There")

    mock_webpush.assert_called_once()
