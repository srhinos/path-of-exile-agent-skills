from __future__ import annotations

import re

CLAUDE_SUBFOLDER = "Claude"
POB_XML_EXTENSION = ".xml"
MIN_SEARCH_TERM_LENGTH = 2

VERSION_PATTERN = re.compile(r"^\d+_\d+$")
HIT_RATE_PATTERN = re.compile(r"^\d+(\.\d+)?%$")

PERCENTAGE_MAX = 100

VALID_AFFIXES = frozenset({"prefix", "suffix"})
VALID_AFFIXES_OR_EMPTY = frozenset({"", "prefix", "suffix", "implicit"})
