from __future__ import annotations

import secrets
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .errors import ServiceError
from .strava import build_authorization_url


@dataclass(frozen=True)
class AuthorizationRequest:
    url: str
    redirect_uri: str
    state: str


def create_authorization_request(client_id: str, *, redirect_uri: str) -> AuthorizationRequest:
    state = secrets.token_urlsafe(32)
    return AuthorizationRequest(
        url=build_authorization_url(client_id, redirect_uri, state),
        redirect_uri=redirect_uri,
        state=state,
    )


def parse_redirect_url(value: str, *, expected_state: str) -> str:
    parsed = urlparse(value.strip())
    query = parse_qs(parsed.query)
    if query.get("error"):
        raise ServiceError(f"Strava authorization was denied: {query['error'][0]}")
    state = query.get("state", [""])[0]
    if not secrets.compare_digest(state, expected_state):
        raise ServiceError("OAuth state did not match; authorization was not saved")
    code = query.get("code", [""])[0]
    if not code:
        raise ServiceError("The callback URL does not contain an authorization code")
    return code


def open_authorization(url: str, *, open_browser: bool) -> None:
    print("Open this URL and approve access to Strava:")
    print(url)
    if open_browser:
        webbrowser.open(url)


def manual_authorization_code(client_id: str, *, open_browser: bool) -> str:
    request = create_authorization_request(client_id, redirect_uri="http://localhost/callback")
    open_authorization(request.url, open_browser=open_browser)
    print("After the redirect, copy the complete URL from the browser address bar.")
    redirect_url = input("Callback URL: ").strip()
    return parse_redirect_url(redirect_url, expected_state=request.state)


def local_authorization_code(
    client_id: str,
    *,
    port: int,
    open_browser: bool,
    timeout: float = 300.0,
) -> str:
    callback: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            callback["url"] = f"http://localhost{self.path}"
            body = b"Authorization received. You can close this window."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    actual_port = server.server_address[1]
    request = create_authorization_request(
        client_id, redirect_uri=f"http://localhost:{actual_port}/callback"
    )
    open_authorization(request.url, open_browser=open_browser)
    server.timeout = 1.0
    deadline = time.monotonic() + timeout
    try:
        while "url" not in callback and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if "url" not in callback:
        raise ServiceError("Timed out waiting for the Strava authorization callback")
    return parse_redirect_url(callback["url"], expected_state=request.state)
