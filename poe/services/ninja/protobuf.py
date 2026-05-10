from __future__ import annotations

import struct

from poe.services.ninja.constants import (
    SIGNED_INT64_MAX,
    UNSIGNED_INT64_OVERFLOW,
    WIRE_32BIT,
    WIRE_32BIT_LEN,
    WIRE_64BIT,
    WIRE_64BIT_LEN,
    WIRE_LENGTH_DELIMITED,
    WIRE_VARINT,
)
from poe.services.ninja.errors import NinjaError


class ProtobufDecodeError(NinjaError):
    """Raised when a protobuf payload is truncated or malformed.

    Inherits from NinjaError so callers using `except NinjaError:` catch
    protobuf decode failures alongside HTTP / schema errors. The audit
    found two distinct ProtobufDecodeError classes (a dead one in
    errors.py inheriting from NinjaError and a live one in this module
    inheriting from PoeError directly) — anything catching NinjaError
    missed the live class. Consolidated to a single hierarchy.
    """


def decode_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    start = pos
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            if result > SIGNED_INT64_MAX:
                result -= UNSIGNED_INT64_OVERFLOW
            return result, pos
        shift += 7
    # Ran off the end mid-varint — payload is truncated.
    raise ProtobufDecodeError(f"truncated varint at offset {start}: buffer ends mid-encoding")


def decode_fields(buf: bytes) -> list[tuple[int, int, object]]:
    fields: list[tuple[int, int, object]] = []
    pos = 0
    while pos < len(buf):
        tag, pos = decode_varint(buf, pos)
        wire_type = tag & 0x07
        field_number = tag >> 3

        if wire_type == WIRE_VARINT:
            value, pos = decode_varint(buf, pos)
            fields.append((field_number, wire_type, value))
        elif wire_type == WIRE_LENGTH_DELIMITED:
            length, pos = decode_varint(buf, pos)
            if pos + length > len(buf):
                raise ProtobufDecodeError(
                    f"truncated length-delimited field {field_number}: "
                    f"length={length} exceeds remaining {len(buf) - pos} bytes"
                )
            fields.append((field_number, wire_type, buf[pos : pos + length]))
            pos += length
        elif wire_type == WIRE_64BIT:
            if pos + WIRE_64BIT_LEN > len(buf):
                raise ProtobufDecodeError(f"truncated 64-bit field {field_number} at offset {pos}")
            fields.append((field_number, wire_type, buf[pos : pos + WIRE_64BIT_LEN]))
            pos += WIRE_64BIT_LEN
        elif wire_type == WIRE_32BIT:
            if pos + WIRE_32BIT_LEN > len(buf):
                raise ProtobufDecodeError(f"truncated 32-bit field {field_number} at offset {pos}")
            fields.append((field_number, wire_type, buf[pos : pos + WIRE_32BIT_LEN]))
            pos += WIRE_32BIT_LEN
        else:
            raise ProtobufDecodeError(
                f"unknown wire type {wire_type} for field {field_number} at offset {pos}"
            )
    return fields


def get_varint(fields: list, num: int, default: int = 0) -> int:
    for fn, wt, val in fields:
        if fn == num and wt == WIRE_VARINT:
            return val
    return default


def get_bool(fields: list, num: int, *, default: bool = False) -> bool:
    for fn, wt, val in fields:
        if fn == num and wt == WIRE_VARINT:
            return bool(val)
    return default


def get_string(fields: list, num: int, default: str = "") -> str:
    for fn, wt, val in fields:
        if fn == num and wt == WIRE_LENGTH_DELIMITED:
            return val.decode("utf-8", errors="replace")
    return default


def get_double(fields: list, num: int, default: float = 0.0) -> float:
    for fn, wt, val in fields:
        if fn == num and wt == WIRE_64BIT:
            return struct.unpack("<d", val)[0]
    return default


def get_bytes(fields: list, num: int) -> bytes | None:
    for fn, wt, val in fields:
        if fn == num and wt == WIRE_LENGTH_DELIMITED:
            return val
    return None


def get_all_messages(fields: list, num: int) -> list[bytes]:
    return [val for fn, wt, val in fields if fn == num and wt == WIRE_LENGTH_DELIMITED]


def get_all_strings(fields: list, num: int) -> list[str]:
    return [
        val.decode("utf-8", errors="replace")
        for fn, wt, val in fields
        if fn == num and wt == WIRE_LENGTH_DELIMITED
    ]


def get_all_varints(fields: list, num: int) -> list[int]:
    result: list[int] = []
    for fn, wt, val in fields:
        if fn == num:
            if wt == WIRE_VARINT:
                result.append(val)
            elif wt == WIRE_LENGTH_DELIMITED:
                pos = 0
                while pos < len(val):
                    v, pos = decode_varint(val, pos)
                    result.append(v)
    return result


def get_map_string_string(fields: list, num: int) -> dict[str, str]:
    result: dict[str, str] = {}
    for fn, wt, val in fields:
        if fn == num and wt == WIRE_LENGTH_DELIMITED:
            entry = decode_fields(val)
            key = get_string(entry, 1)
            value = get_string(entry, 2)
            if key:
                result[key] = value
    return result
