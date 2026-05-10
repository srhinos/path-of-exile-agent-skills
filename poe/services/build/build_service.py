from __future__ import annotations

import contextlib
import shutil
from pathlib import Path
from xml.etree.ElementTree import ParseError as XMLParseError

from defusedxml import ElementTree as SafeET

from poe.exceptions import BuildNotFoundError, BuildValidationError, CodecError
from poe.models.build.build import (
    BuildComparison,
    BuildDocument,
    BuildMetadata,
    BuildNotes,
    MutationResult,
    ValidationResult,
)
from poe.models.build.config import BuildConfig
from poe.models.build.items import ItemSet
from poe.models.build.stats import StatBlock
from poe.models.build.tree import TreeSpec
from poe.paths import (
    list_build_files,
    resolve_build_file,
    resolve_or_file,
    validate_build_name,
    validate_file_path,
)
from poe.safety import get_claude_builds_path, is_inside_claude_folder, resolve_for_write
from poe.services.build.constants import (
    ASCENDANCY_IDS,
    CATEGORY_ALIASES,
    CLASS_ID_TO_NAME,
    CLASS_IDS,
    DEFAULT_TREE_VERSION,
    MAX_CHARACTER_LEVEL,
    POB_COLOR_RE,
    STALE_STATS_WARNING,
    VALID_BANDITS,
    VALID_PANTHEON_MAJOR,
    VALID_PANTHEON_MINOR,
)
from poe.services.build.validation import validate_build
from poe.services.build.xml.parser import parse_build_file
from poe.services.build.xml.writer import write_build_file
from poe.types import StatCategory


