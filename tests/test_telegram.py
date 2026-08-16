from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from onelap2strava.config import StravaCredentials, save_credentials
from onelap2strava.errors import ConfigError, ServiceError
from onelap2strava.telegram import (
    TelegramBot,
    _allowed_user_ids,
    _environment_bool,
    _load_offset,
    _safe_filename,
    _save_offset,
)

from .fit_factory import make_fit


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None, content: bytes = b"") -> None:
        self.payload = payload or {"ok": True, "result": True}
        self.content = content
        self.status_code = 200

    def json(self) -> dict[str, Any]:
        return self.payload

    def raise_for_status(self) -> None:
        return

    def iter_bytes(self) -> Iterator[bytes]:
        yield self.content


class FakeTelegramClient:
    def __init__(self, fit_content: bytes = b"") -> None:
        self.fit_content = fit_content
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.documents: list[tuple[bytes, str]] = []
        self.updates: list[list[dict[str, Any]]] = []
        self.webhook_url = ""
        self.closed = False

    def request(self, _verb: str, url: str, **kwargs: Any) -> FakeResponse:
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, kwargs))
        if method == "getWebhookInfo":
            return FakeResponse({"ok": True, "result": {"url": self.webhook_url}})
        if method == "getUpdates":
            if not self.updates:
                raise KeyboardInterrupt
            return FakeResponse({"ok": True, "result": self.updates.pop(0)})
        if method == "getFile":
            return FakeResponse({"ok": True, "result": {"file_path": "files/activity.fit"}})
        if method == "sendDocument":
            file_tuple = kwargs["files"]["document"]
            self.documents.append((file_tuple[1].read(), kwargs["data"]["caption"]))
        return FakeResponse()

    @contextmanager
    def stream(self, _verb: str, _url: str, **_kwargs: Any) -> Iterator[FakeResponse]:
        yield FakeResponse(content=self.fit_content)

    def close(self) -> None:
        self.closed = True


def make_bot(monkeypatch, tmp_path: Path, fake: FakeTelegramClient) -> TelegramBot:
    fake_module = SimpleNamespace(HTTPError=httpx.HTTPError, Client=lambda **_kwargs: fake)
    monkeypatch.setattr("onelap2strava.telegram._httpx_module", lambda: fake_module)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42")
    return TelegramBot(config_path=tmp_path / "config.toml", state_path=tmp_path / "state.json")


def test_environment_parsing_and_safe_filename(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42, 99")
    monkeypatch.setenv("FEATURE_FLAG", "yes")

    assert _allowed_user_ids() == {42, 99}
    assert _environment_bool("FEATURE_FLAG", False)
    assert _environment_bool("MISSING_FLAG", False) is False
    assert _safe_filename("../ride?.fit") == "ride_.fit"

    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "invalid")
    with pytest.raises(ConfigError, match="comma-separated"):
        _allowed_user_ids()
    monkeypatch.setenv("FEATURE_FLAG", "maybe")
    with pytest.raises(ConfigError, match="true or false"):
        _environment_bool("FEATURE_FLAG", False)


def test_offset_round_trip_and_invalid_state(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    assert _load_offset(path) == 0

    _save_offset(path, 17)

    assert _load_offset(path) == 17
    path.write_text("not json", encoding="utf-8")
    assert _load_offset(path) == 0


def test_whoami_works_before_authorization(monkeypatch, tmp_path: Path) -> None:
    fake = FakeTelegramClient()
    bot = make_bot(monkeypatch, tmp_path, fake)

    bot._handle_message({"chat": {"id": 7}, "from": {"id": 999}, "text": "/whoami"})
    bot._handle_message({"chat": {"id": 7}, "from": {"id": 999}, "text": "/help"})
    bot.close()

    sent_messages = [call for call in fake.calls if call[0] == "sendMessage"]
    assert len(sent_messages) == 1
    assert "999" in sent_messages[0][1]["data"]["text"]
    assert fake.closed


def test_conversion_only_returns_synthetic_fit(monkeypatch, tmp_path: Path) -> None:
    fake = FakeTelegramClient(make_fit())
    bot = make_bot(monkeypatch, tmp_path, fake)

    bot._handle_message(
        {
            "chat": {"id": 7},
            "from": {"id": 42},
            "document": {
                "file_id": "file-id",
                "file_name": "ride.fit",
                "file_size": 1000,
            },
        }
    )

    assert len(fake.documents) == 1
    assert fake.documents[0][0] != make_fit()
    assert "not configured" in fake.documents[0][1]


def test_authorized_bot_uploads_to_strava(monkeypatch, tmp_path: Path) -> None:
    fake = FakeTelegramClient(make_fit())
    bot = make_bot(monkeypatch, tmp_path, fake)
    save_credentials(
        StravaCredentials("12345", "client-secret", "refresh-token"),
        tmp_path / "config.toml",
    )

    class FakeStrava:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            return

        def __enter__(self) -> FakeStrava:
            return self

        def __exit__(self, *_args: object) -> None:
            return

        def upload_fit(self, _path: Path) -> SimpleNamespace:
            return SimpleNamespace(activity_url="https://www.strava.com/activities/100")

    monkeypatch.setattr("onelap2strava.telegram.StravaClient", FakeStrava)
    bot._handle_document(
        7,
        {"file_id": "file-id", "file_name": "ride.fit", "file_size": 1000},
    )

    messages = [call for call in fake.calls if call[0] == "sendMessage"]
    assert "activities/100" in messages[-1][1]["data"]["text"]
    assert not fake.documents


def test_strava_failure_returns_converted_file(monkeypatch, tmp_path: Path) -> None:
    fake = FakeTelegramClient(make_fit())
    bot = make_bot(monkeypatch, tmp_path, fake)
    save_credentials(
        StravaCredentials("12345", "client-secret", "refresh-token"),
        tmp_path / "config.toml",
    )

    class FailingStrava:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            return

        def __enter__(self) -> FailingStrava:
            return self

        def __exit__(self, *_args: object) -> None:
            return

        def upload_fit(self, _path: Path) -> None:
            raise ServiceError("test failure")

    monkeypatch.setattr("onelap2strava.telegram.StravaClient", FailingStrava)
    bot._handle_document(
        7,
        {"file_id": "file-id", "file_name": "ride.fit", "file_size": 1000},
    )

    assert len(fake.documents) == 1
    assert "test failure" in fake.documents[0][1]


def test_run_persists_update_offset(monkeypatch, tmp_path: Path) -> None:
    fake = FakeTelegramClient()
    fake.updates.append(
        [
            {
                "update_id": 10,
                "message": {
                    "chat": {"id": 7},
                    "from": {"id": 42},
                    "text": "/status",
                },
            }
        ]
    )
    bot = make_bot(monkeypatch, tmp_path, fake)

    with pytest.raises(KeyboardInterrupt):
        bot.run()

    assert _load_offset(tmp_path / "state.json") == 11


def test_run_rejects_active_webhook(monkeypatch, tmp_path: Path) -> None:
    fake = FakeTelegramClient()
    fake.webhook_url = "https://example.invalid/hook"
    bot = make_bot(monkeypatch, tmp_path, fake)

    with pytest.raises(ConfigError, match="active webhook"):
        bot.run()
