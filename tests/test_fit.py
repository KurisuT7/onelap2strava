from __future__ import annotations

import struct

import pytest

from onelap2strava.errors import FitError
from onelap2strava.fit import convert_fit_bytes, convert_fit_file, fit_crc

from .fit_factory import make_fit, read_record_coordinates


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("big_endian", [False, True])
def test_conversion_preserves_valid_fit_container(compressed: bool, big_endian: bool) -> None:
    source = make_fit(compressed=compressed, big_endian=big_endian)

    converted, result = convert_fit_bytes(source)
    latitude, longitude = read_record_coordinates(
        converted, compressed=compressed, big_endian=big_endian
    )

    assert (latitude, longitude) == pytest.approx((39.908823, 116.39747), abs=2e-7)
    assert result.record_points == 1
    assert result.metadata_pairs == 0
    assert result.adjusted_pairs == 1
    assert struct.unpack_from("<H", converted, len(converted) - 2)[0] == fit_crc(converted[:-2])


def test_outside_china_is_valid_but_not_adjusted() -> None:
    source = make_fit(latitude=48.8566, longitude=2.3522, gcj_input=False)

    converted, result = convert_fit_bytes(source)

    assert converted == source
    assert result.record_points == 1
    assert result.adjusted_pairs == 0


def test_session_coordinate_summaries_are_converted() -> None:
    source = make_fit(include_session=True)

    converted, result = convert_fit_bytes(source)

    assert converted != source
    assert result.record_points == 1
    assert result.metadata_pairs == 4
    assert result.adjusted_pairs == 5


def test_rejects_bad_file_crc() -> None:
    source = bytearray(make_fit())
    source[-1] ^= 0xFF

    with pytest.raises(FitError, match="file CRC"):
        convert_fit_bytes(source)


def test_rejects_trailing_data() -> None:
    with pytest.raises(FitError, match="trailing"):
        convert_fit_bytes(make_fit() + b"extra")


def test_atomic_file_conversion_and_overwrite_guard(tmp_path) -> None:
    source = tmp_path / "ride.fit"
    target = tmp_path / "ride.wgs84.fit"
    source.write_bytes(make_fit())

    result = convert_fit_file(source, target)

    assert target.is_file()
    assert result.adjusted_pairs == 1
    with pytest.raises(FitError, match="already exists"):
        convert_fit_file(source, target)


def test_official_garmin_sdk_accepts_converted_file() -> None:
    garmin_fit_sdk = pytest.importorskip("garmin_fit_sdk")
    converted, _ = convert_fit_bytes(make_fit())
    stream = garmin_fit_sdk.Stream.from_byte_array(bytearray(converted))
    decoder = garmin_fit_sdk.Decoder(stream)

    assert decoder.check_integrity()
