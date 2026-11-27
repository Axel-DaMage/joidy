"""Unit tests for ``services.oauth_flow`` / ``services.oauth_tokens`` (#1530).

These are the shared helpers the Google/Strava/Spotify ``/callback``
endpoints and the five integration token resolvers were consolidated onto.
Security-critical invariants pinned here:

- the signed CSRF ``state`` is verified BEFORE any token exchange;
- error pages never leak provider/HTTP details or tokens;
- token resolution keeps the header-override → stored-token → 401 contract,
  with capability gates running only on the stored-token path.
"""

import asyncio
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from config import settings
from database import Base
from services import oauth_flow, oauth_state, oauth_tokens


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """A real httpx.HTTPStatusError so helpers can map upstream statuses."""
    request = httpx.Request("POST", "https://provider.example/oauth/token")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


class OAuthFlowTestBase(unittest.TestCase):
    """In-memory SQLite session + a fixed SECRET_KEY for state signing."""

    def setUp(self) -> None:
        self._orig_secret = settings.secret_key
        settings.secret_key = "test-secret-key-for-oauth-flow"
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.addCleanup(self.db.close)
        self.addCleanup(engine.dispose)

    def tearDown(self) -> None:
        settings.secret_key = self._orig_secret

    def _run(self, coro):
        return asyncio.run(coro)


