from __future__ import annotations

from pathlib import Path
from typing import Any

from onelap2strava.config import StravaCredentials, load_credentials
from onelap2strava.strava import StravaClient, exchange_authorization_code


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(self, posts: list[FakeResponse], gets: list[FakeResponse] | None = None) -> None:
        self.posts = posts
        self.gets = gets or []
        self.closed = False

    def post(self, _url: str, **_kwargs: Any) -> FakeResponse:
        return self.posts.pop(0)

    def get(self, _url: str, **_kwargs: Any) -> FakeResponse:
        return self.gets.pop(0)

    def close(self) -> None:
        self.closed = True


def test_exchange_authorization_code() -> None:
    fake = FakeClient([FakeResponse({"refresh_token": "new-refresh"})])

    credentials = exchange_authorization_code("12345", "secret", "code", client=fake)

    assert credentials.client_id == "12345"
    assert credentials.refresh_token == "new-refresh"
    assert not fake.closed


def test_upload_refreshes_and_persists_rotated_token(tmp_path: Path, monkeypatch) -> None:
    fit_path = tmp_path / "activity.fit"
    fit_path.write_bytes(b"fit")
    config_path = tmp_path / "config.toml"
    credentials = StravaCredentials("12345", "secret", "old-refresh")
    fake = FakeClient(
        [
            FakeResponse({"access_token": "access", "refresh_token": "rotated-refresh"}),
            FakeResponse({"id": 77}),
        ],
        [FakeResponse({"activity_id": 88})],
    )
    monkeypatch.setattr("onelap2strava.strava.time.sleep", lambda _seconds: None)

    with StravaClient(credentials, config_path=config_path, client=fake) as client:
        result = client.upload_fit(fit_path)

    assert result.upload_id == 77
    assert result.activity_id == 88
    assert result.activity_url.endswith("/88")
    assert load_credentials(config_path).refresh_token == "rotated-refresh"
    assert not fake.closed
