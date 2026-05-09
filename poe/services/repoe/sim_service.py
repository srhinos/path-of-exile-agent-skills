from __future__ import annotations

import dataclasses
import math
import re

from poe.constants import MIN_SEARCH_TERM_LENGTH
from poe.exceptions import BuildNotFoundError, SimDataError, SlotError
from poe.models.build.items import EquippedItem
from poe.models.sim import (
    BaseItemSearchResult,
    BenchCraftListResult,
    EssenceListResult,
    FossilListResult,
    ItemAnalysisResult,
    ModPoolResult,
    ModTierResult,
    SimulationResult,
)
from poe.paths import resolve_build_file
from poe.services.build.xml.parser import parse_build_file
from poe.services.ninja.client import NinjaClient
from poe.services.ninja.discovery import DiscoveryService
from poe.services.ninja.economy import EconomyService
from poe.services.ninja.errors import NinjaError
from poe.services.repoe.constants import (
    DEFAULT_ILVL,
    DEFAULT_ITERATIONS,
    DEFAULT_MAX_ATTEMPTS,
    RARITY_PRODUCED,
    RARITY_REQUIRED,
)
from poe.services.repoe.data import RepoEData
from poe.services.repoe.sim import CraftingEngine
from poe.types import CraftMethod, Influence


