from __future__ import annotations

from pathlib import Path

import pytest

from poe.models.ninja.protobuf import Dictionary, NinjaSearchResult
from poe.services.ninja.protobuf import (
    decode_fields,
    decode_varint,
    get_all_messages,
    get_all_strings,
    get_all_varints,
    get_bool,
    get_bytes,
    get_double,
    get_map_string_string,
    get_string,
    get_varint,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestDecodeVarint:
    def test_single_byte(self):
        val, pos = decode_varint(b"\x05", 0)
        assert val == 5
        assert pos == 1

    def test_multi_byte(self):
        val, pos = decode_varint(b"\xac\x02", 0)
        assert val == 300
        assert pos == 2

    def test_with_offset(self):
        val, pos = decode_varint(b"\x00\x05", 1)
        assert val == 5
        assert pos == 2

    def test_zero(self):
        val, pos = decode_varint(b"\x00", 0)
        assert val == 0
        assert pos == 1


class TestDecodeFields:
    def test_varint_field(self):
        # field 1, wire type 0, value 150 -> tag=0x08, varint=0x96 0x01
        fields = decode_fields(b"\x08\x96\x01")
        assert len(fields) == 1
        fn, wt, val = fields[0]
        assert fn == 1
        assert wt == 0
        assert val == 150

    def test_string_field(self):
        # field 2, wire type 2, "testing"
        data = b"\x12\x07testing"
        fields = decode_fields(data)
        assert len(fields) == 1
        fn, wt, val = fields[0]
        assert fn == 2
        assert wt == 2
        assert val == b"testing"

    def test_multiple_fields(self):
        data = b"\x08\x01\x12\x03abc"
        fields = decode_fields(data)
        assert len(fields) == 2

    def test_empty_buffer(self):
        assert decode_fields(b"") == []


class TestHelpers:
    def test_get_varint(self):
        fields = decode_fields(b"\x08\x2a")
        assert get_varint(fields, 1) == 42
        assert get_varint(fields, 2) == 0
        assert get_varint(fields, 2, 99) == 99

    def test_get_bool(self):
        fields = decode_fields(b"\x08\x01")
        assert get_bool(fields, 1) is True
        assert get_bool(fields, 2) is False

    def test_get_string(self):
        fields = decode_fields(b"\x12\x05hello")
        assert get_string(fields, 2) == "hello"
        assert get_string(fields, 3) == ""
        assert get_string(fields, 3, "default") == "default"

    def test_get_double(self):
        import struct

        double_bytes = struct.pack("<d", 12.5)
        # field 2, wire type 1
        data = b"\x11" + double_bytes
        fields = decode_fields(data)
        assert get_double(fields, 2) == 12.5
        assert get_double(fields, 3) == 0.0

    def test_get_bytes(self):
        fields = decode_fields(b"\x12\x03abc")
        assert get_bytes(fields, 2) == b"abc"
        assert get_bytes(fields, 3) is None

    def test_get_all_messages(self):
        data = b"\x12\x01a\x12\x01b"
        fields = decode_fields(data)
        msgs = get_all_messages(fields, 2)
        assert len(msgs) == 2
        assert msgs[0] == b"a"
        assert msgs[1] == b"b"

    def test_get_all_strings(self):
        data = b"\x12\x03foo\x12\x03bar"
        fields = decode_fields(data)
        assert get_all_strings(fields, 2) == ["foo", "bar"]

    def test_get_all_varints_unpacked(self):
        data = b"\x08\x01\x08\x02\x08\x03"
        fields = decode_fields(data)
        assert get_all_varints(fields, 1) == [1, 2, 3]

    def test_get_all_varints_packed(self):
        # field 3, wire type 2, packed varints [1, 2, 3]
        data = b"\x1a\x03\x01\x02\x03"
        fields = decode_fields(data)
        assert get_all_varints(fields, 3) == [1, 2, 3]

    def test_get_map_string_string(self):
        # map entry: field 7, wire type 2, containing field 1="key" and field 2="val"
        entry = b"\x0a\x03key\x12\x03val"
        data = b"\x3a" + bytes([len(entry)]) + entry
        fields = decode_fields(data)
        assert get_map_string_string(fields, 7) == {"key": "val"}


class TestNinjaSearchResult:
    def test_decode_fixture(self):
        data = (FIXTURES / "search_result.bin").read_bytes()
        msg = NinjaSearchResult.from_protobuf(data)

        assert msg.result is not None
        assert msg.result.total == 124428
        assert len(msg.result.dimensions) == 2
        assert msg.result.dimensions[0].id == "class"
        assert msg.result.dimensions[0].dictionary_id == "dict-class"
        assert len(msg.result.dimensions[0].counts) == 2
        assert msg.result.dimensions[0].counts[0].key == 0
        assert msg.result.dimensions[0].counts[0].count == 15234

    def test_integer_dimensions(self):
        data = (FIXTURES / "search_result.bin").read_bytes()
        msg = NinjaSearchResult.from_protobuf(data)

        assert len(msg.result.integer_dimensions) == 2
        level_dim = msg.result.integer_dimensions[0]
        assert level_dim.id == "level"
        assert level_dim.min_value == 70
        assert level_dim.max_value == 100

    def test_dictionary_references(self):
        data = (FIXTURES / "search_result.bin").read_bytes()
        msg = NinjaSearchResult.from_protobuf(data)

        assert len(msg.result.dictionaries) == 2
        assert msg.result.dictionaries[0].id == "dict-class"
        assert msg.result.dictionaries[0].hash == "abc123"

    def test_value_lists(self):
        data = (FIXTURES / "search_result.bin").read_bytes()
        msg = NinjaSearchResult.from_protobuf(data)

        assert len(msg.result.value_lists) == 1
        vl = msg.result.value_lists[0]
        assert vl.id == "names"
        assert len(vl.values) == 2
        assert vl.values[0].str_val == "TestChar1"

    def test_fields_and_sections(self):
        data = (FIXTURES / "search_result.bin").read_bytes()
        msg = NinjaSearchResult.from_protobuf(data)

        assert len(msg.result.fields) == 1
        assert msg.result.fields[0].id == "name"
        assert len(msg.result.sections) == 1
        assert msg.result.sections[0].id == "main"
        assert len(msg.result.field_descriptors) == 1
        assert msg.result.default_field_ids == ["name"]

    def test_performance_points(self):
        data = (FIXTURES / "search_result.bin").read_bytes()
        msg = NinjaSearchResult.from_protobuf(data)

        assert len(msg.result.performance_points) == 1
        assert msg.result.performance_points[0].name == "query"
        assert msg.result.performance_points[0].ms == 12.5

    def test_empty_message(self):
        msg = NinjaSearchResult.from_protobuf(b"")
        assert msg.result is None

    def test_is_pydantic(self):
        from pydantic import BaseModel

        assert issubclass(NinjaSearchResult, BaseModel)
        msg = NinjaSearchResult.from_protobuf(b"")
        assert isinstance(msg, BaseModel)

    def test_serializes_to_json(self):
        data = (FIXTURES / "search_result.bin").read_bytes()
        msg = NinjaSearchResult.from_protobuf(data)
        json_str = msg.model_dump_json()
        assert "124428" in json_str
        assert "dict-class" in json_str


class TestDictionary:
    def test_decode_fixture(self):
        data = (FIXTURES / "dictionary.bin").read_bytes()
        d = Dictionary.from_protobuf(data)

        assert d.id == "class"
        assert d.values == ["Pathfinder", "Necromancer", "Deadeye", "Champion"]
        assert len(d.properties) == 1
        assert d.properties[0].id == "color"
        assert len(d.properties[0].values) == 4

    def test_is_pydantic(self):
        from pydantic import BaseModel

        assert issubclass(Dictionary, BaseModel)


class TestVarintSignedInt64Boundary:
    def test_signed_int64_max_returns_unchanged(self):
        # SIGNED_INT64_MAX = 0x7FFF_FFFF_FFFF_FFFF — the largest non-negative
        # value representable as int64. It must NOT trigger the overflow path.
        from poe.services.ninja.constants import SIGNED_INT64_MAX

        encoded = _encode_varint(SIGNED_INT64_MAX)
        val, _ = decode_varint(encoded, 0)
        assert val == SIGNED_INT64_MAX

    def test_just_above_signed_int64_max_treated_as_negative(self):
        # SIGNED_INT64_MAX + 1 should wrap to -SIGNED_INT64_MAX-1 (i.e. INT64_MIN).
        from poe.services.ninja.constants import (
            SIGNED_INT64_MAX,
            UNSIGNED_INT64_OVERFLOW,
        )

        encoded = _encode_varint(SIGNED_INT64_MAX + 1)
        val, _ = decode_varint(encoded, 0)
        assert val == (SIGNED_INT64_MAX + 1) - UNSIGNED_INT64_OVERFLOW
        assert val < 0

    def test_negative_one_wire_encoding(self):
        # uint64 encoding of -1 is 0xFFFF_FFFF_FFFF_FFFF.
        from poe.services.ninja.constants import UNSIGNED_INT64_OVERFLOW

        encoded = _encode_varint(UNSIGNED_INT64_OVERFLOW - 1)
        val, _ = decode_varint(encoded, 0)
        assert val == -1


class TestVarintParametrized:
    @pytest.mark.parametrize(
        ("encoded", "expected_val", "expected_pos"),
        [
            (b"\x00", 0, 1),
            (b"\x01", 1, 1),
            (b"\x7f", 127, 1),
            (b"\x80\x01", 128, 2),
            (b"\xff\x01", 255, 2),
            (b"\xac\x02", 300, 2),
            (b"\xff\xff\xff\xff\x07", 2**31 - 1, 5),
        ],
    )
    def test_varint_decode(self, encoded, expected_val, expected_pos):
        val, pos = decode_varint(encoded, 0)
        assert val == expected_val
        assert pos == expected_pos


class TestDecodeFieldsInvariants:
    def test_unknown_wire_type_breaks_loop(self):
        # Wire type 3 (start group, deprecated) and 4 (end group) break the loop.
        # Using 0x1B = field 3 wire type 3, then garbage.
        data = b"\x08\x01\x1b\xff\xff"
        fields = decode_fields(data)
        # Should have decoded the first field then broken on unknown wire type.
        assert len(fields) == 1
        fn, _, _ = fields[0]
        assert fn == 1

    def test_field_numbers_preserved(self):
        # field 1 = varint, field 2 = string, field 3 = varint
        data = b"\x08\x01\x12\x03foo\x18\x02"
        fields = decode_fields(data)
        field_nums = [f[0] for f in fields]
        assert field_nums == [1, 2, 3]

    def test_64bit_wire_type(self):
        # field 4 (0x21 = 4<<3 | 1), 8 bytes payload
        data = b"\x21" + b"\x00\x00\x00\x00\x00\x00\xf0\x3f"  # double 1.0
        fields = decode_fields(data)
        assert len(fields) == 1
        fn, wt, val = fields[0]
        assert fn == 4
        assert wt == 1
        assert len(val) == 8

    def test_32bit_wire_type(self):
        # field 5 (0x2d = 5<<3 | 5), 4 bytes payload
        data = b"\x2d\x01\x02\x03\x04"
        fields = decode_fields(data)
        assert len(fields) == 1
        fn, wt, val = fields[0]
        assert fn == 5
        assert wt == 5
        assert len(val) == 4


class TestHelpersDefaults:
    def test_get_varint_default_when_field_missing(self):
        fields = decode_fields(b"")
        assert get_varint(fields, 99, default=42) == 42

    def test_get_bool_default_when_field_missing(self):
        fields = decode_fields(b"")
        assert get_bool(fields, 99) is False
        assert get_bool(fields, 99, default=True) is True

    def test_get_string_default_when_field_missing(self):
        fields = decode_fields(b"")
        assert get_string(fields, 99) == ""
        assert get_string(fields, 99, default="fallback") == "fallback"

    def test_get_double_default_when_field_missing(self):
        fields = decode_fields(b"")
        assert get_double(fields, 99) == 0.0
        assert get_double(fields, 99, default=3.14) == 3.14

    def test_get_bytes_returns_none_when_missing(self):
        fields = decode_fields(b"")
        assert get_bytes(fields, 99) is None

    def test_get_all_messages_empty_when_missing(self):
        fields = decode_fields(b"")
        assert get_all_messages(fields, 99) == []

    def test_get_all_strings_empty_when_missing(self):
        fields = decode_fields(b"")
        assert get_all_strings(fields, 99) == []

    def test_get_all_varints_empty_when_missing(self):
        fields = decode_fields(b"")
        assert get_all_varints(fields, 99) == []

    def test_get_map_string_string_empty_when_missing(self):
        fields = decode_fields(b"")
        assert get_map_string_string(fields, 99) == {}


class TestHelpersWireTypeFiltering:
    def test_get_varint_ignores_other_wire_types(self):
        # field 1 is a string, not a varint — get_varint must return default.
        fields = decode_fields(b"\x0a\x03foo")
        assert get_varint(fields, 1, default=99) == 99

    def test_get_string_ignores_other_wire_types(self):
        # field 1 is a varint, not a string.
        fields = decode_fields(b"\x08\x01")
        assert get_string(fields, 1, default="x") == "x"

    def test_get_double_ignores_wrong_wire_type(self):
        # field 1 is varint, not 64-bit.
        fields = decode_fields(b"\x08\x01")
        assert get_double(fields, 1, default=9.9) == 9.9


class TestStringInvalidUtf8:
    def test_get_string_replaces_invalid_utf8(self):
        # \xff is not valid UTF-8 start byte.
        fields = decode_fields(b"\x12\x01\xff")
        s = get_string(fields, 2)
        # errors="replace" — should produce a U+FFFD replacement char.
        assert s == "�"

    def test_get_all_strings_replaces_invalid_utf8(self):
        fields = decode_fields(b"\x12\x01\xff")
        ss = get_all_strings(fields, 2)
        assert ss == ["�"]


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)
