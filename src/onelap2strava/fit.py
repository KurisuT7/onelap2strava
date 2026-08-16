from __future__ import annotations

import os
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import FitError
from .geo import gcj02_to_wgs84

_CRC_TABLE = (
    0x0000,
    0xCC01,
    0xD801,
    0x1400,
    0xF001,
    0x3C00,
    0x2800,
    0xE401,
    0xA001,
    0x6C00,
    0x7800,
    0xB401,
    0x5000,
    0x9C01,
    0x8801,
    0x4400,
)
_SEMICIRCLES = 2_147_483_648.0
_INVALID_SINT32 = {-2_147_483_648, 2_147_483_647}
_SINT32_BASE_TYPE = 5
_TIMESTAMP_FIELD = 253


@dataclass(frozen=True)
class ConversionResult:
    record_points: int
    metadata_pairs: int
    adjusted_pairs: int
    crc: str


@dataclass(frozen=True)
class _Field:
    number: int
    size: int
    base_type: int


@dataclass(frozen=True)
class _Definition:
    global_message: int
    endian: str
    fields: tuple[_Field, ...]
    developer_size: int

    @property
    def payload_size(self) -> int:
        return sum(field.size for field in self.fields) + self.developer_size

    def field(self, number: int) -> _Field | None:
        return next((field for field in self.fields if field.number == number), None)

    def field_offset(self, number: int, compressed_timestamp: bool) -> int | None:
        offset = 0
        for field in self.fields:
            if compressed_timestamp and field.number == _TIMESTAMP_FIELD:
                continue
            if field.number == number:
                return offset
            offset += field.size
        return None

    def message_size(self, compressed_timestamp: bool) -> int:
        size = self.payload_size
        if compressed_timestamp:
            timestamp = self.field(_TIMESTAMP_FIELD)
            if timestamp is None or timestamp.size != 4:
                raise FitError("Compressed timestamp message has no 4-byte timestamp field")
            size -= timestamp.size
        return size


def fit_crc(data: bytes | bytearray | memoryview) -> int:
    crc = 0
    for byte in data:
        value = _CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ value ^ _CRC_TABLE[byte & 0xF]
        value = _CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ value ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc & 0xFFFF


def _require(position: int, size: int, end: int, context: str) -> None:
    if position < 0 or size < 0 or position + size > end:
        raise FitError(f"FIT file is truncated while reading {context}")


def _read_u16(data: bytearray, position: int, endian: str) -> int:
    return int(struct.unpack_from(f"{endian}H", data, position)[0])


def _read_i32(data: bytearray, position: int, endian: str) -> int:
    return int(struct.unpack_from(f"{endian}i", data, position)[0])


def _write_i32(data: bytearray, position: int, value: int, endian: str) -> None:
    struct.pack_into(f"{endian}i", data, position, value)


def _semicircles_to_degrees(value: int) -> float:
    return value * 180.0 / _SEMICIRCLES


def _degrees_to_semicircles(value: float) -> int:
    converted = round(value * _SEMICIRCLES / 180.0)
    return max(-2_147_483_648, min(2_147_483_647, converted))


def _validate_container(data: bytearray) -> tuple[int, int]:
    if len(data) < 14:
        raise FitError("FIT file is too small")
    header_size = data[0]
    if header_size not in {12, 14}:
        raise FitError(f"Unsupported FIT header size: {header_size}")
    if bytes(data[8:12]) != b".FIT":
        raise FitError("Input is not a FIT file")
    if header_size == 14:
        stored_header_crc = struct.unpack_from("<H", data, 12)[0]
        calculated_header_crc = fit_crc(data[:12])
        if stored_header_crc != calculated_header_crc:
            raise FitError("FIT header CRC check failed")

    data_size = struct.unpack_from("<I", data, 4)[0]
    expected_size = header_size + data_size + 2
    if len(data) != expected_size:
        if len(data) < expected_size:
            raise FitError("FIT file is truncated")
        raise FitError("Chained or trailing FIT data is not supported")

    stored_file_crc = struct.unpack_from("<H", data, header_size + data_size)[0]
    calculated_file_crc = fit_crc(data[: header_size + data_size])
    if stored_file_crc != calculated_file_crc:
        raise FitError("FIT file CRC check failed")
    return header_size, data_size


def _coordinate_pairs(global_message: int) -> tuple[tuple[int, int, bool], ...]:
    if global_message == 20:  # record
        return ((0, 1, True),)
    if global_message == 19:  # lap
        return ((3, 4, False), (5, 6, False))
    if global_message == 18:  # session
        return (
            (3, 4, False),
            (29, 30, False),
            (31, 32, False),
            (38, 39, False),
        )
    return ()


