from __future__ import annotations

import argparse
import dataclasses
import getpass
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .config import default_config_path, load_credentials, save_credentials
from .errors import Onelap2StravaError
from .fit import ConversionResult, convert_fit_file


def _default_output(source: Path) -> Path:
    return source.with_name(f"{source.stem}.wgs84{source.suffix or '.fit'}")


def _print_result(result: ConversionResult, output: Path, *, as_json: bool) -> None:
    if as_json:
        document = dataclasses.asdict(result)
        document["output"] = str(output)
        print(json.dumps(document, ensure_ascii=False))
        return
    print(f"Wrote {output}")
    print(
        f"Track points: {result.record_points}; metadata pairs: {result.metadata_pairs}; "
        f"adjusted pairs: {result.adjusted_pairs}; CRC: {result.crc}"
    )


def _convert(args: argparse.Namespace) -> int:
    source = Path(args.input)
    output = Path(args.output) if args.output else _default_output(source)
    result = convert_fit_file(source, output, overwrite=args.force)
    _print_result(result, output, as_json=args.json)
    return 0


def _authorize(args: argparse.Namespace) -> int:
    from .oauth import local_authorization_code, manual_authorization_code
    from .strava import exchange_authorization_code

    client_id = (args.client_id or input("Strava client ID: ")).strip()
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET") or getpass.getpass(
        "Strava client secret: "
    )
    if args.manual:
        code = manual_authorization_code(client_id, open_browser=not args.no_browser)
    else:
        code = local_authorization_code(
            client_id,
            port=args.port,
            open_browser=not args.no_browser,
            timeout=args.timeout,
        )
    credentials = exchange_authorization_code(client_id, client_secret, code)
    path = save_credentials(credentials, args.config)
    print(f"Saved Strava authorization to {path}")
    return 0


def _upload(args: argparse.Namespace) -> int:
    from .strava import StravaClient

    source = Path(args.input)
    credentials = load_credentials(args.config)
    with tempfile.TemporaryDirectory(prefix="onelap2strava-") as temporary:
        if args.skip_conversion:
            upload_path = source
        else:
            upload_path = Path(temporary) / f"{source.stem}.wgs84.fit"
            result = convert_fit_file(source, upload_path)
            if result.adjusted_pairs == 0:
                print(
                    "Warning: no coordinates were adjusted; confirm the input really uses GCJ-02.",
                    file=sys.stderr,
                )
        with StravaClient(credentials, config_path=args.config) as client:
            upload = client.upload_fit(upload_path, timeout=args.timeout)
    print(upload.activity_url)
    return 0


def _bot(args: argparse.Namespace) -> int:
    from .telegram import run_bot

    run_bot(config_path=args.config, state_path=args.state)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onelap2strava",
        description=(
            "Convert GCJ-02 coordinates in FIT activities and optionally upload them to Strava."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    convert = commands.add_parser("convert", help="convert a FIT file to WGS84")
    convert.add_argument("input", help="input FIT file")
    convert.add_argument("-o", "--output", help="output FIT file")
    convert.add_argument("--force", action="store_true", help="replace an existing output")
    convert.add_argument("--json", action="store_true", help="print machine-readable results")
    convert.set_defaults(handler=_convert)

    authorize = commands.add_parser("auth", help="authorize a Strava account")
    authorize.add_argument("--client-id", help="numeric Strava application client ID")
    authorize.add_argument(
        "--config", type=Path, default=default_config_path(), help="credential file path"
    )
    authorize.add_argument(
        "--manual",
        action="store_true",
        help="paste the callback URL instead of starting a local callback server",
    )
    authorize.add_argument("--no-browser", action="store_true", help="do not open a browser")
    authorize.add_argument("--port", type=int, default=8765, help="local callback port")
    authorize.add_argument(
        "--timeout", type=float, default=300.0, help="callback timeout in seconds"
    )
    authorize.set_defaults(handler=_authorize)

    upload = commands.add_parser("upload", help="convert and upload a FIT file")
    upload.add_argument("input", help="input FIT file")
    upload.add_argument(
        "--config", type=Path, default=default_config_path(), help="credential file path"
    )
    upload.add_argument(
        "--skip-conversion",
        action="store_true",
        help="upload the input unchanged because it is already WGS84",
    )
    upload.add_argument("--timeout", type=float, default=120.0, help="Strava processing timeout")
    upload.set_defaults(handler=_upload)

    bot = commands.add_parser("bot", help="run the optional Telegram bot")
    bot.add_argument(
        "--config", type=Path, default=default_config_path(), help="credential file path"
    )
    bot.add_argument("--state", type=Path, default=None, help="Telegram update state file")
    bot.set_defaults(handler=_bot)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except Onelap2StravaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
