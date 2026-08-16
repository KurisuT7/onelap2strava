from __future__ import annotations

import json
import os
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError


@dataclass(frozen=True)
class StravaCredentials:
    client_id: str
    client_secret: str = field(repr=False)
    refresh_token: str = field(repr=False)

    def validate(self) -> None:
        if not self.client_id.isdigit():
            raise ConfigError("Strava client_id must contain digits only")
        if not self.client_secret:
            raise ConfigError("Strava client_secret is missing")
        if not self.refresh_token:
            raise ConfigError("Strava refresh_token is missing")


def default_config_path() -> Path:
    override = os.environ.get("ONELAP2STRAVA_CONFIG")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "onelap2strava" / "config.toml"


def default_state_path() -> Path:
    override = os.environ.get("ONELAP2STRAVA_STATE")
    if override:
        return Path(override).expanduser()
    return default_config_path().with_name("bot-state.json")


def load_credentials(path: str | Path | None = None) -> StravaCredentials:
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.is_file():
        raise ConfigError(f"Strava configuration was not found: {config_path}")
    try:
        document = tomllib.loads(config_path.read_text(encoding="utf-8"))
        section = document["strava"]
        credentials = StravaCredentials(
            client_id=str(section["client_id"]).strip(),
            client_secret=str(section["client_secret"]).strip(),
            refresh_token=str(section["refresh_token"]).strip(),
        )
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Invalid Strava configuration: {config_path}") from exc
    credentials.validate()
    return credentials


def _atomic_private_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        if os.name != "nt":
            path.chmod(0o600)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def save_credentials(credentials: StravaCredentials, path: str | Path | None = None) -> Path:
    credentials.validate()
    config_path = Path(path) if path is not None else default_config_path()
    content = (
        "[strava]\n"
        f"client_id = {json.dumps(credentials.client_id)}\n"
        f"client_secret = {json.dumps(credentials.client_secret)}\n"
        f"refresh_token = {json.dumps(credentials.refresh_token)}\n"
    )
    _atomic_private_write(config_path, content)
    return config_path
