# onelap2strava

[简体中文](README.zh-CN.md)

Convert GCJ-02 coordinates in FIT activity files to WGS84, then optionally upload the result to
Strava. It works as a local command-line tool or as a self-hosted Telegram bot.

The converter changes coordinate fields only. Timestamps, sensor data, laps, sessions, and device
metadata remain in the original FIT stream. The file and header CRCs are validated before conversion
and the file CRC is rebuilt afterward.

## Important

Use this tool only when the source FIT file is known to contain **GCJ-02** coordinates. FIT does not
declare its coordinate system, so the tool cannot distinguish GCJ-02 from WGS84 automatically.
Converting an already-WGS84 activity inside China will move the route in the wrong direction.

No Onelap account access, private API, or Strava scraping is used. You export the FIT file yourself;
Strava upload uses its documented [OAuth](https://developers.strava.com/docs/authentication/) and
[Uploads](https://developers.strava.com/docs/uploads/) APIs.

## Install

Python 3.11 or newer is required.

```bash
git clone https://github.com/KurisuT7/onelap2strava.git
cd onelap2strava
python -m venv .venv
. .venv/bin/activate             # Windows: .venv\Scripts\activate
python -m pip install -e .
```

Convert a file locally:

```bash
onelap2strava convert activity.fit
# writes activity.wgs84.fit
```

Existing output files are not replaced unless `--force` is supplied. Use `--json` for
machine-readable conversion statistics.

## Upload to Strava

Install the Strava extra:

```bash
python -m pip install -e ".[strava]"
```

Create a [Strava API application](https://www.strava.com/settings/api) and set its authorization
callback domain to `localhost`. Then run:

```bash
onelap2strava auth --client-id YOUR_NUMERIC_CLIENT_ID
onelap2strava upload activity.fit
```

`auth` requests `read,activity:write`, receives the callback on `127.0.0.1`, and stores the client
secret and refresh token in the user configuration directory. On Unix, the file is written with
mode `0600`. Use `auth --manual` on a headless host.

`upload` converts the input in a temporary directory and waits for Strava's asynchronous processing.
Use `--skip-conversion` only when the input is already WGS84.

## Telegram bot

The bot accepts FIT documents from an explicit user allowlist. It uploads to Strava when the host is
authorized; otherwise it returns the converted file. Activity files are processed in a temporary
directory and removed after each request. Strava credentials cannot be set through Telegram.

The complete guide starts with creating a bot through `@BotFather`, then covers Docker and native
deployment, the first allowlisted upload, optional Strava authorization, routine operations, and
troubleshooting:

- [Telegram bot deployment guide](docs/telegram-bot.md)
- [Telegram Bot 部署指南](docs/telegram-bot.zh-CN.md)

The Docker container runs as a non-root user with a read-only root filesystem, no Linux
capabilities, and a persistent named volume for configuration and polling state. A missing
allowlist authorizes no file uploads; only `/whoami` responds.

## Scope and limitations

- FIT headers of 12 or 14 bytes are supported.
- Record coordinates and the standard lap/session coordinate summaries are converted.
- Chained FIT files are rejected instead of being partially rewritten.
- Telegram's Bot API currently limits bot downloads to 20 MB.
- The converter is intentionally offline; only optional Strava and Telegram commands use the network.

Before processing location history through the bot, review Telegram's and Strava's privacy terms.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests generate synthetic FIT streams; do not submit personal
activity files as fixtures. Report security issues through the private process in
[SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).

This project is not affiliated with or endorsed by Onelap or Strava. Their names and trademarks
belong to their respective owners.
