from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.prepare_release import changelog_section, prepare_release, project_version


def test_changelog_section_rejects_missing_version() -> None:
    try:
        changelog_section("## [Unreleased]\n", "9.9.9")
    except ValueError as exc:
        assert "9.9.9" in str(exc)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("missing changelog version was accepted")


def test_prepare_release_builds_expected_assets(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    version = project_version(root)
    dist = tmp_path / "dist"
    output = tmp_path / "release"
    dist.mkdir()
    (dist / f"onelap2strava-{version}-py3-none-any.whl").write_bytes(b"wheel")
    (dist / f"onelap2strava-{version}.tar.gz").write_bytes(b"sdist")

    prepare_release(root, version, dist, output)

    archive = output / f"onelap2strava-{version}-compose.zip"
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    prefix = f"onelap2strava-{version}-compose"
    assert f"{prefix}/compose.yaml" in names
    assert f"{prefix}/.env.example" in names
    assert f"{prefix}/docs/telegram-bot.zh-CN.md" in names
    assert "onelap2strava" in (output / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    checksums = (output / "SHA256SUMS").read_text(encoding="utf-8")
    assert archive.name in checksums
    assert f"onelap2strava-{version}-py3-none-any.whl" in checksums
