from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from onelap2strava.cli import main
from onelap2strava.config import StravaCredentials, save_credentials

from .fit_factory import make_fit


def test_convert_command_json_output(tmp_path, capsys) -> None:
    source = tmp_path / "ride.fit"
    target = tmp_path / "converted.fit"
    source.write_bytes(make_fit())

    exit_code = main(["convert", str(source), "-o", str(target), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["record_points"] == 1
    assert payload["output"] == str(target)
    assert target.is_file()


def test_convert_command_returns_clean_error(tmp_path, capsys) -> None:
    exit_code = main(["convert", str(tmp_path / "missing.fit")])

    assert exit_code == 1
    assert "error:" in capsys.readouterr().err


def test_auth_command_saves_credentials(tmp_path, monkeypatch, capsys) -> None:
    config = tmp_path / "config.toml"
    credentials = StravaCredentials("12345", "client-secret", "refresh-token")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        "onelap2strava.oauth.manual_authorization_code",
        lambda *_args, **_kwargs: "authorization-code",
    )
    monkeypatch.setattr(
        "onelap2strava.strava.exchange_authorization_code",
        lambda *_args, **_kwargs: credentials,
    )

    exit_code = main(
        [
            "auth",
            "--manual",
            "--no-browser",
            "--client-id",
            "12345",
            "--config",
            str(config),
        ]
    )

    assert exit_code == 0
    assert config.is_file()
    assert "Saved Strava authorization" in capsys.readouterr().out


def test_upload_and_bot_commands(tmp_path, monkeypatch, capsys) -> None:
    source = tmp_path / "ride.fit"
    config = tmp_path / "config.toml"
    source.write_bytes(make_fit())
    save_credentials(StravaCredentials("12345", "client-secret", "refresh-token"), config)

    class FakeStravaClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            return

        def __enter__(self) -> FakeStravaClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return

        def upload_fit(self, path: Path, **_kwargs: Any) -> SimpleNamespace:
            assert path.is_file()
            return SimpleNamespace(activity_url="https://www.strava.com/activities/200")

    bot_call: dict[str, Any] = {}
    monkeypatch.setattr("onelap2strava.strava.StravaClient", FakeStravaClient)
    monkeypatch.setattr(
        "onelap2strava.telegram.run_bot",
        lambda **kwargs: bot_call.update(kwargs),
    )

    assert main(["upload", str(source), "--config", str(config)]) == 0
    assert "activities/200" in capsys.readouterr().out
    assert main(["bot", "--config", str(config)]) == 0
    assert bot_call["config_path"] == config
