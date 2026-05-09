from __future__ import annotations

import pytest

from poe.services.build.xml.slots import (
    CANONICAL_SLOTS,
    SLOT_CATEGORIES,
    normalize_slot,
)


class TestCanonicalSlots:
    def test_canonical_slots_count(self):
        assert len(CANONICAL_SLOTS) == 19

    def test_all_categories_in_canonical(self):
        for slots in SLOT_CATEGORIES.values():
            for slot in slots:
                assert slot in CANONICAL_SLOTS

    def test_slot_categories_keys(self):
        assert set(SLOT_CATEGORIES.keys()) == {
            "weapon",
            "armour",
            "jewellery",
            "flask",
            "tincture",
        }


class TestNormalizeSlot:
    def test_normalize_exact_match(self):
        assert normalize_slot("Helmet") == "Helmet"
        assert normalize_slot("Body Armour") == "Body Armour"
        assert normalize_slot("Ring 1") == "Ring 1"

    def test_normalize_case_insensitive(self):
        assert normalize_slot("helmet") == "Helmet"
        assert normalize_slot("HELMET") == "Helmet"
        assert normalize_slot("body armour") == "Body Armour"

    def test_normalize_aliases(self):
        assert normalize_slot("helm") == "Helmet"
        assert normalize_slot("chest") == "Body Armour"
        assert normalize_slot("mainhand") == "Weapon 1"
        assert normalize_slot("offhand") == "Weapon 2"
        assert normalize_slot("boot") == "Boots"
        assert normalize_slot("glove") == "Gloves"

    def test_normalize_substring_fallback(self):
        assert normalize_slot("flask 3") == "Flask 3"
        assert normalize_slot("weapon 2 swap") == "Weapon 2 Swap"

    def test_normalize_unknown(self):
        assert normalize_slot("zzz_invalid_zzz") is None

    def test_normalize_strips_whitespace(self):
        assert normalize_slot("  helmet  ") == "Helmet"


class TestNormalizeSlotFullCoverage:
    @pytest.mark.parametrize("slot", CANONICAL_SLOTS)
    def test_canonical_input_self_normalizes(self, slot):
        assert normalize_slot(slot) == slot

    @pytest.mark.parametrize("slot", CANONICAL_SLOTS)
    def test_lowercase_input_normalizes(self, slot):
        assert normalize_slot(slot.lower()) == slot

    @pytest.mark.parametrize("slot", CANONICAL_SLOTS)
    def test_uppercase_input_normalizes(self, slot):
        assert normalize_slot(slot.upper()) == slot

    @pytest.mark.parametrize("slot", CANONICAL_SLOTS)
    def test_each_canonical_slot_in_categories_or_unique(self, slot):
        all_categorized: set[str] = set()
        for slots in SLOT_CATEGORIES.values():
            all_categorized.update(slots)
        assert slot in all_categorized

    def test_canonical_slots_unique(self):
        assert len(CANONICAL_SLOTS) == len(set(CANONICAL_SLOTS))

    def test_no_duplicate_aliases_collide(self):
        for slot in CANONICAL_SLOTS:
            normalized = normalize_slot(slot.casefold())
            assert normalized == slot

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("helm", "Helmet"),
            ("hat", "Helmet"),
            ("chest", "Body Armour"),
            ("body", "Body Armour"),
            ("armor", "Body Armour"),
            ("armour", "Body Armour"),
            ("ring", "Ring 1"),
            ("ring1", "Ring 1"),
            ("ring2", "Ring 2"),
            ("weapon", "Weapon 1"),
            ("weapon1", "Weapon 1"),
            ("weapon2", "Weapon 2"),
            ("mainhand", "Weapon 1"),
            ("offhand", "Weapon 2"),
            ("main hand", "Weapon 1"),
            ("off hand", "Weapon 2"),
            ("glove", "Gloves"),
            ("boot", "Boots"),
            ("amulet", "Amulet"),
            ("belt", "Belt"),
        ],
    )
    def test_all_aliases_resolve(self, alias, expected):
        assert normalize_slot(alias) == expected

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("HELM", "Helmet"),
            ("Helm", "Helmet"),
            ("CHEST", "Body Armour"),
            ("MainHand", "Weapon 1"),
            ("OFFHAND", "Weapon 2"),
        ],
    )
    def test_alias_case_insensitive(self, alias, expected):
        assert normalize_slot(alias) == expected

    @pytest.mark.xfail(
        strict=True,
        reason="Bug: empty string substring-matches first canonical slot",
    )
    def test_empty_string_returns_none(self):
        assert normalize_slot("") is None

    @pytest.mark.xfail(
        strict=True,
        reason="Bug: whitespace-only normalizes to first canonical slot via substring",
    )
    def test_whitespace_only_returns_none(self):
        assert normalize_slot("   ") is None


class TestSlotCategoriesInvariants:
    def test_categories_partition_canonical(self):
        all_in_cats: list[str] = []
        for slots in SLOT_CATEGORIES.values():
            all_in_cats.extend(slots)
        # Every canonical slot appears at least once
        for slot in CANONICAL_SLOTS:
            assert slot in all_in_cats

    @pytest.mark.parametrize("category", ["weapon", "armour", "jewellery", "flask", "tincture"])
    def test_each_category_non_empty(self, category):
        assert len(SLOT_CATEGORIES[category]) > 0

    def test_flask_category_has_5_slots(self):
        assert len(SLOT_CATEGORIES["flask"]) == 5

    def test_armour_category_has_4_slots(self):
        assert len(SLOT_CATEGORIES["armour"]) == 4
