# Telegram bot deployment

[简体中文](telegram-bot.zh-CN.md)

This guide starts with a new Telegram bot and ends with a verified FIT conversion. Docker Compose is
the recommended deployment. The native Python option is covered at the end.

## 1. Prerequisites

You need:

- a Telegram account;
- a Linux host with `curl`, `unzip`, Docker Engine, and the Docker Compose v2 plugin;
- a FIT activity known to use GCJ-02 coordinates for the final test;
- optionally, a Strava account and API application for automatic upload.

Check Docker before continuing:

```bash
docker version
docker compose version
```

## 2. Create the bot with BotFather

1. Open Telegram and start a private chat with the official [`@BotFather`](https://t.me/BotFather).
2. Send `/newbot`.
3. Enter a display name. This is the name people see in Telegram.
4. Enter a unique username. It must end in `bot`, for example `my_fit_converter_bot`.
5. BotFather returns an API token. Store it like a password. Anyone with this token can control the
   bot.

Optionally add the command menu in BotFather:

1. Send `/mybots` and select the new bot.
2. Select **Edit Bot** and **Edit Commands**.
3. Send this list:

```text
start - Show how to use the bot
help - Show how to use the bot
status - Show bot and Strava status
whoami - Show your Telegram user ID
```

Do not paste the token into an issue, chat command, shell history, screenshot, or tracked file. If it
is exposed, use BotFather's `/revoke` command and replace it immediately.

Telegram documents the same creation flow in its
[BotFather tutorial](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).

## 3. Download and configure onelap2strava

Download and extract the `v0.2.0` Compose bundle on the deployment host:

```bash
curl -fLO https://github.com/KurisuT7/onelap2strava/releases/download/v0.2.0/onelap2strava-0.2.0-compose.zip
unzip onelap2strava-0.2.0-compose.zip
cd onelap2strava-0.2.0-compose
```

The bundle contains the versioned Compose file, empty configuration example, documentation, and
license. It pulls a prebuilt image, so the host does not build the project from source.

Create the private environment file:

```bash
cp .env.example .env
```

On Windows PowerShell, use this instead:

```powershell
Copy-Item .env.example .env
```

Open `.env` in a text editor and add the BotFather token. Leave the allowlist empty for the first
start:

```dotenv
TELEGRAM_BOT_TOKEN=PASTE_THE_BOTFATHER_TOKEN_HERE
TELEGRAM_ALLOWED_USER_IDS=
TELEGRAM_UPLOAD_TO_STRAVA=true
TELEGRAM_SEND_CONVERTED=false
```

`.env` is ignored by Git. Do not rename it to `.env.example` or commit it.

## 4. Start the bot for the first time

Pull the fixed-version image and start one long-polling bot instance:

```bash
docker compose pull
docker compose up -d
```

Confirm that the container is running:

```bash
docker compose ps
docker compose logs --tail=50 bot
```

With an empty allowlist, the bot deliberately ignores files and commands other than `/whoami`.

## 5. Add yourself to the allowlist

1. Open the bot using the username created in BotFather.
2. Press **Start**, then send `/whoami`.
3. Copy the numeric ID from `Your Telegram user ID is ...`.
4. Set that ID in `.env`:

```dotenv
TELEGRAM_ALLOWED_USER_IDS=123456789
```

Separate multiple IDs with commas and no spaces:

```dotenv
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

Recreate the container so it reads the new environment:

```bash
docker compose up -d --force-recreate
```

Send `/status`. Before Strava authorization it should report `Strava: conversion only`.

## 6. Verify conversion-only mode

Send the bot a `.fit` file that is known to contain GCJ-02 coordinates. Do not test with an original
WGS84 file: converting it would move the route in the wrong direction.

The bot should:

1. acknowledge that conversion started;
2. return a file whose name ends in `.wgs84.fit`;
3. report how many track points and coordinate pairs were processed.

The downloaded source and converted copy exist only in a temporary directory during the request and
are removed afterward. Telegram's hosted Bot API currently allows bots to download files up to
20 MB.

## 7. Enable automatic Strava upload (optional)

Skip this section if you only want the converted FIT file returned in Telegram.

1. Sign in to Strava and open [My API Application](https://www.strava.com/settings/api).
2. Create an application and complete the required fields.
3. Set **Authorization Callback Domain** to `localhost`.
4. Copy the numeric Client ID. Keep the Client Secret private.

Strava's current setup requirements and field descriptions are in its
[Getting Started guide](https://developers.strava.com/docs/getting-started/).

Run authorization inside the Compose service so the resulting credentials are saved in the
persistent `bot-data` volume:

```bash
docker compose run --rm bot auth --manual --no-browser --client-id YOUR_NUMERIC_CLIENT_ID
```

Then:

1. Enter the Client Secret at the hidden prompt.
2. Copy the printed authorization URL into a browser and approve the requested
   `read,activity:write` access.
3. The browser redirects to a `http://localhost/callback?...` address. A connection error on that
   page is expected when the command runs on another host.
4. Copy the complete address from the browser address bar, including its query string, and paste it
   at the `Callback URL:` prompt.
5. Wait for `Saved Strava authorization to /data/config.toml`.

Restart the bot and verify the result:

```bash
docker compose up -d --force-recreate
```

Send `/status`; it should report `Strava: enabled`. Send a known GCJ-02 FIT file and confirm that the
bot returns a Strava activity link. Set `TELEGRAM_SEND_CONVERTED=true` if you want both that link and
the converted file after a successful upload.

## 8. Routine operations

Show status and recent logs:

```bash
docker compose ps
docker compose logs --tail=100 bot
```

Restart after changing `.env`:

```bash
docker compose up -d --force-recreate
```

To upgrade, download and extract the newer version's Compose bundle, copy the existing `.env` into
the new directory, then run `docker compose pull` and `docker compose up -d` there. The Compose
project name is fixed, so the new bundle reuses the existing `bot-data` volume. Review the changelog
before upgrading and repeat the conversion test afterward.

Stop the bot while retaining authorization and polling state:

```bash
docker compose down
```

Do not add `-v` unless you intentionally want to delete the `bot-data` volume, including saved
Strava authorization and Telegram polling state.

## 9. Troubleshooting

### The bot does not answer `/whoami`

- Check `docker compose ps` and `docker compose logs --tail=100 bot`.
- Confirm that `TELEGRAM_BOT_TOKEN` contains the token for the username you opened.
- Recreate the container after editing `.env`.

### `/whoami` works, but files are ignored

- Confirm that the numeric ID is in `TELEGRAM_ALLOWED_USER_IDS`.
- Recreate the container after changing the allowlist.
- Send the activity as a document whose filename ends in `.fit` and is no larger than 20 MB.

### Telegram reports `409 Conflict`

Only one long-polling process may use a token. Stop the old deployment or duplicate container, then
start one instance. If the log says an active webhook exists, remove that webhook in the system that
created it before using this long-polling bot.

### `/status` says `conversion only`

This is correct when Strava has not been authorized or when `TELEGRAM_UPLOAD_TO_STRAVA=false`. Repeat
the authorization command and confirm that it finishes with the `/data/config.toml` message.

### Strava rejects an upload

- Confirm that authorization granted `activity:write`.
- Check the bot log for the Strava error returned by the API.
- Confirm that the input is a valid FIT activity and has not already been uploaded as a duplicate.

### The converted route is wrong

Stop using that output. The input was probably already WGS84 or used another coordinate system.
onelap2strava cannot infer a FIT file's coordinate system.

## Native Python deployment

Use this only when you already manage long-running Python services without Docker.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install "onelap2strava[bot,strava] @ https://github.com/KurisuT7/onelap2strava/releases/download/v0.2.0/onelap2strava-0.2.0-py3-none-any.whl"
export TELEGRAM_BOT_TOKEN=YOUR_TOKEN
export TELEGRAM_ALLOWED_USER_IDS=YOUR_NUMERIC_USER_ID
onelap2strava bot
```

On Windows PowerShell, activation and environment variables use:

```powershell
.venv\Scripts\Activate.ps1
$env:TELEGRAM_BOT_TOKEN = "YOUR_TOKEN"
$env:TELEGRAM_ALLOWED_USER_IDS = "YOUR_NUMERIC_USER_ID"
onelap2strava bot
```

Keep only one bot process running. Use your operating system's service manager to persist the
environment and restart the process; do not place tokens directly in service command arguments.
