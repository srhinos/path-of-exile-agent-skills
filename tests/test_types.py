import pytest

from poe.types import (
    CraftMethod,
    Influence,
    MatchMode,
    QualityId,
    Rarity,
    StatCategory,
)


class TestRarity:
    def test_values(self):
        assert list(Rarity) == [
            Rarity.NORMAL,
            Rarity.MAGIC,
            Rarity.RARE,
            Rarity.UNIQUE,
            Rarity.RELIC,
        ]

    def test_string_comparison(self):
        assert Rarity.NORMAL == "NORMAL"
        assert Rarity.RARE == "RARE"

    def test_str_conversion(self):
        assert str(Rarity.MAGIC) == "MAGIC"


class TestInfluence:
    def test_all_influences(self):
        assert len(list(Influence)) == 8

    def test_values_match_existing_strings(self):
        assert Influence.SHAPER == "Shaper"
        assert Influence.ELDER == "Elder"
        assert Influence.CRUSADER == "Crusader"
        assert Influence.HUNTER == "Hunter"
        assert Influence.REDEEMER == "Redeemer"
        assert Influence.WARLORD == "Warlord"
        assert Influence.SEARING_EXARCH == "Searing Exarch"
        assert Influence.EATER_OF_WORLDS == "Eater of Worlds"


class TestCraftMethod:
    def test_values(self):
        assert CraftMethod.CHAOS == "chaos"
        assert CraftMethod.ALT == "alt"
        assert CraftMethod.FOSSIL == "fossil"
        assert CraftMethod.ESSENCE == "essence"

    def test_membership(self):
        assert "chaos" in list(CraftMethod)


class TestMatchMode:
    def test_values(self):
        assert MatchMode.ALL == "all"
        assert MatchMode.ANY == "any"


class TestStatCategory:
    def test_values(self):
        assert StatCategory.OFF == "off"
        assert StatCategory.DEF == "def"
        assert StatCategory.ALL == "all"


class TestQualityId:
    def test_values(self):
        assert QualityId.DEFAULT == "Default"
        assert QualityId.ANOMALOUS == "Anomalous"
        assert QualityId.DIVERGENT == "Divergent"
        assert QualityId.PHANTASMAL == "Phantasmal"

    def test_default_matches_parser(self):
        assert QualityId.DEFAULT == "Default"


# ── Full enum coverage (Pattern 3) ───────────────────────────────────────────


class TestRarityFullCoverage:
    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (Rarity.NORMAL, "NORMAL"),
            (Rarity.MAGIC, "MAGIC"),
            (Rarity.RARE, "RARE"),
            (Rarity.UNIQUE, "UNIQUE"),
            (Rarity.RELIC, "RELIC"),
        ],
    )
    def test_each_value(self, member, expected):
        assert member.value == expected
        assert str(member) == expected

    @pytest.mark.parametrize(
        ("variant", "canonical"),
        [
            ("normal", "NORMAL"),
            ("Magic", "MAGIC"),
            ("rArE", "RARE"),
            ("UNIQUE", "UNIQUE"),
        ],
    )
    def test_casefold_to_canonical(self, variant, canonical):
        canon = next((m for m in Rarity if m.value.casefold() == variant.casefold()), None)
        assert canon is not None
        assert canon.value == canonical

    def test_count(self):
        assert len(list(Rarity)) == 5


class TestCraftMethodFullCoverage:
    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (CraftMethod.CHAOS, "chaos"),
            (CraftMethod.ALT, "alt"),
            (CraftMethod.FOSSIL, "fossil"),
            (CraftMethod.ESSENCE, "essence"),
            (CraftMethod.ALCHEMY, "alchemy"),
            (CraftMethod.TRANSMUTATION, "transmutation"),
            (CraftMethod.AUGMENTATION, "augmentation"),
            (CraftMethod.DIVINE, "divine"),
            (CraftMethod.BLESSED, "blessed"),
            (CraftMethod.HARVEST, "harvest"),
            (CraftMethod.CONQUEROR_EXALT, "conqueror_exalt"),
            (CraftMethod.AWAKENER, "awakener"),
            (CraftMethod.VEILED_CHAOS, "veiled_chaos"),
            (CraftMethod.VAAL, "vaal"),
            (CraftMethod.FRACTURE, "fracture"),
            (CraftMethod.TAINTED_DIVINE, "tainted_divine"),
            (CraftMethod.REGAL, "regal"),
            (CraftMethod.EXALT, "exalt"),
            (CraftMethod.ANNUL, "annul"),
            (CraftMethod.SCOUR, "scour"),
        ],
    )
    def test_each_method(self, member, expected):
        assert member.value == expected

    def test_method_count(self):
        assert len(list(CraftMethod)) == 20

    @pytest.mark.parametrize("method", list(CraftMethod))
    def test_each_method_value_is_lowercase(self, method):
        assert method.value == method.value.lower()


class TestInfluenceFullCoverage:
    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (Influence.SHAPER, "Shaper"),
            (Influence.ELDER, "Elder"),
            (Influence.CRUSADER, "Crusader"),
            (Influence.HUNTER, "Hunter"),
            (Influence.REDEEMER, "Redeemer"),
            (Influence.WARLORD, "Warlord"),
            (Influence.SEARING_EXARCH, "Searing Exarch"),
            (Influence.EATER_OF_WORLDS, "Eater of Worlds"),
        ],
    )
    def test_each_value(self, member, expected):
        assert member.value == expected

    @pytest.mark.parametrize(
        ("variant", "canonical"),
        [
            ("shaper", "Shaper"),
            ("ELDER", "Elder"),
            ("seArInG ExArCh", "Searing Exarch"),
        ],
    )
    def test_casefold_to_canonical(self, variant, canonical):
        canon = next((m for m in Influence if m.value.casefold() == variant.casefold()), None)
        assert canon is not None
        assert canon.value == canonical


class TestMatchModeFullCoverage:
    @pytest.mark.parametrize("member", list(MatchMode))
    def test_each_member_is_strenum(self, member):
        assert isinstance(member.value, str)

    def test_count(self):
        assert len(list(MatchMode)) == 2

    @pytest.mark.parametrize(
        ("variant", "canonical"),
        [("ALL", "all"), ("Any", "any"), ("any", "any")],
    )
    def test_casefold_lookup(self, variant, canonical):
        canon = next((m for m in MatchMode if m.value.casefold() == variant.casefold()), None)
        assert canon is not None
        assert canon.value == canonical


class TestStatCategoryFullCoverage:
    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (StatCategory.OFF, "off"),
            (StatCategory.DEF, "def"),
            (StatCategory.ALL, "all"),
        ],
    )
    def test_each_value(self, member, expected):
        assert member.value == expected

    def test_count(self):
        assert len(list(StatCategory)) == 3


class TestQualityIdFullCoverage:
    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (QualityId.DEFAULT, "Default"),
            (QualityId.ANOMALOUS, "Anomalous"),
            (QualityId.DIVERGENT, "Divergent"),
            (QualityId.PHANTASMAL, "Phantasmal"),
        ],
    )
    def test_each_value(self, member, expected):
        assert member.value == expected

    def test_count(self):
        assert len(list(QualityId)) == 4

    @pytest.mark.parametrize("member", list(QualityId))
    def test_capitalised_form(self, member):
        assert member.value[0].isupper()
