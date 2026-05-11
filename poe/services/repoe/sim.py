from __future__ import annotations

import asyncio
import copy
import dataclasses
import logging
import os
import random
import typing
from dataclasses import dataclass, field

from poe.exceptions import SimDataError
from poe.services.repoe.constants import (
    CONQUEROR_EXCLUSIONS,
    DEFAULT_ILVL,
    DEFAULT_ITERATIONS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_WORKERS,
    MAX_INFLUENCES,
    RECOMBINATOR_TRANSFER_CHANCE,
    TAINTED_OUTCOME_CHANCE,
    VALUE_RANGE_LENGTH,
)
from poe.types import CraftMethod, Rarity

if typing.TYPE_CHECKING:
    from poe.services.repoe.data import RepoEData

_logger = logging.getLogger("poe.sim")


@dataclass(frozen=True, slots=True)
class BestTier:
    ilvl: int
    values: tuple[tuple[int, int], ...]
    weight: int

    def __post_init__(self) -> None:
        # Inverted ranges (max < min) cause random.randint to raise mid-roll,
        # killing a worker silently. Reject at construction so a malformed
        # RePoE entry surfaces at load time, not at iteration N of N0,000.
        for pair in self.values:
            if len(pair) != VALUE_RANGE_LENGTH or pair[0] > pair[1]:
                raise ValueError(
                    f"BestTier.values entry {pair!r} is invalid: "
                    "expected (min, max) with min <= max"
                )


@dataclass(frozen=True, slots=True)
class ModPoolEntry:
    mod_id: str
    name: str
    affix: str
    group: str
    weight: int
    tier_count: int
    best_tier: BestTier
    implicit_tags: tuple[str, ...]
    influence: str | None
    stat_ids: tuple[str, ...] = ()


@dataclass
class RolledMod:
    """A mod rolled onto an item."""

    mod_id: str
    name: str
    affix: str  # "prefix" or "suffix"
    group: str
    weight: int
    chance: float
    tier: BestTier
    rolls: list
    is_crafted: bool = False
    # Carries through from ModPoolEntry.influence so consumers (awakener_orb,
    # divine, etc.) can identify influenced mods by their data, not by
    # heuristics like `mod_id.startswith("mod_")` which misses most RePoE mods.
    influence: str | None = None


@dataclass
class CraftableItem:
    """An item being crafted."""

    base_name: str
    base_id: str
    ilvl: int
    influences: list[str] = field(default_factory=list)
    rarity: str = Rarity.RARE
    prefixes: list[RolledMod] = field(default_factory=list)
    suffixes: list[RolledMod] = field(default_factory=list)
    max_prefixes: int = 3
    max_suffixes: int = 3
    prefixes_locked: bool = False
    suffixes_locked: bool = False
    fractured_mods: list[RolledMod] = field(default_factory=list)
    implicits: list[RolledMod] = field(default_factory=list)
    max_crafted_mods: int = 1
    is_synthesised: bool = False
    is_mirrored: bool = False
    is_corrupted: bool = False
    catalyst_type: str = ""
    catalyst_quality: int = 0
    # Mutated by apply_metamod for "cannot_roll_attack_mods" /
    # "cannot_roll_caster_mods". _build_mod_pool unions these with any
    # method-specific blocked_tags (fossils) so tagged mods can't roll.
    blocked_tags: set[str] = field(default_factory=set)

    @property
    def all_mods(self) -> list[RolledMod]:
        return self.prefixes + self.suffixes + self.fractured_mods

    @property
    def open_prefixes(self) -> int:
        fractured_prefixes = sum(1 for m in self.fractured_mods if m.affix == "prefix")
        return self.max_prefixes - len(self.prefixes) - fractured_prefixes

    @property
    def open_suffixes(self) -> int:
        fractured_suffixes = sum(1 for m in self.fractured_mods if m.affix == "suffix")
        return self.max_suffixes - len(self.suffixes) - fractured_suffixes

    @property
    def groups(self) -> set[str]:
        return {m.group for m in self.all_mods}

    @property
    def crafted_mod_count(self) -> int:
        return sum(1 for m in self.prefixes + self.suffixes if m.is_crafted)

    def check_invariants(self) -> None:
        """Assert game-rule invariants on the current item state.

        CraftableItem is @dataclass (not Pydantic) so field assignments
        don't trigger validators. Mutation paths in the engine collectively
        enforce these rules at their entry points; this method is the
        forcing function that catches any path that bypasses them. Raises
        SimDataError on violation so simulator workers fail loudly rather
        than silently producing impossible items.
        """
        if self.max_prefixes < 0 or self.max_suffixes < 0 or self.max_crafted_mods < 0:
            msg = (
                f"Negative slot capacity: max_prefixes={self.max_prefixes} "
                f"max_suffixes={self.max_suffixes} "
                f"max_crafted_mods={self.max_crafted_mods}"
            )
            raise SimDataError(msg)

        prefix_total = len(self.prefixes) + sum(
            1 for m in self.fractured_mods if m.affix == "prefix"
        )
        if prefix_total > self.max_prefixes:
            msg = f"prefixes={prefix_total} exceeds max_prefixes={self.max_prefixes}"
            raise SimDataError(msg)

        suffix_total = len(self.suffixes) + sum(
            1 for m in self.fractured_mods if m.affix == "suffix"
        )
        if suffix_total > self.max_suffixes:
            msg = f"suffixes={suffix_total} exceeds max_suffixes={self.max_suffixes}"
            raise SimDataError(msg)

        if self.crafted_mod_count > self.max_crafted_mods:
            msg = (
                f"crafted_mod_count={self.crafted_mod_count} exceeds "
                f"max_crafted_mods={self.max_crafted_mods}"
            )
            raise SimDataError(msg)

        if len(self.influences) > MAX_INFLUENCES:
            msg = (
                f"influences={self.influences!r} exceeds max of {MAX_INFLUENCES} "
                f"(game rule: at most 2 influences per item)"
            )
            raise SimDataError(msg)

        # Conqueror exclusivity (Shaper+Elder etc.) is an entry rule for
        # conqueror_exalt, NOT a permanent state invariant — Awakener's Orb
        # legitimately combines a Shaper item and an Elder item. The pair-rule
        # check lives at the conqueror_exalt boundary; check_invariants stays
        # silent on which conquerors coexist.

        prefix_groups = {m.group for m in self.prefixes}
        if len(prefix_groups) != len(self.prefixes):
            msg = f"duplicate prefix mod group on item: {[m.group for m in self.prefixes]}"
            raise SimDataError(msg)
        suffix_groups = {m.group for m in self.suffixes}
        if len(suffix_groups) != len(self.suffixes):
            msg = f"duplicate suffix mod group on item: {[m.group for m in self.suffixes]}"
            raise SimDataError(msg)


@dataclass
class SimResult:
    """Results from a crafting simulation."""

    method: str
    iterations: int
    hits: int
    hit_rate: float
    avg_attempts: float
    avg_cost_chaos: float
    cost_per_attempt: float
    percentiles: dict[str, int]  # "p50", "p75", "p90", "p99" -> attempts


