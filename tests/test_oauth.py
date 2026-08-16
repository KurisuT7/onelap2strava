from __future__ import annotations

import threading
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

import pytest

from onelap2strava.errors import ServiceError
from onelap2strava.oauth import (
    create_authorization_request,
    local_authorization_code,
    parse_redirect_url,
)


def test_authorization_request_and_callback() -> None:
    request = create_authorization_request("12345", redirect_uri="http://localhost:8765/callback")

    assert "scope=read%2Cactivity%3Awrite" in request.url
    assert "client_id=12345" in request.url
    callback = f"http://localhost:8765/callback?code=sample-code&state={request.state}"
    assert parse_redirect_url(callback, expected_state=request.state) == "sample-code"


def test_callback_rejects_wrong_state() -> None:
    with pytest.raises(ServiceError, match="state"):
        parse_redirect_url(
            "http://localhost/callback?code=sample-code&state=wrong",
            expected_state="expected",
        )


def test_local_callback_server_receives_code(monkeypatch) -> None:
    request_thread: threading.Thread | None = None

    def open_callback(url: str, *, open_browser: bool) -> None:
        nonlocal request_thread
        assert not open_browser
        query = parse_qs(urlparse(url).query)
        redirect_uri = query["redirect_uri"][0]
        callback_url = (
            f"{redirect_uri}?{urlencode({'code': 'local-code', 'state': query['state'][0]})}"
        )

        def request() -> None:
            with urlopen(callback_url, timeout=5) as response:
                assert response.status == 200

        request_thread = threading.Thread(target=request)
        request_thread.start()

    monkeypatch.setattr("onelap2strava.oauth.open_authorization", open_callback)

    code = local_authorization_code("12345", port=0, open_browser=False, timeout=5)
    assert code == "local-code"
    assert request_thread is not None
    request_thread.join(timeout=5)
    assert not request_thread.is_alive()
