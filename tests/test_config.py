from __future__ import annotations

import os
import stat

import pytest

from onelap2strava.config import StravaCredentials, load_credentials, save_credentials
from onelap2strava.errors import ConfigError


def test_credentials_round_trip_without_repr_leak(tmp_path) -> None:
    path = tmp_path / "config.toml"
    credentials = StravaCredentials("12345", "top-secret", "refresh-secret")

    save_credentials(credentials, path)

    assert load_credentials(path) == credentials
    assert "top-secret" not in repr(credentials)
    assert "refresh-secret" not in repr(credentials)
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_invalid_client_id_is_rejected(tmp_path) -> None:
    with pytest.raises(ConfigError, match="digits only"):
        save_credentials(StravaCredentials("not-a-number", "secret", "refresh"), tmp_path / "x")


def test_missing_config_is_reported(tmp_path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_credentials(tmp_path / "missing.toml")
