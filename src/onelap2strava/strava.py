from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .config import StravaCredentials, save_credentials
from .errors import ConfigError, ServiceError

_AUTHORIZATION_URL = "https://www.strava.com/oauth/authorize"
_TOKEN_URL = "https://www.strava.com/oauth/token"  # noqa: S105 - public OAuth endpoint
_UPLOADS_URL = "https://www.strava.com/api/v3/uploads"


def _httpx_module() -> Any:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - depends on installation extras
        raise ConfigError(
            'Strava support is not installed. Install "onelap2strava[strava]".'
        ) from exc
    return httpx


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    if not client_id.isdigit():
        raise ConfigError("Strava client_id must contain digits only")
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "approval_prompt": "force",
            "scope": "read,activity:write",
            "state": state,
        }
    )
    return f"{_AUTHORIZATION_URL}?{query}"


def _response_json(response: Any, operation: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ServiceError(f"Strava {operation} returned an invalid response") from exc
    if not isinstance(payload, dict):
        raise ServiceError(f"Strava {operation} returned an invalid response")
    if response.status_code >= 400:
        message = payload.get("message") or payload.get("error") or "request failed"
        raise ServiceError(f"Strava {operation} failed with HTTP {response.status_code}: {message}")
    return payload


def exchange_authorization_code(
    client_id: str,
    client_secret: str,
    code: str,
    *,
    client: Any | None = None,
) -> StravaCredentials:
    httpx = _httpx_module()
    owns_client = client is None
    session = client or httpx.Client(timeout=30.0)
    try:
        response = session.post(
            _TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        payload = _response_json(response, "authorization")
    except httpx.HTTPError as exc:
        raise ServiceError("Could not reach Strava during authorization") from exc
    finally:
        if owns_client:
            session.close()
    refresh_token = str(payload.get("refresh_token") or "")
    credentials = StravaCredentials(client_id, client_secret, refresh_token)
    credentials.validate()
    return credentials


@dataclass(frozen=True)
class UploadResult:
    upload_id: int
    activity_id: int

    @property
    def activity_url(self) -> str:
        return f"https://www.strava.com/activities/{self.activity_id}"


class StravaClient:
    def __init__(
        self,
        credentials: StravaCredentials,
        *,
        config_path: str | Path | None = None,
        client: Any | None = None,
    ) -> None:
        credentials.validate()
        httpx = _httpx_module()
        self._httpx = httpx
        self._credentials = credentials
        self._config_path = config_path
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=30.0)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> StravaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _access_token(self) -> str:
        try:
            response = self._client.post(
                _TOKEN_URL,
                data={
                    "client_id": self._credentials.client_id,
                    "client_secret": self._credentials.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self._credentials.refresh_token,
                },
            )
            payload = _response_json(response, "token refresh")
        except self._httpx.HTTPError as exc:
            raise ServiceError("Could not reach Strava while refreshing the token") from exc

        access_token = str(payload.get("access_token") or "")
        if not access_token:
            raise ServiceError("Strava token refresh did not return an access token")
        refresh_token = str(payload.get("refresh_token") or self._credentials.refresh_token)
        if refresh_token != self._credentials.refresh_token:
            self._credentials = StravaCredentials(
                self._credentials.client_id,
                self._credentials.client_secret,
                refresh_token,
            )
            save_credentials(self._credentials, self._config_path)
        return access_token

    def upload_fit(
        self,
        path: str | Path,
        *,
        poll_interval: float = 1.0,
        timeout: float = 120.0,
    ) -> UploadResult:
        fit_path = Path(path)
        if not fit_path.is_file():
            raise ConfigError(f"FIT file does not exist: {fit_path}")
        access_token = self._access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            with fit_path.open("rb") as handle:
                response = self._client.post(
                    _UPLOADS_URL,
                    headers=headers,
                    data={"data_type": "fit"},
                    files={"file": (fit_path.name, handle, "application/octet-stream")},
                    timeout=120.0,
                )
            payload = _response_json(response, "upload")
        except self._httpx.HTTPError as exc:
            raise ServiceError("Could not reach Strava while uploading the FIT file") from exc

        try:
            upload_id = int(payload["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceError("Strava upload did not return an upload ID") from exc

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(max(1.0, poll_interval))
            try:
                response = self._client.get(
                    f"{_UPLOADS_URL}/{upload_id}", headers=headers, timeout=30.0
                )
                status = _response_json(response, "upload status")
            except self._httpx.HTTPError as exc:
                raise ServiceError("Could not reach Strava while checking the upload") from exc
            if status.get("error"):
                raise ServiceError(f"Strava rejected the upload: {status['error']}")
            if status.get("activity_id"):
                return UploadResult(upload_id, int(status["activity_id"]))
        raise ServiceError("Strava did not finish processing the upload before the timeout")
