# Changelog

All notable user-facing changes are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/), and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-18

### Added

- A universal Python wheel and source distribution attached to each GitHub Release.
- Versioned Linux AMD64 and ARM64 container images published through GitHub Container Registry.
- A self-contained Compose deployment bundle, SHA-256 checksums, image provenance, and SBOM.
- Release validation for clean wheel installation, FIT conversion, non-root container execution,
  persistent-volume writes, and rendered Compose configuration.

### Changed

- End-user installation now starts from prebuilt Release assets; source builds remain documented for
  contributors.
- Telegram deployments pull a fixed-version image instead of building from a source checkout.
- Compose uses a stable project name so upgrades keep the existing Strava authorization and Telegram
  polling state.

### Fixed

- The container now creates `/data` with ownership matching its non-root runtime user before a named
  volume is mounted.

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

[Unreleased]: https://github.com/KurisuT7/onelap2strava/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/KurisuT7/onelap2strava/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KurisuT7/onelap2strava/releases/tag/v0.1.0
