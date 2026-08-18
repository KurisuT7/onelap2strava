from __future__ import annotations

import argparse
import hashlib
import re
import tomllib
import zipfile
from pathlib import Path

BUNDLE_FILES = (
    ("compose.yaml", "compose.yaml"),
    (".env.example", ".env.example"),
    ("README.md", "README.md"),
    ("README.zh-CN.md", "README.zh-CN.md"),
    ("docs/telegram-bot.md", "docs/telegram-bot.md"),
    ("docs/telegram-bot.zh-CN.md", "docs/telegram-bot.zh-CN.md"),
    ("LICENSE", "LICENSE"),
)


def project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def changelog_section(changelog: str, version: str) -> str:
    heading = re.search(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\s*$",
        changelog,
        flags=re.MULTILINE,
    )
    if heading is None:
        raise ValueError(f"CHANGELOG.md has no dated section for {version}")
    remainder = changelog[heading.end() :]
    following = re.search(r"^## \[", remainder, flags=re.MULTILINE)
    section = remainder[: following.start() if following else None].strip()
    if not section:
        raise ValueError(f"CHANGELOG.md section for {version} is empty")
    return section


def _write_bundle(root: Path, version: str, destination: Path) -> Path:
    archive = destination / f"onelap2strava-{version}-compose.zip"
    prefix = f"onelap2strava-{version}-compose"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for source_name, archive_name in BUNDLE_FILES:
            source = root / source_name
            if not source.is_file():
                raise FileNotFoundError(source)
            info = zipfile.ZipInfo(f"{prefix}/{archive_name}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            output.writestr(info, source.read_bytes())
    return archive


def _write_checksums(assets: list[Path], destination: Path) -> None:
    lines = []
    for asset in sorted(assets, key=lambda path: path.name):
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        lines.append(f"{digest}  {asset.name}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def prepare_release(root: Path, version: str, dist_dir: Path, output_dir: Path) -> None:
    if project_version(root) != version:
        raise ValueError(f"requested version {version} does not match pyproject.toml")
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    image = f"ghcr.io/kurisut7/onelap2strava:{version}"
    if f"image: {image}" not in compose:
        raise ValueError(f"compose.yaml does not use the release image {image}")

    wheel = dist_dir / f"onelap2strava-{version}-py3-none-any.whl"
    sdist = dist_dir / f"onelap2strava-{version}.tar.gz"
    for distribution in (wheel, sdist):
        if not distribution.is_file():
            raise FileNotFoundError(distribution)

    output_dir.mkdir(parents=True, exist_ok=True)
    expected_outputs = (
        output_dir / f"onelap2strava-{version}-compose.zip",
        output_dir / "SHA256SUMS",
        output_dir / "RELEASE_NOTES.md",
    )
    existing = [path for path in expected_outputs if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to replace release output: {existing[0]}")

    archive = _write_bundle(root, version, output_dir)
    _write_checksums([wheel, sdist, archive], output_dir / "SHA256SUMS")
    changes = changelog_section((root / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    notes = (
        f"# onelap2strava {version}\n\n"
        "Install the wheel asset for local conversion and Strava upload. For the Telegram bot, "
        "download the Compose bundle; it pulls the matching prebuilt image from "
        f"`{image}`.\n\n"
        "## Changes\n\n"
        f"{changes}\n"
    )
    (output_dir / "RELEASE_NOTES.md").write_text(notes, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare verified GitHub release assets.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    prepare_release(root, args.version, args.dist_dir.resolve(), args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
