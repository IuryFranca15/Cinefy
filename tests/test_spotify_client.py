import time

import pytest
import requests

from cinefy import spotify_client as sc


@pytest.fixture(autouse=True)
def fake_config(monkeypatch):
    monkeypatch.setattr(sc, "get_spotify_config", lambda: {
        "client_id": "id-teste", "client_secret": "segredo-example-fake", "redirect_uri": sc.DEFAULT_REDIRECT_URI,
    })


def test_default_redirect_is_loopback_ip():
    assert sc.DEFAULT_REDIRECT_URI.startswith("http://127.0.0.1")
    assert "localhost" not in sc.DEFAULT_REDIRECT_URI


def test_state_roundtrip_and_tampering():
    state = sc.make_state()
    assert sc.verify_state(state)
    issued, nonce, signature = state.split(".")
    assert not sc.verify_state(f"{issued}.{nonce}.{'0' * len(signature)}")
    assert not sc.verify_state(f"{int(issued) + 1}.{nonce}.{signature}")
    assert not sc.verify_state("")
    assert not sc.verify_state(None)
    assert not sc.verify_state("lixo")


def test_state_expires():
    state = sc.make_state(now=time.time() - sc.STATE_MAX_AGE_SECONDS - 5)
    assert not sc.verify_state(state)


def test_state_depends_on_client_secret(monkeypatch):
    state = sc.make_state()
    monkeypatch.setattr(sc, "get_spotify_config", lambda: {"client_id": "x", "client_secret": "outro", "redirect_uri": ""})
    assert not sc.verify_state(state)


def test_refresh_without_refresh_token_returns_none():
    assert sc.refresh_access_token({"access_token": "a"}) is None


def test_refresh_network_failure_is_temporary(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("sem rede")
    monkeypatch.setattr(sc.requests, "post", boom)
    with pytest.raises(sc.SpotifyTemporaryError):
        sc.refresh_access_token({"refresh_token": "r"})


def test_refresh_rejected_token_returns_none(monkeypatch):
    class Resp:
        status_code = 400
        def json(self):
            return {"error": "invalid_grant", "error_description": "Refresh token revoked"}
    monkeypatch.setattr(sc.requests, "post", lambda *a, **k: Resp())
    assert sc.refresh_access_token({"refresh_token": "r"}) is None


def test_refresh_keeps_old_refresh_token(monkeypatch):
    class Resp:
        status_code = 200
        content = b"{}"
        def json(self):
            return {"access_token": "novo", "expires_in": 3600}
    monkeypatch.setattr(sc.requests, "post", lambda *a, **k: Resp())
    result = sc.refresh_access_token({"refresh_token": "antigo"})
    assert result["access_token"] == "novo" and result["refresh_token"] == "antigo"
    assert result["expires_at"] > time.time()
