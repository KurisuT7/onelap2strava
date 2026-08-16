from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from .config import default_config_path, default_state_path, load_credentials
from .errors import ConfigError, FitError, ServiceError
from .fit import ConversionResult, convert_fit_file
from .strava import StravaClient

_API_ROOT = "https://api.telegram.org"
_DOWNLOAD_LIMIT = 20_000_000


def _httpx_module() -> Any:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - depends on installation extras
        raise ConfigError(
            'Telegram support is not installed. Install "onelap2strava[bot]".'
        ) from exc
    return httpx


def _environment_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false")


def _allowed_user_ids() -> set[int]:
    raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
    if not raw.strip():
        return set()
    result: set[int] = set()
    for item in raw.split(","):
        try:
            user_id = int(item.strip())
        except ValueError as exc:
            raise ConfigError(
                "TELEGRAM_ALLOWED_USER_IDS must be a comma-separated list of integers"
            ) from exc
        if user_id <= 0:
            raise ConfigError("Telegram user IDs must be positive integers")
        result.add(user_id)
    return result


def _safe_filename(value: str) -> str:
    filename = Path(value.replace("\\", "/")).name
    cleaned = "".join(
        character if character.isalnum() or character in {".", "_", "-", " "} else "_"
        for character in filename
    ).strip(" .")
    return cleaned or "activity.fit"


