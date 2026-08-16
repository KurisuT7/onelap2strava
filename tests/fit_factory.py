from __future__ import annotations

import struct

from onelap2strava.fit import fit_crc
from onelap2strava.geo import wgs84_to_gcj02

SEMICIRCLES = 2_147_483_648.0


def to_semicircles(value: float) -> int:
    return round(value * SEMICIRCLES / 180.0)


def make_fit(
    *,
    latitude: float = 39.908823,
    longitude: float = 116.39747,
    compressed: bool = False,
    big_endian: bool = False,
    gcj_input: bool = True,
    include_session: bool = False,
) -> bytes:
    if gcj_input:
        latitude, longitude = wgs84_to_gcj02(latitude, longitude)
    endian = ">" if big_endian else "<"
    architecture = 1 if big_endian else 0
    definition = bytearray([0x40, 0, architecture])
    definition.extend(struct.pack(f"{endian}H", 20))
    definition.append(3)
    definition.extend([253, 4, 0x86])
    definition.extend([0, 4, 0x85])
    definition.extend([1, 4, 0x85])

    if compressed:
        record = bytearray([0x81])
    else:
        record = bytearray([0x00])
        record.extend(struct.pack(f"{endian}I", 1_000_000_000))
    record.extend(struct.pack(f"{endian}i", to_semicircles(latitude)))
    record.extend(struct.pack(f"{endian}i", to_semicircles(longitude)))
    message_data = definition + record

    if include_session:
        session_definition = bytearray([0x41, 0, architecture])
        session_definition.extend(struct.pack(f"{endian}H", 18))
        session_definition.append(8)
        for field_number in (3, 4, 29, 30, 31, 32, 38, 39):
            session_definition.extend([field_number, 4, 0x85])
        session = bytearray([0x01])
        for _ in range(4):
            session.extend(struct.pack(f"{endian}i", to_semicircles(latitude)))
            session.extend(struct.pack(f"{endian}i", to_semicircles(longitude)))
        message_data += session_definition + session

    header = bytearray(14)
    header[0] = 14
    header[1] = 0x20
    struct.pack_into("<H", header, 2, 2100)
    struct.pack_into("<I", header, 4, len(message_data))
    header[8:12] = b".FIT"
    struct.pack_into("<H", header, 12, fit_crc(header[:12]))
    body = header + message_data
    return bytes(body + struct.pack("<H", fit_crc(body)))


def read_record_coordinates(
    data: bytes, *, compressed: bool, big_endian: bool
) -> tuple[float, float]:
    endian = ">" if big_endian else "<"
    definition_size = 1 + 5 + 3 * 3
    record_start = 14 + definition_size + 1
    if not compressed:
        record_start += 4
    latitude = struct.unpack_from(f"{endian}i", data, record_start)[0]
    longitude = struct.unpack_from(f"{endian}i", data, record_start + 4)[0]
    return latitude * 180.0 / SEMICIRCLES, longitude * 180.0 / SEMICIRCLES
