"""Unit tests for in-product GitHub App registration."""

import json
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

from orqis.integrations.github import app_register


def test_build_manifest_includes_callback_urls():
    with patch.object(app_register.config, "PUBLIC_URL", "http://localhost:8787"):
        manifest = app_register.build_manifest("Orqis Test")
    assert manifest["name"] == "Orqis Test"
    assert manifest["redirect_url"].endswith("/integrations/github/register/callback")
    assert manifest["hook_attributes"]["active"] is False


def test_build_manifest_webhook_when_public_https():
    with patch.object(app_register.config, "PUBLIC_URL", "https://orqis.example.com"):
        manifest = app_register.build_manifest()
    assert manifest["hook_attributes"]["active"] is True
    assert manifest["hook_attributes"]["url"].endswith("/integrations/github/webhook")


def test_register_url_encodes_manifest():
    manifest = {"name": "Orqis", "url": "http://localhost:8787"}
    url = app_register.register_url(manifest)
    assert url.startswith("https://github.com/settings/apps/new?")
    assert "manifest=" in url


def test_registration_allowed_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setattr(app_register, "SECRETS_DIR", tmp_path)
    with patch("orqis.integrations.github.auth.is_configured", return_value=False):
        with patch.object(app_register.config, "HOSTED", False):
            assert app_register.registration_allowed() is True


def test_registration_blocked_when_configured():
    with patch("orqis.integrations.github.auth.is_configured", return_value=True):
        assert app_register.registration_allowed() is False


def test_apply_runtime_credentials_persists_files(tmp_path, monkeypatch):
    monkeypatch.setattr(app_register, "SECRETS_DIR", tmp_path)
    monkeypatch.setattr(app_register, "ENV_PATH", tmp_path / "orqis-github-app.env")
    monkeypatch.setattr(app_register, "PEM_PATH", tmp_path / "orqis-github-app.pem")
    monkeypatch.setattr(app_register, "STATUS_PATH", tmp_path / "app_setup_status.json")

    data = {
        "id": 12345,
        "slug": "orqis-test",
        "pem": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
        "webhook_secret": "whsec_test",
        "html_url": "https://github.com/apps/orqis-test",
    }
    with patch.object(app_register.config, "PUBLIC_URL", "http://localhost:8787"):
        status = app_register.apply_runtime_credentials(data)

    assert status["slug"] == "orqis-test"
    assert app_register.PEM_PATH.is_file()
    assert "GITHUB_APP_ID=12345" in app_register.ENV_PATH.read_text(encoding="utf-8")
    saved = json.loads(app_register.STATUS_PATH.read_text(encoding="utf-8"))
    assert saved["state"] == "done"
    assert app_register.config.GITHUB_APP_ID == "12345"
    assert app_register.config.GITHUB_APP_SLUG == "orqis-test"
