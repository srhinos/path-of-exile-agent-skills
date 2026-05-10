from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from poe.constants import VALID_CONFIG_INPUT_TYPES


class ConfigEntry(BaseModel):
    """A single config input: boolean toggle, number, or string value.

    Parsed from PoB XML <Input> elements. input_type determines how
    the value is interpreted (boolean, number, string).
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(min_length=1)
    value: str | float | bool
    input_type: str = "boolean"

    @field_validator("input_type")
    @classmethod
    def _validate_input_type(cls, v: str) -> str:
        if v not in VALID_CONFIG_INPUT_TYPES:
            raise ValueError(
                f"input_type must be one of {sorted(VALID_CONFIG_INPUT_TYPES)}, got {v!r}"
            )
        return v


class BuildConfig(BaseModel):
    """A named set of configuration inputs for a build.

    Builds can have multiple config sets. Returned directly by
    ConfigService.get(). Inputs are the active settings, placeholders
    are default/empty entries shown in the PoB UI.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default="1", min_length=1)
    title: str = "Default"
    inputs: list[ConfigEntry] = []
    placeholders: list[ConfigEntry] = []
