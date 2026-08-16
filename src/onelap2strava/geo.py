from __future__ import annotations

import math

_AXIS = 6_378_245.0
_ECCENTRICITY = 0.00669342162296594323
_INVERSE_TOLERANCE = 1e-7
_INVERSE_ITERATIONS = 10


def is_outside_china(latitude: float, longitude: float) -> bool:
    """Return whether a point is outside the conventional GCJ-02 boundary."""

    return not (72.004 <= longitude <= 137.8347 and 0.8293 <= latitude <= 55.8271)


def _transform_latitude(x: float, y: float) -> float:
    value = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
    value += 0.2 * math.sqrt(abs(x))
    value += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    value += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    value += (
        (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    )
    return value


def _transform_longitude(x: float, y: float) -> float:
    value = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y
    value += 0.1 * math.sqrt(abs(x))
    value += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    value += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    value += (
        (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    )
    return value


def _delta(latitude: float, longitude: float) -> tuple[float, float]:
    delta_latitude = _transform_latitude(longitude - 105.0, latitude - 35.0)
    delta_longitude = _transform_longitude(longitude - 105.0, latitude - 35.0)
    radians = latitude / 180.0 * math.pi
    magic = math.sin(radians)
    magic = 1 - _ECCENTRICITY * magic * magic
    root = math.sqrt(magic)
    delta_latitude = (
        delta_latitude * 180.0 / ((_AXIS * (1 - _ECCENTRICITY)) / (magic * root) * math.pi)
    )
    delta_longitude = delta_longitude * 180.0 / (_AXIS / root * math.cos(radians) * math.pi)
    return delta_latitude, delta_longitude


def wgs84_to_gcj02(latitude: float, longitude: float) -> tuple[float, float]:
    """Convert WGS84 coordinates to GCJ-02 coordinates."""

    if is_outside_china(latitude, longitude):
        return latitude, longitude
    delta_latitude, delta_longitude = _delta(latitude, longitude)
    return latitude + delta_latitude, longitude + delta_longitude


def gcj02_to_wgs84(latitude: float, longitude: float) -> tuple[float, float]:
    """Convert GCJ-02 coordinates to WGS84 using an iterative inverse."""

    if is_outside_china(latitude, longitude):
        return latitude, longitude

    guess_latitude = latitude
    guess_longitude = longitude
    for _ in range(_INVERSE_ITERATIONS):
        converted_latitude, converted_longitude = wgs84_to_gcj02(guess_latitude, guess_longitude)
        error_latitude = converted_latitude - latitude
        error_longitude = converted_longitude - longitude
        guess_latitude -= error_latitude
        guess_longitude -= error_longitude
        if max(abs(error_latitude), abs(error_longitude)) < _INVERSE_TOLERANCE:
            break
    return guess_latitude, guess_longitude
