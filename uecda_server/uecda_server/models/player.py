"""Player model."""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from .card import CardSet


class PlayerRank(IntEnum):
    """Player rank (social status)."""

    DAIFUGO = 0  # 大富豪 (1st place)
    FUGO = 1  # 富豪 (2nd place)
    HEIMIN = 2  # 平民 (3rd place)
    HINMIN = 3  # 貧民 (4th place)
    DAIHINMIN = 4  # 大貧民 (5th place)


RANK_NAMES_JP = {
    PlayerRank.DAIFUGO: "大富豪",
    PlayerRank.FUGO: "富豪",
    PlayerRank.HEIMIN: "平民",
    PlayerRank.HINMIN: "貧民",
    PlayerRank.DAIHINMIN: "大貧民",
}


class Player(BaseModel):
    """Player state."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    player_id: int  # 0-4
    name: str = "Player"
    socket: Any = None  # socket.socket, but Any for pydantic compatibility
    protocol_version: int = 20070

    # Game state (mutable, not part of identity)
    rank: PlayerRank = PlayerRank.HEIMIN
    seat: int = 0  # Seat position (0-4)

    # Turn state
    has_passed: bool = False  # Passed this round
    has_finished: bool = False  # Finished the game (no cards left)
    finish_order: int = -1  # Order of finishing (-1 if not finished)

    def hand_count(self, hand: CardSet) -> int:
        """Get number of cards in hand."""
        return hand.count()

    def reset_turn_state(self) -> None:
        """Reset turn-related state (called when field is cleared)."""
        self.has_passed = False

    def reset_game_state(self) -> None:
        """Reset game-related state (called at start of new game)."""
        self.has_passed = False
        self.has_finished = False
        self.finish_order = -1

    def __str__(self) -> str:
        status = ""
        if self.has_finished:
            status = f" (#{self.finish_order + 1})"
        elif self.has_passed:
            status = " (pass)"
        return f"Player{self.player_id}[{self.name}]{status}"

    def __repr__(self) -> str:
        return (
            f"Player(id={self.player_id}, name={self.name!r}, "
            f"rank={self.rank.name}, finished={self.has_finished})"
        )
