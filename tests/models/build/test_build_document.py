from __future__ import annotations

import pytest

from poe.models.build import (
    BuildConfig,
    BuildDocument,
    Item,
    ItemSet,
    ItemSlot,
    StatEntry,
    TreeSpec,
)

# ── Item slot counting ───────────────────────────────────────────────────────


class TestItemSlots:
    def test_open_prefixes_all_open(self):
        item = Item(id=1, text="", prefix_slots=[None, None, None])
        assert item.open_prefixes == 3

    def test_open_prefixes_some_filled(self):
        item = Item(id=1, text="", prefix_slots=["IncreasedLife6", None, "SpellDamage3"])
        assert item.open_prefixes == 1

    def test_open_prefixes_none_open(self):
        item = Item(id=1, text="", prefix_slots=["A", "B", "C"])
        assert item.open_prefixes == 0

    def test_open_suffixes_all_open(self):
        item = Item(id=1, text="", suffix_slots=[None, None, None])
        assert item.open_suffixes == 3

    def test_open_suffixes_mixed(self):
        item = Item(id=1, text="", suffix_slots=["ColdRes5", None])
        assert item.open_suffixes == 1

    def test_filled_prefixes(self):
        item = Item(id=1, text="", prefix_slots=["IncreasedLife6", None, "SpellDamage3"])
        assert item.filled_prefixes == 2

    def test_filled_suffixes(self):
        item = Item(id=1, text="", suffix_slots=["ColdRes5", "LightRes4", None])
        assert item.filled_suffixes == 2

    def test_empty_slots_lists(self):
        item = Item(id=1, text="")
        assert item.open_prefixes == 0
        assert item.open_suffixes == 0
        assert item.filled_prefixes == 0
        assert item.filled_suffixes == 0


# ── BuildDocument.get_stat ───────────────────────────────────────────────────────────


class TestBuildGetStat:
    def test_stat_found(self):
        build = BuildDocument(
            player_stats=[
                StatEntry(stat="Life", value=4500),
                StatEntry(stat="TotalDPS", value=150000),
            ]
        )
        assert build.get_stat("Life") == 4500

    def test_stat_missing(self):
        build = BuildDocument(player_stats=[StatEntry(stat="Life", value=4500)])
        assert build.get_stat("NonExistent") is None

    def test_stat_zero_value(self):
        build = BuildDocument(player_stats=[StatEntry(stat="TotalDPS", value=0)])
        assert build.get_stat("TotalDPS") == 0

    def test_stat_empty_list(self):
        build = BuildDocument()
        assert build.get_stat("Life") is None


# ── BuildDocument.get_active_spec ────────────────────────────────────────────────────


class TestBuildGetActiveSpec:
    def test_active_spec_first(self):
        specs = [TreeSpec(title="Main"), TreeSpec(title="Second")]
        build = BuildDocument(active_spec=1, specs=specs)
        assert build.get_active_spec().title == "Main"

    def test_active_spec_second(self):
        specs = [TreeSpec(title="Main"), TreeSpec(title="Second")]
        build = BuildDocument(active_spec=2, specs=specs)
        assert build.get_active_spec().title == "Second"

    def test_active_spec_out_of_range_returns_last(self):
        specs = [TreeSpec(title="Only")]
        build = BuildDocument(active_spec=5, specs=specs)
        assert build.get_active_spec().title == "Only"

    def test_active_spec_empty_returns_none(self):
        build = BuildDocument(active_spec=1, specs=[])
        assert build.get_active_spec() is None


# ── BuildDocument.get_active_config ──────────────────────────────────────────────────


class TestBuildGetActiveConfig:
    def test_active_config_found(self):
        cs = BuildConfig(id="2", title="Custom")
        build = BuildDocument(active_config_set="2", config_sets=[BuildConfig(id="1"), cs])
        assert build.get_active_config().title == "Custom"

    def test_active_config_fallback_to_first(self):
        cs = BuildConfig(id="1", title="Default")
        build = BuildDocument(active_config_set="99", config_sets=[cs])
        assert build.get_active_config().title == "Default"

    def test_active_config_empty(self):
        build = BuildDocument(config_sets=[])
        assert build.get_active_config() is None


# ── BuildDocument.get_equipped_items ─────────────────────────────────────────────────


class TestBuildGetEquippedItems:
    def _build_with_items(self):
        items = [
            Item(id=1, text="", name="Helm"),
            Item(id=2, text="", name="Chest"),
            Item(id=3, text="", name="Boots"),
        ]
        sets = [
            ItemSet(
                id="1",
                slots=[ItemSlot(name="Helmet", item_id=1), ItemSlot(name="Body Armour", item_id=2)],
            ),
            ItemSet(id="2", slots=[ItemSlot(name="Boots", item_id=3)]),
        ]
        return BuildDocument(items=items, active_item_set="1", item_sets=sets)

    def test_active_set(self):
        build = self._build_with_items()
        equipped = build.get_equipped_items()
        names = [name for name, _ in equipped]
        assert "Helmet" in names
        assert "Body Armour" in names
        assert len(equipped) == 2

    def test_specific_set(self):
        build = self._build_with_items()
        equipped = build.get_equipped_items(item_set_id="2")
        assert len(equipped) == 1
        assert equipped[0][0] == "Boots"

    def test_no_sets(self):
        build = BuildDocument(items=[Item(id=1, text="")], item_sets=[])
        assert build.get_equipped_items() == []

    def test_missing_item_id(self):
        sets = [ItemSet(id="1", slots=[ItemSlot(name="Helmet", item_id=999)])]
        build = BuildDocument(items=[], item_sets=sets, active_item_set="1")
        assert build.get_equipped_items() == []


# ── Pydantic semantic invariants for BuildDocument (Pattern 5) ─────────────


class TestBuildDocumentInvariants:
    def test_level_rejects_zero(self):
        with pytest.raises((ValueError, TypeError)):
            BuildDocument(level=0)

    def test_level_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            BuildDocument(level=-5)

    def test_level_rejects_above_100(self):
        with pytest.raises((ValueError, TypeError)):
            BuildDocument(level=999)

    def test_active_spec_rejects_zero(self):
        with pytest.raises((ValueError, TypeError)):
            BuildDocument(active_spec=0)

    def test_active_spec_rejects_negative(self):
        with pytest.raises((ValueError, TypeError)):
            BuildDocument(active_spec=-1)

    def test_target_version_rejects_arbitrary_string(self):
        with pytest.raises((ValueError, TypeError)):
            BuildDocument(target_version="not_a_version!!")

    def test_get_active_spec_returns_none_for_missing(self):
        b = BuildDocument(active_spec=1, specs=[])
        assert b.get_active_spec() is None

    def test_get_stat_returns_none_for_missing(self):
        b = BuildDocument()
        assert b.get_stat("anything") is None


class TestStatEntryInvariants:
    def test_basic_construction(self):
        s = StatEntry(stat="Life", value=4500)
        assert s.value == 4500

    def test_stat_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            StatEntry(stat="", value=1)

    def test_value_rejects_nan(self):
        with pytest.raises((ValueError, TypeError)):
            StatEntry(stat="Life", value=float("nan"))

    def test_value_rejects_inf(self):
        with pytest.raises((ValueError, TypeError)):
            StatEntry(stat="Life", value=float("inf"))


class TestItemSetInvariants:
    def test_default_id(self):
        s = ItemSet()
        assert s.id == "1"

    def test_id_rejects_empty(self):
        with pytest.raises((ValueError, TypeError)):
            ItemSet(id="")
