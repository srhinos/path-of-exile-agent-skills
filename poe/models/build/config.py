from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ConfigEntry(BaseModel):
    """A single config input: boolean toggle, number, or string value.

    Parsed from PoB XML <Input> elements. input_type determines how
    the value is interpreted (boolean, number, string).
    """

    model_config = ConfigDict(validate_assignment=True)

    name: str
    value: str | float | bool
    input_type: str = "boolean"


class BuildConfig(BaseModel):
    """A named set of configuration inputs for a build.

    Builds can have multiple config sets. Returned directly by
    ConfigService.get(). Inputs are the active settings, placeholders
    are default/empty entries shown in the PoB UI.
    """

    model_config = ConfigDict(validate_assignment=True)

    id: str = "1"
    title: str = "Default"
    inputs: list[ConfigEntry] = []
    placeholders: list[ConfigEntry] = []