def convert_fit_bytes(source: bytes | bytearray) -> tuple[bytes, ConversionResult]:
    """Convert every supported GCJ-02 coordinate pair in a FIT byte stream."""

    data = bytearray(source)
    header_size, data_size = _validate_container(data)
    definitions: dict[int, _Definition] = {}
    position = header_size
    data_end = header_size + data_size
    record_points = 0
    metadata_pairs = 0
    adjusted_pairs = 0

    while position < data_end:
        _require(position, 1, data_end, "message header")
        message_header = data[position]
        position += 1
        compressed_timestamp = bool(message_header & 0x80)

        if compressed_timestamp:
            local_message = (message_header >> 5) & 0x03
            is_definition = False
            has_developer_fields = False
        else:
            if message_header & 0x10:
                raise FitError("Reserved FIT message header bit is set")
            local_message = message_header & 0x0F
            is_definition = bool(message_header & 0x40)
            has_developer_fields = bool(message_header & 0x20)

        if is_definition:
            _require(position, 5, data_end, "definition message")
            architecture = data[position + 1]
            if architecture not in {0, 1}:
                raise FitError(f"Unsupported FIT architecture: {architecture}")
            endian = ">" if architecture == 1 else "<"
            global_message = _read_u16(data, position + 2, endian)
            field_count = data[position + 4]
            position += 5
            _require(position, field_count * 3, data_end, "field definitions")
            fields = []
            for _ in range(field_count):
                fields.append(_Field(data[position], data[position + 1], data[position + 2]))
                position += 3

            developer_size = 0
            if has_developer_fields:
                _require(position, 1, data_end, "developer field count")
                developer_count = data[position]
                position += 1
                _require(position, developer_count * 3, data_end, "developer fields")
                for _ in range(developer_count):
                    developer_size += data[position + 1]
                    position += 3

            definitions[local_message] = _Definition(
                global_message=global_message,
                endian=endian,
                fields=tuple(fields),
                developer_size=developer_size,
            )
            continue

        definition = definitions.get(local_message)
        if definition is None:
            raise FitError(f"Data message uses undefined local message {local_message}")
        message_size = definition.message_size(compressed_timestamp)
        _require(position, message_size, data_end, "data message")
        message_start = position

        for latitude_number, longitude_number, is_record in _coordinate_pairs(
            definition.global_message
        ):
            latitude_field = definition.field(latitude_number)
            longitude_field = definition.field(longitude_number)
            if latitude_field is None or longitude_field is None:
                continue
            if (
                latitude_field.size != 4
                or longitude_field.size != 4
                or latitude_field.base_type & 0x1F != _SINT32_BASE_TYPE
                or longitude_field.base_type & 0x1F != _SINT32_BASE_TYPE
            ):
                continue
            latitude_offset = definition.field_offset(latitude_number, compressed_timestamp)
            longitude_offset = definition.field_offset(longitude_number, compressed_timestamp)
            if latitude_offset is None or longitude_offset is None:
                continue

            latitude_position = message_start + latitude_offset
            longitude_position = message_start + longitude_offset
            latitude_raw = _read_i32(data, latitude_position, definition.endian)
            longitude_raw = _read_i32(data, longitude_position, definition.endian)
            if latitude_raw in _INVALID_SINT32 or longitude_raw in _INVALID_SINT32:
                continue
            latitude = _semicircles_to_degrees(latitude_raw)
            longitude = _semicircles_to_degrees(longitude_raw)
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                continue

            converted_latitude, converted_longitude = gcj02_to_wgs84(latitude, longitude)
            converted_latitude_raw = _degrees_to_semicircles(converted_latitude)
            converted_longitude_raw = _degrees_to_semicircles(converted_longitude)
            _write_i32(data, latitude_position, converted_latitude_raw, definition.endian)
            _write_i32(data, longitude_position, converted_longitude_raw, definition.endian)
            if converted_latitude_raw != latitude_raw or converted_longitude_raw != longitude_raw:
                adjusted_pairs += 1
            if is_record:
                record_points += 1
            else:
                metadata_pairs += 1

        position += message_size

    if position != data_end:
        raise FitError("FIT message data does not end at the declared boundary")
    if record_points == 0:
        raise FitError("No record coordinates were found")

    new_crc = fit_crc(data[:data_end])
    struct.pack_into("<H", data, data_end, new_crc)
    result = ConversionResult(
        record_points=record_points,
        metadata_pairs=metadata_pairs,
        adjusted_pairs=adjusted_pairs,
        crc=f"0x{new_crc:04x}",
    )
    return bytes(data), result


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def convert_fit_file(
    source: str | Path,
    target: str | Path,
    *,
    overwrite: bool = False,
) -> ConversionResult:
    """Convert a FIT file and atomically write the result."""

    source_path = Path(source)
    target_path = Path(target)
    if not source_path.is_file():
        raise FitError(f"Input file does not exist: {source_path}")
    same_file = source_path.resolve() == target_path.resolve()
    if target_path.exists() and not overwrite:
        raise FitError(f"Output file already exists: {target_path}")
    if same_file and not overwrite:
        raise FitError("Refusing to replace the input file without overwrite=True")
    converted, result = convert_fit_bytes(source_path.read_bytes())
    _atomic_write(target_path, converted)
    return result
