import pytest

from poe.exceptions import (
    BuildNotFoundError,
    BuildValidationError,
    CodecError,
    EngineNotAvailableError,
    PoeError,
    SimDataError,
    SlotError,
)


class TestExceptionHierarchy:
    def test_base_is_exception(self):
        assert issubclass(PoeError, Exception)

    @pytest.mark.parametrize(
        "exc_class",
        [
            BuildNotFoundError,
            SlotError,
            EngineNotAvailableError,
            SimDataError,
            BuildValidationError,
            CodecError,
        ],
    )
    def test_subclasses(self, exc_class):
        assert issubclass(exc_class, PoeError)

    def test_catchable_as_poe_error(self):
        with pytest.raises(PoeError):
            raise BuildNotFoundError("missing")

    def test_message_preserved(self):
        err = SimDataError("fetch failed")
        assert str(err) == "fetch failed"

    @pytest.mark.parametrize(
        "exc_class",
        [
            BuildNotFoundError,
            SlotError,
            EngineNotAvailableError,
            SimDataError,
            BuildValidationError,
            CodecError,
        ],
    )
    def test_raise_and_catch_specific(self, exc_class):
        with pytest.raises(exc_class, match="test"):
            raise exc_class("test")


_ALL_SUBCLASSES = [
    BuildNotFoundError,
    SlotError,
    EngineNotAvailableError,
    SimDataError,
    BuildValidationError,
    CodecError,
]


class TestAllPoeErrorSubclassesInstantiable:
    @pytest.mark.parametrize("exc_class", _ALL_SUBCLASSES)
    def test_default_construction(self, exc_class):
        err = exc_class()
        assert isinstance(err, PoeError)
        assert isinstance(err, Exception)

    @pytest.mark.parametrize("exc_class", _ALL_SUBCLASSES)
    def test_with_message(self, exc_class):
        err = exc_class("specific failure")
        assert str(err) == "specific failure"

    @pytest.mark.parametrize("exc_class", _ALL_SUBCLASSES)
    def test_with_unicode_message(self, exc_class):
        err = exc_class("unicode: küsst, Mórrigan, 中文")
        assert "küsst" in str(err)
        assert "Mórrigan" in str(err)
        assert "中文" in str(err)

    @pytest.mark.parametrize("exc_class", _ALL_SUBCLASSES)
    def test_chaining_preserves_cause(self, exc_class):
        original = ValueError("root cause")
        try:
            try:
                raise original
            except ValueError as e:
                raise exc_class("wrapped") from e
        except exc_class as wrapped:
            assert wrapped.__cause__ is original

    @pytest.mark.parametrize("exc_class", _ALL_SUBCLASSES)
    def test_subclass_does_not_inherit_from_other_subclass(self, exc_class):
        siblings = [c for c in _ALL_SUBCLASSES if c is not exc_class]
        for sibling in siblings:
            assert not issubclass(exc_class, sibling)