class SimService:
    """Owns crafting business logic."""

    def __init__(self, repoe_data: RepoEData | None = None) -> None:
        self._data = repoe_data or RepoEData()

    def get_mods(
        self,
        base_name: str,
        *,
        ilvl: int = DEFAULT_ILVL,
        influences: list[str] | None = None,
        affix_type: str | None = None,
        limit: int = 30,
    ) -> ModPoolResult:
        if influences:
            valid_map = {i.value.casefold(): i.value for i in Influence}
            for idx, inf in enumerate(influences):
                matched = valid_map.get(inf.casefold())
                if not matched:
                    raise SimDataError(
                        f"Unknown influence: {inf!r}. Valid: {sorted(valid_map.values())}"
                    )
                influences[idx] = matched
        mods = self._data.get_mod_pool(
            base_name,
            ilvl=ilvl,
            influences=influences or [],
            affix_type=affix_type,
        )
        if not mods:
            bitem = self._data.get_base_item(base_name)
            if not bitem:
                raise SimDataError(
                    f"Base item '{base_name}' not found. Use 'poe sim search <query>'."
                )
            raise SimDataError("No mods found for given filters")
        return ModPoolResult(
            base=base_name,
            ilvl=ilvl,
            influences=influences or ["none"],
            filter=affix_type or "all",
            total_mods=len(mods),
            mods=[dataclasses.asdict(m) for m in mods[:limit]],
        )

    def get_tiers(self, mod_id: str, base_name: str, *, ilvl: int = DEFAULT_ILVL) -> ModTierResult:
        tiers = self._data.get_mod_tiers(mod_id, base_name, ilvl=ilvl)
        if not tiers:
            pool = self._data.get_mod_pool(base_name, ilvl=ilvl)
            for mod in pool:
                if mod.group.casefold() == mod_id.casefold():
                    tiers = self._data.get_mod_tiers(mod.mod_id, base_name, ilvl=ilvl)
                    if tiers:
                        mod_id = mod.mod_id
                        break
        if not tiers:
            raise SimDataError(f"No tiers found for mod {mod_id} on {base_name}")
        return ModTierResult(mod_id=mod_id, base=base_name, ilvl=ilvl, tiers=tiers)

    def get_fossils(self, *, filter_tag: str | None = None) -> FossilListResult:
        fossils = self._data.get_fossils(filter_tag=filter_tag)
        return FossilListResult(filter=filter_tag, count=len(fossils), fossils=fossils)

    def get_essences(self, base_name: str | None = None) -> EssenceListResult:
        essences = self._data.get_essences(base_name=base_name)
        return EssenceListResult(base=base_name or "all", count=len(essences), essences=essences)

    def get_bench_crafts(self, base_name: str) -> BenchCraftListResult:
        bitem = self._data.get_base_item(base_name)
        if not bitem:
            raise SimDataError(f"Base item '{base_name}' not found. Use 'poe sim search <query>'.")
        crafts = self._data.get_bench_crafts(base_name)
        return BenchCraftListResult(base=base_name, count=len(crafts), crafts=crafts)

    def search_bases(self, query: str) -> BaseItemSearchResult:
        results = self._data.search_base_items(query)
        items = [
            {
                "name": bitem["name"],
                "drop_level": bitem["drop_level"],
                "properties": bitem.get("properties", {}),
            }
            for bitem in results[:20]
        ]
        return BaseItemSearchResult(query=query, count=len(results), items=items)

    def analyze_item(
        self, build_name: str, *, slot: str, ilvl: int | None = None
    ) -> ItemAnalysisResult:
        """Analyze an equipped item's mods, tiers, and open affix slots."""
        try:
            path = resolve_build_file(build_name)
        except (FileNotFoundError, BuildNotFoundError) as e:
            raise BuildNotFoundError(str(e)) from e
        build_obj = parse_build_file(path)

        equipped = build_obj.get_equipped_items()
        target_item = None
        target_slot = None
        for slot_name, item in equipped:
            if slot.casefold() in slot_name.casefold():
                target_item = item
                target_slot = slot_name
                break
        if not target_item or not target_slot:
            raise SlotError(f"No item found in slot matching '{slot}'")

        item_ilvl = ilvl or target_item.item_level or DEFAULT_ILVL
        bitem = self._data.get_base_item(target_item.base_type)
        base_found = bitem is not None
        analysis: dict = {"base_found": base_found, "ilvl_used": item_ilvl}

        if base_found:
            mods = self._data.get_mod_pool(
                target_item.base_type,
                ilvl=item_ilvl,
                influences=target_item.influences,
            )
            avail_prefixes = [m for m in mods if m.affix == "prefix"]
            avail_suffixes = [m for m in mods if m.affix == "suffix"]
            analysis["total_rollable_prefixes"] = len(avail_prefixes)
            analysis["total_rollable_suffixes"] = len(avail_suffixes)
            analysis["open_prefix_slots"] = target_item.open_prefixes
            analysis["open_suffix_slots"] = target_item.open_suffixes
            if target_item.open_prefixes > 0:
                analysis["top_available_prefixes"] = [
                    dataclasses.asdict(m) for m in avail_prefixes[:10]
                ]
            if target_item.open_suffixes > 0:
                analysis["top_available_suffixes"] = [
                    dataclasses.asdict(m) for m in avail_suffixes[:10]
                ]
            bench = self._data.get_bench_crafts(target_item.base_type)
            if bench:
                analysis["bench_craft_count"] = len(bench)
                analysis["bench_crafts_sample"] = bench[:5]
        return ItemAnalysisResult(
            slot=target_slot,
            item=EquippedItem(slot=target_slot, **target_item.model_dump()).model_dump(
                exclude_none=True
            ),
            analysis=analysis,
        )

    async def simulate(
        self,
        base_name: str,
        *,
        ilvl: int = DEFAULT_ILVL,
        method: str,
        target: list[str],
        fossils: list[str] | None = None,
        essence: str | None = None,
        influence: list[str] | None = None,
        iterations: int = DEFAULT_ITERATIONS,
        match: str = "all",
        existing_mods: list[str] | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        workers: int | None = None,
    ) -> SimulationResult:
        valid_methods = {m.value for m in CraftMethod}
        if method not in valid_methods:
            raise SimDataError(f"Unknown craft method: {method!r}. Valid: {sorted(valid_methods)}")
        if method == CraftMethod.ESSENCE and not essence:
            raise SimDataError("--essence is required when method is 'essence'")
        if method == CraftMethod.FOSSIL and not fossils:
            raise SimDataError("--fossils is required when method is 'fossil'")
        if influence:
            valid_map = {i.value.casefold(): i.value for i in Influence}
            for idx, inf in enumerate(influence):
                matched = valid_map.get(inf.casefold())
                if not matched:
                    raise SimDataError(
                        f"Unknown influence: {inf!r}. Valid: {sorted(valid_map.values())}"
                    )
                influence[idx] = matched
        mod_pool = self._data.get_mod_pool(base_name, ilvl=ilvl, influences=influence or [])
        pool_groups = {mod.group.casefold() for mod in mod_pool}
        resolved_targets = []
        for t in target:
            resolved = self.resolve_mod_name(t, base_name, influences=influence)
            final = resolved or t
            if final.casefold() not in pool_groups:
                available = sorted({mod.group for mod in mod_pool})[:20]
                raise SimDataError(
                    f"Target mod {t!r} not found in mod pool for {base_name!r}. "
                    f"Available groups (first 20): {available}"
                )
            resolved_targets.append(final)
        if existing_mods:
            for em in existing_mods:
                resolved_em = self.resolve_mod_name(em, base_name, influences=influence) or em
                if resolved_em.casefold() not in pool_groups:
                    available = sorted({mod.group for mod in mod_pool})[:20]
                    raise SimDataError(
                        f"Existing mod {em!r} not found in mod pool for {base_name!r}. "
                        f"Available groups (first 20): {available}"
                    )
        eng = CraftingEngine(self._data.snapshot())
        try:
            sim_result = await eng.simulate(
                base=base_name,
                ilvl=ilvl,
                method=method,
                target_mods=resolved_targets,
                iterations=iterations,
                influences=influence or [],
                fossils=fossils,
                match_mode=match,
                essence_name=essence,
                existing_mods=existing_mods,
                max_attempts=max_attempts,
                workers=workers,
            )
        except ValueError as e:
            raise SimDataError(str(e)) from e

        def _finite(v: float) -> float | None:
            return None if not math.isfinite(v) else v

        return SimulationResult(
            base=base_name,
            ilvl=ilvl,
            method=method,
            targets=target,
            fossils=fossils,
            essence=essence,
            match_mode=match,
            iterations=sim_result.iterations,
            hit_rate=f"{sim_result.hit_rate:.1%}",
            avg_attempts=_finite(round(sim_result.avg_attempts, 1)),
            cost_per_attempt=_finite(round(sim_result.cost_per_attempt, 1)),
            avg_cost_chaos=_finite(round(sim_result.avg_cost_chaos, 1)),
            percentiles=sim_result.percentiles,
        )

    def simulate_multistep(
        self,
        base_name: str,
        *,
        ilvl: int = DEFAULT_ILVL,
        steps: list[dict],
        target: list[str],
        iterations: int = DEFAULT_ITERATIONS,
        influence: list[str] | None = None,
        match: str = "all",
    ) -> dict:
        produced_rarity = "normal"
        for i, step in enumerate(steps):
            method = step.get("method", "chaos")
            required = RARITY_REQUIRED.get(method)
            if required and produced_rarity != required:
                raise SimDataError(
                    f"Step {i + 1} ({method}) requires {required} rarity, "
                    f"but previous step produces {produced_rarity} items"
                )
            produced_rarity = RARITY_PRODUCED.get(method, produced_rarity)
        mod_pool = self._data.get_mod_pool(base_name, ilvl=ilvl, influences=influence or [])
        pool_groups = {mod.group.casefold() for mod in mod_pool}
        resolved_targets = []
        for t in target:
            resolved = self.resolve_mod_name(t, base_name, influences=influence)
            final = resolved or t
            if final.casefold() not in pool_groups:
                available = sorted({mod.group for mod in mod_pool})[:20]
                raise SimDataError(
                    f"Target mod {t!r} not found in mod pool for {base_name!r}. "
                    f"Available groups (first 20): {available}"
                )
            resolved_targets.append(final)
        eng = CraftingEngine(self._data.snapshot())
        target_set = {t.casefold() for t in resolved_targets}
        hits = 0
        attempts_on_hit: list[int] = []
        try:
            for _ in range(iterations):
                item = eng.create_item(base_name, ilvl, influence)
                for step in steps:
                    method = step.get("method", "chaos")
                    self._apply_multistep_method(eng, item, method, step)
                rolled_groups = {m.group.casefold() for m in item.all_mods}
                hit = (
                    target_set.issubset(rolled_groups)
                    if match == "all"
                    else bool(target_set & rolled_groups)
                )
                if hit:
                    hits += 1
                    attempts_on_hit.append(1)
        except ValueError as e:
            raise SimDataError(str(e)) from e
        hit_rate = hits / iterations if iterations > 0 else 0
        return {
            "base": base_name,
            "steps": [s.get("method") for s in steps],
            "targets": target,
            "iterations": iterations,
            "hit_rate": f"{hit_rate:.1%}",
            "hits": hits,
        }

    @staticmethod
    def _apply_multistep_method(
        eng: CraftingEngine,
        item: object,
        method: str,
        step: dict,
    ) -> None:
        simple_dispatch: dict[str, callable] = {
            CraftMethod.CHAOS: eng.chaos_roll,
            CraftMethod.ALT: eng.alt_roll,
            CraftMethod.REGAL: eng.regal,
            CraftMethod.EXALT: eng.exalt,
            CraftMethod.ANNUL: eng.annul,
            CraftMethod.SCOUR: eng.scour,
            CraftMethod.ALCHEMY: eng.alchemy,
            CraftMethod.TRANSMUTATION: eng.transmutation,
            CraftMethod.AUGMENTATION: eng.augmentation,
            CraftMethod.DIVINE: eng.divine,
            CraftMethod.BLESSED: eng.blessed,
            CraftMethod.VEILED_CHAOS: eng.veiled_chaos,
            CraftMethod.VAAL: eng.vaal_orb,
            CraftMethod.FRACTURE: eng.fracture,
            CraftMethod.TAINTED_DIVINE: eng.tainted_divine,
        }
        if method in simple_dispatch:
            simple_dispatch[method](item)
        elif method == CraftMethod.FOSSIL:
            eng.fossil_roll(item, step.get("fossils", []))
        elif method == CraftMethod.ESSENCE:
            eng.essence_roll(item, step.get("essence", ""))
        elif method == CraftMethod.HARVEST:
            eng.harvest_reforge(item, tag=step.get("tag"))
        elif method == CraftMethod.CONQUEROR_EXALT:
            eng.conqueror_exalt(item, step.get("influence", ""))
        else:
            valid = ", ".join(m.value for m in CraftMethod)
            msg = f"Unknown step method: {method!r} (valid: {valid})"
            raise ValueError(msg)

    def fossil_optimizer(self, mod_name: str) -> list[dict]:
        fossils = self._data.get_fossils()
        seen: set[tuple[str, str]] = set()
        results = []
        mod_cf = mod_name.casefold()
        search_terms = self._expand_mod_search_terms(mod_cf)

        def _matches(tag: str) -> bool:
            tag_cf = tag.casefold()
            return any(term in tag_cf or tag_cf in term for term in search_terms)

        for fossil in fossils:
            for tag, multiplier in fossil.get("positive_weights", {}).items():
                if _matches(tag):
                    key = (fossil["name"], tag)
                    if key not in seen:
                        seen.add(key)
                        results.append(
                            {
                                "fossil": fossil["name"],
                                "tag": tag,
                                "multiplier": multiplier,
                                "effect": (
                                    "boost"
                                    if multiplier > 1
                                    else "reduce"
                                    if multiplier < 1
                                    else "neutral"
                                ),
                            }
                        )
            for tag, multiplier in fossil.get("negative_weights", {}).items():
                if _matches(tag):
                    key = (fossil["name"], tag)
                    if key not in seen:
                        seen.add(key)
                        results.append(
                            {
                                "fossil": fossil["name"],
                                "tag": tag,
                                "multiplier": multiplier,
                                "effect": "block" if multiplier == 0 else "reduce",
                            }
                        )
            for tag in fossil.get("blocked", []):
                if _matches(tag):
                    key = (fossil["name"], tag)
                    if key not in seen:
                        seen.add(key)
                        results.append(
                            {
                                "fossil": fossil["name"],
                                "tag": tag,
                                "multiplier": 0.0,
                                "effect": "block",
                            }
                        )
        results.sort(key=lambda x: x["multiplier"], reverse=True)
        return results

    @staticmethod
    def _expand_mod_search_terms(mod_cf: str) -> list[str]:
        """Expand a mod name into search terms for fossil tag matching.

        Splits camelCase/PascalCase names into components so "ColdResistance"
        matches fossil tags like "cold" and "resistance".
        """
        terms = [mod_cf]
        parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", mod_cf, re.IGNORECASE)
        terms.extend(p.casefold() for p in parts if len(p) > MIN_SEARCH_TERM_LENGTH)
        if "_" in mod_cf:
            terms.extend(p.casefold() for p in mod_cf.split("_") if len(p) > MIN_SEARCH_TERM_LENGTH)
        return list(dict.fromkeys(terms))

    async def compare_methods(
        self,
        base_name: str,
        *,
        ilvl: int = DEFAULT_ILVL,
        target: list[str],
        fossils: list[str] | None = None,
        essence: str | None = None,
        influence: list[str] | None = None,
        iterations: int = DEFAULT_ITERATIONS,
    ) -> list[dict]:
        methods_to_try = ["chaos", "alt"]
        if fossils:
            methods_to_try.append("fossil")
        if essence:
            methods_to_try.append("essence")
        results = []

        def _finite(v: float | None) -> float | None:
            if v is None:
                return None
            return None if not math.isfinite(v) else v

        for method in methods_to_try:
            sim = await self.simulate(
                base_name,
                ilvl=ilvl,
                method=method,
                target=target,
                fossils=fossils if method == "fossil" else None,
                essence=essence if method == "essence" else None,
                influence=influence,
                iterations=iterations,
                workers=1,
            )

            results.append(
                {
                    "method": method,
                    "hit_rate": sim.hit_rate,
                    "avg_attempts": _finite(sim.avg_attempts),
                    "avg_cost_chaos": _finite(sim.avg_cost_chaos),
                    "cost_per_attempt": sim.cost_per_attempt,
                }
            )
        results.sort(
            key=lambda x: x["avg_cost_chaos"] if x["avg_cost_chaos"] is not None else float("inf")
        )
        return results

    def suggest_craft(self, mod_names: list[str]) -> list[dict]:
        suggestions = []
        for mod in mod_names:
            fossil_matches = self.fossil_optimizer(mod)
            if fossil_matches:
                best = fossil_matches[0]
                suggestions.append(
                    {
                        "mod": mod,
                        "approach": "fossil",
                        "fossil": best["fossil"],
                        "multiplier": best["multiplier"],
                    }
                )
            else:
                suggestions.append(
                    {
                        "mod": mod,
                        "approach": "chaos",
                        "reason": "no fossil boosts this mod",
                    }
                )
        return suggestions

    def resolve_mod_name(
        self,
        display_name: str,
        base_name: str,
        *,
        influences: list[str] | None = None,
    ) -> str | None:
        mods = self._data.get_mod_pool(base_name, influences=influences or [])
        name_cf = display_name.casefold()
        for mod in mods:
            if name_cf in mod.name.casefold():
                return mod.group
        return None

    def mod_weights(
        self,
        base_name: str,
        *,
        ilvl: int = DEFAULT_ILVL,
        influences: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        mods = self._data.get_mod_pool(
            base_name,
            ilvl=ilvl,
            influences=influences or [],
        )
        total = sum(m.weight for m in mods)
        results = []
        for mod in mods[:limit]:
            pct = (mod.weight / total * 100) if total > 0 else 0
            results.append(
                {
                    "mod_id": mod.mod_id,
                    "name": mod.name,
                    "group": mod.group,
                    "affix": mod.affix,
                    "weight": mod.weight,
                    "probability": f"{pct:.2f}%",
                }
            )
        return results

    def get_prices(self, *, league: str = "current") -> dict:
        try:
            with NinjaClient() as client:
                if league == "current":
                    discovery = DiscoveryService(client)
                    info = discovery.get_current_league()
                    resolved = info.name if info else league
                else:
                    resolved = league
                economy = EconomyService(client)
                crafting = economy.get_crafting_prices(resolved)
                result = crafting.model_dump()
                result["league"] = resolved
                return result
        except NinjaError:
            return self._data.get_prices(league=league)
