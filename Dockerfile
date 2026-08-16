FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md README.zh-CN.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels ".[bot]"

FROM python:3.13-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ONELAP2STRAVA_CONFIG=/data/config.toml \
    ONELAP2STRAVA_STATE=/data/bot-state.json

RUN useradd --create-home --uid 10001 app
COPY --from=builder /wheels /wheels
RUN python -m pip install /wheels/*.whl && rm -rf /wheels

USER app
WORKDIR /data
ENTRYPOINT ["onelap2strava"]
CMD ["bot"]