def _load_offset(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        return max(0, int(document.get("offset", 0)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def _save_offset(path: Path, offset: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(json.dumps({"offset": offset}, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_path, path)


class TelegramBot:
    def __init__(self, *, config_path: Path, state_path: Path) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ConfigError("TELEGRAM_BOT_TOKEN is required")
        self._token = token
        self._allowed_users = _allowed_user_ids()
        self._config_path = config_path
        self._state_path = state_path
        self._upload_enabled = _environment_bool("TELEGRAM_UPLOAD_TO_STRAVA", True)
        self._send_converted = _environment_bool("TELEGRAM_SEND_CONVERTED", False)
        self._httpx = _httpx_module()
        self._client = self._httpx.Client(timeout=60.0)

    def close(self) -> None:
        self._client.close()

    def _api_url(self, method: str) -> str:
        return f"{_API_ROOT}/bot{self._token}/{method}"

    def _request(self, method: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request("POST", self._api_url(method), **kwargs)
        except self._httpx.HTTPError as exc:
            raise ServiceError(f"Telegram {method} request failed") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise ServiceError(f"Telegram {method} returned an invalid response") from exc
        if response.status_code >= 400 or not payload.get("ok"):
            description = payload.get("description") or "request failed"
            raise ServiceError(
                f"Telegram {method} failed with HTTP {response.status_code}: {description}"
            )
        return payload.get("result")

    def _send_message(self, chat_id: int, text: str) -> None:
        self._request(
            "sendMessage",
            data={
                "chat_id": str(chat_id),
                "text": text,
                "disable_web_page_preview": "true",
            },
        )

    def _send_document(self, chat_id: int, path: Path, caption: str) -> None:
        with path.open("rb") as handle:
            self._request(
                "sendDocument",
                data={"chat_id": str(chat_id), "caption": caption[:1024]},
                files={"document": (path.name, handle, "application/octet-stream")},
                timeout=120.0,
            )

    def _download(self, file_id: str, target: Path) -> None:
        file_info = self._request("getFile", data={"file_id": file_id})
        file_path = str(file_info.get("file_path") or "")
        if not file_path:
            raise ServiceError("Telegram did not return a download path")
        url = f"{_API_ROOT}/file/bot{self._token}/{file_path}"
        downloaded = 0
        try:
            with self._client.stream("GET", url, timeout=120.0) as response:
                response.raise_for_status()
                with target.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        downloaded += len(chunk)
                        if downloaded > _DOWNLOAD_LIMIT:
                            raise ServiceError("Telegram file exceeds the 20 MB download limit")
                        handle.write(chunk)
        except self._httpx.HTTPError as exc:
            raise ServiceError("Telegram file download failed") from exc

    @staticmethod
    def _summary(result: ConversionResult) -> str:
        return (
            f"Processed {result.record_points} track points; "
            f"adjusted {result.adjusted_pairs} coordinate pairs."
        )

    def _return_converted(
        self, chat_id: int, converted: Path, result: ConversionResult, reason: str
    ) -> None:
        self._send_document(chat_id, converted, f"{self._summary(result)}\n{reason}")

    def _handle_document(self, chat_id: int, document: dict[str, Any]) -> None:
        filename = _safe_filename(str(document.get("file_name") or "activity.fit"))
        if not filename.lower().endswith(".fit"):
            self._send_message(chat_id, "Please send a .fit file.")
            return
        file_size = int(document.get("file_size") or 0)
        if file_size > _DOWNLOAD_LIMIT:
            self._send_message(chat_id, "The file exceeds Telegram's 20 MB download limit.")
            return

        self._send_message(chat_id, "Converting GCJ-02 coordinates to WGS84…")
        with tempfile.TemporaryDirectory(prefix="onelap2strava-") as temporary:
            workdir = Path(temporary)
            source = workdir / filename
            converted = workdir / f"{Path(filename).stem}.wgs84.fit"
            self._download(str(document["file_id"]), source)
            result = convert_fit_file(source, converted)

            if not self._upload_enabled:
                self._return_converted(
                    chat_id, converted, result, "Automatic Strava upload is disabled."
                )
                return
            try:
                credentials = load_credentials(self._config_path)
            except ConfigError:
                self._return_converted(
                    chat_id, converted, result, "Strava is not configured on this host."
                )
                return

            try:
                with StravaClient(credentials, config_path=self._config_path) as strava:
                    upload = strava.upload_fit(converted)
            except ServiceError as exc:
                self._return_converted(chat_id, converted, result, f"Strava upload failed: {exc}")
                return

            message = f"Uploaded to Strava: {upload.activity_url}"
            if self._send_converted:
                self._send_document(chat_id, converted, message)
            else:
                self._send_message(chat_id, message)

    def _handle_message(self, message: dict[str, Any]) -> None:
        chat_id = int(message["chat"]["id"])
        sender = message.get("from") or {}
        user_id = int(sender.get("id") or 0)
        text = str(message.get("text") or "").strip()

        if text == "/whoami":
            self._send_message(chat_id, f"Your Telegram user ID is {user_id}.")
            return
        if user_id not in self._allowed_users:
            return
        if text in {"/start", "/help"}:
            self._send_message(
                chat_id,
                "Send a GCJ-02 .fit file. I will convert it to WGS84 and upload it "
                "to Strava when this host is authorized.",
            )
            return
        if text == "/status":
            configured = self._config_path.is_file() and self._upload_enabled
            status = "enabled" if configured else "conversion only"
            self._send_message(chat_id, f"Bot is running. Strava: {status}.")
            return
        if message.get("document"):
            self._handle_document(chat_id, message["document"])
            return
        self._send_message(chat_id, "Send a .fit file or use /help.")

    def run(self) -> None:
        webhook = self._request("getWebhookInfo")
        if webhook.get("url"):
            raise ConfigError(
                "This bot has an active webhook. Remove it before using long polling."
            )
        if not self._allowed_users:
            print(
                "No Telegram users are allowed. Send /whoami, add the returned ID to "
                "TELEGRAM_ALLOWED_USER_IDS, and restart the bot.",
                flush=True,
            )
        offset = _load_offset(self._state_path)
        while True:
            try:
                updates = self._request(
                    "getUpdates",
                    data={
                        "offset": str(offset),
                        "timeout": "50",
                        "allowed_updates": json.dumps(["message"]),
                    },
                    timeout=60.0,
                )
                for update in updates:
                    next_offset = int(update["update_id"]) + 1
                    message = update.get("message")
                    if message:
                        try:
                            self._handle_message(message)
                        except (ConfigError, FitError, ServiceError, OSError) as exc:
                            chat_id = int(message["chat"]["id"])
                            with suppress(ServiceError):
                                self._send_message(chat_id, f"Could not process the file: {exc}")
                    offset = next_offset
                    _save_offset(self._state_path, offset)
            except ServiceError as exc:
                print(f"Bot error: {exc}", flush=True)
                time.sleep(5)


def run_bot(*, config_path: str | Path | None = None, state_path: str | Path | None = None) -> None:
    bot = TelegramBot(
        config_path=Path(config_path) if config_path else default_config_path(),
        state_path=Path(state_path) if state_path else default_state_path(),
    )
    try:
        bot.run()
    finally:
        bot.close()