class CraftingEngine:
    """Simulates PoE crafting using mod pool data."""

    _RARE_MOD_COUNTS: typing.ClassVar[list[int]] = [4, 5, 6]
    _RARE_MOD_WEIGHTS: typing.ClassVar[list[int]] = [8, 3, 1]
    _MIN_MODS_FOR_BOTH_AFFIXES: typing.ClassVar[int] = 2
    _FILTER_ANY: typing.ClassVar[int] = 0
    _FILTER_PREFIX: typing.ClassVar[int] = 1
    _FILTER_SUFFIX: typing.ClassVar[int] = 2

    def __init__(self, data: RepoEData, rng: random.Random | None = None) -> None:
        """Initialize with a RepoEData instance for mod pool lookups."""
        self.data = data
        self._rng = rng or random.Random()
        self._mod_pool_cache: dict[tuple, list[ModPoolEntry]] = {}

    def _rare_mod_count(self) -> int:
        """Sample a rare item mod count using GGG's 58/28/14 distribution."""
        return self._rng.choices(self._RARE_MOD_COUNTS, weights=self._RARE_MOD_WEIGHTS, k=1)[0]

    def create_item(
        self,
        base: str,
        ilvl: int = DEFAULT_ILVL,
        influences: list[str] | None = None,
    ) -> CraftableItem:
        """Create a blank craftable item."""
        bitem = self.data.get_base_item(base)
        if not bitem:
            raise ValueError(f"Unknown base item: {base}")

        base_id = bitem["id"]

        return CraftableItem(
            base_name=base,
            base_id=base_id,
            ilvl=ilvl,
            influences=influences or [],
            max_prefixes=bitem["max_prefixes"],
            max_suffixes=bitem["max_suffixes"],
        )

    def _get_base_mod_pool(
        self,
        item: CraftableItem,
        *,
        extra_domains: frozenset[str] = frozenset(),
    ) -> list[ModPoolEntry]:
        cache_key = (
            item.base_name,
            item.ilvl,
            tuple(sorted(item.influences)),
            tuple(sorted(extra_domains)),
        )
        if cache_key not in self._mod_pool_cache:
            self._mod_pool_cache[cache_key] = self.data.get_mod_pool(
                item.base_name,
                ilvl=item.ilvl,
                influences=item.influences,
                extra_domains=extra_domains,
            )
        return self._mod_pool_cache[cache_key]

    def _build_mod_pool(
        self,
        item: CraftableItem,
        affix_type: str | None = None,
        fossil_weights: dict[str, float] | None = None,
        blocked_tags: set[str] | None = None,
        *,
        extra_domains: frozenset[str] = frozenset(),
    ) -> list[ModPoolEntry]:
        """Build the weighted mod pool for an item, respecting current mods.

        NOTE: Fossil/blocked-tag filtering is duplicated in _prepare_fast_pool.
        Update both when changing mod pool construction logic.
        """
        all_mods = self._get_base_mod_pool(item, extra_domains=extra_domains)

        existing_groups = item.groups
        pool: list[ModPoolEntry] = []
        open_prefixes = item.open_prefixes
        open_suffixes = item.open_suffixes

        # Union method-specific blocked tags (fossils) with item-level
        # blocked tags applied via metamods. apply_metamod populates
        # item.blocked_tags from _METAMOD_BLOCKED_TAGS so cannot_roll_*
        # actually filter the rollable pool.
        effective_blocked: set[str] = set()
        if blocked_tags:
            effective_blocked.update(blocked_tags)
        if item.blocked_tags:
            effective_blocked.update(item.blocked_tags)

        for mod in all_mods:
            if mod.group in existing_groups:
                continue

            affix = mod.affix

            if affix_type and affix != affix_type:
                continue

            if affix == "prefix" and open_prefixes <= 0:
                continue
            if affix == "suffix" and open_suffixes <= 0:
                continue

            if effective_blocked and mod.implicit_tags:
                mod_tags = [t.casefold() for t in mod.implicit_tags]
                if any(t in effective_blocked for t in mod_tags):
                    continue

            if fossil_weights and mod.implicit_tags:
                multiplier = 1.0
                for tag_name in mod.implicit_tags:
                    key = tag_name.casefold()
                    if key in fossil_weights:
                        multiplier *= fossil_weights[key]
                weight = int(mod.weight * max(multiplier, 0))
                if weight <= 0:
                    continue
                pool.append(dataclasses.replace(mod, weight=weight))
            else:
                pool.append(mod)

        return pool

    def _weighted_pick(self, pool: list[ModPoolEntry]) -> ModPoolEntry | None:
        """Weighted random selection from mod pool."""
        if not pool:
            return None
        total = sum(m.weight for m in pool)
        if total <= 0:
            return None
        r = self._rng.randint(1, total)
        cumulative = 0
        for mod in pool:
            cumulative += mod.weight
            if r <= cumulative:
                return mod
        return pool[-1]

    def _roll_values(self, tier: BestTier) -> list:
        """Roll random values within tier ranges."""
        return [self._rng.randint(int(v[0]), int(v[1])) for v in tier.values]

    def _add_mod(self, item: CraftableItem, mod: ModPoolEntry, pool_total: int = 0) -> RolledMod:
        """Roll and add a mod to the item."""
        chance = mod.weight / pool_total if pool_total > 0 else 0

        rolled = RolledMod(
            mod_id=mod.mod_id,
            name=mod.name,
            affix=mod.affix,
            group=mod.group,
            weight=mod.weight,
            chance=chance,
            tier=mod.best_tier,
            influence=mod.influence,
            rolls=self._roll_values(mod.best_tier),
        )

        if mod.affix == "prefix":
            item.prefixes.append(rolled)
        else:
            item.suffixes.append(rolled)

        return rolled

    def _get_fossil_weights(self, fossil_names: list[str]) -> tuple[dict[str, float], set[str]]:
        """Get combined fossil weight multipliers and blocked tags."""
        fossils = self.data.get_fossils()
        weights: dict[str, float] = {}
        blocked_tags: set[str] = set()

        for fossil in fossils:
            if fossil["name"] not in fossil_names:
                continue
            for tag in fossil.get("blocked", []):
                blocked_tags.add(tag.casefold())
            for tag_name, w in fossil.get("positive_weights", {}).items():
                key = tag_name.casefold()
                weights[key] = weights.get(key, 1.0) * w
            for tag_name, w in fossil.get("negative_weights", {}).items():
                key = tag_name.casefold()
                weights[key] = weights.get(key, 1.0) * w

        return weights, blocked_tags

    def _check_craftable(self, item: CraftableItem) -> None:
        if item.is_mirrored:
            raise ValueError("Cannot craft on a mirrored item")
        if item.is_corrupted:
            raise ValueError("Cannot craft on a corrupted item")
        item.check_invariants()

    def _pick_excluding_groups(
        self,
        pool: list[ModPoolEntry],
        excluded_groups: set[str],
        affix_type: str | None = None,
        max_prefixes: int = 3,
        max_suffixes: int = 3,
        current_prefixes: int = 0,
        current_suffixes: int = 0,
    ) -> ModPoolEntry | None:
        # NOTE: Weighted selection with group exclusion is duplicated in
        # _fast_pick / _fast_total. Update both when changing this logic.
        total = 0
        for mod in pool:
            if mod.group in excluded_groups:
                continue
            affix = mod.affix
            if affix_type and affix != affix_type:
                continue
            if affix == "prefix" and current_prefixes >= max_prefixes:
                continue
            if affix == "suffix" and current_suffixes >= max_suffixes:
                continue
            total += mod.weight
        if total <= 0:
            return None
        r = self._rng.randint(1, total)
        cumulative = 0
        for mod in pool:
            if mod.group in excluded_groups:
                continue
            affix = mod.affix
            if affix_type and affix != affix_type:
                continue
            if affix == "prefix" and current_prefixes >= max_prefixes:
                continue
            if affix == "suffix" and current_suffixes >= max_suffixes:
                continue
            cumulative += mod.weight
            if r <= cumulative:
                return mod
        return None

    def _roll_item(
        self,
        item: CraftableItem,
        num_mods: int,
        fossil_weights: dict[str, float] | None = None,
        blocked_tags: set[str] | None = None,
        *,
        require_both_affixes: bool = False,
        extra_domains: frozenset[str] = frozenset(),
    ) -> None:
        # NOTE: Roll logic (mod count, group exclusion, ensure-both-affixes) is
        # duplicated in _run_chunk_fast. Update both when changing roll behavior.
        item.prefixes.clear()
        item.suffixes.clear()

        full_pool = self._build_mod_pool(
            item,
            fossil_weights=fossil_weights,
            blocked_tags=blocked_tags,
            extra_domains=extra_domains,
        )

        for _ in range(num_mods):
            picked = self._pick_excluding_groups(
                full_pool,
                item.groups,
                max_prefixes=item.max_prefixes,
                max_suffixes=item.max_suffixes,
                current_prefixes=len(item.prefixes),
                current_suffixes=len(item.suffixes),
            )
            if picked:
                self._add_mod(item, picked)

        if require_both_affixes and num_mods >= self._MIN_MODS_FOR_BOTH_AFFIXES:
            # Run prefix-fix and suffix-fix independently — both can be empty
            # when small pools exhaust via group-exclusion. The previous
            # if/elif structure only forced one side.
            if not item.prefixes and item.open_prefixes > 0:
                picked = self._pick_excluding_groups(
                    full_pool,
                    item.groups,
                    affix_type="prefix",
                    max_prefixes=item.max_prefixes,
                    max_suffixes=item.max_suffixes,
                    current_prefixes=len(item.prefixes),
                    current_suffixes=len(item.suffixes),
                )
                if picked:
                    self._add_mod(item, picked)
            if not item.suffixes and item.open_suffixes > 0:
                picked = self._pick_excluding_groups(
                    full_pool,
                    item.groups,
                    affix_type="suffix",
                    max_prefixes=item.max_prefixes,
                    max_suffixes=item.max_suffixes,
                    current_prefixes=len(item.prefixes),
                    current_suffixes=len(item.suffixes),
                )
                if picked:
                    self._add_mod(item, picked)

    def chaos_roll(self, item: CraftableItem) -> None:
        self._check_craftable(item)
        item.rarity = Rarity.RARE
        if not item.prefixes_locked and not item.suffixes_locked:
            self._roll_item(item, self._rare_mod_count(), require_both_affixes=True)
            return

        # Both sides locked: nothing to roll. Returning early avoids the
        # if/elif at the bottom assigning affix_type='suffix' for
        # prefixes_locked and then rolling a suffix despite suffixes_locked.
        if item.prefixes_locked and item.suffixes_locked:
            return

        if not item.prefixes_locked:
            item.prefixes.clear()
        if not item.suffixes_locked:
            item.suffixes.clear()

        total_target = self._rare_mod_count()
        remaining = total_target - len(item.all_mods)
        for _ in range(max(remaining, 0)):
            affix_type = None
            if item.prefixes_locked:
                affix_type = "suffix"
            elif item.suffixes_locked:
                affix_type = "prefix"
            pool = self._build_mod_pool(item, affix_type=affix_type)
            picked = self._weighted_pick(pool)
            if picked:
                self._add_mod(item, picked)

    def alt_roll(self, item: CraftableItem) -> None:
        self._check_craftable(item)
        item.rarity = Rarity.MAGIC
        orig_p, orig_s = item.max_prefixes, item.max_suffixes
        item.max_prefixes, item.max_suffixes = 1, 1
        self._roll_item(item, self._rng.randint(1, 2))
        item.max_prefixes, item.max_suffixes = orig_p, orig_s

    def regal(self, item: CraftableItem) -> RolledMod | None:
        self._check_craftable(item)
        if item.rarity != Rarity.MAGIC:
            return None
        item.rarity = Rarity.RARE
        pool = self._build_mod_pool(item)
        picked = self._weighted_pick(pool)
        if picked:
            total = sum(m.weight for m in pool)
            return self._add_mod(item, picked, pool_total=total)
        return None

    def exalt(self, item: CraftableItem) -> RolledMod | None:
        self._check_craftable(item)
        if item.rarity != Rarity.RARE:
            return None
        pool = self._build_mod_pool(item)
        picked = self._weighted_pick(pool)
        if picked:
            total = sum(m.weight for m in pool)
            return self._add_mod(item, picked, pool_total=total)
        return None

    def annul(self, item: CraftableItem) -> RolledMod | None:
        self._check_craftable(item)
        if not item.all_mods:
            return None

        removable = []
        if not item.prefixes_locked:
            removable.extend(m for m in item.prefixes if not m.is_crafted)
        if not item.suffixes_locked:
            removable.extend(m for m in item.suffixes if not m.is_crafted)

        if not removable:
            return None

        removed = self._rng.choice(removable)
        if removed in item.prefixes:
            item.prefixes.remove(removed)
        else:
            item.suffixes.remove(removed)
        return removed

    def scour(self, item: CraftableItem) -> None:
        self._check_craftable(item)
        if item.prefixes_locked and item.suffixes_locked:
            return
        if not item.prefixes_locked:
            item.prefixes.clear()
        if not item.suffixes_locked:
            item.suffixes.clear()
        if not item.prefixes and not item.suffixes and not item.fractured_mods:
            item.rarity = Rarity.NORMAL

    def apply_crafted_mod(
        self,
        item: CraftableItem,
        mod: ModPoolEntry | dict,
    ) -> RolledMod | None:
        self._check_craftable(item)
        if item.crafted_mod_count >= item.max_crafted_mods:
            raise ValueError(
                f"Item already has {item.crafted_mod_count}/{item.max_crafted_mods} crafted mods"
            )
        if isinstance(mod, ModPoolEntry):
            affix = mod.affix
            mod_id = mod.mod_id
            name = mod.name
            group = mod.group
            weight = mod.weight
            tier = mod.best_tier
        else:
            affix = mod["affix"]
            mod_id = mod["mod_id"]
            name = mod["name"]
            group = mod["group"]
            weight = mod.get("weight", 0)
            raw_tier = mod.get("best_tier")
            if isinstance(raw_tier, BestTier):
                tier = raw_tier
            elif isinstance(raw_tier, dict) and raw_tier:
                tier = BestTier(
                    ilvl=raw_tier.get("ilvl", 0),
                    values=tuple(tuple(v) for v in raw_tier.get("values", [])),
                    weight=raw_tier.get("weight", 0),
                )
            else:
                tier = BestTier(ilvl=0, values=(), weight=0)
        if affix == "prefix" and item.open_prefixes <= 0:
            raise ValueError("No open prefix slots")
        if affix == "suffix" and item.open_suffixes <= 0:
            raise ValueError("No open suffix slots")
        # Metamod locks (Cannot Roll/Change Prefixes/Suffixes) gate all mutations
        # on the locked affix, including crafted mods. Without this gate a caller
        # could craft on a "Cannot Be Changed" affix and bypass the lock.
        if affix == "prefix" and item.prefixes_locked:
            raise ValueError("Cannot craft prefix: prefixes are locked by a metamod")
        if affix == "suffix" and item.suffixes_locked:
            raise ValueError("Cannot craft suffix: suffixes are locked by a metamod")
        rolled = RolledMod(
            mod_id=mod_id,
            name=name,
            affix=affix,
            group=group,
            weight=weight,
            chance=1.0,
            tier=tier,
            rolls=self._roll_values(tier) if tier.values else [],
            is_crafted=True,
        )
        if affix == "prefix":
            item.prefixes.append(rolled)
        else:
            item.suffixes.append(rolled)
        return rolled

    def remove_crafted_mod(self, item: CraftableItem, mod_id: str) -> RolledMod | None:
        for mod_list in (item.prefixes, item.suffixes):
            for m in mod_list:
                if m.mod_id == mod_id and m.is_crafted:
                    mod_list.remove(m)
                    return m
        return None

    def remove_all_crafted_mods(self, item: CraftableItem) -> list[RolledMod]:
        removed = []
        for mod_list in (item.prefixes, item.suffixes):
            crafted = [m for m in mod_list if m.is_crafted]
            for m in crafted:
                mod_list.remove(m)
                removed.append(m)
        item.max_crafted_mods = 1
        return removed

    _METAMOD_LOCKS: typing.ClassVar[dict[str, str]] = {
        "prefixes_cannot_be_changed": "prefixes_locked",
        "suffixes_cannot_be_changed": "suffixes_locked",
    }

    _METAMOD_BLOCKED_TAGS: typing.ClassVar[dict[str, set[str]]] = {
        "cannot_roll_attack_mods": {"attack"},
        "cannot_roll_caster_mods": {"caster"},
    }

    def apply_metamod(self, item: CraftableItem, metamod_type: str) -> RolledMod:
        # Validate metamod_type before any state mutation. Without this gate
        # a typo (e.g. "prefix_cannot_be_changed" missing the trailing 's')
        # appended a fake metamod with no lock effect while still consuming
        # a suffix slot and a crafted-mod slot.
        known = set(self._METAMOD_LOCKS) | set(self._METAMOD_BLOCKED_TAGS)
        if metamod_type not in known:
            raise ValueError(
                f"Unknown metamod {metamod_type!r}; must be one of {sorted(known)}"
            )
        self._check_craftable(item)
        if item.open_suffixes <= 0:
            raise ValueError("No open suffix slots for metamod")
        # Metamods consume a crafted slot. Without this check, callers could
        # stack 4+ metamods on a 1-craft item, exceeding the bench's
        # "Can Have Multiple Crafted Mods" cap silently.
        if item.crafted_mod_count >= item.max_crafted_mods:
            raise ValueError(
                f"Item already has {item.crafted_mod_count}/{item.max_crafted_mods} crafted mods"
            )

        lock_attr = self._METAMOD_LOCKS.get(metamod_type)
        if lock_attr:
            setattr(item, lock_attr, True)

        # cannot_roll_attack_mods / cannot_roll_caster_mods don't lock an
        # affix side; they block tagged mods from rolling. Surfacing the
        # blocked tags onto the item lets _build_mod_pool consult them.
        blocked = self._METAMOD_BLOCKED_TAGS.get(metamod_type)
        if blocked:
            item.blocked_tags = item.blocked_tags | blocked

        rolled = RolledMod(
            mod_id=f"metamod_{metamod_type}",
            name=metamod_type.replace("_", " ").title(),
            affix="suffix",
            group=f"Metamod{metamod_type}",
            weight=0,
            chance=1.0,
            tier=BestTier(ilvl=0, values=(), weight=0),
            rolls=[],
            is_crafted=True,
        )
        item.suffixes.append(rolled)
        return rolled

    def remove_metamod(self, item: CraftableItem, metamod_type: str) -> RolledMod | None:
        mod_id = f"metamod_{metamod_type}"
        for m in item.suffixes:
            if m.mod_id == mod_id:
                item.suffixes.remove(m)
                lock_attr = self._METAMOD_LOCKS.get(metamod_type)
                if lock_attr:
                    setattr(item, lock_attr, False)
                return m
        return None

    def _find_essence(self, essences: list[dict], essence_name: str) -> dict | None:
        """Find an essence by name, accepting both 'Greed' and 'Essence of Greed'."""
        name_cf = essence_name.casefold()
        for ess in essences:
            ess_cf = ess["name"].casefold()
            if ess_cf in (name_cf, f"essence of {name_cf}"):
                return ess
        return None

    def essence_roll(self, item: CraftableItem, essence_name: str) -> None:
        self._check_craftable(item)
        item.rarity = Rarity.RARE
        item.prefixes.clear()
        item.suffixes.clear()

        essences = self.data.get_essences(base_name=item.base_name)
        ess = self._find_essence(essences, essence_name)
        if not ess:
            raise ValueError(f"Unknown essence: {essence_name!r}")

        guaranteed_mod = None
        if ess.get("mods"):
            mod_text = ess["mods"][0].get("mod", "")
            pool = self._build_mod_pool(item)
            for m in pool:
                if mod_text in (m.mod_id, m.name):
                    guaranteed_mod = m
                    break
            if not guaranteed_mod:
                text_cf = mod_text.casefold()
                for m in pool:
                    name_cf = m.name.casefold()
                    if name_cf in text_cf or text_cf in name_cf:
                        guaranteed_mod = m
                        break

        if guaranteed_mod:
            self._add_mod(item, guaranteed_mod)

        total_target = self._rare_mod_count()
        remaining = total_target - len(item.all_mods)
        for _ in range(remaining):
            pool = self._build_mod_pool(item)
            picked = self._weighted_pick(pool)
            if picked:
                self._add_mod(item, picked)

        # Rare items always carry at least one prefix and one suffix when
        # mod count >= MIN_MODS_FOR_BOTH_AFFIXES. The guaranteed-essence-mod
        # plus three weighted rolls can all collide on a single affix; force
        # the missing side to mirror chaos/alch/fossil semantics.
        self._force_both_affixes(item, total_target)

    def _force_both_affixes(self, item: CraftableItem, num_mods: int) -> None:
        if num_mods < self._MIN_MODS_FOR_BOTH_AFFIXES:
            return
        if not item.prefixes and item.open_prefixes > 0:
            pool = self._build_mod_pool(item, affix_type="prefix")
            picked = self._weighted_pick(pool)
            if picked:
                self._add_mod(item, picked)
        if not item.suffixes and item.open_suffixes > 0:
            pool = self._build_mod_pool(item, affix_type="suffix")
            picked = self._weighted_pick(pool)
            if picked:
                self._add_mod(item, picked)

    def fossil_roll(self, item: CraftableItem, fossil_names: list[str]) -> None:
        self._check_craftable(item)
        item.rarity = Rarity.RARE
        fossil_weights, blocked_tags = self._get_fossil_weights(fossil_names)
        self._roll_item(
            item,
            self._rare_mod_count(),
            fossil_weights=fossil_weights,
            blocked_tags=blocked_tags,
            require_both_affixes=True,
            # Delve mods are only rollable via fossils.
            extra_domains=frozenset({"delve"}),
        )

    def transmutation(self, item: CraftableItem) -> None:
        self._check_craftable(item)
        if item.rarity != Rarity.NORMAL:
            raise ValueError("Transmutation requires a Normal item")
        item.rarity = Rarity.MAGIC
        orig_p, orig_s = item.max_prefixes, item.max_suffixes
        item.max_prefixes, item.max_suffixes = 1, 1
        self._roll_item(item, self._rng.randint(1, 2))
        item.max_prefixes, item.max_suffixes = orig_p, orig_s

    def augmentation(self, item: CraftableItem) -> RolledMod | None:
        self._check_craftable(item)
        if item.rarity != Rarity.MAGIC:
            raise ValueError("Augmentation requires a Magic item")
        if len(item.prefixes) >= 1 and len(item.suffixes) >= 1:
            raise ValueError("Magic item already has both a prefix and suffix")
        pool = self._build_mod_pool(item)
        picked = self._weighted_pick(pool)
        if picked:
            total = sum(m.weight for m in pool)
            return self._add_mod(item, picked, pool_total=total)
        return None

    def alchemy(self, item: CraftableItem) -> None:
        self._check_craftable(item)
        if item.rarity != Rarity.NORMAL:
            raise ValueError("Alchemy requires a Normal item")
        item.rarity = Rarity.RARE
        self._roll_item(item, self._rare_mod_count(), require_both_affixes=True)

    def divine(self, item: CraftableItem) -> None:
        self._check_craftable(item)
        if not item.prefixes and not item.suffixes and not item.fractured_mods:
            raise ValueError("No mods to reroll values on")
        # Fractured mods can be divined: only the group is locked, not the
        # rolled values. Skipping fractured_mods left them frozen on divines.
        for mod in item.prefixes + item.suffixes + item.fractured_mods:
            mod.rolls = self._roll_values(mod.tier)

    def blessed(self, item: CraftableItem) -> None:
        self._check_craftable(item)
        if not item.implicits:
            raise ValueError("No implicits to reroll values on")
        for mod in item.implicits:
            mod.rolls = self._roll_values(mod.tier)

    def harvest_reforge(
        self,
        item: CraftableItem,
        *,
        tag: str | None = None,
        multiplier: float = 10.0,
    ) -> None:
        self._check_craftable(item)
        item.rarity = Rarity.RARE
        if tag:
            weights = {tag.casefold(): multiplier}
            self._roll_item(
                item,
                self._rare_mod_count(),
                fossil_weights=weights,
                require_both_affixes=True,
            )
        else:
            self._roll_item(item, self._rare_mod_count(), require_both_affixes=True)

    def harvest_augment(self, item: CraftableItem, tag: str) -> RolledMod | None:
        self._check_craftable(item)
        if item.rarity != Rarity.RARE:
            raise ValueError("Harvest augment requires a Rare item")
        pool = self._build_mod_pool(item)
        tag_cf = tag.casefold()
        tagged = [m for m in pool if tag_cf in [t.casefold() for t in m.implicit_tags]]
        if not tagged:
            return None
        picked = self._weighted_pick(tagged)
        if picked:
            total = sum(m.weight for m in tagged)
            return self._add_mod(item, picked, pool_total=total)
        return None

    # Game rule: items can have at most 2 influences, and certain conqueror
    # pairs are mutually exclusive (Shaper+Elder, Crusader+Warlord,
    # Hunter+Redeemer cannot coexist). Eldritch (Searing Exarch / Eater of
    # Worlds) are added via different mechanics, not via this method.
    def conqueror_exalt(self, item: CraftableItem, influence: str) -> RolledMod | None:
        self._check_craftable(item)
        if item.rarity != Rarity.RARE:
            raise ValueError("Conqueror Exalt requires a Rare item")
        if influence not in CONQUEROR_EXCLUSIONS:
            raise ValueError(
                f"Unknown conqueror influence: {influence!r}. Valid: {sorted(CONQUEROR_EXCLUSIONS)}"
            )
        excluded = CONQUEROR_EXCLUSIONS[influence]
        if excluded in item.influences:
            raise ValueError(
                f"Influence {influence!r} is mutually exclusive with "
                f"existing influence {excluded!r}"
            )
        if influence not in item.influences and len(item.influences) >= MAX_INFLUENCES:
            raise ValueError(
                f"Item already has {len(item.influences)} influences (max 2): {item.influences}"
            )
        if influence not in item.influences:
            item.influences.append(influence)
        pool = self._build_mod_pool(item)
        inf_pool = [m for m in pool if m.influence is not None]
        if not inf_pool:
            return None
        picked = self._weighted_pick(inf_pool)
        if picked:
            total = sum(m.weight for m in inf_pool)
            return self._add_mod(item, picked, pool_total=total)
        return None

    def awakener_orb(
        self,
        item1: CraftableItem,
        item2: CraftableItem,
    ) -> CraftableItem:
        self._check_craftable(item1)
        self._check_craftable(item2)
        if not item1.influences or not item2.influences:
            raise ValueError("Both items must be influenced")
        if set(item1.influences) & set(item2.influences):
            raise ValueError("Items must have different influences")
        # Filter by influence field — most real RePoE mod IDs don't start
        # with "mod_", so the previous startswith heuristic dropped almost
        # every actual influence mod, producing a chaos-rolled item with
        # no preserved influence mods (contract violation).
        inf1_mods = [m for m in item1.all_mods if m.influence is not None]
        inf2_mods = [m for m in item2.all_mods if m.influence is not None]
        kept_mod1 = self._rng.choice(inf1_mods) if inf1_mods else None
        kept_mod2 = self._rng.choice(inf2_mods) if inf2_mods else None
        # Combine influences with deterministic order (item1 first, item2's new
        # entries appended) and cap at MAX_INFLUENCES so an Awakener-on-already-
        # awakened item can't push the count past the game-rule cap.
        combined: list[str] = list(item1.influences)
        for inf in item2.influences:
            if inf not in combined:
                combined.append(inf)
        item2.influences = combined[:MAX_INFLUENCES]
        item2.prefixes.clear()
        item2.suffixes.clear()
        # Copy the kept mods so subsequent mutations on item2 (divine, etc.)
        # don't reach back into item1 via shared RolledMod references. Skip
        # the second kept mod when its group collides with the first — same-
        # group prefix/suffix duplicates would fail check_invariants on the
        # next mutation.
        used_groups: set[str] = set()
        for mod in (kept_mod1, kept_mod2):
            if not mod or mod.group in used_groups:
                continue
            mod_copy = copy.copy(mod)
            if mod_copy.affix == "prefix" and item2.open_prefixes > 0:
                item2.prefixes.append(mod_copy)
                used_groups.add(mod_copy.group)
            elif mod_copy.affix == "suffix" and item2.open_suffixes > 0:
                item2.suffixes.append(mod_copy)
                used_groups.add(mod_copy.group)
        remaining = self._rare_mod_count() - len(item2.prefixes) - len(item2.suffixes)
        for _ in range(max(remaining, 0)):
            pool = self._build_mod_pool(item2)
            picked = self._weighted_pick(pool)
            if picked:
                self._add_mod(item2, picked)
        item2.check_invariants()
        return item2

    def veiled_chaos(self, item: CraftableItem) -> None:
        self._check_craftable(item)
        if item.rarity != Rarity.RARE:
            raise ValueError("Veiled Chaos requires a Rare item")
        self.chaos_roll(item)
        # Veiled mods come from the "unveiled" domain; only veiled-chaos and
        # aisling_bench unlock that domain.
        pool = self._build_mod_pool(item, extra_domains=frozenset({"unveiled"}))
        if pool:
            picked = self._weighted_pick(pool)
            if picked:
                mod = self._add_mod(item, picked)
                mod.name = f"Veiled: {mod.name}"

    def aisling_bench(self, item: CraftableItem) -> RolledMod | None:
        self._check_craftable(item)
        if item.rarity != Rarity.RARE:
            raise ValueError("Aisling bench requires a Rare item")
        removable = [m for m in item.prefixes + item.suffixes if not m.is_crafted]
        if not removable:
            return None
        removed = self._rng.choice(removable)
        if removed in item.prefixes:
            item.prefixes.remove(removed)
        else:
            item.suffixes.remove(removed)
        pool = self._build_mod_pool(item, extra_domains=frozenset({"unveiled"}))
        if not pool:
            return None
        picked = self._weighted_pick(pool)
        if picked:
            mod = self._add_mod(item, picked)
            mod.name = f"Veiled: {mod.name}"
            return mod
        return None

    def vaal_orb(self, item: CraftableItem) -> str:
        # Mirrored items can't be vaal'd; corrupted items can't be re-corrupted.
        # Without these gates, the "reroll" outcome would call _roll_item on a
        # corrupted/mirrored item, which violates the engine's craftable contract.
        if item.is_corrupted:
            raise ValueError("Item is already corrupted")
        if item.is_mirrored:
            raise ValueError("Mirrored items cannot be corrupted")
        outcome = self._rng.choice(["implicit", "reroll", "nothing", "brick"])
        if outcome == "reroll":
            # Roll while uncorrupted, then mark corrupted, so _roll_item's
            # internal _check_craftable does not reject.
            item.rarity = Rarity.RARE
            self._roll_item(item, self._rare_mod_count())
        item.is_corrupted = True
        if outcome == "implicit":
            item.implicits.append(
                RolledMod(
                    mod_id="corruption_implicit",
                    name="Corruption Implicit",
                    affix="implicit",
                    group="CorruptionImplicit",
                    weight=0,
                    chance=1.0,
                    tier=BestTier(ilvl=0, values=(), weight=0),
                    rolls=[],
                )
            )
        return outcome

    def recombinate(
        self,
        item1: CraftableItem,
        item2: CraftableItem,
    ) -> CraftableItem:
        # Pick a base, then derive max_prefixes/max_suffixes from THAT base.
        # Using item1's caps unconditionally let a flask-base recombine end up
        # with body-armour 3/3 caps and 6 transferred mods.
        chosen_idx = self._rng.choice([0, 1])
        chosen_base_name = (item1.base_name, item2.base_name)[chosen_idx]
        chosen_base_id = (item1.base_id, item2.base_id)[chosen_idx]
        chosen_max_p = (item1.max_prefixes, item2.max_prefixes)[chosen_idx]
        chosen_max_s = (item1.max_suffixes, item2.max_suffixes)[chosen_idx]
        # The bundled base record is the source of truth in case the original
        # item caps were tampered with (negative, oversize, etc.).
        bitem = self.data.get_base_item(chosen_base_name)
        if bitem is not None:
            chosen_max_p = bitem.get("max_prefixes", chosen_max_p)
            chosen_max_s = bitem.get("max_suffixes", chosen_max_s)
        result = CraftableItem(
            base_name=chosen_base_name,
            base_id=chosen_base_id,
            ilvl=max(item1.ilvl, item2.ilvl),
            rarity=Rarity.RARE,
            max_prefixes=chosen_max_p,
            max_suffixes=chosen_max_s,
        )
        all_prefixes = list(item1.prefixes + item2.prefixes)
        all_suffixes = list(item1.suffixes + item2.suffixes)
        # Copy each transferred mod so divine/blessed on the result item
        # doesn't re-roll the same RolledMod still owned by item1/item2.
        for mod in all_prefixes:
            if (
                self._rng.random() < RECOMBINATOR_TRANSFER_CHANCE
                and result.open_prefixes > 0
                and mod.group not in result.groups
            ):
                result.prefixes.append(copy.copy(mod))
        for mod in all_suffixes:
            if (
                self._rng.random() < RECOMBINATOR_TRANSFER_CHANCE
                and result.open_suffixes > 0
                and mod.group not in result.groups
            ):
                result.suffixes.append(copy.copy(mod))
        if item1.influences or item2.influences:
            combined: list[str] = list(item1.influences)
            for inf in item2.influences:
                if inf not in combined:
                    combined.append(inf)
            result.influences = combined[:MAX_INFLUENCES]
        result.check_invariants()
        return result

    def beast_prefix_to_suffix(
        self,
        item: CraftableItem,
    ) -> tuple[RolledMod | None, RolledMod | None]:
        self._check_craftable(item)
        added = None
        removed = None
        if item.suffixes:
            removed = self._rng.choice(item.suffixes)
            item.suffixes.remove(removed)
        pool = self._build_mod_pool(item, affix_type="prefix")
        picked = self._weighted_pick(pool)
        if picked:
            added = self._add_mod(item, picked)
        return added, removed

    def beast_suffix_to_prefix(
        self,
        item: CraftableItem,
    ) -> tuple[RolledMod | None, RolledMod | None]:
        self._check_craftable(item)
        added = None
        removed = None
        if item.prefixes:
            removed = self._rng.choice(item.prefixes)
            item.prefixes.remove(removed)
        pool = self._build_mod_pool(item, affix_type="suffix")
        picked = self._weighted_pick(pool)
        if picked:
            added = self._add_mod(item, picked)
        return added, removed

    def beast_imprint(self, item: CraftableItem) -> CraftableItem:
        if item.rarity != Rarity.MAGIC:
            raise ValueError("Imprint requires a Magic item")
        return copy.deepcopy(item)

    def beast_split(self, item: CraftableItem) -> tuple[CraftableItem, CraftableItem]:
        self._check_craftable(item)
        item1 = copy.deepcopy(item)
        item2 = copy.deepcopy(item)
        # Partition mods between the two halves; copy each transferred mod
        # so subsequent mutations on item1/item2 don't reach back into the
        # source item via shared RolledMod references.
        item1.prefixes = []
        item1.suffixes = []
        item2.prefixes = []
        item2.suffixes = []
        for m in item.prefixes:
            target = item1 if self._rng.random() < RECOMBINATOR_TRANSFER_CHANCE else item2
            target.prefixes.append(copy.copy(m))
        for m in item.suffixes:
            target = item1 if self._rng.random() < RECOMBINATOR_TRANSFER_CHANCE else item2
            target.suffixes.append(copy.copy(m))
        # PoE beast split does NOT mirror the halves (game-correct).
        return item1, item2

    _MIN_MODS_FOR_FRACTURE: typing.ClassVar[int] = 4

    def fracture(self, item: CraftableItem) -> RolledMod | None:
        self._check_craftable(item)
        if item.rarity != Rarity.RARE:
            raise ValueError("Fracturing requires a Rare item")
        if item.fractured_mods:
            raise ValueError("Item already has a fractured mod")
        all_explicit = item.prefixes + item.suffixes
        if len(all_explicit) < self._MIN_MODS_FOR_FRACTURE:
            raise ValueError(f"Item needs at least {self._MIN_MODS_FOR_FRACTURE} mods to fracture")
        target = self._rng.choice(all_explicit)
        if target in item.prefixes:
            item.prefixes.remove(target)
        else:
            item.suffixes.remove(target)
        item.fractured_mods.append(target)
        return target

    def tainted_divine(self, item: CraftableItem) -> None:
        if not item.is_corrupted:
            raise ValueError("Tainted Divine requires a corrupted item")
        for mod in item.prefixes + item.suffixes:
            mod.rolls = self._roll_values(mod.tier)

    def tainted_chaos(self, item: CraftableItem) -> str:
        if item.is_mirrored:
            raise ValueError("Mirrored items cannot be tainted-chaos'd")
        if not item.is_corrupted:
            raise ValueError("Tainted Chaos requires a corrupted item")
        if self._rng.random() < TAINTED_OUTCOME_CHANCE:
            pool = self._build_mod_pool(item)
            picked = self._weighted_pick(pool)
            if picked:
                self._add_mod(item, picked)
            return "added"
        all_mods = item.prefixes + item.suffixes
        if all_mods:
            removed = self._rng.choice(all_mods)
            if removed in item.prefixes:
                item.prefixes.remove(removed)
            else:
                item.suffixes.remove(removed)
        return "removed"

    def tainted_exalt(self, item: CraftableItem) -> str:
        if item.is_mirrored:
            raise ValueError("Mirrored items cannot be tainted-exalt'd")
        if not item.is_corrupted:
            raise ValueError("Tainted Exalt requires a corrupted item")
        if self._rng.random() < TAINTED_OUTCOME_CHANCE:
            pool = self._build_mod_pool(item)
            picked = self._weighted_pick(pool)
            if picked:
                self._add_mod(item, picked)
            return "added"
        all_mods = item.prefixes + item.suffixes
        if all_mods:
            removed = self._rng.choice(all_mods)
            if removed in item.prefixes:
                item.prefixes.remove(removed)
            else:
                item.suffixes.remove(removed)
        return "removed"

    def tainted_mythic(self, item: CraftableItem) -> str:
        if not item.is_corrupted:
            raise ValueError("Tainted Mythic requires a corrupted item")
        if item.rarity != Rarity.UNIQUE:
            raise ValueError("Tainted Mythic requires a Unique item")
        return "transformed"

    def tainted_fusing(self, item: CraftableItem) -> str:
        if not item.is_corrupted:
            raise ValueError("Tainted Fusing requires a corrupted item")
        return "relinked"

    def _apply_roll(
        self,
        item: CraftableItem,
        method: str,
        fossil_weights: dict[str, float] | None,
        blocked_tags: set[str] | None,
        essence_name: str | None,
    ) -> None:
        """Apply a single roll to the item based on the crafting method."""
        if method == CraftMethod.ESSENCE and essence_name:
            self.essence_roll(item, essence_name)
        elif method == CraftMethod.FOSSIL and fossil_weights:
            item.rarity = Rarity.RARE
            self._roll_item(
                item,
                self._rare_mod_count(),
                fossil_weights=fossil_weights,
                blocked_tags=blocked_tags,
                require_both_affixes=True,
            )
        elif method == CraftMethod.ALT:
            item.rarity = Rarity.MAGIC
            orig_p, orig_s = item.max_prefixes, item.max_suffixes
            item.max_prefixes, item.max_suffixes = 1, 1
            self._roll_item(item, self._rng.randint(1, 2))
            item.max_prefixes, item.max_suffixes = orig_p, orig_s
        elif method in (CraftMethod.CHAOS, CraftMethod.ALCHEMY, CraftMethod.HARVEST):
            item.rarity = Rarity.RARE
            self._roll_item(item, self._rare_mod_count(), require_both_affixes=True)
        elif method == CraftMethod.TRANSMUTATION:
            item.rarity = Rarity.MAGIC
            orig_p, orig_s = item.max_prefixes, item.max_suffixes
            item.max_prefixes, item.max_suffixes = 1, 1
            self._roll_item(item, self._rng.randint(1, 2))
            item.max_prefixes, item.max_suffixes = orig_p, orig_s
        else:
            valid = ", ".join(m.value for m in CraftMethod)
            raise ValueError(f"Unknown craft method: {method!r} (valid: {valid})")

    def _get_cost_per_attempt(
        self,
        method: str,
        fossils: list[str] | None,
        essence_name: str | None,
    ) -> float:
        """Calculate the chaos-equivalent cost per crafting attempt."""
        # Narrow the suppression: only data-availability errors should hide
        # here. A bare Exception swallow masked schema mismatches and
        # programming bugs. SimDataError covers data-layer surprises;
        # FileNotFoundError covers a missing bundled JSON; OSError covers
        # disk read failures.
        prices = None
        try:
            prices = self.data.get_prices()
        except (SimDataError, FileNotFoundError, OSError) as e:
            _logger.warning("get_prices unavailable, defaulting cost: %s", e)

        if method == CraftMethod.FOSSIL and fossils:
            return self.data.get_craft_cost("fossil", prices=prices, fossils=fossils)
        if method == CraftMethod.ESSENCE and essence_name:
            return self.data.get_craft_cost("essence", prices=prices, essence=essence_name)
        if method == CraftMethod.ALT:
            return self.data.get_craft_cost("alt", prices=prices)
        return 1.0

    @staticmethod
    def _run_chunk(
        data: RepoEData,
        base: str,
        ilvl: int,
        method: str,
        target_set: set[str],
        chunk_size: int,
        max_attempts: int,
        match_mode: str,
        fossil_weights: dict[str, float] | None,
        blocked_tags: set[str] | None,
        essence_name: str | None,
        existing_mods: list[str] | None,
        influences: list[str],
        seed: int,
    ) -> list[int]:
        if method in (CraftMethod.CHAOS, CraftMethod.FOSSIL, CraftMethod.ALT):
            return CraftingEngine._run_chunk_fast(
                data,
                base,
                ilvl,
                method,
                target_set,
                chunk_size,
                max_attempts,
                match_mode,
                fossil_weights,
                blocked_tags,
                existing_mods,
                influences,
                seed,
            )
        engine = CraftingEngine(data, rng=random.Random(seed))
        attempts_on_hit: list[int] = []
        item = engine.create_item(base, ilvl, influences)
        pinned_pool_entries: list[ModPoolEntry] = []
        pinned_groups: set[str] = set()
        if existing_mods:
            pool = engine._build_mod_pool(item)
            for mod_name in existing_mods:
                for m in pool:
                    if m.group.casefold() == mod_name.casefold():
                        pinned_pool_entries.append(m)
                        pinned_groups.add(m.group.casefold())
                        break

        for _ in range(chunk_size):
            for attempt in range(1, max_attempts + 1):
                engine._apply_roll(
                    item,
                    method,
                    fossil_weights,
                    blocked_tags,
                    essence_name,
                )
                if pinned_pool_entries:
                    item.prefixes = [
                        m for m in item.prefixes if m.group.casefold() not in pinned_groups
                    ]
                    item.suffixes = [
                        m for m in item.suffixes if m.group.casefold() not in pinned_groups
                    ]
                    pinned_prefix_count = sum(1 for p in pinned_pool_entries if p.affix == "prefix")
                    pinned_suffix_count = len(pinned_pool_entries) - pinned_prefix_count
                    # SimService.simulate validates pinned ≤ max_{prefix,suffix} at the
                    # boundary, so the subtraction can't go negative in practice. The
                    # max(0, ...) is defensive in case a future code path bypasses
                    # that validation.
                    prefix_room = max(0, item.max_prefixes - pinned_prefix_count)
                    suffix_room = max(0, item.max_suffixes - pinned_suffix_count)
                    if len(item.prefixes) > prefix_room:
                        item.prefixes = item.prefixes[:prefix_room]
                    if len(item.suffixes) > suffix_room:
                        item.suffixes = item.suffixes[:suffix_room]
                    for pinned in pinned_pool_entries:
                        engine._add_mod(item, pinned)

                if match_mode == "all":
                    hit = all(
                        any(t == m.group.casefold() for m in item.prefixes)
                        or any(t == m.group.casefold() for m in item.suffixes)
                        or any(t == m.group.casefold() for m in item.fractured_mods)
                        for t in target_set
                    )
                else:
                    hit = any(
                        any(t == m.group.casefold() for m in item.prefixes)
                        or any(t == m.group.casefold() for m in item.suffixes)
                        or any(t == m.group.casefold() for m in item.fractured_mods)
                        for t in target_set
                    )
                if hit:
                    attempts_on_hit.append(attempt)
                    break

        return attempts_on_hit

    @staticmethod
    def _fast_total(
        rolled_groups: set[str],
        n_prefix: int,
        n_suffix: int,
        max_p: int,
        max_s: int,
        group_prefix_w: dict[str, int],
        group_suffix_w: dict[str, int],
        total_prefix_w: int,
        total_suffix_w: int,
        affix_filter: int = 0,
    ) -> int:
        _fp = CraftingEngine._FILTER_PREFIX
        _fs = CraftingEngine._FILTER_SUFFIX
        prefix_avail = affix_filter != _fs and n_prefix < max_p
        suffix_avail = affix_filter != _fp and n_suffix < max_s
        total = 0
        if prefix_avail:
            total += total_prefix_w
            for g in rolled_groups:
                total -= group_prefix_w.get(g, 0)
        if suffix_avail:
            total += total_suffix_w
            for g in rolled_groups:
                total -= group_suffix_w.get(g, 0)
        return total

    @staticmethod
    def _fast_pick(
        pool_size: int,
        weights: list[int],
        groups: list[str],
        is_prefix: list[bool],
        rolled_groups: set[str],
        n_prefix: int,
        n_suffix: int,
        max_p: int,
        max_s: int,
        rng_randint: typing.Callable,
        group_prefix_w: dict[str, int],
        group_suffix_w: dict[str, int],
        total_prefix_w: int,
        total_suffix_w: int,
        affix_filter: int = 0,
    ) -> int:
        """Return pool index of picked mod, or -1 if none available."""
        total = CraftingEngine._fast_total(
            rolled_groups,
            n_prefix,
            n_suffix,
            max_p,
            max_s,
            group_prefix_w,
            group_suffix_w,
            total_prefix_w,
            total_suffix_w,
            affix_filter,
        )
        if total <= 0:
            return -1
        prefix_full = n_prefix >= max_p
        suffix_full = n_suffix >= max_s
        _fp = CraftingEngine._FILTER_PREFIX
        _fs = CraftingEngine._FILTER_SUFFIX
        r = rng_randint(0, total - 1)
        cumulative = 0
        for i in range(pool_size):
            if groups[i] in rolled_groups:
                continue
            ip = is_prefix[i]
            if affix_filter == _fp and not ip:
                continue
            if affix_filter == _fs and ip:
                continue
            if ip and prefix_full:
                continue
            if not ip and suffix_full:
                continue
            cumulative += weights[i]
            if r < cumulative:
                return i
        return -1

    @staticmethod
    def _prepare_fast_pool(
        data: RepoEData,
        base: str,
        ilvl: int,
        influences: list[str],
        fossil_weights: dict[str, float] | None,
        blocked_tags: set[str] | None,
        *,
        extra_domains: frozenset[str] = frozenset(),
    ) -> tuple[int, list[int], list[str], list[bool], dict[str, int], dict[str, int], int, int]:
        engine = CraftingEngine(data)
        base_pool = engine._get_base_mod_pool(
            engine.create_item(base, ilvl, influences),
            extra_domains=extra_domains,
        )

        if fossil_weights:
            filtered: list[ModPoolEntry] = []
            for mod in base_pool:
                if blocked_tags and mod.implicit_tags:
                    mod_tags = [t.casefold() for t in mod.implicit_tags]
                    if any(t in blocked_tags for t in mod_tags):
                        continue
                if mod.implicit_tags:
                    multiplier = 1.0
                    for tag_name in mod.implicit_tags:
                        key = tag_name.casefold()
                        if key in fossil_weights:
                            multiplier *= fossil_weights[key]
                    w = int(mod.weight * max(multiplier, 0))
                    if w <= 0:
                        continue
                    filtered.append(dataclasses.replace(mod, weight=w))
                else:
                    filtered.append(mod)
            base_pool = filtered

        pool_size = len(base_pool)
        weights = [m.weight for m in base_pool]
        groups = [m.group.casefold() for m in base_pool]
        is_prefix = [m.affix == "prefix" for m in base_pool]

        group_prefix_w: dict[str, int] = {}
        group_suffix_w: dict[str, int] = {}
        total_prefix_w = 0
        total_suffix_w = 0
        for i in range(pool_size):
            g = groups[i]
            w = weights[i]
            if is_prefix[i]:
                group_prefix_w[g] = group_prefix_w.get(g, 0) + w
                total_prefix_w += w
            else:
                group_suffix_w[g] = group_suffix_w.get(g, 0) + w
                total_suffix_w += w

        return (
            pool_size,
            weights,
            groups,
            is_prefix,
            group_prefix_w,
            group_suffix_w,
            total_prefix_w,
            total_suffix_w,
        )

    @staticmethod
    def _resolve_pinned_groups(
        existing_mods: list[str] | None,
        groups: list[str],
        is_prefix: list[bool] | None = None,
    ) -> tuple[set[str], int, int]:
        pinned: set[str] = set()
        n_pinned_prefix = 0
        n_pinned_suffix = 0
        if existing_mods:
            for mod_name in existing_mods:
                mcf = mod_name.casefold()
                for i, g in enumerate(groups):
                    if g == mcf:
                        pinned.add(g)
                        if is_prefix is not None and is_prefix[i]:
                            n_pinned_prefix += 1
                        elif is_prefix is not None:
                            n_pinned_suffix += 1
                        break
        return pinned, n_pinned_prefix, n_pinned_suffix

    @staticmethod
    def _run_chunk_fast(
        data: RepoEData,
        base: str,
        ilvl: int,
        method: str,
        target_set: set[str],
        chunk_size: int,
        max_attempts: int,
        match_mode: str,
        fossil_weights: dict[str, float] | None,
        blocked_tags: set[str] | None,
        existing_mods: list[str] | None,
        influences: list[str],
        seed: int,
    ) -> list[int]:
        """Optimized simulation loop for chaos/fossil/alt methods.

        This is a performance-critical duplicate of the logic in:
        - _build_mod_pool (fossil weight filtering) → _prepare_fast_pool
        - _roll_item (mod count, group exclusion, ensure-both-affixes)
        - _pick_excluding_groups (weighted selection) → _fast_pick / _fast_total

        It skips RolledMod/CraftableItem object creation and uses precomputed
        parallel arrays + per-group weight sums for O(1) total weight lookups.

        If you change crafting roll logic in any of those methods, you MUST
        update the corresponding code here or simulation results will diverge.
        """
        rng = random.Random(seed)
        rng_randint = rng.randint
        choices_fn = rng.choices

        (
            pool_size,
            weights,
            groups,
            is_prefix,
            group_prefix_w,
            group_suffix_w,
            total_prefix_w,
            total_suffix_w,
        ) = CraftingEngine._prepare_fast_pool(
            data,
            base,
            ilvl,
            influences,
            fossil_weights,
            blocked_tags,
            extra_domains=(frozenset({"delve"}) if method == CraftMethod.FOSSIL else frozenset()),
        )

        mod_counts = CraftingEngine._RARE_MOD_COUNTS
        mod_weights = CraftingEngine._RARE_MOD_WEIGHTS
        is_alt = method == CraftMethod.ALT
        # Use the base's actual max_{prefixes,suffixes}; previously hardcoded
        # to 3/3, which produced incorrect distributions on jewels (max 2),
        # flasks (max 1), abyss jewels (max 2), and any future base with
        # non-3/3 caps. Alt orbs always cap at 1/1 (Magic items).
        bitem = data.get_base_item(base)
        base_max_p = bitem["max_prefixes"] if bitem else 3
        base_max_s = bitem["max_suffixes"] if bitem else 3
        max_p = 1 if is_alt else base_max_p
        max_s = 1 if is_alt else base_max_s
        min_both = CraftingEngine._MIN_MODS_FOR_BOTH_AFFIXES

        pinned_groups, pinned_prefixes, pinned_suffixes = CraftingEngine._resolve_pinned_groups(
            existing_mods, groups, is_prefix
        )
        n_pinned = len(pinned_groups)
        match_all = match_mode == "all"
        attempts_on_hit: list[int] = []
        append = attempts_on_hit.append

        for _ in range(chunk_size):
            for attempt in range(1, max_attempts + 1):
                num_mods = (
                    rng.randint(1, 2)
                    if is_alt
                    else choices_fn(
                        mod_counts,
                        weights=mod_weights,
                        k=1,
                    )[0]
                )
                new_mods = max(0, num_mods - n_pinned)

                rolled_groups: set[str] = set(pinned_groups)
                n_prefix = pinned_prefixes
                n_suffix = pinned_suffixes

                fast_pick = CraftingEngine._fast_pick
                pick_args = (
                    pool_size,
                    weights,
                    groups,
                    is_prefix,
                )
                weight_args = (
                    group_prefix_w,
                    group_suffix_w,
                    total_prefix_w,
                    total_suffix_w,
                )
                for _ in range(new_mods):
                    idx = fast_pick(
                        *pick_args,
                        rolled_groups,
                        n_prefix,
                        n_suffix,
                        max_p,
                        max_s,
                        rng_randint,
                        *weight_args,
                    )
                    if idx < 0:
                        break
                    rolled_groups.add(groups[idx])
                    if is_prefix[idx]:
                        n_prefix += 1
                    else:
                        n_suffix += 1

                if not is_alt and num_mods >= min_both:
                    # Run prefix-fix and suffix-fix independently so an item
                    # that rolled zero prefixes AND zero suffixes (rare but
                    # possible when small pools collide on existing groups)
                    # gets one of EACH forced, mirroring the slow path's
                    # require_both_affixes behavior. The previous if/elif
                    # only ever forced a single side.
                    if n_prefix == 0 and n_prefix < max_p:
                        idx = fast_pick(
                            *pick_args,
                            rolled_groups,
                            n_prefix,
                            n_suffix,
                            max_p,
                            max_s,
                            rng_randint,
                            *weight_args,
                            affix_filter=CraftingEngine._FILTER_PREFIX,
                        )
                        if idx >= 0:
                            rolled_groups.add(groups[idx])
                            n_prefix += 1
                    if n_suffix == 0 and n_suffix < max_s:
                        idx = fast_pick(
                            *pick_args,
                            rolled_groups,
                            n_prefix,
                            n_suffix,
                            max_p,
                            max_s,
                            rng_randint,
                            *weight_args,
                            affix_filter=CraftingEngine._FILTER_SUFFIX,
                        )
                        if idx >= 0:
                            rolled_groups.add(groups[idx])
                            n_suffix += 1

                if match_all:
                    hit = target_set <= rolled_groups
                else:
                    hit = not target_set.isdisjoint(rolled_groups)
                if hit:
                    append(attempt)
                    break

        return attempts_on_hit

    async def simulate(
        self,
        base: str,
        ilvl: int,
        method: str,
        target_mods: list[str],
        iterations: int = DEFAULT_ITERATIONS,
        influences: list[str] | None = None,
        fossils: list[str] | None = None,
        match_mode: str = "all",
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        essence_name: str | None = None,
        existing_mods: list[str] | None = None,
        workers: int | None = None,
    ) -> SimResult:
        target_set = {t.casefold() for t in target_mods}

        fossil_weights, blocked_tags = None, None
        if method == CraftMethod.FOSSIL and fossils:
            fossil_weights, blocked_tags = self._get_fossil_weights(fossils)

        num_workers = workers or min((os.cpu_count() or 2) // 2, DEFAULT_WORKERS)
        num_workers = max(num_workers, 1)
        chunk_size = iterations // num_workers
        remainder = iterations % num_workers

        base_seed = self._rng.randint(0, 2**31)

        tasks = []
        for i in range(num_workers):
            size = chunk_size + (1 if i < remainder else 0)
            if size <= 0:
                continue
            tasks.append(
                asyncio.to_thread(
                    self._run_chunk,
                    self.data,
                    base,
                    ilvl,
                    method,
                    target_set,
                    size,
                    max_attempts,
                    match_mode,
                    fossil_weights,
                    blocked_tags,
                    essence_name,
                    existing_mods,
                    influences or [],
                    base_seed + i,
                )
            )

        chunk_results = await asyncio.gather(*tasks)

        all_attempts: list[int] = []
        for chunk in chunk_results:
            all_attempts.extend(chunk)

        hits = len(all_attempts)
        cost_per = self._get_cost_per_attempt(method, fossils, essence_name)
        avg_attempts = sum(all_attempts) / len(all_attempts) if all_attempts else float("inf")
        hit_rate = hits / iterations if iterations > 0 else 0

        percentiles = {}
        if all_attempts:
            sorted_attempts = sorted(all_attempts)
            for label, pct in [("p50", 0.5), ("p75", 0.75), ("p90", 0.9), ("p99", 0.99)]:
                idx = min(int(len(sorted_attempts) * pct), len(sorted_attempts) - 1)
                percentiles[label] = sorted_attempts[idx]

        return SimResult(
            method=method,
            iterations=iterations,
            hits=hits,
            hit_rate=hit_rate,
            avg_attempts=avg_attempts,
            avg_cost_chaos=avg_attempts * cost_per,
            cost_per_attempt=cost_per,
            percentiles=percentiles,
        )
