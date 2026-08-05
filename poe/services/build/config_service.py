from __future__ import annotations

from poe.exceptions import BuildValidationError
from poe.models.build.build import MutationResult
from poe.models.build.config import BuildConfig, ConfigEntry
from poe.services.build.build_service import BuildService
from poe.services.build.constants import CONFIG_PRESETS, POB_CONFIG_KEYS, STALE_STATS_WARNING


class ConfigService:
    """Owns build configuration business logic."""

    def __init__(self, build_svc: BuildService | None = None) -> None:
        self._build = build_svc or BuildService()

    def get(self, name: str, *, file_path: str | None = None) -> BuildConfig:
        _, build_obj = self._build.load(name, file_path)
        cfg = build_obj.get_active_config()
        if not cfg:
            raise BuildValidationError("No config found")
        return cfg

    def list_options(self, query: str | None = None) -> list[dict]:
        results = []
        for key, info in POB_CONFIG_KEYS.items():
            if query:
                q = query.casefold()
                if q not in key.casefold() and q not in info["desc"].casefold():
                    continue
            results.append({"key": key, "type": info["type"], "description": info["desc"]})
        return results

    def list_sets(self, name: str, *, file_path: str | None = None) -> list[dict]:
        _, build_obj = self._build.load(name, file_path)
        return [
            {
                "id": cs.id,
                "title": cs.title,
                "input_count": len(cs.inputs),
                "active": cs.id == build_obj.active_config_set,
            }
            for cs in build_obj.config_sets
        ]

    def add_set(
        self,
        name: str,
        *,
        title: str = "New Config",
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        max_id = max((int(cs.id) for cs in build_obj.config_sets), default=0)
        new_id = str(max_id + 1)
        build_obj.config_sets.append(BuildConfig(id=new_id, title=title))
        self._build.save(build_obj, path)
        return MutationResult(
            new_set_id=new_id,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def remove_set(
        self,
        name: str,
        config_set: str,
        *,
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if len(build_obj.config_sets) <= 1:
            raise BuildValidationError("Cannot remove the last remaining config set")
        if not any(cs.id == config_set for cs in build_obj.config_sets):
            raise BuildValidationError(f"Config set {config_set} not found")
        build_obj.config_sets = [cs for cs in build_obj.config_sets if cs.id != config_set]
        if build_obj.active_config_set == config_set:
            build_obj.active_config_set = build_obj.config_sets[0].id
        self._build.save(build_obj, path)
        return MutationResult(
            removed_set_id=config_set,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def switch_set(
        self,
        name: str,
        config_set: str,
        *,
        file_path: str | None = None,
    ) -> MutationResult:
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        if not any(cs.id == config_set for cs in build_obj.config_sets):
            raise BuildValidationError(f"Config set {config_set} not found")
        build_obj.active_config_set = config_set
        self._build.save(build_obj, path)
        return MutationResult(
            active_config_set=config_set,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def set(
        self,
        name: str,
        *,
        boolean: list[str] | None = None,
        number: list[str] | None = None,
        string: list[str] | None = None,
        remove: list[str] | None = None,
        file_path: str | None = None,
    ) -> dict:
        boolean = boolean or []
        number = number or []
        string = string or []
        remove = remove or []
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        cfg = build_obj.get_active_config()
        if not cfg:
            cfg = BuildConfig(id=build_obj.active_config_set, title="Default")
            build_obj.config_sets.append(cfg)
        input_map = {inp.name: inp for inp in cfg.inputs}
        for kv in boolean:
            k, v = self._parse_kv(kv)
            if v.casefold() not in ("true", "false"):
                raise BuildValidationError(f"Invalid boolean value: {v!r}")
            input_map[k] = ConfigEntry(name=k, value=v.casefold() == "true", input_type="boolean")
        for kv in number:
            k, v = self._parse_kv(kv)
            try:
                input_map[k] = ConfigEntry(name=k, value=float(v), input_type="number")
            except ValueError as e:
                raise BuildValidationError(f"Invalid number: {v!r}") from e
        for kv in string:
            k, v = self._parse_kv(kv)
            input_map[k] = ConfigEntry(name=k, value=v, input_type="string")
        for k in remove:
            input_map.pop(k, None)
        cfg.inputs = list(input_map.values())
        self._build.save(build_obj, path)
        return MutationResult(
            input_count=len(cfg.inputs),
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def apply_preset(
        self,
        name: str,
        preset: str,
        *,
        file_path: str | None = None,
    ) -> MutationResult:
        preset_by_casefold = {p.casefold(): p for p in CONFIG_PRESETS}
        canonical = preset_by_casefold.get(preset.casefold())
        if canonical is None:
            raise BuildValidationError(
                f"Unknown preset: {preset!r}. Valid: {sorted(CONFIG_PRESETS)}"
            )
        preset = canonical
        path, build_obj, cloned_from = self._build.load_for_write(name, file_path)
        cfg = build_obj.get_active_config()
        if not cfg:
            cfg = BuildConfig(id=build_obj.active_config_set, title="Default")
            build_obj.config_sets.append(cfg)
        input_map = {inp.name: inp for inp in cfg.inputs}
        for key, value in CONFIG_PRESETS[preset].items():
            if isinstance(value, bool):
                input_map[key] = ConfigEntry(name=key, value=value, input_type="boolean")
            elif isinstance(value, (int, float)):
                input_map[key] = ConfigEntry(name=key, value=float(value), input_type="number")
            else:
                input_map[key] = ConfigEntry(name=key, value=str(value), input_type="string")
        cfg.inputs = list(input_map.values())
        self._build.save(build_obj, path)
        return MutationResult(
            preset=preset,
            input_count=len(cfg.inputs),
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    @staticmethod
    def _parse_kv(kv: str) -> tuple[str, str]:
        if "=" not in kv:
            raise BuildValidationError(f"Invalid format: {kv!r} (expected key=value)")
        return kv.split("=", 1)
