from poe.constants import CLAUDE_SUBFOLDER, POB_XML_EXTENSION
from poe.services.repoe.constants import DEFAULT_ILVL, DEFAULT_ITERATIONS


def test_default_ilvl():
    assert DEFAULT_ILVL == 84


def test_default_iterations():
    assert DEFAULT_ITERATIONS == 10000


def test_claude_subfolder():
    assert CLAUDE_SUBFOLDER == "Claude"


def test_pob_xml_extension():
    assert POB_XML_EXTENSION == ".xml"


# ── Invariants for constants (Pattern 1) ────────────────────────────────────


def test_claude_subfolder_is_str():
    assert isinstance(CLAUDE_SUBFOLDER, str)
    assert CLAUDE_SUBFOLDER


def test_pob_xml_extension_starts_with_dot():
    assert POB_XML_EXTENSION.startswith(".")
    assert len(POB_XML_EXTENSION) > 1


def test_default_ilvl_in_valid_range():
    assert isinstance(DEFAULT_ILVL, int)
    assert 1 <= DEFAULT_ILVL <= 100


def test_default_iterations_positive():
    assert isinstance(DEFAULT_ITERATIONS, int)
    assert DEFAULT_ITERATIONS > 0
