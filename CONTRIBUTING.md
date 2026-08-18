# Contributing

Small, focused changes are easiest to review. Open an issue before starting a large feature or a
change to the FIT parser's supported message types.

## Development

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
pytest --cov
python -m build
python -m twine check dist/*
```

Tests must use synthetic or explicitly redistributable FIT data. Never submit personal activity
files, credentials, chat IDs, server addresses, or production configuration.

## Commits and changelog

Keep each commit focused and use the
[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) form:

```text
type(optional-scope): concise imperative summary
```

Use `feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci`, or `chore` as appropriate. Explain the
reason and compatibility impact in the body when the subject alone is insufficient. Add a concise
entry under `Unreleased` in [CHANGELOG.md](CHANGELOG.md) for user-visible behavior, security,
configuration, or compatibility changes; omit internal-only changes.

By contributing, you agree that your contribution is licensed under the MIT License.

## Releases

Release only from a clean commit on `main` after CI succeeds. Update the version in `pyproject.toml`,
move the user-visible changelog entries into a dated version section, and update both maintained
languages and the fixed image tag in `compose.yaml` together.

Create and push one annotated `vMAJOR.MINOR.PATCH` tag. The Release workflow reruns the full checks,
builds the wheel, source distribution, Compose bundle, checksums, and multi-platform container image,
then creates a Draft GitHub Release. Inspect its tag target, notes, assets, checksums, image digest,
anonymous image pull, clean installation, and first documented result before publishing the draft.
Never move a published version tag; issue a new patch version when a release is wrong.
