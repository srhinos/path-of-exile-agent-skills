from __future__ import annotations

import json
import sys
from typing import Any

from pydantic import BaseModel

# Registry: model class -> human formatter function
_human_formatters: dict[type, Any] = {}


def human_formatter(model_cls: type):
    """Register a human-readable formatter for a pydantic model class.

    Usage::

        @human_formatter(MyModel)
        def format_my_model(model: MyModel) -> str:
            return f"{model.name}: {model.value}"
    """

    def decorator(func):
        _human_formatters[model_cls] = func
        return func

    return decorator


def render(data: Any, *, json_mode: bool = False) -> None:
    """Render data to stdout as JSON or human-readable text.

    Parameters
    ----------
    data
        A pydantic BaseModel, list of BaseModels, or dict.
    json_mode
        If True, output raw JSON instead of human-readable text.
    """
    text = _format_json(data) if json_mode else _format_human(data)
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    else:
        print(text)


def _format_json(data: Any) -> str:
    if isinstance(data, BaseModel):
        return data.model_dump_json(indent=2, exclude_none=True)
    # `allow_nan=False` so any inf/NaN slipping through service-layer
    # finite-validators raises rather than emitting non-RFC `Infinity`/
    # `NaN` tokens that external JSON consumers reject. `default=str`
    # handles Path/Enum/datetime/Decimal/set that callers may pass
    # without going through a Pydantic model.
    if isinstance(data, list) and data and isinstance(data[0], BaseModel):
        return json.dumps(
            [item.model_dump(exclude_none=True) for item in data],
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        )
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False, default=str)


def _format_human(data: Any) -> str:
    if isinstance(data, BaseModel):
        formatter = _human_formatters.get(type(data))
        if formatter:
            return formatter(data)
        return _format_dict_human(data.model_dump(exclude_none=True))

    if isinstance(data, list) and data and isinstance(data[0], BaseModel):
        formatter = _human_formatters.get(type(data[0]))
        if formatter:
            return "\n\n".join(formatter(item) for item in data)
        return "\n\n".join(_format_dict_human(item.model_dump(exclude_none=True)) for item in data)

    return _format_dict_human(data)


def _format_value(v: Any) -> str:
    """Format a scalar value for human output."""
    if isinstance(v, tuple):
        return str(list(v))
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _format_dict_human(data: Any, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{prefix}{k}:")
                lines.append(_format_dict_human(v, indent + 1))
            elif isinstance(v, tuple):
                lines.append(f"{prefix}{k}:")
                lines.append(_format_dict_human(list(v), indent + 1))
            else:
                lines.append(f"{prefix}{k}: {_format_value(v)}")
    elif isinstance(data, (list, tuple)):
        for item in data:
            if isinstance(item, dict):
                lines.append(_format_dict_human(item, indent))
                lines.append("")
            elif isinstance(item, (list, tuple)):
                lines.append(f"{prefix}- {list(item)}")
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}{_format_value(data)}")
    return "\n".join(lines)
