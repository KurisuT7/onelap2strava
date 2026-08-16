from __future__ import annotations

import pytest

from onelap2strava.geo import gcj02_to_wgs84, is_outside_china, wgs84_to_gcj02


def test_gcj_inverse_round_trip() -> None:
    wgs84 = (39.908823, 116.39747)
    gcj02 = wgs84_to_gcj02(*wgs84)
    restored = gcj02_to_wgs84(*gcj02)

    assert gcj02 != wgs84
    assert restored == pytest.approx(wgs84, abs=1e-7)


def test_coordinates_outside_china_are_unchanged() -> None:
    paris = (48.8566, 2.3522)

    assert is_outside_china(*paris)
    assert wgs84_to_gcj02(*paris) == paris
    assert gcj02_to_wgs84(*paris) == paris