class BuildService:
    """Owns all build file business logic."""

    def list_builds(self) -> list[BuildMetadata]:
        files = list_build_files()
        entries = []
        for f in files:
            meta = BuildMetadata(name=f.stem, file_path=str(f))
            with contextlib.suppress(ValueError, KeyError, OSError, XMLParseError):
                meta.class_name, meta.ascendancy, meta.level, meta.version = (
                    self._extract_build_attrs(f)
                )
            entries.append(meta)
        return entries

    @staticmethod
    def _extract_build_attrs(path: Path) -> tuple[str, str, int, str]:
        tree = SafeET.parse(str(path))
        build_el = tree.find("Build")
        if build_el is None:
            return "", "", 1, ""
        return (
            build_el.get("className", ""),
            build_el.get("ascendClassName", ""),
            int(build_el.get("level", "1")),
            build_el.get("targetVersion", ""),
        )

    def load(self, name: str, file_path: str | None = None, **kwargs) -> tuple[Path, BuildDocument]:
        try:
            path = resolve_or_file(name, file_path)
            return path, parse_build_file(path, **kwargs)
        except (FileNotFoundError, BuildNotFoundError) as e:
            raise BuildNotFoundError(str(e)) from e
        except (XMLParseError, ValueError) as e:
            raise CodecError(f"Failed to parse build file: {e}") from e

    def load_for_write(
        self, name: str, file_path: str | None = None
    ) -> tuple[Path, BuildDocument, str | None]:
        try:
            if file_path:
                validate_file_path(file_path)
                path, cloned_from = Path(file_path), None
            else:
                path, cloned_from = resolve_for_write(name)
            return path, parse_build_file(path), cloned_from
        except (FileNotFoundError, BuildNotFoundError) as e:
            raise BuildNotFoundError(str(e)) from e
        except (XMLParseError, ValueError) as e:
            raise CodecError(f"Failed to parse build file: {e}") from e

    def save(self, build_obj: BuildDocument, path: Path) -> None:
        write_build_file(build_obj, path)

    def create(
        self,
        name: str,
        *,
        class_name: str = "Scion",
        ascendancy: str = "",
        level: int = 1,
        tree_version: str | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        if file_path:
            validate_file_path(file_path)
            path = Path(file_path)
        else:
            builds_path = get_claude_builds_path()
            path = builds_path / (name if name.endswith(".xml") else name + ".xml")

        if path.exists():
            raise BuildValidationError(f"File already exists: {path}")

        if level < 1 or level > MAX_CHARACTER_LEVEL:
            raise BuildValidationError(
                f"Level must be between 1 and {MAX_CHARACTER_LEVEL}, got {level}"
            )

        class_id = CLASS_IDS.get(class_name)
        if class_id is None:
            raise BuildValidationError(f"Unknown class: {class_name!r}. Valid: {sorted(CLASS_IDS)}")
        ascend_class_id = 0
        if ascendancy:
            asc = ASCENDANCY_IDS.get(ascendancy)
            if not asc:
                raise BuildValidationError(
                    f"Unknown ascendancy: {ascendancy!r}. Valid: {sorted(ASCENDANCY_IDS)}"
                )
            if asc[0] != class_id:
                expected_class = CLASS_ID_TO_NAME.get(asc[0], "?")
                raise BuildValidationError(
                    f"Ascendancy {ascendancy!r} does not belong to class {class_name!r} "
                    f"(belongs to {expected_class})"
                )
            class_id, ascend_class_id = asc

        build_obj = BuildDocument(
            class_name=class_name,
            ascend_class_name=ascendancy,
            level=level,
            specs=[
                TreeSpec(
                    tree_version=tree_version or DEFAULT_TREE_VERSION,
                    class_id=class_id,
                    ascend_class_id=ascend_class_id,
                )
            ],
            skill_set_ids=[1],
            item_sets=[ItemSet(id="1")],
            config_sets=[BuildConfig(id="1", title="Default")],
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        write_build_file(build_obj, path)
        return MutationResult(path=str(path))

    def delete(
        self, name: str, *, file_path: str | None = None, confirm: bool = False
    ) -> MutationResult:
        if file_path:
            validate_file_path(file_path)
            path = Path(file_path)
        else:
            try:
                claude_dir = get_claude_builds_path()
            except (FileNotFoundError, BuildNotFoundError):
                claude_dir = None
            filename = name if name.endswith(".xml") else name + ".xml"
            if claude_dir and (claude_dir / filename).exists():
                path = claude_dir / filename
            else:
                try:
                    path = resolve_build_file(name)
                except (FileNotFoundError, BuildNotFoundError) as e:
                    raise BuildNotFoundError(str(e)) from e

        if not path.exists():
            raise BuildNotFoundError(f"File not found: {path}")
        if not file_path and not is_inside_claude_folder(path):
            raise BuildValidationError(
                "Cannot delete builds outside the Claude/ folder. Use --file to override."
            )
        if not confirm:
            raise BuildValidationError("Use --confirm to delete")
        path.unlink()
        return MutationResult(deleted=str(path))

    def analyze(self, name: str) -> BuildDocument:
        _, build_obj = self.load(name)
        return build_obj

    def stats(self, name: str, *, category: str = StatCategory.ALL) -> StatBlock:
        category = CATEGORY_ALIASES.get(category, category)
        valid = {c.value for c in StatCategory}
        if category not in valid:
            raise BuildValidationError(
                f"Unknown stat category: {category!r}. Valid: {sorted(valid)}"
            )
        _, build_obj = self.load(name)
        all_stats = {s.stat: s.value for s in build_obj.player_stats}
        def_keys = {
            k
            for k in all_stats
            if any(
                t in k
                for t in [
                    "Resist",
                    "Block",
                    "Dodge",
                    "Suppress",
                    "EHP",
                    "DamageReduction",
                    "Regen",
                    "Recovery",
                    "Ward",
                    "Armour",
                    "Evasion",
                    "MaximumHitTaken",
                    "MovementSpeed",
                    "Devotion",
                ]
            )
            or k in {"Life", "Mana", "EnergyShield", "ManaUnreserved", "NetLifeRegen"}
        }
        off_keys = {
            k
            for k in all_stats
            if any(t in k for t in ["DPS", "Crit", "AverageHit", "AverageBurst", "Impale"])
            or k
            in {
                "Speed",
                "HitChance",
                "TotalDot",
                "BleedDPS",
                "IgniteDPS",
                "PoisonDPS",
                "MirageDPS",
                "CullingDPS",
                "ManaCost",
                "ManaPerSecondCost",
                "LifeCost",
            }
        }
        if category == StatCategory.OFF:
            filtered = {k: v for k, v in all_stats.items() if k in off_keys}
        elif category == StatCategory.DEF:
            filtered = {k: v for k, v in all_stats.items() if k in def_keys}
        else:
            filtered = all_stats
        return StatBlock(category=category, stats=filtered)

    def compare(self, name1: str, name2: str) -> BuildComparison:
        _, build1 = self.load(name1)
        _, build2 = self.load(name2)
        stats1 = {s.stat: s.value for s in build1.player_stats}
        stats2 = {s.stat: s.value for s in build2.player_stats}
        comparison = {}
        for key in sorted(set(stats1) | set(stats2)):
            v1, v2 = stats1.get(key, 0.0), stats2.get(key, 0.0)
            diff = v2 - v1
            comparison[key] = {
                name1: v1,
                name2: v2,
                "diff": diff,
                "pct": round(diff / v1 * 100, 1) if v1 else None,
            }
        cfg1 = build1.get_active_config()
        cfg2 = build2.get_active_config()
        config_diff: dict = {}
        if cfg1 or cfg2:
            inputs1 = {inp.name: inp.value for inp in (cfg1.inputs if cfg1 else [])}
            inputs2 = {inp.name: inp.value for inp in (cfg2.inputs if cfg2 else [])}
            for k in sorted(set(inputs1) | set(inputs2)):
                v1 = inputs1.get(k, "(not set)")
                v2 = inputs2.get(k, "(not set)")
                if v1 != v2:
                    config_diff[k] = {name1: v1, name2: v2}
        return BuildComparison(
            build1=BuildMetadata(
                name=name1,
                class_name=build1.class_name,
                ascendancy=build1.ascend_class_name,
                level=build1.level,
                version=build1.target_version,
            ),
            build2=BuildMetadata(
                name=name2,
                class_name=build2.class_name,
                ascendancy=build2.ascend_class_name,
                level=build2.level,
                version=build2.target_version,
            ),
            stat_comparison=comparison,
            config_diff=config_diff,
        )

    def notes_get(self, name: str, *, file_path: str | None = None) -> BuildNotes:
        _, build_obj = self.load(name, file_path)
        # `notes` is the raw text (color codes + whitespace preserved) so a
        # caller that round-trips it via notes_set keeps the build's on-disk
        # formatting. `notes_display` is the color-stripped form for UIs.
        raw = build_obj.notes
        display = POB_COLOR_RE.sub("", raw.strip())
        return BuildNotes(build_name=name, notes=raw, notes_display=display)

    def notes_set(self, name: str, notes: str, *, file_path: str | None = None) -> MutationResult:
        path, build_obj, cloned_from = self.load_for_write(name, file_path)
        build_obj.notes = notes
        self.save(build_obj, path)
        return MutationResult(
            notes=notes,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def validate(self, name: str) -> ValidationResult:
        _, build_obj = self.load(name)
        issues = validate_build(build_obj)
        return ValidationResult(build=name, issues=issues, issue_count=len(issues))

    def export(self, name: str, dest: str) -> MutationResult:
        try:
            src = resolve_build_file(name)
        except (FileNotFoundError, BuildNotFoundError) as e:
            raise BuildNotFoundError(str(e)) from e
        dest_path = Path(dest)
        if dest_path.is_dir():
            dest_path = dest_path / src.name
        shutil.copy2(src, dest_path)
        return MutationResult(exported_to=str(dest_path))

    def rename(self, name: str, new_name: str) -> MutationResult:
        validate_build_name(new_name)
        try:
            src = resolve_build_file(name)
        except (FileNotFoundError, BuildNotFoundError) as e:
            raise BuildNotFoundError(str(e)) from e
        if not is_inside_claude_folder(src):
            raise BuildValidationError("Cannot rename builds outside the Claude/ folder")
        dest = src.parent / (new_name if new_name.endswith(".xml") else new_name + ".xml")
        if dest.exists():
            raise BuildValidationError(f"File already exists: {dest}")
        src.rename(dest)
        return MutationResult(old_name=name, new_name=new_name, path=str(dest))

    def duplicate(
        self,
        name: str,
        new_name: str,
        *,
        file_path: str | None = None,
    ) -> MutationResult:
        validate_build_name(new_name)
        if file_path:
            validate_file_path(file_path)
        try:
            src = Path(file_path) if file_path else resolve_build_file(name)
        except (FileNotFoundError, BuildNotFoundError) as e:
            raise BuildNotFoundError(str(e)) from e
        if not src.exists():
            raise BuildNotFoundError(f"File not found: {src}")
        dest_dir = get_claude_builds_path()
        filename = new_name if new_name.endswith(".xml") else new_name + ".xml"
        dest = dest_dir / filename
        if dest.exists():
            raise BuildValidationError(f"File already exists: {dest}")
        shutil.copy2(src, dest)
        return MutationResult(original=str(src), path=str(dest))

    def set_level(self, name: str, level: int, *, file_path: str | None = None) -> MutationResult:
        if level < 1 or level > MAX_CHARACTER_LEVEL:
            raise BuildValidationError(f"Level must be 1-100, got {level}")
        path, build_obj, cloned_from = self.load_for_write(name, file_path)
        build_obj.level = level
        self.save(build_obj, path)
        return MutationResult(
            level=level,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    @staticmethod
    def _canonical_class_or_raise(class_name: str | None) -> str | None:
        if class_name is None:
            return None
        canonical = {c.casefold(): c for c in CLASS_IDS}.get(class_name.casefold())
        if canonical is None:
            raise BuildValidationError(f"Unknown class: {class_name!r}. Valid: {sorted(CLASS_IDS)}")
        return canonical

    @staticmethod
    def _canonical_ascendancy_or_raise(ascendancy: str | None) -> str | None:
        if ascendancy is None:
            return None
        canonical = {a.casefold(): a for a in ASCENDANCY_IDS}.get(ascendancy.casefold())
        if canonical is None:
            raise BuildValidationError(
                f"Unknown ascendancy: {ascendancy!r}. Valid: {sorted(ASCENDANCY_IDS)}"
            )
        return canonical

    def set_class(
        self,
        name: str,
        *,
        class_name: str | None = None,
        ascendancy: str | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        if not class_name and not ascendancy:
            raise BuildValidationError("Provide at least one of --class or --ascendancy")
        class_name = self._canonical_class_or_raise(class_name)
        ascendancy = self._canonical_ascendancy_or_raise(ascendancy)
        if class_name and ascendancy:
            asc = ASCENDANCY_IDS.get(ascendancy)
            class_id = CLASS_IDS.get(class_name)
            if asc and class_id is not None and asc[0] != class_id:
                expected_class = CLASS_ID_TO_NAME.get(asc[0], "?")
                raise BuildValidationError(
                    f"Ascendancy {ascendancy!r} does not belong to class {class_name!r} "
                    f"(belongs to {expected_class})"
                )
        path, build_obj, cloned_from = self.load_for_write(name, file_path)
        spec = build_obj.get_active_spec()
        if ascendancy and not class_name:
            # Reject when ascendancy is given alone but doesn't match the
            # current class. Prior behavior silently re-classed the build,
            # invalidating the passive tree (Marauder build → Trickster
            # ascendancy → silently became Shadow with Marauder nodes).
            asc = ASCENDANCY_IDS.get(ascendancy)
            if asc and spec and spec.class_id != asc[0]:
                expected_class = CLASS_ID_TO_NAME.get(asc[0], "?")
                current_class = CLASS_ID_TO_NAME.get(spec.class_id, build_obj.class_name)
                raise BuildValidationError(
                    f"Ascendancy {ascendancy!r} does not belong to current class "
                    f"{current_class!r} (belongs to {expected_class}). "
                    "Pass --class explicitly to switch classes."
                )
        if class_name:
            class_id = CLASS_IDS.get(class_name)
            if class_id is None:
                raise BuildValidationError(
                    f"Unknown class: {class_name!r}. Valid: {sorted(CLASS_IDS)}"
                )
            build_obj.class_name = class_name
            if spec:
                spec.class_id = class_id
            if not ascendancy:
                build_obj.ascend_class_name = ""
                if spec:
                    spec.ascend_class_id = 0
        if ascendancy:
            asc = ASCENDANCY_IDS.get(ascendancy)
            if not asc:
                raise BuildValidationError(
                    f"Unknown ascendancy: {ascendancy!r}. Valid: {sorted(ASCENDANCY_IDS)}"
                )
            build_obj.ascend_class_name = ascendancy
            if spec:
                spec.class_id, spec.ascend_class_id = asc
                build_obj.class_name = CLASS_ID_TO_NAME.get(asc[0], build_obj.class_name)
        self.save(build_obj, path)
        return MutationResult(
            class_name=build_obj.class_name,
            ascendancy=build_obj.ascend_class_name,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def set_bandit(self, name: str, bandit: str, *, file_path: str | None = None) -> MutationResult:
        bandit_by_casefold = {b.casefold(): b for b in VALID_BANDITS}
        canonical = bandit_by_casefold.get(bandit.casefold())
        if canonical is None:
            raise BuildValidationError(
                f"Unknown bandit: {bandit!r}. Valid: {sorted(VALID_BANDITS)}"
            )
        bandit = canonical
        path, build_obj, cloned_from = self.load_for_write(name, file_path)
        build_obj.bandit = bandit if bandit != "None" else None
        self.save(build_obj, path)
        return MutationResult(
            bandit=bandit,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def set_pantheon(
        self,
        name: str,
        *,
        major: str | None = None,
        minor: str | None = None,
        file_path: str | None = None,
    ) -> MutationResult:
        major_by_casefold = {p.casefold(): p for p in VALID_PANTHEON_MAJOR}
        minor_by_casefold = {p.casefold(): p for p in VALID_PANTHEON_MINOR}
        if major is not None:
            canonical_major = major_by_casefold.get(major.casefold())
            if canonical_major is None:
                raise BuildValidationError(
                    f"Unknown major pantheon: {major!r}. "
                    f"Valid: {sorted(VALID_PANTHEON_MAJOR - {''})}"
                )
            major = canonical_major
        if minor is not None:
            canonical_minor = minor_by_casefold.get(minor.casefold())
            if canonical_minor is None:
                raise BuildValidationError(
                    f"Unknown minor pantheon: {minor!r}. "
                    f"Valid: {sorted(VALID_PANTHEON_MINOR - {''})}"
                )
            minor = canonical_minor
        path, build_obj, cloned_from = self.load_for_write(name, file_path)
        if major is not None:
            build_obj.pantheon_major = major
        if minor is not None:
            build_obj.pantheon_minor = minor
        self.save(build_obj, path)
        return MutationResult(
            pantheon_major=build_obj.pantheon_major,
            pantheon_minor=build_obj.pantheon_minor,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )

    def summary(self, name: str, *, file_path: str | None = None) -> dict:
        _, build_obj = self.load(name, file_path)
        get = build_obj.get_stat
        total = get("TotalDPS") or 0.0
        combined = get("CombinedDPS") or total
        main_skill = ""
        idx = build_obj.main_socket_group - 1
        if 0 <= idx < len(build_obj.skill_groups):
            group = build_obj.skill_groups[idx]
            for gem in group.gems:
                if gem.enabled and gem.name_spec and not gem.name_spec.endswith("Support"):
                    main_skill = gem.name_spec
                    break
        return {
            "name": name,
            "class": build_obj.class_name,
            "ascendancy": build_obj.ascend_class_name,
            "level": build_obj.level,
            "main_skill": main_skill,
            "life": get("Life") or 0,
            "energy_shield": get("EnergyShield") or 0,
            "mana": get("Mana") or 0,
            "total_dps": total,
            "combined_dps": combined,
            "fire_resist": get("FireResist") or 0,
            "cold_resist": get("ColdResist") or 0,
            "lightning_resist": get("LightningResist") or 0,
            "chaos_resist": get("ChaosResist") or 0,
        }

    def set_main_skill(
        self, name: str, index: int, *, file_path: str | None = None
    ) -> MutationResult:
        path, build_obj, cloned_from = self.load_for_write(name, file_path)
        if index < 1 or index > len(build_obj.skill_groups):
            raise BuildValidationError(
                f"Index {index} out of range (1-{len(build_obj.skill_groups)})"
            )
        build_obj.main_socket_group = index
        self.save(build_obj, path)
        return MutationResult(
            main_socket_group=index,
            warning=STALE_STATS_WARNING,
            cloned_from=cloned_from,
            working_copy=str(path) if cloned_from else None,
        )
