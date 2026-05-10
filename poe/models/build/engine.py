from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EngineInfo(BaseModel):
    """PoB installation status, returned by EngineService.info().

    Reports whether PoB is found, the engine is initialized,
    and a build is loaded for stat calculation.
    """

    model_config = ConfigDict(validate_assignment=True)

    pob_path: str = ""
    initialized: bool = False
    build_loaded: bool = False
    lua_version: str = ""
