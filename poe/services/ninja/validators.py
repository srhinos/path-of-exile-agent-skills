from __future__ import annotations

from poe.services.ninja.constants import NINJA_GAMES
from poe.services.ninja.errors import NinjaError


def normalize_game(game: str) -> str:
    """Casefold and validate the `--game` parameter against {poe1, poe2}.

    Without this, any non-"poe2" string silently routed to poe1 endpoints
    via `game == "poe2"` checks scattered across services. `--game POE1`,
    `--game pOe2`, and `--game garbage` all worked the same — wrong league,
    wrong API base, wrong types — without surfacing an error.
    """
    if not isinstance(game, str):
        raise NinjaError(f"--game must be 'poe1' or 'poe2', got {game!r}")
    normalized = game.casefold()
    if normalized not in NINJA_GAMES:
        raise NinjaError(f"--game must be 'poe1' or 'poe2', got {game!r}")
    return normalized
