# Changelog

All notable user-facing changes are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/), and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-16

### Added

- Offline conversion of GCJ-02 coordinates in FIT activities to WGS84.
- Validation for FIT headers, CRCs, message boundaries, and unsupported chained files.
- A local CLI for conversion, Strava OAuth authorization, and activity upload.
- An allowlisted Telegram bot with conversion-only and automatic Strava upload modes.
- Docker Compose deployment with a non-root container, read-only root filesystem, and persistent
  credential and polling state.
- English and Simplified Chinese documentation, including a complete BotFather-to-first-upload
  deployment guide.
- Synthetic tests, static analysis, package validation, dependency auditing, and GitHub Actions CI.

### Security

- FIT files are processed in per-request temporary directories and removed afterward.
- Tokens, activity files, personal identifiers, and host-specific configuration are excluded from
  the repository.

[Unreleased]: https://github.com/KurisuT7/onelap2strava/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/KurisuT7/onelap2strava/releases/tag/v0.1.0
