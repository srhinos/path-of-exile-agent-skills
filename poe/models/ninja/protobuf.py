from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict

from poe.services.ninja.protobuf import (
    decode_fields,
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


class DimensionCount(BaseModel):
    """A single key→count entry within a dimension."""

    model_config = ConfigDict(validate_assignment=True)

    key: int = 0
    count: int = 0

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(key=get_varint(f, 1), count=get_varint(f, 2))


class Dimension(BaseModel):
    """Categorical dimension with per-value counts and dictionary reference."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    dictionary_id: str = ""
    counts: list[DimensionCount] = []

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            id=get_string(f, 1),
            dictionary_id=get_string(f, 2),
            counts=[DimensionCount.from_protobuf(m) for m in get_all_messages(f, 3)],
        )


class IntegerDimension(BaseModel):
    """Numeric stat range (level, life, ES, etc.)."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    min_value: int = 0
    max_value: int = 0

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            id=get_string(f, 1),
            min_value=get_varint(f, 2),
            max_value=get_varint(f, 3),
        )


class PerformancePoint(BaseModel):
    """Server-side timing data."""

    model_config = ConfigDict(validate_assignment=True)

    name: str = ""
    ms: float = 0.0

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(name=get_string(f, 1), ms=get_double(f, 2))


class SearchValue(BaseModel):
    """A single value in a per-character result array."""

    model_config = ConfigDict(validate_assignment=True)

    str_val: str = ""
    number: int = 0
    numbers: list[int] = []
    strs: list[str] = []
    boolean: bool = False

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            str_val=get_string(f, 1),
            number=get_varint(f, 2),
            numbers=get_all_varints(f, 3),
            strs=get_all_strings(f, 4),
            boolean=get_bool(f, 5),
        )


class ValueList(BaseModel):
    """Per-character result array (names, accounts, stats)."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    values: list[SearchValue] = []

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            id=get_string(f, 1),
            values=[SearchValue.from_protobuf(m) for m in get_all_messages(f, 2)],
        )


class DictionaryReference(BaseModel):
    """Hash reference for a string lookup table."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    hash: str = ""

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(id=get_string(f, 1), hash=get_string(f, 2))


class SearchField(BaseModel):
    """UI column metadata from search response."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    type: str = ""
    name: str = ""
    value_list_ids: list[str] = []
    sort_id: str = ""
    integer_dimension_id: str = ""
    properties: dict[str, str] = {}
    main_field_id: str = ""
    description: str = ""
    group: str = ""
    pinned: bool = False

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            id=get_string(f, 1),
            type=get_string(f, 2),
            name=get_string(f, 3),
            value_list_ids=get_all_strings(f, 4),
            sort_id=get_string(f, 5),
            integer_dimension_id=get_string(f, 6),
            properties=get_map_string_string(f, 7),
            main_field_id=get_string(f, 8),
            description=get_string(f, 9),
            group=get_string(f, 10),
            pinned=get_bool(f, 11),
        )


class FieldDescriptor(BaseModel):
    """Column descriptor for UI rendering."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    name: str = ""
    optional: bool = False
    description: str = ""
    group: str = ""
    pinned: bool = False

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            id=get_string(f, 1),
            name=get_string(f, 2),
            optional=get_bool(f, 3),
            description=get_string(f, 4),
            group=get_string(f, 5),
            pinned=get_bool(f, 6),
        )


class Section(BaseModel):
    """UI section metadata."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    type: str = ""
    name: str = ""
    dimension_id: str = ""
    properties: dict[str, str] = {}

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            id=get_string(f, 1),
            type=get_string(f, 2),
            name=get_string(f, 3),
            dimension_id=get_string(f, 4),
            properties=get_map_string_string(f, 5),
        )


class SearchResult(BaseModel):
    """Full decoded builds/atlas search response."""

    model_config = ConfigDict(validate_assignment=True)

    total: int = 0
    dimensions: list[Dimension] = []
    integer_dimensions: list[IntegerDimension] = []
    performance_points: list[PerformancePoint] = []
    value_lists: list[ValueList] = []
    dictionaries: list[DictionaryReference] = []
    fields: list[SearchField] = []
    sections: list[Section] = []
    field_descriptors: list[FieldDescriptor] = []
    default_field_ids: list[str] = []

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            total=get_varint(f, 1),
            dimensions=[Dimension.from_protobuf(m) for m in get_all_messages(f, 2)],
            integer_dimensions=[IntegerDimension.from_protobuf(m) for m in get_all_messages(f, 3)],
            performance_points=[PerformancePoint.from_protobuf(m) for m in get_all_messages(f, 4)],
            value_lists=[ValueList.from_protobuf(m) for m in get_all_messages(f, 5)],
            dictionaries=[DictionaryReference.from_protobuf(m) for m in get_all_messages(f, 6)],
            fields=[SearchField.from_protobuf(m) for m in get_all_messages(f, 7)],
            sections=[Section.from_protobuf(m) for m in get_all_messages(f, 8)],
            field_descriptors=[FieldDescriptor.from_protobuf(m) for m in get_all_messages(f, 9)],
            default_field_ids=get_all_strings(f, 10),
        )


class NinjaSearchResult(BaseModel):
    """Top-level wrapper for builds/atlas search protobuf responses."""

    model_config = ConfigDict(validate_assignment=True)

    result: SearchResult | None = None

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        result_data = get_bytes(f, 1)
        return cls(
            result=SearchResult.from_protobuf(result_data) if result_data else None,
        )


class DictionaryProperty(BaseModel):
    """Per-value metadata column in a dictionary (e.g., color, type)."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    values: list[str] = []

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(id=get_string(f, 1), values=get_all_strings(f, 2))


class Dictionary(BaseModel):
    """String lookup table fetched by hash, used to resolve dimension keys."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = ""
    values: list[str] = []
    properties: list[DictionaryProperty] = []

    @classmethod
    def from_protobuf(cls, data: bytes) -> Self:
        f = decode_fields(data)
        return cls(
            id=get_string(f, 1),
            values=get_all_strings(f, 2),
            properties=[DictionaryProperty.from_protobuf(m) for m in get_all_messages(f, 3)],
        )