class CallbackPageTest(OAuthFlowTestBase):
    def test_ok_page(self) -> None:
        resp = oauth_flow.callback_page(ok=True, message="Google conectado")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["content-type"])
        body = bytes(resp.body).decode()
        self.assertIn("OK", body)
        self.assertIn("Google conectado", body)

    def test_error_page_escapes_html_and_quotes(self) -> None:
        resp = oauth_flow.callback_page(ok=False, message='<script>"x"</script>', status_code=403)
        self.assertEqual(resp.status_code, 403)
        body = bytes(resp.body).decode()
        self.assertNotIn('<script>"x"</script>', body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("ERROR", body)


class RunCallbackTest(OAuthFlowTestBase):
    def test_error_param_short_circuits(self) -> None:
        exchange = AsyncMock()
        persist = AsyncMock()
        resp = self._run(
            oauth_flow.run_callback(
                provider="google",
                provider_label="Google",
                code="abc",
                error="access_denied",
                state="",
                db=self.db,
                exchange=exchange,
                persist=persist,
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Error de autorización con Google", resp.body.decode())
        exchange.assert_not_awaited()
        persist.assert_not_awaited()

    def test_missing_code(self) -> None:
        exchange = AsyncMock()
        persist = AsyncMock()
        resp = self._run(
            oauth_flow.run_callback(
                provider="google",
                provider_label="Google",
                code="",
                error="",
                state="",
                db=self.db,
                exchange=exchange,
                persist=persist,
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Falta el código de autorización", resp.body.decode())
        exchange.assert_not_awaited()

    def test_invalid_state_denied_before_exchange(self) -> None:
        exchange = AsyncMock()
        persist = AsyncMock()
        resp = self._run(
            oauth_flow.run_callback(
                provider="google",
                provider_label="Google",
                code="abc",
                error="",
                state="forged",
                db=self.db,
                exchange=exchange,
                persist=persist,
            )
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Estado OAuth inválido o expirado", resp.body.decode())
        exchange.assert_not_awaited()
        persist.assert_not_awaited()

    def test_foreign_provider_state_rejected(self) -> None:
        # A state legitimately signed for Spotify must not pass a Google callback.
        exchange = AsyncMock()
        persist = AsyncMock()
        resp = self._run(
            oauth_flow.run_callback(
                provider="google",
                provider_label="Google",
                code="abc",
                error="",
                state=oauth_state.generate_state("spotify"),
                db=self.db,
                exchange=exchange,
                persist=persist,
            )
        )
        self.assertEqual(resp.status_code, 403)
        exchange.assert_not_awaited()

    def test_valid_state_exchanges_and_persists(self) -> None:
        state = oauth_state.generate_state("google")
        tokens = {"access_token": "ACCESS", "refresh_token": "REFRESH", "expires_in": 3600}
        exchange = AsyncMock(return_value=tokens)
        persist = AsyncMock()
        resp = self._run(
            oauth_flow.run_callback(
                provider="google",
                provider_label="Google",
                code="abc123",
                error="",
                state=state,
                db=self.db,
                exchange=exchange,
                persist=persist,
            )
        )
        body = bytes(resp.body).decode()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Google conectado", body)
        self.assertNotIn("ACCESS", body)
        self.assertNotIn("REFRESH", body)
        exchange.assert_awaited_once_with("abc123")
        persist.assert_awaited_once_with(self.db, tokens)

    def test_exchange_http_error_maps_to_error_page(self) -> None:
        state = oauth_state.generate_state("strava")
        exchange = AsyncMock(side_effect=_http_status_error(400))
        persist = AsyncMock()
        resp = self._run(
            oauth_flow.run_callback(
                provider="strava",
                provider_label="Strava",
                code="abc",
                error="",
                state=state,
                db=self.db,
                exchange=exchange,
                persist=persist,
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Intercambio de token con Strava falló", resp.body.decode())
        persist.assert_not_awaited()

    def test_exchange_runtime_error_maps_to_not_configured(self) -> None:
        state = oauth_state.generate_state("spotify")
        exchange = AsyncMock(side_effect=RuntimeError("missing client id"))
        persist = AsyncMock()
        resp = self._run(
            oauth_flow.run_callback(
                provider="spotify",
                provider_label="Spotify",
                code="abc",
                error="",
                state=state,
                db=self.db,
                exchange=exchange,
                persist=persist,
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Spotify OAuth no está configurado", resp.body.decode())
        persist.assert_not_awaited()


class ResolveAccessTokenTest(OAuthFlowTestBase):
    def test_header_override_wins_and_skips_lookup(self) -> None:
        get_stored = AsyncMock()
        check = MagicMock()
        result = self._run(
            oauth_flow.resolve_access_token(
                self.db,
                header_token="HDR",
                get_stored=get_stored,
                not_connected_detail="No conectado",
                check_capability=check,
            )
        )
        self.assertEqual(result, "HDR")
        get_stored.assert_not_awaited()
        check.assert_not_called()

    def test_stored_token_used(self) -> None:
        get_stored = AsyncMock(return_value="STORED")
        result = self._run(
            oauth_flow.resolve_access_token(
                self.db,
                header_token=None,
                get_stored=get_stored,
                not_connected_detail="No conectado",
            )
        )
        self.assertEqual(result, "STORED")
        get_stored.assert_awaited_once_with(self.db)

    def test_missing_stored_raises_401_with_provider_detail(self) -> None:
        get_stored = AsyncMock(return_value=None)
        with self.assertRaises(HTTPException) as ctx:
            self._run(
                oauth_flow.resolve_access_token(
                    self.db,
                    header_token=None,
                    get_stored=get_stored,
                    not_connected_detail="Strava no está conectado o la sesión expiró",
                )
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Strava no está conectado o la sesión expiró")

    def test_capability_check_runs_on_stored_path(self) -> None:
        get_stored = AsyncMock(return_value="STORED")
        check = MagicMock()
        result = self._run(
            oauth_flow.resolve_access_token(
                self.db,
                header_token=None,
                get_stored=get_stored,
                not_connected_detail="No conectado",
                check_capability=check,
            )
        )
        self.assertEqual(result, "STORED")
        check.assert_called_once_with(self.db)

    def test_capability_check_exception_propagates(self) -> None:
        get_stored = AsyncMock(return_value="STORED")
        check = MagicMock(side_effect=HTTPException(status_code=403, detail="reconnect"))
        with self.assertRaises(HTTPException) as ctx:
            self._run(
                oauth_flow.resolve_access_token(
                    self.db,
                    header_token=None,
                    get_stored=get_stored,
                    not_connected_detail="No conectado",
                    check_capability=check,
                )
            )
        self.assertEqual(ctx.exception.status_code, 403)


class ResolveExpiryTest(unittest.TestCase):
    def test_absolute_expiry_wins(self) -> None:
        expiry = datetime.now(UTC) + timedelta(hours=2)
        self.assertEqual(oauth_tokens.resolve_expiry(10, expiry), expiry)

    def test_naive_expiry_assumed_utc(self) -> None:
        naive = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)
        resolved = oauth_tokens.resolve_expiry(None, naive)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.tzinfo, UTC)
        self.assertAlmostEqual(resolved.timestamp(), naive.replace(tzinfo=UTC).timestamp(), delta=1)

    def test_expires_in_seconds_from_now(self) -> None:
        before = datetime.now(UTC)
        resolved = oauth_tokens.resolve_expiry(3600, None)
        assert resolved is not None
        self.assertGreaterEqual(resolved, before + timedelta(seconds=3600))
        self.assertLessEqual(resolved, datetime.now(UTC) + timedelta(seconds=3600))

    def test_none_when_neither_given(self) -> None:
        self.assertIsNone(oauth_tokens.resolve_expiry(None, None))


class AccessTokenFreshTest(unittest.TestCase):
    def test_fresh_token(self) -> None:
        expiry = datetime.now(UTC) + timedelta(seconds=3600)
        self.assertTrue(oauth_tokens.access_token_fresh("tok", expiry))

    def test_expired_token(self) -> None:
        expiry = datetime.now(UTC) - timedelta(seconds=100)
        self.assertFalse(oauth_tokens.access_token_fresh("tok", expiry))

    def test_within_refresh_buffer_is_stale(self) -> None:
        # Expires in 30s < the 60s buffer — refreshed proactively.
        expiry = datetime.now(UTC) + timedelta(seconds=30)
        self.assertFalse(oauth_tokens.access_token_fresh("tok", expiry))

    def test_missing_token_or_expiry(self) -> None:
        expiry = datetime.now(UTC) + timedelta(seconds=3600)
        self.assertFalse(oauth_tokens.access_token_fresh(None, expiry))
        self.assertFalse(oauth_tokens.access_token_fresh("tok", None))

    def test_naive_expiry_read_as_utc(self) -> None:
        naive = (datetime.now(UTC) + timedelta(seconds=3600)).replace(tzinfo=None)
        self.assertTrue(oauth_tokens.access_token_fresh("tok", naive))


class HasUsableRefreshTokenTest(OAuthFlowTestBase):
    def test_no_row(self) -> None:
        self.assertFalse(oauth_tokens.has_usable_refresh_token(None))

    def test_row_without_refresh_token(self) -> None:
        row = types.SimpleNamespace(refresh_token_encrypted=None)
        self.assertFalse(oauth_tokens.has_usable_refresh_token(row))

    def test_row_with_decryptable_refresh_token(self) -> None:
        row = types.SimpleNamespace(refresh_token_encrypted=oauth_tokens.encrypt_token("r"))
        self.assertTrue(oauth_tokens.has_usable_refresh_token(row))

    def test_row_with_undecryptable_refresh_token(self) -> None:
        row = types.SimpleNamespace(refresh_token_encrypted="corrupted-ciphertext")
        self.assertFalse(oauth_tokens.has_usable_refresh_token(row))


if __name__ == "__main__":
    unittest.main()
